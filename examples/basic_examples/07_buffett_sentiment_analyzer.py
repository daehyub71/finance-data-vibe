"""
examples/basic_examples/07_buffett_sentiment_analyzer.py

워런 버핏 스타일 뉴스 감정 분석 엔진
✅ 가치투자 관점 감정 사전 구축
✅ 펀더멘털 vs 노이즈 분류
✅ 일별 종목별 감정 지수 계산
✅ 장기투자 관련성 스코어링

비중: 뉴스감정분석 25% (보조 지표 역할)
"""

import sys
import os
from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
from tqdm import tqdm
import logging
from collections import defaultdict, Counter

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BuffettSentimentAnalyzer:
    """
    워런 버핏 스타일 뉴스 감정 분석기
    
    핵심 철학:
    1. 펀더멘털 뉴스에 높은 가중치
    2. 단기 노이즈는 낮은 가중치  
    3. 장기 투자 관련성 우선
    4. 감정 역투자 신호 활용
    """
    
    def __init__(self):
        self.db_path = project_root / "finance_data.db"
        
        # 데이터베이스 스키마 검증
        if not self._validate_database_schema():
            logger.error("❌ 데이터베이스 스키마가 부적절합니다!")
            logger.error("🔧 마이그레이션을 실행하세요: python examples/basic_examples/08_db_migration_sentiment.py")
            raise RuntimeError("데이터베이스 마이그레이션 필요")
        
        # 워런 버핏 스타일 감정 사전 구축
        self._build_buffett_sentiment_dictionary()
        
        # 뉴스 카테고리별 가중치 (가치투자 관점)
        self.news_weights = {
            'fundamental': 1.0,      # 펀더멘털 뉴스 (최고 가중치)
            'business': 0.8,         # 사업 관련 뉴스
            'financial': 0.9,        # 재무 관련 뉴스
            'management': 0.7,       # 경영진 관련 뉴스
            'market': 0.4,           # 시장 일반 뉴스
            'technical': 0.3,        # 기술적 분석 뉴스 (낮은 가중치)
            'noise': 0.1            # 노이즈성 뉴스 (최저 가중치)
        }
        
        logger.info("✅ 워런 버핏 스타일 감정 분석기 초기화 완료")
    
    def _build_buffett_sentiment_dictionary(self):
        """워런 버핏 스타일 감정 사전 구축 (가치투자 관점)"""
        
        # 🟢 긍정 감정 사전 (가치투자 호재)
        self.positive_words = {
            # 📊 펀더멘털 강화 (가장 중요)
            'fundamental_strong': {
                'words': [
                    '실적개선', '매출증가', '영업이익', '순이익증가', '이익률개선',
                    'ROE상승', '자기자본이익률', '부채감소', '재무건전성', '유동성개선',
                    '영업현금흐름', '잉여현금', '자본확충', '재무구조개선', '신용등급상향'
                ],
                'weight': 3.0  # 최고 가중치
            },
            
            # 🏭 사업모델 강화
            'business_strong': {
                'words': [
                    '신사업', '사업확장', '시장점유율', '경쟁우위', '브랜드가치',
                    '특허취득', '기술력', '연구개발', '혁신', '차별화',
                    '시장진입', '해외진출', '신규고객', '계약체결', '파트너십'
                ],
                'weight': 2.5
            },
            
            # 💼 경영 품질
            'management_quality': {
                'words': [
                    '경영진교체', '전문경영', '투명경영', '지배구조개선', 'ESG',
                    '배당증액', '배당정책', '주주환원', '자사주매입', '감자',
                    '구조조정완료', '효율성개선', '비용절감', '생산성향상'
                ],
                'weight': 2.0
            },
            
            # 📈 성장 동력
            'growth_drivers': {
                'words': [
                    '매출확대', '수주증가', '주문급증', '백로그', '파이프라인',
                    '신제품출시', '제품포트폴리오', '고부가가치', '프리미엄',
                    '글로벌진출', '수출증가', '시장확대', '고객기반확장'
                ],
                'weight': 2.0
            }
        }
        
        # 🔴 부정 감정 사전 (가치투자 악재)
        self.negative_words = {
            # 📉 펀더멘털 악화 (가장 위험)
            'fundamental_weak': {
                'words': [
                    '실적악화', '매출감소', '적자전환', '손실확대', '이익률하락',
                    'ROE하락', '부채증가', '재무악화', '유동성위기', '자금난',
                    '현금흐름악화', '신용등급하향', '부실', '구조조정', '정리해고'
                ],
                'weight': 3.0  # 최고 위험 가중치
            },
            
            # 🏭 사업모델 위기  
            'business_risk': {
                'words': [
                    '시장축소', '점유율하락', '경쟁심화', '가격경쟁', '마진압박',
                    '기술낙후', '특허분쟁', '소송', '규제강화', '제재',
                    '고객이탈', '계약해지', '사업철수', '공장폐쇄', '감산'
                ],
                'weight': 2.5
            },
            
            # 💼 경영 리스크
            'management_risk': {
                'words': [
                    '경영진갈등', '지배구조', '횡령', '배임', '분식회계',
                    '감사의견', '외부감사', '금융감독원', '검찰수사', '기소',
                    '배당중단', '무배', '주주갈등', '경영권분쟁'
                ],
                'weight': 2.0
            },
            
            # 📉 시장 리스크
            'market_risk': {
                'words': [
                    '경기침체', '불황', '금리인상', '인플레이션', '환율급등',
                    '원자재가격', '유가급등', '공급망차질', '팬데믹', '지정학적리스크',
                    '무역분쟁', '관세', '수출규제', '경제제재'
                ],
                'weight': 1.5
            }
        }
        
        # 🔄 중립 키워드 (노이즈 필터링용)
        self.neutral_noise_words = {
            '주가', '시세', '차트', '기술적', '이평선', '거래량', 
            '매수추천', '매도추천', '목표주가', '주식', '증권',
            '단타', '스윙', '데이트레이딩', '급등주', '급락주'
        }
        
        logger.info("📊 워런 버핏 스타일 감정 사전 구축 완료")
        logger.info(f"   🟢 긍정 카테고리: {len(self.positive_words)}개")
        logger.info(f"   🔴 부정 카테고리: {len(self.negative_words)}개")
    
    def _validate_database_schema(self) -> bool:
        """데이터베이스 스키마 검증"""
        
        if not self.db_path.exists():
            logger.error(f"❌ 데이터베이스 파일이 없습니다: {self.db_path}")
            return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # news_articles 테이블 존재 확인
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='news_articles'")
                if not cursor.fetchone():
                    logger.error("❌ news_articles 테이블이 없습니다")
                    return False
                
                # 필요한 컬럼들 확인
                cursor.execute("PRAGMA table_info(news_articles)")
                existing_columns = [row[1] for row in cursor.fetchall()]
                
                required_columns = ['sentiment_score', 'sentiment_label', 'news_category', 'long_term_relevance']
                missing_columns = [col for col in required_columns if col not in existing_columns]
                
                if missing_columns:
                    logger.error(f"❌ 누락된 컬럼: {missing_columns}")
                    return False
                
                logger.info("✅ 데이터베이스 스키마 검증 완료")
                return True
                
        except Exception as e:
            logger.error(f"❌ 데이터베이스 스키마 검증 실패: {e}")
            return False
    
    def categorize_news_content(self, title: str, content: str) -> str:
        """뉴스 내용을 가치투자 관점으로 카테고리 분류"""
        
        text = f"{title} {content}".lower()
        
        # 펀더멘털 뉴스 (최우선)
        fundamental_keywords = [
            '실적', '매출', '영업이익', '순이익', '재무제표', 'roe', '부채비율',
            '배당', '감사보고서', '공시', '사업보고서', '분기실적', '연간실적'
        ]
        
        if any(keyword in text for keyword in fundamental_keywords):
            return 'fundamental'
        
        # 사업 관련 뉴스
        business_keywords = [
            '신사업', '사업확장', '인수합병', '전략적제휴', '파트너십',
            '신제품', '연구개발', '특허', '기술개발', '시장진출'
        ]
        
        if any(keyword in text for keyword in business_keywords):
            return 'business'
        
        # 재무 관련 뉴스
        financial_keywords = [
            '자금조달', '투자유치', '채권발행', '대출', '신용등급',
            '재무구조', '현금흐름', '유동성', '자본금', '증자'
        ]
        
        if any(keyword in text for keyword in financial_keywords):
            return 'financial'
        
        # 경영진 관련 뉴스
        management_keywords = [
            '대표이사', 'ceo', '경영진', '임원', '사장', '회장',
            '이사회', '주주총회', '지배구조', '경영권', '승계'
        ]
        
        if any(keyword in text for keyword in management_keywords):
            return 'management'
        
        # 기술적/차트 뉴스 (낮은 가중치)
        technical_keywords = [
            '차트', '기술적', '이평선', '지지선', '저항선', '돌파',
            '목표주가', '매수추천', '매도추천', 'rsi', 'macd'
        ]
        
        if any(keyword in text for keyword in technical_keywords):
            return 'technical'
        
        # 시장 일반 뉴스
        market_keywords = [
            '코스피', '코스닥', '증시', '주식시장', '경기', '금리',
            '환율', '유가', '원자재', '인플레이션'
        ]
        
        if any(keyword in text for keyword in market_keywords):
            return 'market'
        
        # 기본값: 노이즈로 분류
        return 'noise'
    
    def calculate_buffett_sentiment_score(self, title: str, content: str, description: str = "") -> Dict:
        """워런 버핏 스타일 감정 점수 계산"""
        
        # 전체 텍스트 결합 및 전처리
        full_text = f"{title} {description} {content}".lower()
        full_text = re.sub(r'[^\w\s]', ' ', full_text)  # 특수문자 제거
        full_text = ' '.join(full_text.split())  # 공백 정리
        
        # 뉴스 카테고리 분류
        news_category = self.categorize_news_content(title, content)
        category_weight = self.news_weights.get(news_category, 0.5)
        
        # 감정 점수 계산
        sentiment_scores = {
            'positive': 0.0,
            'negative': 0.0,
            'neutral': 0.0
        }
        
        detail_scores = {
            'positive_details': defaultdict(list),
            'negative_details': defaultdict(list)
        }
        
        # 긍정 감정 분석
        for category, data in self.positive_words.items():
            for word in data['words']:
                if word in full_text:
                    score = data['weight'] * category_weight
                    sentiment_scores['positive'] += score
                    detail_scores['positive_details'][category].append({
                        'word': word,
                        'score': score
                    })
        
        # 부정 감정 분석
        for category, data in self.negative_words.items():
            for word in data['words']:
                if word in full_text:
                    score = data['weight'] * category_weight
                    sentiment_scores['negative'] += score
                    detail_scores['negative_details'][category].append({
                        'word': word,
                        'score': score
                    })
        
        # 중립/노이즈 체크
        noise_count = sum(1 for word in self.neutral_noise_words if word in full_text)
        if noise_count > 0:
            sentiment_scores['neutral'] = noise_count * 0.1
        
        # 최종 감정 점수 계산 (-1.0 ~ 1.0)
        total_positive = sentiment_scores['positive']
        total_negative = sentiment_scores['negative']
        total_sentiment = total_positive + total_negative + sentiment_scores['neutral']
        
        if total_sentiment > 0:
            final_score = (total_positive - total_negative) / total_sentiment
        else:
            final_score = 0.0
        
        # 감정 라벨 결정 (워런 버핏 관점)
        if final_score > 0.3:
            sentiment_label = 'bullish'  # 장기 상승 전망
        elif final_score < -0.3:
            sentiment_label = 'bearish'  # 장기 하락 위험
        elif final_score > 0.1:
            sentiment_label = 'positive'  # 소폭 긍정
        elif final_score < -0.1:
            sentiment_label = 'negative'  # 소폭 부정
        else:
            sentiment_label = 'neutral'   # 중립
        
        # 장기 투자 관련성 점수 (0~100)
        long_term_relevance = self._calculate_long_term_relevance(
            news_category, total_positive, total_negative
        )
        
        return {
            'sentiment_score': round(final_score, 4),
            'sentiment_label': sentiment_label,
            'news_category': news_category,
            'category_weight': category_weight,
            'long_term_relevance': long_term_relevance,
            'positive_score': round(total_positive, 2),
            'negative_score': round(total_negative, 2),
            'detail_analysis': detail_scores
        }
    
    def _calculate_long_term_relevance(self, category: str, pos_score: float, neg_score: float) -> int:
        """장기 투자 관련성 점수 계산 (0~100)"""
        
        # 카테고리별 기본 점수
        base_scores = {
            'fundamental': 90,  # 펀더멘털은 장기 투자에 가장 중요
            'business': 80,     # 사업 모델 변화도 중요
            'financial': 85,    # 재무 상황도 중요
            'management': 70,   # 경영진도 장기적으로 중요
            'market': 40,       # 시장 일반은 보통
            'technical': 20,    # 기술적 분석은 장기 투자에 덜 중요
            'noise': 10        # 노이즈는 거의 무관
        }
        
        base_score = base_scores.get(category, 30)
        
        # 감정 강도 보너스/페널티
        intensity = abs(pos_score - neg_score)
        if intensity > 5.0:
            base_score += 20  # 강한 감정은 더 중요
        elif intensity > 2.0:
            base_score += 10
        elif intensity < 0.5:
            base_score -= 10  # 약한 감정은 덜 중요
        
        return max(0, min(100, base_score))
    
    def analyze_news_batch(self, limit: int = None) -> pd.DataFrame:
        """수집된 뉴스 배치 감정 분석"""
        
        logger.info("🔍 워런 버핏 스타일 뉴스 감정 분석 시작")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 감정 분석이 안된 뉴스들 조회
                query = """
                    SELECT id, stock_code, stock_name, title, content, description, 
                           pub_date, source, collected_at
                    FROM news_articles
                    WHERE sentiment_score IS NULL OR sentiment_score = 0.0
                    ORDER BY collected_at DESC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                news_df = pd.read_sql_query(query, conn)
                
                if news_df.empty:
                    logger.info("✅ 모든 뉴스가 이미 감정 분석 완료되었습니다")
                    return pd.DataFrame()
                
                logger.info(f"📊 감정 분석 대상: {len(news_df):,}건")
                
                # 감정 분석 실행
                results = []
                cursor = conn.cursor()
                
                progress_bar = tqdm(news_df.iterrows(), 
                                  total=len(news_df),
                                  desc="🔍 워런 버핏 감정분석",
                                  unit="뉴스")
                
                for idx, row in progress_bar:
                    try:
                        # 감정 분석 수행
                        sentiment_result = self.calculate_buffett_sentiment_score(
                            title=row['title'] or "",
                            content=row['content'] or "",
                            description=row['description'] or ""
                        )
                        
                        # 결과 저장
                        results.append({
                            'id': row['id'],
                            'stock_code': row['stock_code'],
                            'sentiment_score': sentiment_result['sentiment_score'],
                            'sentiment_label': sentiment_result['sentiment_label'],
                            'news_category': sentiment_result['news_category'],
                            'long_term_relevance': sentiment_result['long_term_relevance'],
                            **sentiment_result
                        })
                        
                        # DB 업데이트
                        cursor.execute('''
                            UPDATE news_articles 
                            SET sentiment_score = ?, 
                                sentiment_label = ?,
                                news_category = ?,
                                long_term_relevance = ?
                            WHERE id = ?
                        ''', (
                            sentiment_result['sentiment_score'],
                            sentiment_result['sentiment_label'], 
                            sentiment_result['news_category'],
                            sentiment_result['long_term_relevance'],
                            row['id']
                        ))
                        
                        progress_bar.set_postfix({
                            'Label': sentiment_result['sentiment_label'][:4],
                            'Category': sentiment_result['news_category'][:4],
                            'Score': f"{sentiment_result['sentiment_score']:.2f}"
                        })
                        
                    except Exception as e:
                        logger.error(f"뉴스 ID {row['id']} 분석 실패: {e}")
                        continue
                
                conn.commit()
                logger.info(f"✅ 감정 분석 완료: {len(results):,}건")
                
                return pd.DataFrame(results)
                
        except Exception as e:
            logger.error(f"❌ 배치 감정 분석 실패: {e}")
            return pd.DataFrame()
    
    def calculate_daily_sentiment_index(self, days: int = 30) -> pd.DataFrame:
        """일별 종목별 워런 버핏 감정 지수 계산"""
        
        logger.info(f"📈 최근 {days}일 일별 감정 지수 계산 중...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 최근 N일간 감정 분석된 뉴스 조회
                query = """
                    SELECT 
                        stock_code,
                        stock_name,
                        DATE(pub_date) as date,
                        sentiment_score,
                        sentiment_label,
                        news_category,
                        long_term_relevance,
                        COUNT(*) as news_count
                    FROM news_articles
                    WHERE sentiment_score IS NOT NULL
                    AND DATE(pub_date) >= DATE('now', '-{} days')
                    GROUP BY stock_code, stock_name, DATE(pub_date), 
                             sentiment_score, sentiment_label, news_category, long_term_relevance
                    ORDER BY stock_code, date DESC
                """.format(days)
                
                news_data = pd.read_sql_query(query, conn)
                
                if news_data.empty:
                    logger.warning("❌ 감정 분석 데이터가 없습니다")
                    return pd.DataFrame()
                
                # 일별 종목별 집계
                daily_sentiment = []
                
                for (stock_code, stock_name, date), group in news_data.groupby(['stock_code', 'stock_name', 'date']):
                    
                    # 워런 버핏 스타일 가중 평균 계산
                    weighted_scores = []
                    category_counts = defaultdict(int)
                    
                    for _, row in group.iterrows():
                        # 장기 투자 관련성으로 가중치 적용
                        weight = row['long_term_relevance'] / 100.0
                        weighted_score = row['sentiment_score'] * weight * row['news_count']
                        weighted_scores.append(weighted_score)
                        category_counts[row['news_category']] += row['news_count']
                    
                    # 최종 감정 지수 계산
                    if weighted_scores:
                        daily_score = np.mean(weighted_scores)
                    else:
                        daily_score = 0.0
                    
                    # 감정 지수를 0~100 범위로 변환 (50이 중립)
                    sentiment_index = 50 + (daily_score * 25)  # -1~1 -> 25~75 범위
                    sentiment_index = max(0, min(100, sentiment_index))
                    
                    # 신뢰도 계산 (뉴스 개수와 카테고리 다양성 기반)
                    total_news = group['news_count'].sum()
                    category_diversity = len(category_counts)
                    confidence = min(100, total_news * 10 + category_diversity * 5)
                    
                    daily_sentiment.append({
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'date': date,
                        'sentiment_index': round(sentiment_index, 2),
                        'sentiment_score': round(daily_score, 4),
                        'total_news': total_news,
                        'confidence': confidence,
                        'fundamental_news': category_counts.get('fundamental', 0),
                        'business_news': category_counts.get('business', 0),
                        'technical_news': category_counts.get('technical', 0),
                        'noise_news': category_counts.get('noise', 0)
                    })
                
                # 결과를 DB에 저장
                daily_df = pd.DataFrame(daily_sentiment)
                
                if not daily_df.empty:
                    cursor = conn.cursor()
                    
                    # 기존 테이블이 없으면 생성
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS daily_sentiment_index (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            stock_code TEXT NOT NULL,
                            stock_name TEXT NOT NULL,
                            date TEXT NOT NULL,
                            sentiment_index REAL NOT NULL,
                            sentiment_score REAL NOT NULL,
                            total_news INTEGER NOT NULL,
                            confidence INTEGER NOT NULL,
                            fundamental_news INTEGER DEFAULT 0,
                            business_news INTEGER DEFAULT 0,
                            technical_news INTEGER DEFAULT 0,
                            noise_news INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(stock_code, date)
                        )
                    ''')
                    
                    # 데이터 삽입
                    for _, row in daily_df.iterrows():
                        cursor.execute('''
                            INSERT OR REPLACE INTO daily_sentiment_index
                            (stock_code, stock_name, date, sentiment_index, sentiment_score,
                             total_news, confidence, fundamental_news, business_news, 
                             technical_news, noise_news)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            row['stock_code'], row['stock_name'], row['date'],
                            row['sentiment_index'], row['sentiment_score'],
                            row['total_news'], row['confidence'],
                            row['fundamental_news'], row['business_news'],
                            row['technical_news'], row['noise_news']
                        ))
                    
                    conn.commit()
                    logger.info(f"✅ 일별 감정 지수 계산 완료: {len(daily_df):,}건")
                
                return daily_df
                
        except Exception as e:
            logger.error(f"❌ 일별 감정 지수 계산 실패: {e}")
            return pd.DataFrame()
    
    def get_buffett_sentiment_summary(self) -> Dict:
        """워런 버핏 스타일 감정 분석 결과 요약"""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                
                # 전체 뉴스 감정 분포
                sentiment_dist = pd.read_sql_query("""
                    SELECT 
                        sentiment_label,
                        news_category,
                        COUNT(*) as count,
                        AVG(sentiment_score) as avg_score,
                        AVG(long_term_relevance) as avg_relevance
                    FROM news_articles
                    WHERE sentiment_score IS NOT NULL
                    GROUP BY sentiment_label, news_category
                    ORDER BY count DESC
                """, conn)
                
                # 종목별 감정 점수 (펀더멘털 뉴스 위주)
                stock_sentiment = pd.read_sql_query("""
                    SELECT 
                        stock_code,
                        stock_name,
                        COUNT(*) as total_news,
                        COUNT(CASE WHEN news_category = 'fundamental' THEN 1 END) as fundamental_news,
                        AVG(sentiment_score) as avg_sentiment,
                        AVG(long_term_relevance) as avg_relevance,
                        AVG(CASE WHEN news_category = 'fundamental' THEN sentiment_score END) as fundamental_sentiment
                    FROM news_articles
                    WHERE sentiment_score IS NOT NULL
                    GROUP BY stock_code, stock_name
                    HAVING COUNT(*) >= 3
                    ORDER BY fundamental_sentiment DESC NULLS LAST, avg_sentiment DESC
                """, conn)
                
                # 최근 7일 감정 트렌드
                recent_trend = pd.read_sql_query("""
                    SELECT 
                        DATE(pub_date) as date,
                        COUNT(*) as total_news,
                        AVG(sentiment_score) as avg_sentiment,
                        COUNT(CASE WHEN news_category = 'fundamental' THEN 1 END) as fundamental_count
                    FROM news_articles
                    WHERE sentiment_score IS NOT NULL
                    AND DATE(pub_date) >= DATE('now', '-7 days')
                    GROUP BY DATE(pub_date)
                    ORDER BY date DESC
                """, conn)
                
                return {
                    'sentiment_distribution': sentiment_dist,
                    'stock_sentiment_ranking': stock_sentiment,
                    'recent_trend': recent_trend,
                    'analysis_timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ 감정 분석 요약 실패: {e}")
            return {}
    
    def get_investment_signals(self, top_n: int = 20) -> pd.DataFrame:
        """워런 버핏 스타일 투자 신호 생성"""
        
        logger.info(f"🎯 워런 버핏 투자 신호 생성 (상위 {top_n}개)")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                
                # 최근 7일간 펀더멘털 뉴스 기반 신호
                query = """
                    SELECT 
                        na.stock_code,
                        na.stock_name,
                        COUNT(*) as total_news,
                        COUNT(CASE WHEN na.news_category = 'fundamental' THEN 1 END) as fundamental_news,
                        AVG(na.sentiment_score) as avg_sentiment,
                        AVG(CASE WHEN na.news_category = 'fundamental' THEN na.sentiment_score END) as fundamental_sentiment,
                        AVG(na.long_term_relevance) as avg_relevance,
                        MAX(na.sentiment_score) as max_sentiment,
                        MIN(na.sentiment_score) as min_sentiment
                    FROM news_articles na
                    WHERE na.sentiment_score IS NOT NULL
                    AND DATE(na.pub_date) >= DATE('now', '-7 days')
                    GROUP BY na.stock_code, na.stock_name
                    HAVING fundamental_news >= 1  -- 펀더멘털 뉴스 최소 1개
                    ORDER BY fundamental_sentiment DESC NULLS LAST, avg_relevance DESC
                    LIMIT ?
                """
                
                signals_df = pd.read_sql_query(query, conn, params=(top_n * 2,))
                
                if signals_df.empty:
                    logger.warning("❌ 투자 신호 생성할 데이터가 없습니다")
                    return pd.DataFrame()
                
                # 신호 강도 계산
                signals_df['signal_strength'] = (
                    signals_df['fundamental_sentiment'].fillna(0) * 0.7 +
                    signals_df['avg_sentiment'] * 0.3
                ) * (signals_df['avg_relevance'] / 100)
                
                # 신호 타입 결정
                def get_signal_type(row):
                    fund_sent = row['fundamental_sentiment'] or 0
                    if fund_sent > 0.3:
                        return 'STRONG_BUY'
                    elif fund_sent > 0.1:
                        return 'BUY'
                    elif fund_sent < -0.3:
                        return 'STRONG_SELL'
                    elif fund_sent < -0.1:
                        return 'SELL'
                    else:
                        return 'HOLD'
                
                signals_df['signal_type'] = signals_df.apply(get_signal_type, axis=1)
                
                # 신뢰도 계산
                signals_df['confidence'] = np.minimum(
                    100,
                    signals_df['fundamental_news'] * 30 + 
                    signals_df['total_news'] * 5 +
                    signals_df['avg_relevance'] * 0.5
                )
                
                # 상위 N개 선택
                final_signals = signals_df.nlargest(top_n, 'signal_strength')
                
                logger.info(f"✅ 투자 신호 생성 완료: {len(final_signals)}개")
                
                return final_signals[['stock_code', 'stock_name', 'signal_type', 
                                    'signal_strength', 'confidence', 'fundamental_sentiment',
                                    'fundamental_news', 'total_news', 'avg_relevance']]
                
        except Exception as e:
            logger.error(f"❌ 투자 신호 생성 실패: {e}")
            return pd.DataFrame()


def main():
    """메인 실행 함수"""
    
    print("\n" + "="*80)
    print("🎯 워런 버핏 스타일 뉴스 감정 분석 엔진")
    print("="*80)
    print("📊 기본분석(45%) : 기술분석(30%) : 뉴스감정분석(25%)")
    print("🎯 가치투자 관점 감정 분석 및 투자 신호 생성")
    print()
    
    # 감정 분석기 초기화
    analyzer = BuffettSentimentAnalyzer()
    
    while True:
        print("\n🔍 워런 버핏 감정 분석 메뉴:")
        print("1. 뉴스 감정 분석 실행 (배치 처리)")
        print("2. 일별 감정 지수 계산")
        print("3. 감정 분석 결과 요약")
        print("4. 워런 버핏 투자 신호 생성")
        print("5. 특정 종목 감정 분석 조회")
        print("6. 테스트: 단일 뉴스 분석")
        print("0. 종료")
        
        choice = input("\n선택 (0-6): ").strip()
        
        if choice == '0':
            print("👋 워런 버핏 감정 분석을 종료합니다.")
            break
            
        elif choice == '1':
            # 뉴스 감정 분석 실행
            limit = input("분석할 뉴스 수 (전체: Enter): ").strip()
            limit = int(limit) if limit.isdigit() else None
            
            print(f"\n🔍 뉴스 감정 분석 시작...")
            results = analyzer.analyze_news_batch(limit=limit)
            
            if not results.empty:
                print(f"\n📊 분석 결과 요약:")
                print(f"   총 분석: {len(results):,}건")
                print(f"   감정 분포:")
                sentiment_counts = results['sentiment_label'].value_counts()
                for label, count in sentiment_counts.items():
                    print(f"     {label}: {count:,}건")
                
                category_counts = results['news_category'].value_counts()
                print(f"   카테고리 분포:")
                for category, count in category_counts.items():
                    print(f"     {category}: {count:,}건")
            
        elif choice == '2':
            # 일별 감정 지수 계산
            days = input("계산할 기간 (일, 기본값: 30): ").strip()
            days = int(days) if days.isdigit() else 30
            
            print(f"\n📈 최근 {days}일 감정 지수 계산...")
            daily_sentiment = analyzer.calculate_daily_sentiment_index(days=days)
            
            if not daily_sentiment.empty:
                print(f"\n📊 일별 감정 지수 요약:")
                print(f"   총 데이터: {len(daily_sentiment):,}건")
                print(f"   평균 감정 지수: {daily_sentiment['sentiment_index'].mean():.2f}")
                print(f"   가장 긍정적: {daily_sentiment['sentiment_index'].max():.2f}")
                print(f"   가장 부정적: {daily_sentiment['sentiment_index'].min():.2f}")
                
                print(f"\n📈 감정 지수 상위 5개:")
                top_sentiment = daily_sentiment.nlargest(5, 'sentiment_index')
                for _, row in top_sentiment.iterrows():
                    print(f"     {row['stock_name']} ({row['stock_code']}): {row['sentiment_index']:.1f} ({row['date']})")
        
        elif choice == '3':
            # 감정 분석 결과 요약
            print("\n📊 워런 버핏 감정 분석 결과 요약 생성 중...")
            summary = analyzer.get_buffett_sentiment_summary()
            
            if summary:
                # 감정 분포
                if not summary['sentiment_distribution'].empty:
                    print(f"\n🎯 감정 분포:")
                    sentiment_dist = summary['sentiment_distribution']
                    for _, row in sentiment_dist.head(10).iterrows():
                        print(f"   {row['sentiment_label']} ({row['news_category']}): {row['count']:,}건 (평균점수: {row['avg_score']:.3f})")
                
                # 종목별 순위
                if not summary['stock_sentiment_ranking'].empty:
                    print(f"\n🏆 펀더멘털 감정 점수 상위 10개:")
                    stock_ranking = summary['stock_sentiment_ranking']
                    for _, row in stock_ranking.head(10).iterrows():
                        fund_sent = row['fundamental_sentiment'] or 0
                        print(f"   {row['stock_name']} ({row['stock_code']}): {fund_sent:.3f} (펀더멘털 뉴스: {row['fundamental_news']}건)")
                
                # 최근 트렌드
                if not summary['recent_trend'].empty:
                    print(f"\n📈 최근 7일 감정 트렌드:")
                    for _, row in summary['recent_trend'].iterrows():
                        print(f"   {row['date']}: 평균감정 {row['avg_sentiment']:.3f}, 펀더멘털 뉴스 {row['fundamental_count']}건")
        
        elif choice == '4':
            # 투자 신호 생성
            top_n = input("생성할 신호 수 (기본값: 20): ").strip()
            top_n = int(top_n) if top_n.isdigit() else 20
            
            print(f"\n🎯 워런 버핏 투자 신호 생성 중 (상위 {top_n}개)...")
            signals = analyzer.get_investment_signals(top_n=top_n)
            
            if not signals.empty:
                print(f"\n🚀 워런 버핏 투자 신호:")
                print("-" * 100)
                for _, row in signals.iterrows():
                    signal_emoji = {
                        'STRONG_BUY': '🚀',
                        'BUY': '📈', 
                        'HOLD': '⏸️',
                        'SELL': '📉',
                        'STRONG_SELL': '🔻'
                    }.get(row['signal_type'], '❓')
                    
                    print(f"{signal_emoji} {row['stock_name']} ({row['stock_code']})")
                    print(f"   신호: {row['signal_type']}")
                    print(f"   신호강도: {row['signal_strength']:.3f}")
                    print(f"   신뢰도: {row['confidence']:.1f}%")
                    print(f"   펀더멘털 감정: {row['fundamental_sentiment']:.3f}")
                    print(f"   뉴스: 펀더멘털 {row['fundamental_news']}건 / 전체 {row['total_news']}건")
                    print()
            
        elif choice == '5':
            # 특정 종목 조회
            stock_code = input("종목코드 입력 (예: 005930): ").strip()
            
            if stock_code:
                try:
                    with sqlite3.connect(analyzer.db_path) as conn:
                        query = """
                            SELECT stock_name, title, sentiment_score, sentiment_label, 
                                   news_category, long_term_relevance, pub_date
                            FROM news_articles
                            WHERE stock_code = ? AND sentiment_score IS NOT NULL
                            ORDER BY pub_date DESC
                            LIMIT 10
                        """
                        
                        stock_news = pd.read_sql_query(query, conn, params=(stock_code,))
                        
                        if not stock_news.empty:
                            stock_name = stock_news.iloc[0]['stock_name']
                            print(f"\n📊 {stock_name} ({stock_code}) 최근 뉴스 감정 분석:")
                            print("-" * 80)
                            
                            for _, row in stock_news.iterrows():
                                print(f"📰 {row['title'][:50]}...")
                                print(f"   감정: {row['sentiment_label']} ({row['sentiment_score']:.3f})")
                                print(f"   카테고리: {row['news_category']}")
                                print(f"   장기 관련성: {row['long_term_relevance']}%")
                                print(f"   날짜: {row['pub_date']}")
                                print()
                        else:
                            print(f"❌ {stock_code} 종목의 감정 분석 데이터가 없습니다.")
                            
                except Exception as e:
                    print(f"❌ 조회 실패: {e}")
        
        elif choice == '6':
            # 테스트: 단일 뉴스 분석
            print("\n🧪 단일 뉴스 감정 분석 테스트")
            title = input("뉴스 제목: ").strip()
            content = input("뉴스 내용: ").strip()
            
            if title or content:
                result = analyzer.calculate_buffett_sentiment_score(title, content)
                
                print(f"\n📊 분석 결과:")
                print(f"   감정 점수: {result['sentiment_score']}")
                print(f"   감정 라벨: {result['sentiment_label']}")
                print(f"   뉴스 카테고리: {result['news_category']}")
                print(f"   카테고리 가중치: {result['category_weight']}")
                print(f"   장기 투자 관련성: {result['long_term_relevance']}%")
                print(f"   긍정 점수: {result['positive_score']}")
                print(f"   부정 점수: {result['negative_score']}")
        
        else:
            print("❌ 올바른 번호를 선택해주세요.")


if __name__ == "__main__":
    main()