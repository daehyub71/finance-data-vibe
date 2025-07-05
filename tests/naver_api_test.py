"""
네이버 뉴스 API 연동 테스트
1. API 연결 확인
2. 삼성전자 뉴스 수집 테스트
3. 기존 데이터베이스 연동
"""

import requests
import sqlite3
import pandas as pd
import time
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
import os
import json
import re
from bs4 import BeautifulSoup

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NaverNewsAPITest:
    """네이버 뉴스 API 테스트 클래스"""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://openapi.naver.com/v1/search/news.json"
        self.headers = {
            'X-Naver-Client-Id': self.client_id,
            'X-Naver-Client-Secret': self.client_secret
        }
        
    def test_connection(self) -> bool:
        """API 연결 테스트"""
        logger.info("🔗 네이버 뉴스 API 연결 테스트 중...")
        
        params = {
            'query': '삼성전자',
            'display': 1,
            'sort': 'date'
        }
        
        try:
            response = requests.get(self.base_url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if 'items' in data:
                logger.info("✅ 네이버 뉴스 API 연결 성공!")
                logger.info(f"📊 API 응답: {len(data['items'])}개 뉴스 검색됨")
                logger.info(f"🔢 전체 검색 결과: {data.get('total', 0):,}개")
                return True
            else:
                logger.error("❌ API 응답에 뉴스 데이터가 없습니다.")
                return False
                
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                logger.error("❌ 인증 실패: Client ID 또는 Secret이 잘못되었습니다.")
            elif response.status_code == 403:
                logger.error("❌ 권한 없음: 검색 API가 활성화되었는지 확인하세요.")
            else:
                logger.error(f"❌ HTTP 오류: {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ 연결 실패: {e}")
            return False
    
    def search_news_detailed(self, query: str, display: int = 10) -> Dict:
        """상세 뉴스 검색 (분석용)"""
        logger.info(f"🔍 '{query}' 검색 중...")
        
        params = {
            'query': query,
            'display': display,
            'sort': 'date'
        }
        
        try:
            response = requests.get(self.base_url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            
            # 뉴스 분석
            analysis = {
                'total_results': data.get('total', 0),
                'returned_count': len(items),
                'news_items': [],
                'sources': {},
                'recent_news': []
            }
            
            for item in items:
                # HTML 태그 제거
                title = re.sub(r'<[^>]+>', '', item['title'])
                description = re.sub(r'<[^>]+>', '', item['description'])
                
                # 뉴스 소스 분석
                if 'originallink' in item:
                    source = self._extract_source(item['originallink'])
                    analysis['sources'][source] = analysis['sources'].get(source, 0) + 1
                
                news_item = {
                    'title': title,
                    'description': description,
                    'link': item['link'],
                    'pub_date': item['pubDate'],
                    'source': self._extract_source(item.get('originallink', ''))
                }
                
                analysis['news_items'].append(news_item)
                
                # 최근 24시간 뉴스 체크
                pub_date = self._parse_date(item['pubDate'])
                if pub_date and (datetime.now() - pub_date).days < 1:
                    analysis['recent_news'].append(news_item)
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ 검색 실패: {e}")
            return {}
    
    def _extract_source(self, url: str) -> str:
        """URL에서 뉴스 소스 추출"""
        if not url:
            return 'Unknown'
            
        if 'naver.com' in url:
            return 'Naver'
        elif 'chosun.com' in url:
            return '조선일보'
        elif 'donga.com' in url:
            return '동아일보'
        elif 'joins.com' in url:
            return '중앙일보'
        elif 'hani.co.kr' in url:
            return '한겨레'
        elif 'khan.co.kr' in url:
            return '경향신문'
        elif 'mk.co.kr' in url:
            return '매일경제'
        elif 'hankyung.com' in url:
            return '한국경제'
        elif 'etnews.com' in url:
            return '전자신문'
        elif 'yonhapnews.co.kr' in url:
            return '연합뉴스'
        else:
            # 도메인에서 추출
            try:
                domain = url.split('//')[1].split('/')[0].split('.')
                return domain[-2] if len(domain) > 1 else 'Unknown'
            except:
                return 'Unknown'
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """날짜 문자열을 datetime으로 변환"""
        try:
            # RFC 2822 형식: "Sat, 05 Jul 2025 14:30:00 +0900"
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            # timezone 정보 제거하여 naive datetime으로 변환
            return dt.replace(tzinfo=None)
        except:
            try:
                # 다른 형식 시도
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except:
                return None
    
    def collect_content(self, url: str) -> str:
        """뉴스 본문 수집"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 네이버 뉴스인 경우
            if 'news.naver.com' in url:
                content_div = soup.find('div', {'id': 'newsct_article'}) or \
                             soup.find('div', {'class': 'newsct_article'}) or \
                             soup.find('div', {'id': 'articleBodyContents'})
                             
                if content_div:
                    # 광고, 스크립트 등 제거
                    for elem in content_div.find_all(['script', 'style', 'ins', 'iframe']):
                        elem.decompose()
                    
                    text = content_div.get_text(strip=True)
                    # 불필요한 문구 제거
                    text = re.sub(r'(// flash 오류를 우회하기 위한 함수 추가.*)', '', text)
                    text = re.sub(r'\s+', ' ', text)  # 여러 공백을 하나로
                    
                    return text[:1000]  # 최대 1000자로 제한
            
            return "본문 추출 실패"
            
        except Exception as e:
            logger.warning(f"본문 수집 실패 - URL: {url}, 오류: {e}")
            return "본문 수집 실패"

def test_existing_database():
    """기존 데이터베이스 연동 테스트"""
    logger.info("🗄️ 기존 데이터베이스 연결 테스트...")
    
    db_path = "finance_data.db"
    
    if not os.path.exists(db_path):
        logger.warning(f"⚠️ 데이터베이스 파일이 없습니다: {db_path}")
        logger.info("🔧 기본 데이터베이스를 생성합니다...")
        
        # 기본 데이터베이스 생성
        create_basic_database()
        return get_sample_stocks()
    
    try:
        with sqlite3.connect(db_path) as conn:
            # 기존 테이블 확인
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"✅ 데이터베이스 연결 성공!")
            logger.info(f"📊 기존 테이블: {', '.join(tables)}")
            
            # 종목 데이터 확인
            if 'stock_info' in tables:
                stock_count = pd.read_sql_query(
                    "SELECT COUNT(*) as count FROM stock_info", conn
                ).iloc[0]['count']
                logger.info(f"📈 등록된 종목 수: {stock_count:,}개")
                
                # 샘플 종목 조회
                sample_stocks = pd.read_sql_query(
                    "SELECT code, name FROM stock_info LIMIT 5", conn
                )
                logger.info("📋 샘플 종목:")
                for _, stock in sample_stocks.iterrows():
                    logger.info(f"  • {stock['name']}({stock['code']})")
                
                return sample_stocks.to_dict('records')
            else:
                logger.warning("⚠️ stock_info 테이블이 없습니다. 기본 종목을 생성합니다.")
                create_basic_stocks()
                return get_sample_stocks()
                
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}")
        return None

def create_basic_database():
    """기본 데이터베이스 구조 생성"""
    db_path = "finance_data.db"
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # 기본 테이블들 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_info (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                market TEXT,
                sector TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                date TEXT NOT NULL,
                open_price REAL,
                high_price REAL,
                low_price REAL,
                close_price REAL,
                volume INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (code) REFERENCES stock_info (code),
                UNIQUE(code, date)
            )
        ''')
        
        conn.commit()
    
    logger.info("✅ 기본 데이터베이스 구조 생성 완료")

def create_basic_stocks():
    """기본 종목 데이터 삽입"""
    db_path = "finance_data.db"
    
    # 주요 종목들
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
        ('012330', '현대모비스', 'KOSPI', '자동차부품')
    ]
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        for stock in basic_stocks:
            cursor.execute('''
                INSERT OR IGNORE INTO stock_info (code, name, market, sector)
                VALUES (?, ?, ?, ?)
            ''', stock)
        
        conn.commit()
    
    logger.info(f"✅ {len(basic_stocks)}개 기본 종목 데이터 생성 완료")

def get_sample_stocks():
    """샘플 종목 반환"""
    return [
        {'code': '005930', 'name': '삼성전자'},
        {'code': '000660', 'name': 'SK하이닉스'},
        {'code': '035420', 'name': 'NAVER'},
        {'code': '005380', 'name': '현대차'},
        {'code': '006400', 'name': '삼성SDI'}
    ]

def create_news_table():
    """뉴스 테이블 생성"""
    logger.info("📰 뉴스 테이블 생성 중...")
    
    db_path = "finance_data.db"
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
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
        
    logger.info("✅ 뉴스 테이블 생성 완료")

def test_news_collection(api: NaverNewsAPITest, stock_code: str = "005930", stock_name: str = "삼성전자"):
    """뉴스 수집 테스트"""
    logger.info(f"📰 {stock_name}({stock_code}) 뉴스 수집 테스트...")
    
    # 뉴스 검색
    analysis = api.search_news_detailed(stock_name, display=5)
    
    if not analysis:
        logger.error("❌ 뉴스 검색 실패")
        return
    
    logger.info(f"🔍 검색 결과:")
    logger.info(f"  • 전체 결과: {analysis['total_results']:,}개")
    logger.info(f"  • 수집된 뉴스: {analysis['returned_count']}개")
    logger.info(f"  • 최근 24시간: {len(analysis['recent_news'])}개")
    
    if analysis['sources']:
        logger.info(f"📊 뉴스 소스:")
        for source, count in analysis['sources'].items():
            logger.info(f"  • {source}: {count}개")
    
    # 첫 번째 뉴스의 본문 수집 테스트
    if analysis['news_items']:
        first_news = analysis['news_items'][0]
        logger.info(f"\n📄 첫 번째 뉴스 상세:")
        logger.info(f"  제목: {first_news['title']}")
        logger.info(f"  설명: {first_news['description'][:100]}...")
        logger.info(f"  소스: {first_news['source']}")
        logger.info(f"  발행: {first_news['pub_date']}")
        
        # 본문 수집 테스트
        content = api.collect_content(first_news['link'])
        logger.info(f"  본문: {content[:200]}...")
        
        # 데이터베이스에 샘플 저장
        save_sample_news(stock_code, stock_name, first_news, content)

def save_sample_news(stock_code: str, stock_name: str, news_item: Dict, content: str):
    """샘플 뉴스를 데이터베이스에 저장"""
    logger.info("💾 샘플 뉴스 저장 중...")
    
    db_path = "finance_data.db"
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO news_articles 
                (stock_code, stock_name, title, link, description, content, pub_date, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stock_code,
                stock_name,
                news_item['title'],
                news_item['link'],
                news_item['description'],
                content,
                news_item['pub_date'],
                news_item['source']
            ))
            
            conn.commit()
            logger.info("✅ 샘플 뉴스 저장 완료")
            
    except Exception as e:
        logger.error(f"❌ 저장 실패: {e}")

def main():
    """메인 실행 함수"""
    
    print("\n" + "="*60)
    print("🚀 네이버 뉴스 API 연동 테스트")
    print("="*60)
    
    # 1. API 인증 정보 입력
    print("\n🔐 네이버 API 인증 정보를 입력하세요:")
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()
    
    if not client_id or not client_secret:
        logger.error("❌ Client ID와 Secret을 모두 입력해주세요.")
        return
    
    # 2. API 연결 테스트
    api = NaverNewsAPITest(client_id, client_secret)
    
    if not api.test_connection():
        logger.error("❌ API 연결에 실패했습니다. 인증 정보를 확인하세요.")
        return
    
    # 3. 기존 데이터베이스 확인
    stocks = test_existing_database()
    
    # 4. 뉴스 테이블 생성
    create_news_table()
    
    # 5. 뉴스 수집 테스트
    print("\n📰 뉴스 수집 테스트를 시작합니다...")
    
    if stocks:
        # 기존 종목으로 테스트
        test_stock = stocks[0]  # 첫 번째 종목
        test_news_collection(api, test_stock['code'], test_stock['name'])
    else:
        # 기본 종목으로 테스트
        test_news_collection(api)
    
    # 6. 결과 확인
    db_path = "finance_data.db"
    with sqlite3.connect(db_path) as conn:
        news_count = pd.read_sql_query(
            "SELECT COUNT(*) as count FROM news_articles", conn
        ).iloc[0]['count']
        
        if news_count > 0:
            recent_news = pd.read_sql_query("""
                SELECT stock_name, title, source, collected_at
                FROM news_articles 
                ORDER BY collected_at DESC 
                LIMIT 3
            """, conn)
            
            print(f"\n🎉 테스트 완료! 데이터베이스에 {news_count}개 뉴스 저장됨")
            print("\n📋 최근 수집된 뉴스:")
            for _, news in recent_news.iterrows():
                print(f"  • [{news['source']}] {news['title'][:50]}...")
        else:
            print("\n⚠️ 뉴스가 저장되지 않았습니다.")
    
    print("\n🚀 다음 단계:")
    print("  1. 전체 종목 뉴스 수집 실행")
    print("  2. 감정 분석 모듈 추가")
    print("  3. 스케줄러로 자동 수집 설정")

if __name__ == "__main__":
    main()