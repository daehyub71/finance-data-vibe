"""
📰 뉴스 수집 및 감정 분석 시스템 (품질 검증 강화 버전)

이 모듈은 주식 관련 뉴스를 수집하고 감정 분석을 수행합니다.

주요 기능:
1. 네이버 금융 뉴스 크롤링
2. 종목별 뉴스 수집
3. 뉴스 텍스트 전처리
4. 감정 분석 (긍정/부정/중립)
5. 종목별 감정 지수 계산
6. 시계열 감정 추이 분석

🆕 품질 검증 강화:
7. 스팸/중복/오류 뉴스 자동 필터링
8. 신뢰도 점수 자동 계산
9. 한글 인코딩 문제 완전 해결
10. 뉴스 품질 등급 시스템

🎯 목표: 신뢰할 수 있는 뉴스 기반 투자 신호 생성
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
import difflib
from collections import Counter
import unicodedata
from typing import List, Dict, Optional, Tuple
import logging

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

# 로깅 설정 (한글 인코딩 완전 해결)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / 'data' / 'news_collection_enhanced.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class NewsQualityValidator:
    """
    뉴스 품질 검증 시스템
    
    스팸, 중복, 오류가 있는 뉴스를 자동으로 필터링하고
    각 뉴스에 신뢰도 점수를 부여합니다.
    """
    
    def __init__(self):
        # 스팸 패턴 정의 (한국 주식 뉴스 특화)
        self.spam_patterns = [
            r'클릭.*조회',
            r'무료.*상담',
            r'지금.*신청',
            r'100%.*수익',
            r'급등.*확실',
            r'대박.*종목',
            r'무조건.*상승',
            r'투자.*보장',
            r'수익률.*\d+%.*보장',
            r'단타.*수익',
            r'로또.*종목',
            r'따상.*확실',
            r'무료.*추천',
            r'VIP.*종목'
        ]
        
        # 신뢰할 수 있는 뉴스 소스 (네이버 금융 기준)
        self.trusted_sources = {
            '연합뉴스': 95,
            '한국경제': 90,
            '매일경제': 88,
            '조선일보': 85,
            '중앙일보': 85,
            '동아일보': 85,
            '머니투데이': 82,
            '전자신문': 80,
            '서울경제': 78,
            '이데일리': 75,
            '파이낸셜뉴스': 78,
            'MBN': 72,
            'SBS Biz': 75
        }
        
        # 의심스러운 키워드 (명백한 오류 포함)
        self.suspicious_keywords = [
            '2만4900원', '5만원', '10만원',  # 명백한 주가 오류
            '999999', '000000', '123456',  # 더미 데이터
            '테스트', 'test', 'TEST',
            '광고', '홍보', '협찬',
            '이벤트', '프로모션',
            '888원', '777원', '666원',  # 의심스러운 패턴
            '○○○원', 'XXX원'  # 마스킹된 데이터
        ]
        
        # 중복 검출용 캐시
        self.content_hashes = set()
        self.title_cache = {}
        
        logger.info("✅ 뉴스 품질 검증 시스템 초기화 완료")
    
    def validate_news(self, news_data: Dict) -> Tuple[bool, int, List[str]]:
        """
        뉴스 품질 종합 검증
        
        Args:
            news_data: 뉴스 데이터 딕셔너리
            
        Returns:
            Tuple[is_valid, quality_score, issues]: 
            - is_valid: 통과 여부 (70점 이상)
            - quality_score: 신뢰도 점수 (0-100)
            - issues: 발견된 문제점 리스트
        """
        issues = []
        score = 100  # 만점에서 시작해서 문제 발견 시 감점
        
        title = news_data.get('title', '')
        content = news_data.get('content', '')
        source = news_data.get('source', '')
        
        # 1. 스팸 검사 (30점 감점)
        if self._is_spam_content(title, content):
            issues.append("스팸 패턴 감지")
            score -= 30
        
        # 2. 중복 검사 (25점 감점)
        if self._is_duplicate_content(title, content):
            issues.append("중복 콘텐츠")
            score -= 25
        
        # 3. 의심스러운 키워드 검사 (20점 감점)
        if self._has_suspicious_keywords(title, content):
            issues.append("의심스러운 키워드 포함")
            score -= 20
        
        # 4. 소스 신뢰도 검사 (점수 조정)
        source_score = self._get_source_credibility(source)
        if source_score < 50:
            issues.append("신뢰도 낮은 소스")
            score = min(score, source_score + 20)
        
        # 5. 콘텐츠 품질 검사 (15점 감점)
        content_quality = self._assess_content_quality(title, content)
        if content_quality < 70:
            issues.append("콘텐츠 품질 부족")
            score -= 15
        
        # 6. 인코딩 오류 검사 (10점 감점)
        if self._has_encoding_issues(title, content):
            issues.append("인코딩 오류")
            score -= 10
        
        # 최종 점수 범위 조정
        score = max(0, min(100, score))
        
        # 70점 이상만 통과
        is_valid = score >= 70 and len(issues) <= 2
        
        if not is_valid:
            logger.debug(f"뉴스 품질 검증 실패: {title[:30]}... (점수: {score}, 문제: {issues})")
        
        return is_valid, score, issues
    
    def _is_spam_content(self, title: str, content: str) -> bool:
        """스팸 패턴 검사"""
        text_combined = f"{title} {content}".lower()
        
        for pattern in self.spam_patterns:
            if re.search(pattern, text_combined):
                return True
        
        # 과도한 특수문자 사용 (스팸 특징)
        special_char_ratio = len(re.findall(r'[!@#$%^&*()+=\[\]{}|\\:";\'<>?,./]', text_combined)) / max(len(text_combined), 1)
        if special_char_ratio > 0.1:  # 10% 이상
            return True
        
        # 과도한 숫자 사용
        number_ratio = len(re.findall(r'\d', text_combined)) / max(len(text_combined), 1)
        if number_ratio > 0.3:  # 30% 이상
            return True
        
        return False
    
    def _is_duplicate_content(self, title: str, content: str) -> bool:
        """중복 콘텐츠 검사"""
        # 제목 기반 유사도 검사
        title_normalized = self._normalize_text(title)
        
        for cached_title in self.title_cache.keys():
            similarity = difflib.SequenceMatcher(None, title_normalized, cached_title).ratio()
            if similarity > 0.85:  # 85% 이상 유사하면 중복
                return True
        
        # 캐시에 추가 (최대 1000개까지만 유지)
        if len(self.title_cache) > 1000:
            # 오래된 항목 절반 삭제
            items = list(self.title_cache.items())
            self.title_cache = dict(items[500:])
        
        self.title_cache[title_normalized] = True
        
        # 내용 해시 기반 중복 검사
        content_hash = hash(self._normalize_text(content))
        if content_hash in self.content_hashes:
            return True
        
        self.content_hashes.add(content_hash)
        
        # 메모리 관리
        if len(self.content_hashes) > 5000:
            # 절반 삭제
            self.content_hashes = set(list(self.content_hashes)[2500:])
        
        return False
    
    def _has_suspicious_keywords(self, title: str, content: str) -> bool:
        """의심스러운 키워드 검사"""
        text_combined = f"{title} {content}".lower()
        
        for keyword in self.suspicious_keywords:
            if keyword.lower() in text_combined:
                return True
        
        return False
    
    def _get_source_credibility(self, source: str) -> int:
        """소스 신뢰도 점수 반환"""
        for trusted_source, score in self.trusted_sources.items():
            if trusted_source in source:
                return score
        
        # 네이버금융 출처는 중간 점수
        if '네이버금융' in source:
            return 65
        
        # 알려지지 않은 소스는 낮은 점수
        return 50
    
    def _assess_content_quality(self, title: str, content: str) -> int:
        """콘텐츠 품질 평가"""
        quality_score = 100
        
        # 제목 길이 검사
        if len(title) < 10 or len(title) > 200:
            quality_score -= 15
        
        # 내용 길이 검사
        if len(content) < 50:
            quality_score -= 25
        elif len(content) > 10000:
            quality_score -= 5
        
        # 문장 구조 검사
        sentences = re.split(r'[.!?]', content)
        if len(sentences) < 2:
            quality_score -= 20
        
        # 의미 있는 단어 비율
        words = re.findall(r'[가-힣]+', content)
        if len(words) < 10:
            quality_score -= 25
        
        # 반복 구문 검사
        word_freq = Counter(words)
        if word_freq.most_common(1) and word_freq.most_common(1)[0][1] > len(words) * 0.1:
            quality_score -= 15
        
        return max(0, quality_score)
    
    def _has_encoding_issues(self, title: str, content: str) -> bool:
        """인코딩 오류 검사"""
        text_combined = f"{title} {content}"
        
        # 깨진 문자 패턴
        broken_patterns = [
            r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ.,!?()[\]{}:;"\'-]',  # 비정상 문자
            r'(?:[��]{2,})',  # 연속된 깨진 문자
            r'(?:&[a-zA-Z]+;){3,}',  # 과도한 HTML 엔티티
            r'[?]{3,}',  # 연속된 물음표 (깨진 문자)
        ]
        
        for pattern in broken_patterns:
            if re.search(pattern, text_combined):
                return True
        
        return False
    
    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화"""
        if not text:
            return ""
        
        # 유니코드 정규화
        text = unicodedata.normalize('NFKC', text)
        
        # 공백 정리
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 특수문자 제거 (비교용)
        text = re.sub(r'[^\w\s가-힣]', '', text)
        
        return text.lower()


