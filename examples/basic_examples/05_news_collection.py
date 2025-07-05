"""
📰 뉴스 수집 및 감정 분석 시스템

이 모듈은 주식 관련 뉴스를 수집하고 감정 분석을 수행합니다.

주요 기능:
1. 네이버 금융 뉴스 크롤링
2. 종목별 뉴스 수집
3. 뉴스 텍스트 전처리
4. 감정 분석 (긍정/부정/중립)
5. 종목별 감정 지수 계산
6. 시계열 감정 추이 분석

데이터 소스:
- 네이버 금융 (finance.naver.com)
- 다음 금융 (finance.daum.net)
- 한국경제 (hankyung.com)

🎯 목표: 뉴스 기반 투자 신호 생성
"""

import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta
import re
import json
from urllib.parse import urljoin, quote
from tqdm import tqdm
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR
    import warnings
    warnings.filterwarnings('ignore')
except ImportError as e:
    print(f"❌ 패키지 설치 필요: {e}")
    exit(1)


class NewsCollector:
    """
    뉴스 수집기
    
    주식 관련 뉴스를 다양한 소스에서 수집하고 저장합니다.
    """
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.db_path = self.data_dir / 'news_data.db'
        
        # 수집 통계
        self.stats = {
            'total_collected': 0,
            'success_count': 0,
            'fail_count': 0,
            'duplicate_count': 0
        }
        
        # HTTP 세션 설정
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        self.init_database()
        print("✅ 뉴스 수집기 초기화 완료")
    
    def init_database(self):
        """🗄️ 뉴스 데이터베이스 초기화"""
        print("🗄️ 뉴스 데이터베이스 초기화 중...")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 뉴스 기사 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT,
                    stock_name TEXT,
                    title TEXT NOT NULL,
                    content TEXT,
                    summary TEXT,
                    url TEXT UNIQUE,
                    source TEXT,
                    author TEXT,
                    published_date TEXT,
                    collected_date TEXT,
                    sentiment_score REAL,
                    sentiment_label TEXT,
                    keywords TEXT,
                    view_count INTEGER,
                    comment_count INTEGER
                )
            ''')
            
            # 감정 분석 결과 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sentiment_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    positive_count INTEGER DEFAULT 0,
                    negative_count INTEGER DEFAULT 0,
                    neutral_count INTEGER DEFAULT 0,
                    total_count INTEGER DEFAULT 0,
                    sentiment_score REAL DEFAULT 0,
                    sentiment_index REAL DEFAULT 50,
                    created_date TEXT,
                    UNIQUE(stock_code, date)
                )
            ''')
            
            # 키워드 추출 결과 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news_keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT,
                    keyword TEXT,
                    frequency INTEGER,
                    date TEXT,
                    sentiment_impact REAL,
                    created_date TEXT
                )
            ''')
            
            # 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_stock_code ON news_articles(stock_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_published_date ON news_articles(published_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment_stock_date ON sentiment_analysis(stock_code, date)')
            
            conn.commit()
        
        print("✅ 뉴스 데이터베이스 초기화 완료")
    
    def get_stock_list_from_db(self):
        """📊 주식 DB에서 종목 리스트 가져오기"""
        stock_db_path = self.data_dir / 'stock_data.db'
        
        if not stock_db_path.exists():
            print("❌ 주식 데이터베이스가 없습니다!")
            return []
        
        try:
            with sqlite3.connect(stock_db_path) as conn:
                query = """
                    SELECT DISTINCT symbol as stock_code, name as stock_name
                    FROM stock_info
                    WHERE symbol IS NOT NULL 
                    AND LENGTH(symbol) = 6
                    ORDER BY symbol
                """
                result = pd.read_sql_query(query, conn)
                return result.to_dict('records')
                
        except Exception as e:
            print(f"❌ 주식 DB 조회 실패: {e}")
            return []
    
    def collect_naver_finance_news(self, stock_code, stock_name, days=7, max_pages=5):
        """
        📰 네이버 금융 뉴스 수집
        
        Args:
            stock_code (str): 종목코드
            stock_name (str): 종목명
            days (int): 수집할 일수
            max_pages (int): 최대 페이지 수
            
        Returns:
            list: 수집된 뉴스 리스트
        """
        news_list = []
        
        try:
            # 네이버 금융 종목 뉴스 URL
            base_url = f"https://finance.naver.com/item/news_news.naver"
            
            for page in range(1, max_pages + 1):
                params = {
                    'code': stock_code,
                    'page': page
                }
                
                try:
                    response = self.session.get(base_url, params=params, timeout=10)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # 뉴스 목록 파싱
                    news_items = soup.select('.tb_cont tr')
                    
                    for item in news_items:
                        try:
                            # 제목과 링크 추출
                            title_elem = item.select_one('.title a')
                            if not title_elem:
                                continue
                            
                            title = title_elem.get_text(strip=True)
                            news_url = urljoin("https://finance.naver.com", title_elem.get('href'))
                            
                            # 날짜 추출
                            date_elem = item.select_one('.date')
                            if date_elem:
                                date_str = date_elem.get_text(strip=True)
                                published_date = self.parse_date(date_str)
                            else:
                                published_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            
                            # 정보 제공자 추출
                            info_elem = item.select_one('.info')
                            source = info_elem.get_text(strip=True) if info_elem else '네이버금융'
                            
                            # 뉴스 상세 내용 수집
                            content, summary = self.get_news_content(news_url)
                            
                            news_data = {
                                'stock_code': stock_code,
                                'stock_name': stock_name,
                                'title': title,
                                'content': content,
                                'summary': summary,
                                'url': news_url,
                                'source': f'네이버금융-{source}',
                                'published_date': published_date,
                                'collected_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            
                            news_list.append(news_data)
                            
                            # 요청 간격 조절
                            time.sleep(random.uniform(0.5, 1.5))
                            
                        except Exception as e:
                            print(f"  ⚠️ 뉴스 항목 파싱 실패: {e}")
                            continue
                    
                    # 페이지 간 간격
                    time.sleep(random.uniform(1, 2))
                    
                except Exception as e:
                    print(f"  ❌ 페이지 {page} 수집 실패: {e}")
                    continue
            
        except Exception as e:
            print(f"❌ {stock_code}({stock_name}) 뉴스 수집 실패: {e}")
        
        return news_list
    
    def get_news_content(self, url):
        """
        📄 뉴스 상세 내용 추출
        
        Args:
            url (str): 뉴스 URL
            
        Returns:
            tuple: (content, summary)
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 다양한 뉴스 사이트의 본문 선택자
            content_selectors = [
                '.news_body',
                '.article_body',
                '.news_content',
                '#news_body',
                '.news_text',
                '.article_content',
                '#articleBodyContents'
            ]
            
            content = ""
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 스크립트, 스타일, 광고 등 제거
                    for unwanted in content_elem.find_all(['script', 'style', 'iframe', 'ins']):
                        unwanted.decompose()
                    
                    content = content_elem.get_text(separator=' ', strip=True)
                    break
            
            # 요약 생성 (첫 2문장)
            sentences = re.split(r'[.!?]\s+', content)
            summary = '. '.join(sentences[:2])[:200] if sentences else content[:200]
            
            return content, summary
            
        except Exception as e:
            return "", ""
    
    def parse_date(self, date_str):
        """📅 날짜 문자열 파싱"""
        try:
            # "07.05" 형태
            if re.match(r'\d{2}\.\d{2}', date_str):
                current_year = datetime.now().year
                month, day = date_str.split('.')
                return f"{current_year}-{month}-{day} 00:00:00"
            
            # "07.05 15:30" 형태
            elif re.match(r'\d{2}\.\d{2} \d{2}:\d{2}', date_str):
                current_year = datetime.now().year
                date_part, time_part = date_str.split(' ')
                month, day = date_part.split('.')
                return f"{current_year}-{month}-{day} {time_part}:00"
            
            # 기타 형태는 현재 시간 반환
            else:
                return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
        except:
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def save_news_to_db(self, news_list):
        """📚 뉴스 데이터를 DB에 저장"""
        if not news_list:
            return 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                saved_count = 0
                for news in news_list:
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO news_articles 
                            (stock_code, stock_name, title, content, summary, url, source, 
                             published_date, collected_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            news.get('stock_code', ''),
                            news.get('stock_name', ''),
                            news.get('title', ''),
                            news.get('content', ''),
                            news.get('summary', ''),
                            news.get('url', ''),
                            news.get('source', ''),
                            news.get('published_date', ''),
                            news.get('collected_date', '')
                        ))
                        
                        if cursor.rowcount > 0:
                            saved_count += 1
                        else:
                            self.stats['duplicate_count'] += 1
                            
                    except Exception as e:
                        print(f"  ⚠️ 뉴스 저장 실패: {e}")
                        continue
                
                conn.commit()
                return saved_count
                
        except Exception as e:
            print(f"❌ 뉴스 DB 저장 실패: {e}")
            return 0
    
    def collect_all_stock_news(self, days=7, max_stocks=None, max_workers=3):
        """
        🚀 모든 종목의 뉴스 수집
        
        Args:
            days (int): 수집할 일수
            max_stocks (int): 최대 종목 수 (None이면 전체)
            max_workers (int): 동시 처리 스레드 수
        """
        print("🚀 전체 종목 뉴스 수집 시작!")
        print("=" * 60)
        
        # 종목 리스트 가져오기
        stock_list = self.get_stock_list_from_db()
        if not stock_list:
            print("❌ 수집할 종목이 없습니다.")
            return
        
        if max_stocks:
            stock_list = stock_list[:max_stocks]
        
        print(f"📊 총 {len(stock_list)}개 종목 뉴스 수집 예정")
        print(f"📅 수집 기간: 최근 {days}일")
        print(f"🧵 동시 처리: {max_workers}개 스레드")
        
        estimated_time = len(stock_list) * 30 / max_workers / 60  # 분 단위
        print(f"⏱️  예상 소요시간: 약 {estimated_time:.1f}분")
        
        confirm = input(f"\n뉴스 수집을 시작하시겠습니까? (y/N): ").strip().lower()
        if confirm != 'y':
            print("👋 수집을 취소했습니다.")
            return
        
        # 멀티스레딩으로 수집
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 작업 제출
            future_to_stock = {}
            for stock in stock_list:
                future = executor.submit(
                    self.collect_stock_news_worker, 
                    stock['stock_code'], 
                    stock['stock_name'], 
                    days
                )
                future_to_stock[future] = stock
            
            # 진행률 표시
            progress_bar = tqdm(
                as_completed(future_to_stock), 
                total=len(stock_list),
                desc="📰 뉴스 수집",
                unit="종목"
            )
            
            for future in progress_bar:
                stock = future_to_stock[future]
                stock_code = stock['stock_code']
                stock_name = stock['stock_name']
                
                try:
                    news_count = future.result()
                    self.stats['success_count'] += 1
                    self.stats['total_collected'] += news_count
                    
                    progress_bar.set_postfix({
                        'Current': f"{stock_code}({stock_name[:8]})",
                        'News': self.stats['total_collected'],
                        'Success': self.stats['success_count']
                    })
                    
                except Exception as e:
                    self.stats['fail_count'] += 1
                    print(f"\n❌ {stock_code}({stock_name}) 뉴스 수집 실패: {e}")
        
        # 수집 결과 출력
        self.print_collection_summary()
    
    def collect_stock_news_worker(self, stock_code, stock_name, days):
        """📰 개별 종목 뉴스 수집 (워커 함수)"""
        try:
            # 네이버 금융 뉴스 수집
            news_list = self.collect_naver_finance_news(stock_code, stock_name, days)
            
            # DB 저장
            saved_count = self.save_news_to_db(news_list)
            
            return saved_count
            
        except Exception as e:
            raise e
    
    def print_collection_summary(self):
        """📋 수집 결과 요약 출력"""
        print("\n" + "=" * 60)
        print("📋 뉴스 수집 완료!")
        print("=" * 60)
        print(f"📊 처리된 종목: {self.stats['success_count'] + self.stats['fail_count']:,}개")
        print(f"✅ 성공: {self.stats['success_count']:,}개")
        print(f"❌ 실패: {self.stats['fail_count']:,}개")
        print(f"📰 수집된 뉴스: {self.stats['total_collected']:,}건")
        print(f"🔄 중복 제외: {self.stats['duplicate_count']:,}건")
        print(f"🗄️ 데이터 저장: {self.db_path}")
        print("=" * 60)
    
    def query_db(self, query, params=None):
        """DB 쿼리 실행"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if params:
                    return pd.read_sql_query(query, conn, params=params)
                else:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"❌ 쿼리 실행 실패: {e}")
            return pd.DataFrame()
    
    def get_news_summary(self):
        """📊 뉴스 수집 현황 요약"""
        print("📊 뉴스 수집 현황")
        print("=" * 40)
        
        # 전체 뉴스 수
        total_news = self.query_db("SELECT COUNT(*) as count FROM news_articles")
        print(f"📰 전체 뉴스: {total_news.iloc[0]['count']:,}건")
        
        # 종목별 뉴스 수 (상위 10개)
        stock_news = self.query_db("""
            SELECT stock_code, stock_name, COUNT(*) as news_count
            FROM news_articles
            GROUP BY stock_code, stock_name
            ORDER BY news_count DESC
            LIMIT 10
        """)
        
        if not stock_news.empty:
            print(f"\n📈 종목별 뉴스 (상위 10개):")
            for _, row in stock_news.iterrows():
                print(f"   {row['stock_code']} ({row['stock_name']}): {row['news_count']}건")
        
        # 일별 뉴스 수 (최근 7일)
        daily_news = self.query_db("""
            SELECT DATE(published_date) as date, COUNT(*) as count
            FROM news_articles
            WHERE published_date >= DATE('now', '-7 days')
            GROUP BY DATE(published_date)
            ORDER BY date DESC
        """)
        
        if not daily_news.empty:
            print(f"\n📅 일별 뉴스 (최근 7일):")
            for _, row in daily_news.iterrows():
                print(f"   {row['date']}: {row['count']}건")
        
        print("=" * 40)


class NewsSentimentAnalyzer:
    """
    뉴스 감정 분석기
    
    수집된 뉴스에 대해 감정 분석을 수행하고 종목별 감정 지수를 계산합니다.
    """
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.db_path = self.data_dir / 'news_data.db'
        
        # 금융 감정 사전 (한국어)
        self.positive_words = {
            '상승', '급등', '호재', '성장', '증가', '확대', '개선', '회복',
            '돌파', '상향', '긍정', '호황', '활성', '부양', '투자', '확장',
            '수익', '이익', '실적', '개발', '혁신', '전망', '기대', '추천',
            '매수', '강세', '반등', '선방', '양호', '우수', '탄탄', '견조'
        }
        
        self.negative_words = {
            '하락', '급락', '악재', '감소', '축소', '악화', '침체', '위기',
            '손실', '적자', '부진', '둔화', '경고', '우려', '불안', '리스크',
            '타격', '충격', '압박', '제재', '규제', '파산', '구조조정',
            '매도', '약세', '조정', '부담', '취약', '악순환', '침체', '저조'
        }
        
        print("✅ 뉴스 감정 분석기 초기화 완료")
    
    def calculate_sentiment_score(self, text):
        """
        📊 텍스트 감정 점수 계산
        
        Args:
            text (str): 분석할 텍스트
            
        Returns:
            tuple: (sentiment_score, sentiment_label)
                   sentiment_score: -1.0 ~ 1.0 (부정 ~ 긍정)
                   sentiment_label: 'positive', 'negative', 'neutral'
        """
        if not text:
            return 0.0, 'neutral'
        
        text = text.lower()
        
        # 긍정/부정 단어 개수 계산
        positive_count = sum(1 for word in self.positive_words if word in text)
        negative_count = sum(1 for word in self.negative_words if word in text)
        
        # 총 감정 단어 수
        total_sentiment_words = positive_count + negative_count
        
        if total_sentiment_words == 0:
            return 0.0, 'neutral'
        
        # 감정 점수 계산 (-1.0 ~ 1.0)
        sentiment_score = (positive_count - negative_count) / total_sentiment_words
        
        # 라벨 결정
        if sentiment_score > 0.2:
            sentiment_label = 'positive'
        elif sentiment_score < -0.2:
            sentiment_label = 'negative'
        else:
            sentiment_label = 'neutral'
        
        return sentiment_score, sentiment_label
    
    def analyze_all_news_sentiment(self):
        """🔍 모든 뉴스에 대해 감정 분석 수행"""
        print("🔍 뉴스 감정 분석 시작!")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 감정 분석이 안된 뉴스들 조회
                query = """
                    SELECT id, title, content, summary, stock_code
                    FROM news_articles
                    WHERE sentiment_score IS NULL
                    ORDER BY id
                """
                news_to_analyze = pd.read_sql_query(query, conn)
                
                if news_to_analyze.empty:
                    print("✅ 모든 뉴스가 이미 감정 분석 완료되었습니다.")
                    return
                
                print(f"📊 감정 분석 대상: {len(news_to_analyze)}건")
                
                cursor = conn.cursor()
                analyzed_count = 0
                
                # 진행률 표시
                progress_bar = tqdm(news_to_analyze.iterrows(), 
                                  total=len(news_to_analyze),
                                  desc="🔍 감정 분석",
                                  unit="뉴스")
                
                for _, row in progress_bar:
                    try:
                        # 제목과 요약을 합쳐서 분석
                        text_to_analyze = f"{row['title']} {row['summary']}"
                        
                        # 감정 분석 수행
                        sentiment_score, sentiment_label = self.calculate_sentiment_score(text_to_analyze)
                        
                        # DB 업데이트
                        cursor.execute('''
                            UPDATE news_articles 
                            SET sentiment_score = ?, sentiment_label = ?
                            WHERE id = ?
                        ''', (sentiment_score, sentiment_label, row['id']))
                        
                        analyzed_count += 1
                        
                        progress_bar.set_postfix({
                            'Analyzed': analyzed_count,
                            'Current': sentiment_label
                        })
                        
                    except Exception as e:
                        print(f"\n⚠️ 뉴스 ID {row['id']} 감정 분석 실패: {e}")
                        continue
                
                conn.commit()
                
                print(f"\n✅ 감정 분석 완료: {analyzed_count}건")
                
                # 감정 분석 결과 요약
                self.summarize_sentiment_results()
                
        except Exception as e:
            print(f"❌ 감정 분석 실패: {e}")
    
    def calculate_daily_sentiment_index(self):
        """📈 일별 종목별 감정 지수 계산"""
        print("📈 일별 감정 지수 계산 중...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 종목별, 일별 감정 분석 결과 집계
                query = """
                    SELECT 
                        stock_code,
                        DATE(published_date) as date,
                        SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) as positive_count,
                        SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) as negative_count,
                        SUM(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
                        COUNT(*) as total_count,
                        AVG(sentiment_score) as avg_sentiment_score
                    FROM news_articles
                    WHERE sentiment_score IS NOT NULL
                    AND published_date >= DATE('now', '-30 days')
                    GROUP BY stock_code, DATE(published_date)
                    ORDER BY stock_code, date
                """
                
                results = pd.read_sql_query(query, conn)
                
                if results.empty:
                    print("❌ 감정 분석 데이터가 없습니다.")
                    return
                
                # 감정 지수 계산 및 저장
                for _, row in results.iterrows():
                    # 감정 지수 계산 (0~100, 50이 중립)
                    if row['total_count'] > 0:
                        positive_ratio = row['positive_count'] / row['total_count']
                        negative_ratio = row['negative_count'] / row['total_count']
                        sentiment_index = 50 + (positive_ratio - negative_ratio) * 50
                    else:
                        sentiment_index = 50
                    
                    # DB에 저장
                    cursor.execute('''
                        INSERT OR REPLACE INTO sentiment_analysis
                        (stock_code, date, positive_count, negative_count, neutral_count,
                         total_count, sentiment_score, sentiment_index, created_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['stock_code'],
                        row['date'],
                        row['positive_count'],
                        row['negative_count'],
                        row['neutral_count'],
                        row['total_count'],
                        row['avg_sentiment_score'],
                        sentiment_index,
                        datetime.now().isoformat()
                    ))
                
                conn.commit()
                print(f"✅ {len(results)}건의 일별 감정 지수 계산 완료")
                
        except Exception as e:
            print(f"❌ 감정 지수 계산 실패: {e}")
    
    def summarize_sentiment_results(self):
        """📊 감정 분석 결과 요약"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 전체 감정 분포
                sentiment_dist = pd.read_sql_query("""
                    SELECT 
                        sentiment_label,
                        COUNT(*) as count,
                        COUNT(*) * 100.0 / (SELECT COUNT(*) FROM news_articles WHERE sentiment_label IS NOT NULL) as percentage
                    FROM news_articles
                    WHERE sentiment_label IS NOT NULL
                    GROUP BY sentiment_label
                """, conn)
                
                print("\n📊 전체 감정 분포:")
                for _, row in sentiment_dist.iterrows():
                    print(f"   {row['sentiment_label']}: {row['count']:,}건 ({row['percentage']:.1f}%)")
                
                # 종목별 감정 점수 (상위/하위 5개)
                stock_sentiment = pd.read_sql_query("""
                    SELECT 
                        stock_code,
                        stock_name,
                        AVG(sentiment_score) as avg_sentiment,
                        COUNT(*) as news_count
                    FROM news_articles
                    WHERE sentiment_score IS NOT NULL
                    GROUP BY stock_code, stock_name
                    HAVING COUNT(*) >= 5
                    ORDER BY avg_sentiment DESC
                """, conn)
                
                if not stock_sentiment.empty:
                    print(f"\n📈 종목별 평균 감정 점수:")
                    print("   🔝 상위 5개:")
                    for _, row in stock_sentiment.head().iterrows():
                        print(f"      {row['stock_code']} ({row['stock_name']}): {row['avg_sentiment']:.3f} ({row['news_count']}건)")
                    
                    print("   📉 하위 5개:")
                    for _, row in stock_sentiment.tail().iterrows():
                        print(f"      {row['stock_code']} ({row['stock_name']}): {row['avg_sentiment']:.3f} ({row['news_count']}건)")
                
        except Exception as e:
            print(f"⚠️ 감정 분석 요약 실패: {e}")
    
    def get_stock_sentiment_trend(self, stock_code, days=30):
        """📈 특정 종목의 감정 추이 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT date, sentiment_index, total_count
                    FROM sentiment_analysis
                    WHERE stock_code = ?
                    AND date >= DATE('now', '-{} days')
                    ORDER BY date
                """.format(days)
                
                return pd.read_sql_query(query, conn, params=(stock_code,))
                
        except Exception as e:
            print(f"❌ 감정 추이 조회 실패: {e}")
            return pd.DataFrame()


def main():
    """메인 실행 함수"""
    
    print("🚀 Finance Data Vibe - 뉴스 수집 및 감정 분석 시스템")
    print("=" * 60)
    
    while True:
        print("\n📰 원하는 기능을 선택하세요:")
        print("1. 전체 종목 뉴스 수집")
        print("2. 특정 종목 뉴스 수집")
        print("3. 뉴스 감정 분석 수행")
        print("4. 일별 감정 지수 계산")
        print("5. 뉴스 수집 현황 확인")
        print("6. 감정 분석 결과 확인")
        print("0. 종료")
        
        choice = input("\n선택하세요 (0-6): ").strip()
        
        if choice == '0':
            print("👋 프로그램을 종료합니다.")
            break
        
        elif choice == '1':
            # 전체 종목 뉴스 수집
            collector = NewsCollector()
            
            days = int(input("수집할 일수를 입력하세요 (기본값: 7): ").strip() or "7")
            max_stocks = input("최대 종목 수 (전체: Enter): ").strip()
            max_stocks = int(max_stocks) if max_stocks else None
            
            collector.collect_all_stock_news(days=days, max_stocks=max_stocks)
        
        elif choice == '2':
            # 특정 종목 뉴스 수집
            collector = NewsCollector()
            
            stock_code = input("종목코드를 입력하세요 (예: 005930): ").strip()
            stock_name = input("종목명을 입력하세요 (예: 삼성전자): ").strip()
            days = int(input("수집할 일수를 입력하세요 (기본값: 7): ").strip() or "7")
            
            if stock_code and stock_name:
                news_list = collector.collect_naver_finance_news(stock_code, stock_name, days)
                saved_count = collector.save_news_to_db(news_list)
                print(f"✅ {saved_count}건의 뉴스를 수집했습니다.")
            else:
                print("❌ 종목코드와 종목명을 모두 입력해주세요.")
        
        elif choice == '3':
            # 뉴스 감정 분석
            analyzer = NewsSentimentAnalyzer()
            analyzer.analyze_all_news_sentiment()
        
        elif choice == '4':
            # 일별 감정 지수 계산
            analyzer = NewsSentimentAnalyzer()
            analyzer.calculate_daily_sentiment_index()
        
        elif choice == '5':
            # 뉴스 수집 현황
            collector = NewsCollector()
            collector.get_news_summary()
        
        elif choice == '6':
            # 감정 분석 결과
            analyzer = NewsSentimentAnalyzer()
            analyzer.summarize_sentiment_results()
        
        else:
            print("❌ 올바른 번호를 선택해주세요.")


if __name__ == "__main__":
    main()