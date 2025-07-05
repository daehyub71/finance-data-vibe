"""
examples/basic_examples/06_full_news_collector.py

전체 종목 뉴스 수집기 - 기존 프로젝트 구조에 맞춘 버전
✅ 최근 2 영업일 뉴스 수집
✅ 네이버 뉴스 API 활용
✅ 종목명 + "주가", "실적", "재무" 키워드 조합
✅ 완전한 본문 내용 추출
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

import requests
import sqlite3
import pandas as pd
import time
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
from bs4 import BeautifulSoup
from tqdm import tqdm
import threading

# 로깅 설정 (Windows 인코딩 문제 해결)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / 'data' / 'news_collection.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BusinessDayCalculator:
    """영업일 및 주말 포함 날짜 계산기"""
    
    @staticmethod
    def get_recent_news_days(days_count: int = 4) -> List[str]:
        """최근 뉴스 수집 대상일 계산 (평일 + 주말 포함)"""
        news_days = []
        current_date = datetime.now()
        
        days_checked = 0
        while len(news_days) < days_count and days_checked < 10:
            current_date -= timedelta(days=1)
            days_checked += 1
            
            # 모든 요일 포함 (월~일)
            news_days.append(current_date.strftime('%Y-%m-%d'))
                
        logger.info(f"[뉴스수집일] 최근 {days_count}일: {', '.join(news_days)}")
        return news_days

class NewsAPIManager:
    """네이버 뉴스 API 관리자"""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://openapi.naver.com/v1/search/news.json"
        self.headers = {
            'X-Naver-Client-Id': self.client_id,
            'X-Naver-Client-Secret': self.client_secret
        }
        
        # API 호출 제한 관리
        self.api_calls_today = 0
        self.max_calls_per_day = 23000  # 여유분 2000회
        self.last_call_time = time.time()
        self.min_interval = 0.12  # 초당 8회 제한 (안전하게)
        self.lock = threading.Lock()
        
    def rate_limit_check(self) -> bool:
        """API 호출 제한 확인"""
        with self.lock:
            current_time = time.time()
            
            if self.api_calls_today >= self.max_calls_per_day:
                logger.warning(f"⚠️ 일일 API 호출 제한 도달: {self.api_calls_today:,}")
                return False
            
            time_since_last_call = current_time - self.last_call_time
            if time_since_last_call < self.min_interval:
                sleep_time = self.min_interval - time_since_last_call
                time.sleep(sleep_time)
            
            self.last_call_time = time.time()
            self.api_calls_today += 1
            
            return True
    
    def search_news(self, query: str, display: int = 100, sort: str = 'date') -> List[Dict]:
        """뉴스 검색"""
        if not self.rate_limit_check():
            return []
        
        params = {
            'query': query,
            'display': min(display, 100),
            'sort': sort
        }
        
        try:
            response = requests.get(self.base_url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            
            # 최근 영업일 필터링
            recent_items = self._filter_recent_news(items)
            
            return recent_items
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 뉴스 검색 API 오류 - 검색어: {query}, 오류: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ 예상치 못한 오류 - 검색어: {query}, 오류: {e}")
            return []
    
    def _filter_recent_news(self, items: List[Dict]) -> List[Dict]:
        """최근 4일간 뉴스만 필터링 (평일 + 주말 포함)"""
        news_days = BusinessDayCalculator.get_recent_news_days(4)
        recent_items = []
        
        for item in items:
            try:
                pub_date_str = item.get('pubDate', '')
                pub_date = self._parse_date(pub_date_str)
                
                if pub_date:
                    pub_date_formatted = pub_date.strftime('%Y-%m-%d')
                    if pub_date_formatted in news_days:
                        recent_items.append(item)
            except:
                continue
        
        return recent_items
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """날짜 문자열을 datetime으로 변환"""
        try:
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            return dt.replace(tzinfo=None)
        except:
            return None

class NewsContentExtractor:
    """뉴스 본문 추출기"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def extract_content(self, url: str) -> str:
        """뉴스 기사 본문 추출"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            content = ""
            
            # 네이버 뉴스 본문 추출
            if 'news.naver.com' in url:
                content = self._extract_naver_content(soup)
            
            # 다른 뉴스 사이트 본문 추출
            if not content:
                content = self._extract_general_content(soup)
            
            return content[:3000] if content else ""
            
        except Exception as e:
            logger.debug(f"본문 추출 실패 - {url}: {e}")
            return ""
    
    def _extract_naver_content(self, soup: BeautifulSoup) -> str:
        """네이버 뉴스 본문 추출"""
        selectors = [
            'div#newsct_article',
            'div.newsct_article', 
            'div#articleBodyContents',
            'div.article_body',
            'div.news_end'
        ]
        
        for selector in selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # 불필요한 요소 제거
                for elem in content_div.find_all(['script', 'style', 'ins', 'iframe', 'aside']):
                    elem.decompose()
                
                text = content_div.get_text(separator=' ', strip=True)
                text = self._clean_text(text)
                
                if len(text) > 100:
                    return text
        
        return ""
    
    def _extract_general_content(self, soup: BeautifulSoup) -> str:
        """일반 뉴스 사이트 본문 추출"""
        selectors = [
            'div.article-content',
            'div.news-content',
            'div.content',
            'article',
            'div.post-content',
            'div.article_txt',
            'div.article-body'
        ]
        
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                for elem in content.find_all(['script', 'style', 'ins', 'iframe']):
                    elem.decompose()
                
                text = content.get_text(separator=' ', strip=True)
                text = self._clean_text(text)
                
                if len(text) > 100:
                    return text
        
        # 마지막 시도: 모든 p 태그
        paragraphs = soup.find_all('p')
        if paragraphs:
            text = ' '.join([p.get_text(strip=True) for p in paragraphs])
            text = self._clean_text(text)
            if len(text) > 100:
                return text
        
        return ""
    
    def _clean_text(self, text: str) -> str:
        """텍스트 정제"""
        # 불필요한 문구 제거
        patterns_to_remove = [
            r'// flash 오류를 우회하기 위한 함수 추가.*',
            r'본 기사는.*?입니다',
            r'저작권자.*?무단.*?금지',
            r'기자\s*=.*?기자',
            r'\[.*?\]',
            r'<.*?>',
            r'&[a-zA-Z]+;'
        ]
        
        for pattern in patterns_to_remove:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # 여러 공백을 하나로
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

class StockNewsCollector:
    """주식 뉴스 수집기 메인 클래스"""
    
    def __init__(self, client_id: str, client_secret: str):
        self.api_manager = NewsAPIManager(client_id, client_secret)
        self.content_extractor = NewsContentExtractor()
        self.db_path = project_root / "finance_data.db"
        self.init_database()  # 데이터베이스 초기화 추가
        
    def init_database(self):
        """데이터베이스 테이블 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 기존 테이블 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            # stock_info 테이블이 없으면 생성
            if 'stock_info' not in existing_tables:
                logger.info("stock_info 테이블을 생성합니다...")
                cursor.execute('''
                    CREATE TABLE stock_info (
                        code TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        market TEXT,
                        sector TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 기본 종목 데이터 삽입
                basic_stocks = [
                    ('005930', '삼성전자', 'KOSPI', 'IT'),
                    ('000660', 'SK하이닉스', 'KOSPI', 'IT'),
                    ('035420', 'NAVER', 'KOSPI', 'IT'),
                    ('005380', '현대차', 'KOSPI', '자동차'),
                    ('006400', '삼성SDI', 'KOSPI', '화학'),
                    ('051910', 'LG화학', 'KOSPI', '화학'),
                    ('096770', 'SK이노베이션', 'KOSPI', '화학'),
                    ('034730', 'SK', 'KOSPI', '지주회사'),
                    ('003550', 'LG', 'KOSPI', '지주회사'),
                    ('012330', '현대모비스', 'KOSPI', '자동차부품'),
                    ('207940', '삼성바이오로직스', 'KOSPI', '바이오'),
                    ('373220', 'LG에너지솔루션', 'KOSPI', '화학'),
                    ('000270', '기아', 'KOSPI', '자동차'),
                    ('068270', '셀트리온', 'KOSPI', '바이오'),
                    ('035720', '카카오', 'KOSPI', 'IT'),
                    ('018260', '삼성에스디에스', 'KOSPI', 'IT'),
                    ('036570', '엔씨소프트', 'KOSPI', 'IT'),
                    ('066570', 'LG전자', 'KOSPI', '전자'),
                    ('105560', 'KB금융', 'KOSPI', '금융'),
                    ('055550', '신한지주', 'KOSPI', '금융')
                ]
                
                for stock in basic_stocks:
                    cursor.execute('''
                        INSERT OR IGNORE INTO stock_info (code, name, market, sector)
                        VALUES (?, ?, ?, ?)
                    ''', stock)
                
                logger.info(f"{len(basic_stocks)}개 기본 종목 데이터 생성 완료")
            
            # news_articles 테이블 생성 (뉴스 저장용)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    link TEXT NOT NULL UNIQUE,
                    description TEXT,
                    content TEXT,
                    pub_date TEXT,
                    source TEXT,
                    sentiment_score REAL DEFAULT 0.0,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_stock_code ON news_articles(stock_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_pub_date ON news_articles(pub_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_collected_at ON news_articles(collected_at)')
            
            conn.commit()
        
    def get_all_stocks(self) -> List[Dict[str, str]]:
        """전체 주식 종목 조회"""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query("""
                SELECT code, name 
                FROM stock_info 
                WHERE name NOT LIKE '%스팩%'
                AND name NOT LIKE '%리츠%'
                AND name NOT LIKE '%ETF%'
                ORDER BY code
            """, conn)
            
        return df.to_dict('records')
    
    def get_existing_links_today(self) -> set:
        """오늘 수집된 뉴스 링크들 (중복 방지)"""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query("""
                SELECT DISTINCT link 
                FROM news_articles 
                WHERE DATE(collected_at) = DATE('now')
            """, conn)
            
        return set(df['link'].tolist()) if not df.empty else set()
    
    def collect_stock_news(self, stock: Dict[str, str]) -> List[Dict]:
        """특정 종목의 뉴스 수집"""
        stock_code = stock['code']
        stock_name = stock['name']
        
        collected_news = []
        existing_links = self.get_existing_links_today()
        
        # 검색 전략: 종목명 + 키워드 조합
        search_strategies = [
            stock_name,
            f"{stock_name} 주가",
            f"{stock_name} 실적",
            f"{stock_name} 재무"
        ]
        
        max_news_per_query = 30
        max_total_news = 50
        
        for query in search_strategies:
            if len(collected_news) >= max_total_news:
                break
            
            if self.api_manager.api_calls_today >= self.api_manager.max_calls_per_day:
                logger.warning("[경고] API 호출 제한 도달, 수집 중단")
                break
            
            news_items = self.api_manager.search_news(query, display=max_news_per_query)
            
            for item in news_items:
                if len(collected_news) >= max_total_news:
                    break
                
                if item['link'] in existing_links:
                    continue
                
                # 종목 관련성 체크
                title = re.sub(r'<[^>]+>', '', item['title'])
                description = re.sub(r'<[^>]+>', '', item['description'])
                
                if self._is_relevant_news(title, description, stock_name, stock_code):
                    # 본문 수집
                    content = self.content_extractor.extract_content(item['link'])
                    
                    news_data = {
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'title': title,
                        'link': item['link'],
                        'description': description,
                        'content': content,
                        'pub_date': item['pubDate'],
                        'source': self._extract_source(item.get('originallink', item['link']))
                    }
                    
                    collected_news.append(news_data)
                    existing_links.add(item['link'])
            
            time.sleep(0.1)
        
        if collected_news:
            logger.info(f"[수집완료] {stock_name}: {len(collected_news)}개 뉴스 수집 완료")
        
        return collected_news
    
    def _is_relevant_news(self, title: str, description: str, stock_name: str, stock_code: str) -> bool:
        """뉴스의 종목 관련성 체크"""
        # 종목명 직접 포함
        if stock_name in title or stock_code in title:
            return True
        
        # 설명에 종목명 포함
        if stock_name in description:
            return True
        
        # 주식 관련 키워드 + 종목명 일부
        stock_keywords = ['주가', '실적', '재무', '매출', '영업이익', '투자', '상장', '공시', '배당']
        text_combined = f"{title} {description}".lower()
        
        if any(keyword in text_combined for keyword in stock_keywords):
            name_parts = stock_name.split()
            if any(part in text_combined for part in name_parts if len(part) > 1):
                return True
        
        return False
    
    def _extract_source(self, url: str) -> str:
        """뉴스 소스 추출"""
        if not url:
            return 'Unknown'
        
        source_mapping = {
            'chosun.com': '조선일보',
            'donga.com': '동아일보',
            'joins.com': '중앙일보',
            'mk.co.kr': '매일경제',
            'hankyung.com': '한국경제',
            'yonhapnews.co.kr': '연합뉴스',
            'mt.co.kr': '머니투데이',
            'etnews.com': '전자신문'
        }
        
        for domain, source in source_mapping.items():
            if domain in url:
                return source
        
        try:
            domain_parts = url.split('//')[1].split('/')[0].split('.')
            return domain_parts[-2] if len(domain_parts) > 1 else 'Unknown'
        except:
            return 'Unknown'
    
    def save_news_batch(self, news_list: List[Dict]) -> int:
        """뉴스 배치 저장"""
        if not news_list:
            return 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            saved_count = 0
            for news in news_list:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO news_articles 
                        (stock_code, stock_name, title, link, description, content, pub_date, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        news['stock_code'],
                        news['stock_name'],
                        news['title'],
                        news['link'],
                        news['description'],
                        news['content'],
                        news['pub_date'],
                        news['source']
                    ))
                    
                    if cursor.rowcount > 0:
                        saved_count += 1
                        
                except sqlite3.Error as e:
                    logger.error(f"저장 실패 - {news['title']}: {e}")
            
            conn.commit()
            
        return saved_count
    
    def collect_all_stocks_news(self, max_workers: int = 3, batch_size: int = 20, test_mode: bool = False):
        """전체 종목 뉴스 수집"""
        
        news_days = BusinessDayCalculator.get_recent_news_days(4)
        stocks = self.get_all_stocks()
        
        if test_mode:
            stocks = stocks[:20]
            logger.info(f"[테스트모드] {len(stocks)}개 종목으로 제한")
        
        logger.info(f"[시작] 총 {len(stocks)}개 종목 뉴스 수집 시작")
        logger.info(f"[수집기간] 최근 4일간 뉴스 수집 (평일 + 주말 포함)")
        
        total_collected = 0
        total_saved = 0
        
        with tqdm(total=len(stocks), desc="뉴스 수집 진행", unit="종목") as pbar:
            
            for i in range(0, len(stocks), batch_size):
                batch = stocks[i:i + batch_size]
                batch_news = []
                
                if self.api_manager.api_calls_today >= self.api_manager.max_calls_per_day:
                    logger.warning("[경고] 일일 API 호출 제한 도달, 수집 중단")
                    break
                
                logger.info(f"[배치처리] 배치 {i//batch_size + 1}/{(len(stocks)-1)//batch_size + 1} 처리 중...")
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_stock = {
                        executor.submit(self.collect_stock_news, stock): stock
                        for stock in batch
                    }
                    
                    for future in as_completed(future_to_stock):
                        stock = future_to_stock[future]
                        try:
                            news_list = future.result()
                            if news_list:
                                batch_news.extend(news_list)
                                total_collected += len(news_list)
                            
                            pbar.set_postfix({
                                'API호출': f"{self.api_manager.api_calls_today:,}",
                                '수집': f"{total_collected:,}",
                                '저장': f"{total_saved:,}"
                            })
                            
                        except Exception as e:
                            logger.error(f"[오류] {stock['name']} 처리 실패: {e}")
                        
                        pbar.update(1)
                
                # 배치 저장
                if batch_news:
                    saved_count = self.save_news_batch(batch_news)
                    total_saved += saved_count
                    logger.info(f"[배치저장] 배치 저장: {len(batch_news)}개 수집 -> {saved_count}개 신규 저장")
                
                # 배치 간 대기
                if i + batch_size < len(stocks):
                    time.sleep(10)
        
        logger.info(f"[완료] 전체 수집 완료!")
        logger.info(f"[결과] 최종 결과: {total_collected:,}개 수집, {total_saved:,}개 저장")
        logger.info(f"[API호출] API 호출 수: {self.api_manager.api_calls_today:,}")
        
        self.print_collection_summary()
    
    def print_collection_summary(self):
        """수집 결과 요약 출력"""
        with sqlite3.connect(self.db_path) as conn:
            # 오늘 수집 통계
            today_stats = pd.read_sql_query("""
                SELECT 
                    COUNT(*) as total_news,
                    COUNT(DISTINCT stock_code) as stocks_with_news,
                    COUNT(DISTINCT source) as news_sources,
                    AVG(LENGTH(content)) as avg_content_length
                FROM news_articles 
                WHERE DATE(collected_at) = DATE('now')
            """, conn).iloc[0]
            
            # 소스별 통계
            source_stats = pd.read_sql_query("""
                SELECT source, COUNT(*) as count
                FROM news_articles 
                WHERE DATE(collected_at) = DATE('now')
                GROUP BY source
                ORDER BY count DESC
                LIMIT 5
            """, conn)
            
            # 종목별 뉴스 수 TOP 5
            stock_stats = pd.read_sql_query("""
                SELECT stock_name, COUNT(*) as news_count
                FROM news_articles 
                WHERE DATE(collected_at) = DATE('now')
                GROUP BY stock_code, stock_name
                ORDER BY news_count DESC
                LIMIT 5
            """, conn)
        
        print(f"\n[수집요약] 오늘 수집 요약:")
        print(f"  • 총 뉴스: {today_stats['total_news']:,}개")
        print(f"  • 뉴스 있는 종목: {today_stats['stocks_with_news']:,}개")
        print(f"  • 뉴스 소스: {today_stats['news_sources']:,}개")
        print(f"  • 평균 본문 길이: {today_stats['avg_content_length']:.0f}자")
        
        if not source_stats.empty:
            print(f"\n[소스별통계] 소스별 뉴스 수:")
            for _, row in source_stats.iterrows():
                print(f"  • {row['source']}: {row['count']}개")
        
        if not stock_stats.empty:
            print(f"\n[인기종목] 뉴스 많은 종목 TOP 5:")
            for _, row in stock_stats.iterrows():
                print(f"  • {row['stock_name']}: {row['news_count']}개")

def get_api_credentials():
    """환경변수에서 네이버 API 인증정보 조회"""
    client_id = os.getenv('NAVER_CLIENT_ID')
    client_secret = os.getenv('NAVER_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("\n[환경변수 설정 필요]")
        print("❌ .env 파일에 네이버 API 인증정보를 설정해주세요:")
        print()
        print("# .env 파일에 추가할 내용:")
        print("NAVER_CLIENT_ID=your_client_id_here")
        print("NAVER_CLIENT_SECRET=your_client_secret_here")
        print()
        
        # 수동 입력 옵션 제공
        choice = input("수동으로 입력하시겠습니까? (y/N): ").strip().lower()
        if choice == 'y':
            client_id = input("🔐 Client ID: ").strip()
            client_secret = input("🔐 Client Secret: ").strip()
            
            if client_id and client_secret:
                # .env 파일에 자동 저장 제안
                save_choice = input("\n이 정보를 .env 파일에 저장하시겠습니까? (y/N): ").strip().lower()
                if save_choice == 'y':
                    save_to_env(client_id, client_secret)
                
                return client_id, client_secret
        
        return None, None
    
    print(f"[환경변수] 네이버 API 인증정보 로드 완료")
    print(f"  • Client ID: {client_id[:10]}...")
    return client_id, client_secret

def save_to_env(client_id: str, client_secret: str):
    """API 인증정보를 .env 파일에 저장"""
    env_file = project_root / '.env'
    
    try:
        # 기존 .env 파일 읽기
        env_content = ""
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                env_content = f.read()
        
        # 기존 NAVER API 설정 제거
        lines = env_content.split('\n')
        filtered_lines = [line for line in lines if not line.startswith(('NAVER_CLIENT_ID', 'NAVER_CLIENT_SECRET'))]
        
        # 새로운 API 설정 추가
        filtered_lines.extend([
            '',
            '# 네이버 뉴스 API 설정',
            f'NAVER_CLIENT_ID={client_id}',
            f'NAVER_CLIENT_SECRET={client_secret}'
        ])
        
        # .env 파일에 저장
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(filtered_lines))
        
        print("✅ .env 파일에 API 인증정보 저장 완료")
        
    except Exception as e:
        print(f"❌ .env 파일 저장 실패: {e}")

def main():
    """메인 실행 함수"""
    
    print("\n" + "="*70)
    print("📰 전체 종목 뉴스 수집기")
    print("="*70)
    print("✅ 최근 4일간 뉴스 대상 (평일 + 주말 포함)")
    print("✅ 종목명 + '주가', '실적', '재무' 키워드 조합")
    print("✅ 완전한 본문 내용 추출")
    print("✅ API 호출 제한 관리 (25,000회/일)")
    
    # 환경변수에서 API 인증 정보 로드
    client_id, client_secret = get_api_credentials()
    
    if not client_id or not client_secret:
        print("❌ API 인증 정보가 필요합니다.")
        return
    
    # 수집기 초기화
    collector = StockNewsCollector(client_id, client_secret)
    
    print("\n🎯 수집 모드 선택:")
    print("1. 테스트 모드 (20개 종목)")
    print("2. 전체 모드 (모든 종목)")
    print("3. 현재 수집 현황 확인")
    print("4. 종료")
    
    choice = input("\n선택 (1-4): ").strip()
    
    if choice == '1':
        print("\n🧪 테스트 모드로 뉴스 수집을 시작합니다...")
        collector.collect_all_stocks_news(test_mode=True)
        
    elif choice == '2':
        stocks = collector.get_all_stocks()
        print(f"\n[전체정보] 전체 대상 종목: {len(stocks):,}개")
        print(f"[예상API] 예상 API 호출: 약 {len(stocks) * 4:,}회")
        
        confirm = input("⚠️ 전체 종목 수집은 시간이 오래 걸립니다. 계속하시겠습니까? (y/N): ").strip().lower()
        if confirm == 'y':
            print("\n🚀 전체 모드로 뉴스 수집을 시작합니다...")
            collector.collect_all_stocks_news(test_mode=False)
        else:
            print("❌ 수집이 취소되었습니다.")
            
    elif choice == '3':
        collector.print_collection_summary()
        
    elif choice == '4':
        print("👋 프로그램을 종료합니다.")
    
    else:
        print("❌ 잘못된 선택입니다.")

if __name__ == "__main__":
    main()