class EnhancedNewsCollector:
    """
    강화된 뉴스 수집기 (품질 검증 통합)
    
    주식 관련 뉴스를 다양한 소스에서 수집하고 저장합니다.
    """
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.db_path = self.data_dir / 'news_data.db'
        
        # 품질 검증 시스템 통합
        self.quality_validator = NewsQualityValidator()
        
        # 수집 통계
        self.stats = {
            'total_collected': 0,
            'success_count': 0,
            'fail_count': 0,
            'duplicate_count': 0,
            'quality_passed': 0,
            'quality_failed': 0,
            'spam_filtered': 0,
            'low_quality_filtered': 0
        }
        
        # HTTP 세션 설정
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        self.init_database()
        print("✅ 강화된 뉴스 수집기 초기화 완료")
    
    def init_database(self):
        """🗄️ 뉴스 데이터베이스 초기화 (품질 관련 컬럼 추가)"""
        print("🗄️ 뉴스 데이터베이스 초기화 중...")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 강화된 뉴스 기사 테이블
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
                    comment_count INTEGER,
                    quality_score INTEGER DEFAULT 0,
                    quality_issues TEXT,
                    is_verified BOOLEAN DEFAULT 0,
                    credibility_rating TEXT DEFAULT 'UNKNOWN'
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
                    average_quality REAL DEFAULT 0,
                    verified_news_ratio REAL DEFAULT 0,
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
                    quality_weighted_impact REAL,
                    created_date TEXT
                )
            ''')
            
            # 품질 필터링 로그 테이블 (새로 추가)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quality_filter_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT,
                    title TEXT,
                    url TEXT,
                    filter_reason TEXT,
                    quality_score INTEGER,
                    filtered_date TEXT
                )
            ''')
            
            # 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_stock_code ON news_articles(stock_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_published_date ON news_articles(published_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_quality_score ON news_articles(quality_score)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_is_verified ON news_articles(is_verified)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment_stock_date ON sentiment_analysis(stock_code, date)')
            
            conn.commit()
        
        print("✅ 강화된 뉴스 데이터베이스 초기화 완료")
    
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
        📰 네이버 금융 뉴스 수집 (품질 검증 통합)
        
        Args:
            stock_code (str): 종목코드
            stock_name (str): 종목명
            days (int): 수집할 일수
            max_pages (int): 최대 페이지 수
            
        Returns:
            list: 수집된 고품질 뉴스 리스트
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
                    
                    # 인코딩 자동 감지
                    response.encoding = response.apparent_encoding
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
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
                            
                            # 뉴스 상세 내용 수집 (강화된 추출)
                            content, summary = self.get_enhanced_news_content(news_url)
                            
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
                            
                            # 🆕 품질 검증
                            is_valid, quality_score, issues = self.quality_validator.validate_news(news_data)
                            
                            if is_valid:
                                # 품질 정보 추가
                                news_data['quality_score'] = quality_score
                                news_data['quality_issues'] = ', '.join(issues) if issues else ''
                                news_data['is_verified'] = True
                                news_data['credibility_rating'] = self._get_credibility_rating(quality_score)
                                
                                news_list.append(news_data)
                                self.stats['quality_passed'] += 1
                            else:
                                # 필터링된 뉴스 로그 저장
                                self._log_filtered_news(stock_code, title, news_url, issues, quality_score)
                                self.stats['quality_failed'] += 1
                                
                                if '스팸 패턴 감지' in issues:
                                    self.stats['spam_filtered'] += 1
                                if '콘텐츠 품질 부족' in issues:
                                    self.stats['low_quality_filtered'] += 1
                            
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
    
    def get_enhanced_news_content(self, url):
        """
        📄 강화된 뉴스 상세 내용 추출
        
        Args:
            url (str): 뉴스 URL
            
        Returns:
            tuple: (content, summary)
        """
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # 인코딩 자동 감지 및 설정
            response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.text, 'html.parser', from_encoding='utf-8')
            
            # 다양한 뉴스 사이트의 본문 선택자 (확장)
            content_selectors = [
                '.news_body',
                '.article_body', 
                '.news_content',
                '#news_body',
                '.news_text',
                '.article_content',
                '#articleBodyContents',
                '.newsct_article',
                '.article-view-content',
                '.news-article-content'
            ]
            
            content = ""
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 광고, 관련기사 등 제거 (강화)
                    for unwanted in content_elem.find_all(['script', 'style', 'iframe', 'ins', 'aside', 'nav', 'footer']):
                        unwanted.decompose()
                    
                    # 광고 관련 클래스 제거
                    for elem in content_elem.find_all(class_=re.compile(r'(ad|advertisement|related|recommend|banner)')):
                        elem.decompose()
                    
                    content = content_elem.get_text(separator=' ', strip=True)
                    break
            
            # 강화된 텍스트 정제
            content = self._advanced_text_cleaning(content)
            
            # 요약 생성 (첫 2-3문장, 품질 고려)
            sentences = re.split(r'[.!?]\s+', content)
            meaningful_sentences = [s for s in sentences if len(s.strip()) > 20]
            summary = '. '.join(meaningful_sentences[:3])[:300] if meaningful_sentences else content[:200]
            
            return content, summary
            
        except Exception as e:
            logger.debug(f"강화된 본문 추출 실패 - {url}: {e}")
            return "", ""
    
    def _advanced_text_cleaning(self, text: str) -> str:
        """강화된 텍스트 정제 (중복 해결 개선)"""
        if not text:
            return ""
        
        # 1. 유니코드 정규화
        text = unicodedata.normalize('NFKC', text)
        
        # 2. HTML 태그 및 엔티티 제거
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', text)
        
        # 3. 불필요한 문구 제거 (확장)
        patterns_to_remove = [
            r'// flash 오류를 우회하기 위한 함수 추가.*',
            r'본\s*기사는.*?입니다',
            r'저작권자.*?무단.*?금지',
            r'ⓒ.*?무단.*?금지',
            r'Copyright.*?All.*?rights.*?reserved',
            r'기자\s*=.*?기자',
            r'^\s*\[.*?\]\s*',
            r'\s*\[.*?\]\s*
            ,
            r'이\s*메일.*?보내기',
            r'카카오톡.*?공유',
            r'페이스북.*?공유',
            r'트위터.*?공유',
            r'무단전재.*?금지',
            r'네이버.*?블로그',
            r'관련.*?뉴스',
            r'이전.*?기사',
            r'다음.*?기사',
            r'.*?구독.*?알림',
            r'.*?팔로우.*?',
            r'광고.*?문의',
            r'제보.*?tip',
            r'더보기.*?클릭',
            r'동영상.*?보기'
        ]
        
        for pattern in patterns_to_remove:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # 4. 특수 문자 정리
        text = re.sub(r'[&\[\]{}()\*\+\?\|\^\$\\.~`!@#%=:;",<>]', ' ', text)
        
        # 5. 숫자와 한글 사이 공백
        text = re.sub(r'(\d)([가-힣])', r'\1 \2', text)
        text = re.sub(r'([가-힣])(\d)', r'\1 \2', text)
        
        # 6. 강화된 중복 제거
        words = text.split()
        cleaned_words = []
        prev_word = ""
        
        for word in words:
            # 연속된 같은 단어 제거
            if word != prev_word and len(word.strip()) > 0:
                cleaned_words.append(word)
            prev_word = word
        
        text = ' '.join(cleaned_words)
        
        # 7. 중복 패턴 제거 (정규표현식, 개선)
        text = re.sub(r'([가-힣A-Za-z0-9]{2,})\1{2,}', r'\1', text)  # 3번 이상 반복
        
        # 8. 반복 구문 제거 (개선된 알고리즘)
        def remove_repeating_patterns(text):
            for length in range(3, 20):  # 더 긴 패턴도 감지
                pattern = f'(.{{{length}}})(\\1)+'
                text = re.sub(pattern, r'\1', text)
            return text
        
        text = remove_repeating_patterns(text)
        
        # 9. 여러 공백을 하나로
        text = re.sub(r'\s+', ' ', text)
        
        # 10. 최종 정리
        text = text.strip()
        
        return text
    
    def _get_credibility_rating(self, quality_score: int) -> str:
        """품질 점수를 등급으로 변환"""
        if quality_score >= 90:
            return 'EXCELLENT'
        elif quality_score >= 80:
            return 'GOOD'
        elif quality_score >= 70:
            return 'FAIR'
        elif quality_score >= 60:
            return 'POOR'
        else:
            return 'VERY_POOR'
    
    def _log_filtered_news(self, stock_code: str, title: str, url: str, issues: List[str], quality_score: int):
        """필터링된 뉴스 로그 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO quality_filter_log 
                    (stock_code, title, url, filter_reason, quality_score, filtered_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    stock_code,
                    title[:200],  # 제목 길이 제한
                    url,
                    ', '.join(issues),
                    quality_score,
                    datetime.now().isoformat()
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"필터링 로그 저장 실패: {e}")
    
    def parse_date(self, date_str):
        """📅 날짜 문자열 파싱 (개선)"""
        try:
            # "07.05" 형태
            if re.match(r'\d{2}\.\d{2}
            , date_str):
                current_year = datetime.now().year
                month, day = date_str.split('.')
                return f"{current_year}-{month}-{day} 00:00:00"
            
            # "07.05 15:30" 형태
            elif re.match(r'\d{2}\.\d{2} \d{2}:\d{2}', date_str):
                current_year = datetime.now().year
                date_part, time_part = date_str.split(' ')
                month, day = date_part.split('.')
                return f"{current_year}-{month}-{day} {time_part}:00"
            
            # "2024.07.05" 형태
            elif re.match(r'\d{4}\.\d{2}\.\d{2}', date_str):
                year, month, day = date_str.split('.')
                return f"{year}-{month}-{day} 00:00:00"
            
            # 기타 형태는 현재 시간 반환
            else:
                return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
        except:
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def save_news_to_db(self, news_list):
        """📚 뉴스 데이터를 DB에 저장 (품질 정보 포함)"""
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
                             published_date, collected_date, quality_score, quality_issues, 
                             is_verified, credibility_rating)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            news.get('stock_code', ''),
                            news.get('stock_name', ''),
                            news.get('title', ''),
                            news.get('content', ''),
                            news.get('summary', ''),
                            news.get('url', ''),
                            news.get('source', ''),
                            news.get('published_date', ''),
                            news.get('collected_date', ''),
                            news.get('quality_score', 0),
                            news.get('quality_issues', ''),
                            news.get('is_verified', True),
                            news.get('credibility_rating', 'UNKNOWN')
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
        🚀 모든 종목의 뉴스 수집 (품질 검증 통합)
        
        Args:
            days (int): 수집할 일수
            max_stocks (int): 최대 종목 수 (None이면 전체)
            max_workers (int): 동시 처리 스레드 수
        """
        print("🚀 강화된 전체 종목 뉴스 수집 시작!")
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
        print(f"🛡️ 품질 검증: 활성화 (70점 이상만 저장)")
        
        estimated_time = len(stock_list) * 30 / max_workers / 60  # 분 단위
        print(f"⏱️  예상 소요시간: 약 {estimated_time:.1f}분")
        
        confirm = input(f"\n고품질 뉴스 수집을 시작하시겠습니까? (y/N): ").strip().lower()
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
                desc="📰 고품질 뉴스 수집",
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
                    
                    # 품질 통과율 계산
                    total_processed = self.stats['quality_passed'] + self.stats['quality_failed']
                    quality_rate = (self.stats['quality_passed'] / max(total_processed, 1)) * 100
                    
                    progress_bar.set_postfix({
                        'Current': f"{stock_code}({stock_name[:8]})",
                        '고품질': self.stats['total_collected'],
                        '품질률': f"{quality_rate:.1f}%"
                    })
                    
                except Exception as e:
                    self.stats['fail_count'] += 1
                    print(f"\n❌ {stock_code}({stock_name}) 뉴스 수집 실패: {e}")
        
        # 수집 결과 출력
        self.print_enhanced_collection_summary()
    
    def collect_stock_news_worker(self, stock_code, stock_name, days):
        """📰 개별 종목 뉴스 수집 (품질 검증 워커)"""
        try:
            # 네이버 금융 뉴스 수집 (품질 검증 통합)
            news_list = self.collect_naver_finance_news(stock_code, stock_name, days)
            
            # DB 저장
            saved_count = self.save_news_to_db(news_list)
            
            return saved_count
            
        except Exception as e:
            raise e
    
    def print_enhanced_collection_summary(self):
        """📋 강화된 수집 결과 요약 출력"""
        print("\n" + "=" * 60)
        print("📋 강화된 뉴스 수집 완료!")
        print("=" * 60)
        print(f"📊 처리된 종목: {self.stats['success_count'] + self.stats['fail_count']:,}개")
        print(f"✅ 성공: {self.stats['success_count']:,}개")
        print(f"❌ 실패: {self.stats['fail_count']:,}개")
        print(f"📰 수집된 고품질 뉴스: {self.stats['total_collected']:,}건")
        print(f"🔄 중복 제외: {self.stats['duplicate_count']:,}건")
        
        # 품질 통계
        total_processed = self.stats['quality_passed'] + self.stats['quality_failed']
        if total_processed > 0:
            quality_rate = (self.stats['quality_passed'] / total_processed) * 100
            print(f"\n🛡️ 품질 검증 결과:")
            print(f"   📊 총 처리: {total_processed:,}건")
            print(f"   ✅ 품질 통과: {self.stats['quality_passed']:,}건 ({quality_rate:.1f}%)")
            print(f"   ❌ 품질 실패: {self.stats['quality_failed']:,}건")
            print(f"   🚫 스팸 필터링: {self.stats['spam_filtered']:,}건")
            print(f"   📉 저품질 필터링: {self.stats['low_quality_filtered']:,}건")
        
        print(f"\n🗄️ 데이터 저장: {self.db_path}")
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
    
    def get_enhanced_news_summary(self):
        """📊 강화된 뉴스 수집 현황 요약"""
        print("📊 강화된 뉴스 수집 현황")
        print("=" * 50)
        
        # 전체 뉴스 수 (품질별)
        total_stats = self.query_db("""
            SELECT 
                COUNT(*) as total_news,
                COUNT(CASE WHEN is_verified = 1 THEN 1 END) as verified_news,
                AVG(quality_score) as avg_quality,
                COUNT(CASE WHEN quality_score >= 80 THEN 1 END) as high_quality_news
            FROM news_articles
        """).iloc[0]
        
        print(f"📰 전체 뉴스: {total_stats['total_news']:,}건")
        print(f"✅ 검증된 뉴스: {total_stats['verified_news']:,}건")
        print(f"📊 평균 품질 점수: {total_stats['avg_quality']:.1f}점")
        print(f"🏆 고품질 뉴스 (80점 이상): {total_stats['high_quality_news']:,}건")
        
        # 종목별 뉴스 수 (품질별, 상위 10개)
        stock_news = self.query_db("""
            SELECT 
                stock_code, 
                stock_name, 
                COUNT(*) as news_count,
                AVG(quality_score) as avg_quality,
                COUNT(CASE WHEN is_verified = 1 THEN 1 END) as verified_count
            FROM news_articles
            GROUP BY stock_code, stock_name
            ORDER BY news_count DESC
            LIMIT 10
        """)
        
        if not stock_news.empty:
            print(f"\n📈 종목별 뉴스 (상위 10개):")
            for _, row in stock_news.iterrows():
                print(f"   {row['stock_code']} ({row['stock_name']}): {row['news_count']}건 "
                      f"(검증: {row['verified_count']}건, 평균품질: {row['avg_quality']:.1f}점)")
        
        # 소스별 신뢰도
        source_stats = self.query_db("""
            SELECT 
                source, 
                COUNT(*) as count,
                AVG(quality_score) as avg_quality,
                COUNT(CASE WHEN is_verified = 1 THEN 1 END) as verified_count
            FROM news_articles
            GROUP BY source
            ORDER BY avg_quality DESC, count DESC
            LIMIT 10
        """)
        
        if not source_stats.empty:
            print(f"\n📰 소스별 신뢰도 (상위 10개):")
            for _, row in source_stats.iterrows():
                verification_rate = (row['verified_count'] / row['count']) * 100
                print(f"   {row['source']}: {row['count']}건 "
                      f"(평균품질: {row['avg_quality']:.1f}점, 검증률: {verification_rate:.1f}%)")
        
        # 일별 뉴스 수 (최근 7일, 품질별)
        daily_news = self.query_db("""
            SELECT 
                DATE(published_date) as date, 
                COUNT(*) as count,
                AVG(quality_score) as avg_quality,
                COUNT(CASE WHEN is_verified = 1 THEN 1 END) as verified_count
            FROM news_articles
            WHERE published_date >= DATE('now', '-7 days')
            GROUP BY DATE(published_date)
            ORDER BY date DESC
        """)
        
        if not daily_news.empty:
            print(f"\n📅 일별 뉴스 (최근 7일):")
            for _, row in daily_news.iterrows():
                verification_rate = (row['verified_count'] / row['count']) * 100
                print(f"   {row['date']}: {row['count']}건 "
                      f"(검증: {row['verified_count']}건, 평균품질: {row['avg_quality']:.1f}점)")
        
        # 필터링 통계
        filter_stats = self.query_db("""
            SELECT 
                filter_reason,
                COUNT(*) as count
            FROM quality_filter_log
            GROUP BY filter_reason
            ORDER BY count DESC
        """)
        
        if not filter_stats.empty:
            print(f"\n🚫 필터링 통계:")
            for _, row in filter_stats.iterrows():
                print(f"   {row['filter_reason']}: {row['count']}건")
        
        print("=" * 50)


class EnhancedNewsSentimentAnalyzer:
    """
    강화된 뉴스 감정 분석기 (품질 가중치 적용)
    
    수집된 고품질 뉴스에 대해 감정 분석을 수행하고 
    품질 점수를 가중치로 하여 더 정확한 감정 지수를 계산합니다.
    """
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.db_path = self.data_dir / 'news_data.db'
        
        # 강화된 금융 감정 사전 (한국어)
        self.positive_words = {
            '상승', '급등', '호재', '성장', '증가', '확대', '개선', '회복',
            '돌파', '상향', '긍정', '호황', '활성', '부양', '투자', '확장',
            '수익', '이익', '실적', '개발', '혁신', '전망', '기대', '추천',
            '매수', '강세', '반등', '선방', '양호', '우수', '탄탄', '견조',
            '흑자', '증익', '호조', '개선', '신고가', '최고', '성공', '우량'
        }
        
        self.negative_words = {
            '하락', '급락', '악재', '감소', '축소', '악화', '침체', '위기',
            '손실', '적자', '부진', '둔화', '경고', '우려', '불안', '리스크',
            '타격', '충격', '압박', '제재', '규제', '파산', '구조조정',
            '매도', '약세', '조정', '부담', '취약', '악순환', '침체', '저조',
            '적자', '감익', '부실', '위험', '신저가', '최저', '실패', '불량'
        }
        
        print("✅ 강화된 뉴스 감정 분석기 초기화 완료")
    
    def calculate_weighted_sentiment_score(self, text, quality_score=100):
        """
        📊 품질 가중치를 적용한 감정 점수 계산
        
        Args:
            text (str): 분석할 텍스트
            quality_score (int): 뉴스 품질 점수 (0-100)
            
        Returns:
            tuple: (sentiment_score, sentiment_label, weighted_score)
        """
        if not text:
            return 0.0, 'neutral', 0.0
        
        text = text.lower()
        
        # 긍정/부정 단어 개수 계산
        positive_count = sum(1 for word in self.positive_words if word in text)
        negative_count = sum(1 for word in self.negative_words if word in text)
        
        # 총 감정 단어 수
        total_sentiment_words = positive_count + negative_count
        
        if total_sentiment_words == 0:
            return 0.0, 'neutral', 0.0
        
        # 기본 감정 점수 계산 (-1.0 ~ 1.0)
        sentiment_score = (positive_count - negative_count) / total_sentiment_words
        
        # 품질 가중치 적용 (품질이 높을수록 더 신뢰)
        quality_weight = quality_score / 100.0
        weighted_score = sentiment_score * quality_weight
        
        # 라벨 결정 (가중치 적용된 점수 기준)
        if weighted_score > 0.15:
            sentiment_label = 'positive'
        elif weighted_score < -0.15:
            sentiment_label = 'negative'
        else:
            sentiment_label = 'neutral'
        
        return sentiment_score, sentiment_label, weighted_score
    
    def analyze_all_news_sentiment(self):
        """🔍 모든 고품질 뉴스에 대해 감정 분석 수행"""
        print("🔍 강화된 뉴스 감정 분석 시작!")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 품질 검증된 뉴스 중 감정 분석이 안된 뉴스들 조회
                query = """
                    SELECT id, title, content, summary, stock_code, quality_score
                    FROM news_articles
                    WHERE sentiment_score IS NULL AND is_verified = 1
                    ORDER BY quality_score DESC, id
                """
                news_to_analyze = pd.read_sql_query(query, conn)
                
                if news_to_analyze.empty:
                    print("✅ 모든 고품질 뉴스가 이미 감정 분석 완료되었습니다.")
                    return
                
                print(f"📊 감정 분석 대상: {len(news_to_analyze)}건 (검증된 뉴스만)")
                
                cursor = conn.cursor()
                analyzed_count = 0
                
                # 진행률 표시
                progress_bar = tqdm(news_to_analyze.iterrows(), 
                                  total=len(news_to_analyze),
                                  desc="🔍 품질가중 감정분석",
                                  unit="뉴스")
                
                for _, row in progress_bar:
                    try:
                        # 제목과 요약을 합쳐서 분석
                        text_to_analyze = f"{row['title']} {row['summary']}"
                        quality_score = row['quality_score']
                        
                        # 품질 가중치 적용 감정 분석 수행
                        sentiment_score, sentiment_label, weighted_score = self.calculate_weighted_sentiment_score(
                            text_to_analyze, quality_score
                        )
                        
                        # DB 업데이트
                        cursor.execute('''
                            UPDATE news_articles 
                            SET sentiment_score = ?, sentiment_label = ?
                            WHERE id = ?
                        ''', (weighted_score, sentiment_label, row['id']))
                        
                        analyzed_count += 1
                        
                        progress_bar.set_postfix({
                            'Analyzed': analyzed_count,
                            'Current': sentiment_label,
                            'Quality': f"{quality_score}점"
                        })
                        
                    except Exception as e:
                        print(f"\n⚠️ 뉴스 ID {row['id']} 감정 분석 실패: {e}")
                        continue
                
                conn.commit()
                
                print(f"\n✅ 강화된 감정 분석 완료: {analyzed_count}건")
                
                # 감정 분석 결과 요약
                self.summarize_enhanced_sentiment_results()
                
        except Exception as e:
            print(f"❌ 강화된 감정 분석 실패: {e}")
    
    def calculate_enhanced_daily_sentiment_index(self):
        """📈 품질 가중치 적용된 일별 종목별 감정 지수 계산"""
        print("📈 강화된 일별 감정 지수 계산 중...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 종목별, 일별 감정 분석 결과 집계 (품질 가중치 적용)
                query = """
                    SELECT 
                        stock_code,
                        DATE(published_date) as date,
                        SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) as positive_count,
                        SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) as negative_count,
                        SUM(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
                        COUNT(*) as total_count,
                        AVG(sentiment_score) as avg_sentiment_score,
                        AVG(quality_score) as avg_quality_score,
                        COUNT(CASE WHEN is_verified = 1 THEN 1 END) * 1.0 / COUNT(*) as verified_ratio
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
                
                # 강화된 감정 지수 계산 및 저장
                for _, row in results.iterrows():
                    # 품질 가중치 적용된 감정 지수 계산 (0~100, 50이 중립)
                    if row['total_count'] > 0:
                        positive_ratio = row['positive_count'] / row['total_count']
                        negative_ratio = row['negative_count'] / row['total_count']
                        
                        # 기본 감정 지수
                        base_sentiment_index = 50 + (positive_ratio - negative_ratio) * 50
                        
                        # 품질 가중치 적용
                        quality_weight = row['avg_quality_score'] / 100.0
                        enhanced_sentiment_index = 50 + (base_sentiment_index - 50) * quality_weight
                        
                        # 검증된 뉴스 비율도 반영
                        verified_weight = row['verified_ratio']
                        final_sentiment_index = 50 + (enhanced_sentiment_index - 50) * verified_weight
                    else:
                        final_sentiment_index = 50
                    
                    # DB에 저장
                    cursor.execute('''
                        INSERT OR REPLACE INTO sentiment_analysis
                        (stock_code, date, positive_count, negative_count, neutral_count,
                         total_count, sentiment_score, sentiment_index, average_quality, 
                         verified_news_ratio, created_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['stock_code'],
                        row['date'],
                        row['positive_count'],
                        row['negative_count'],
                        row['neutral_count'],
                        row['total_count'],
                        row['avg_sentiment_score'],
                        final_sentiment_index,
                        row['avg_quality_score'],
                        row['verified_ratio'],
                        datetime.now().isoformat()
                    ))
                
                conn.commit()
                print(f"✅ {len(results)}건의 강화된 일별 감정 지수 계산 완료")
                
        except Exception as e:
            print(f"❌ 강화된 감정 지수 계산 실패: {e}")
    
    def summarize_enhanced_sentiment_results(self):
        """📊 강화된 감정 분석 결과 요약"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 전체 감정 분포 (검증된 뉴스만)
                sentiment_dist = pd.read_sql_query("""
                    SELECT 
                        sentiment_label,
                        COUNT(*) as count,
                        AVG(quality_score) as avg_quality,
                        COUNT(*) * 100.0 / (SELECT COUNT(*) FROM news_articles WHERE sentiment_label IS NOT NULL AND is_verified = 1) as percentage
                    FROM news_articles
                    WHERE sentiment_label IS NOT NULL AND is_verified = 1
                    GROUP BY sentiment_label
                """, conn)
                
                print("\n📊 강화된 감정 분포 (검증된 뉴스만):")
                for _, row in sentiment_dist.iterrows():
                    print(f"   {row['sentiment_label']}: {row['count']:,}건 ({row['percentage']:.1f}%, 평균품질: {row['avg_quality']:.1f}점)")
                
                # 종목별 감정 점수 (상위/하위 5개, 품질 가중치 적용)
                stock_sentiment = pd.read_sql_query("""
                    SELECT 
                        stock_code,
                        stock_name,
                        AVG(sentiment_score) as avg_sentiment,
                        AVG(quality_score) as avg_quality,
                        COUNT(*) as news_count,
                        COUNT(CASE WHEN is_verified = 1 THEN 1 END) as verified_count
                    FROM news_articles
                    WHERE sentiment_score IS NOT NULL AND is_verified = 1
                    GROUP BY stock_code, stock_name
                    HAVING COUNT(*) >= 5
                    ORDER BY avg_sentiment DESC
                """, conn)
                
                if not stock_sentiment.empty:
                    print(f"\n📈 종목별 평균 감정 점수 (품질 가중치 적용):")
                    print("   🔝 상위 5개:")
                    for _, row in stock_sentiment.head().iterrows():
                        print(f"      {row['stock_code']} ({row['stock_name']}): {row['avg_sentiment']:.3f} "
                              f"(품질: {row['avg_quality']:.1f}점, 검증: {row['verified_count']}/{row['news_count']}건)")
                    
                    print("   📉 하위 5개:")
                    for _, row in stock_sentiment.tail().iterrows():
                        print(f"      {row['stock_code']} ({row['stock_name']}): {row['avg_sentiment']:.3f} "
                              f"(품질: {row['avg_quality']:.1f}점, 검증: {row['verified_count']}/{row['news_count']}건)")
                
        except Exception as e:
            print(f"⚠️ 강화된 감정 분석 요약 실패: {e}")
    
    def get_enhanced_stock_sentiment_trend(self, stock_code, days=30):
        """📈 특정 종목의 강화된 감정 추이 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT 
                        date, 
                        sentiment_index, 
                        total_count,
                        average_quality,
                        verified_news_ratio
                    FROM sentiment_analysis
                    WHERE stock_code = ?
                    AND date >= DATE('now', '-{} days')
                    ORDER BY date
                """.format(days)
                
                return pd.read_sql_query(query, conn, params=(stock_code,))
                
        except Exception as e:
            print(f"❌ 강화된 감정 추이 조회 실패: {e}")
            return pd.DataFrame()


def main():
    """메인 실행 함수"""
    
    print("🚀 Finance Data Vibe - 강화된 뉴스 수집 및 감정 분석 시스템")
    print("=" * 70)
    print("🆕 품질 검증 시스템 통합 - 스팸/중복/오류 자동 필터링")
    print("🆕 신뢰도 점수 기반 품질 관리")
    print("🆕 한글 인코딩 문제 완전 해결")
    print("🆕 품질 가중치 적용 감정 분석")
    
    while True:
        print("\n📰 원하는 기능을 선택하세요:")
        print("1. 전체 종목 고품질 뉴스 수집")
        print("2. 특정 종목 뉴스 수집")
        print("3. 강화된 뉴스 감정 분석 수행")
        print("4. 품질 가중치 적용 일별 감정 지수 계산")
        print("5. 강화된 뉴스 수집 현황 확인")
        print("6. 품질별 감정 분석 결과 확인")
        print("7. 품질 필터링 통계 확인")
        print("0. 종료")
        
        choice = input("\n선택하세요 (0-7): ").strip()
        
        if choice == '0':
            print("👋 프로그램을 종료합니다.")
            break
        
        elif choice == '1':
            # 전체 종목 고품질 뉴스 수집
            collector = EnhancedNewsCollector()
            
            days = int(input("수집할 일수를 입력하세요 (기본값: 7): ").strip() or "7")
            max_stocks = input("최대 종목 수 (전체: Enter): ").strip()
            max_stocks = int(max_stocks) if max_stocks else None
            
            print(f"\n🛡️ 품질 검증 활성화: 70점 이상만 저장")
            print(f"🚫 자동 필터링: 스팸/중복/오류 뉴스 제거")
            
            collector.collect_all_stock_news(days=days, max_stocks=max_stocks)
        
        elif choice == '2':
            # 특정 종목 뉴스 수집
            collector = EnhancedNewsCollector()
            
            stock_code = input("종목코드를 입력하세요 (예: 005930): ").strip()
            stock_name = input("종목명을 입력하세요 (예: 삼성전자): ").strip()
            days = int(input("수집할 일수를 입력하세요 (기본값: 7): ").strip() or "7")
            
            if stock_code and stock_name:
                news_list = collector.collect_naver_finance_news(stock_code, stock_name, days)
                saved_count = collector.save_news_to_db(news_list)
                
                if news_list:
                    avg_quality = sum(news.get('quality_score', 0) for news in news_list) / len(news_list)
                    print(f"✅ {saved_count}건의 고품질 뉴스를 수집했습니다. (평균 품질: {avg_quality:.1f}점)")
                else:
                    print("❌ 품질 기준을 통과한 뉴스가 없습니다.")
            else:
                print("❌ 종목코드와 종목명을 모두 입력해주세요.")
        
        elif choice == '3':
            # 강화된 뉴스 감정 분석
            analyzer = EnhancedNewsSentimentAnalyzer()
            analyzer.analyze_all_news_sentiment()
        
        elif choice == '4':
            # 품질 가중치 적용 일별 감정 지수 계산
            analyzer = EnhancedNewsSentimentAnalyzer()
            analyzer.calculate_enhanced_daily_sentiment_index()
        
        elif choice == '5':
            # 강화된 뉴스 수집 현황
            collector = EnhancedNewsCollector()
            collector.get_enhanced_news_summary()
        
        elif choice == '6':
            # 품질별 감정 분석 결과
            analyzer = EnhancedNewsSentimentAnalyzer()
            analyzer.summarize_enhanced_sentiment_results()
        
        elif choice == '7':
            # 품질 필터링 통계
            collector = EnhancedNewsCollector()
            
            # 필터링 통계 조회
            filter_stats = collector.query_db("""
                SELECT 
                    filter_reason,
                    COUNT(*) as count,
                    AVG(quality_score) as avg_quality_score
                FROM quality_filter_log
                WHERE DATE(filtered_date) >= DATE('now', '-7 days')
                GROUP BY filter_reason
                ORDER BY count DESC
            """)
            
            if not filter_stats.empty:
                print("\n🚫 최근 7일 품질 필터링 통계:")
                print("=" * 50)
                for _, row in filter_stats.iterrows():
                    print(f"   {row['filter_reason']}: {row['count']:,}건 (평균 점수: {row['avg_quality_score']:.1f}점)")
                
                # 전체 통계
                total_filtered = filter_stats['count'].sum()
                total_saved = collector.query_db("""
                    SELECT COUNT(*) as count 
                    FROM news_articles 
                    WHERE DATE(collected_date) >= DATE('now', '-7 days')
                """).iloc[0]['count']
                
                filter_rate = (total_filtered / max(total_filtered + total_saved, 1)) * 100
                print(f"\n📊 필터링 효과:")
                print(f"   🚫 필터링된 뉴스: {total_filtered:,}건")
                print(f"   ✅ 저장된 뉴스: {total_saved:,}건")
                print(f"   📈 필터링률: {filter_rate:.1f}%")
            else:
                print("❌ 최근 필터링 데이터가 없습니다.")
        
        else:
            print("❌ 올바른 번호를 선택해주세요.")


if __name__ == "__main__":
    main()