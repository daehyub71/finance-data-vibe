"""
🚀 통합 워런 버핏 스코어카드 시스템 (기술분석 포함)

이 모듈은 워런 버핏의 투자 철학에 기술분석을 통합한 완전한 평가 시스템입니다.

평가 기준 (기본분석 45% : 기술분석 30% : 뉴스감정분석 25%):
📊 기본분석 (45점): ROE, 부채비율, 성장성, 안정성
📈 기술분석 (30점): RSI, MACD, 볼린저밴드, 이동평균
📰 감정분석 (25점): 뉴스 감정, 장기 투자 관련성

🎯 목표: 완전한 워런 버핏 + 기술분석 통합 투자 시스템
"""

import sys
from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR
    import matplotlib.font_manager as fm
    
    # 한글 폰트 설정
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False
except ImportError as e:
    print(f"❌ 패키지 설치 필요: {e}")
    exit(1)


class TechnicalIndicators:
    """
    📈 기술적 분석 지표 계산기
    
    워런 버핏 스타일 장기투자에 최적화된 기술적 지표들을 계산합니다.
    """
    
    @staticmethod
    def calculate_sma(prices, window):
        """단순이동평균 계산"""
        return prices.rolling(window=window).mean()
    
    @staticmethod
    def calculate_ema(prices, window):
        """지수이동평균 계산"""
        return prices.ewm(span=window).mean()
    
    @staticmethod
    def calculate_rsi(prices, window=14):
        """RSI (Relative Strength Index) 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(prices, fast=12, slow=26, signal=9):
        """MACD 계산"""
        exp1 = prices.ewm(span=fast).mean()
        exp2 = prices.ewm(span=slow).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal).mean()
        histogram = macd - signal_line
        
        return {
            'macd': macd,
            'signal': signal_line,
            'histogram': histogram
        }
    
    @staticmethod
    def calculate_bollinger_bands(prices, window=20, num_std=2):
        """볼린저 밴드 계산"""
        sma = prices.rolling(window=window).mean()
        std = prices.rolling(window=window).std()
        
        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)
        
        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band,
            'bb_position': (prices - lower_band) / (upper_band - lower_band)
        }
    
    @staticmethod
    def calculate_stochastic(high, low, close, k_period=14, d_period=3):
        """스토캐스틱 계산"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k_percent = ((close - lowest_low) / (highest_high - lowest_low)) * 100
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return {
            'k': k_percent,
            'd': d_percent
        }


class IntegratedBuffettScorecard:
    """
    🚀 통합 워런 버핏 스코어카드
    
    기본분석(45%) + 기술분석(30%) + 뉴스감정분석(25%)을 통합한 완전한 평가 시스템
    """
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.dart_db_path = self.data_dir / 'dart_data.db'
        self.stock_db_path = self.data_dir / 'stock_data.db'
        self.news_db_path = project_root / "finance_data.db"
        
        # 체크: 필요한 DB들이 존재하는지 확인
        self.validate_databases()
        
        # 점수 비중 (워런 버핏 철학 반영)
        self.score_weights = {
            'fundamental': 45,    # 기본분석 (가장 중요)
            'technical': 30,      # 기술분석 (타이밍)
            'sentiment': 25       # 뉴스감정분석 (보조)
        }
        
        # 워런 버핏 품질 기준
        self.quality_criteria = {
            # 기본분석 기준
            'excellent_roe': 20.0,
            'good_roe': 15.0,
            'min_roe': 10.0,
            'max_debt_ratio': 50.0,
            'excellent_debt_ratio': 30.0,
            'min_current_ratio': 150.0,
            'min_profit_years': 5,
            
            # 기술분석 기준 (장기투자 관점)
            'oversold_rsi': 30,      # RSI 과매도
            'overbought_rsi': 70,    # RSI 과매수
            'bullish_macd_threshold': 0.1,
            'bb_oversold': 0.2,      # 볼린저밴드 하단 근처
            'bb_overbought': 0.8,    # 볼린저밴드 상단 근처
            
            # 감정분석 기준
            'positive_sentiment': 0.3,
            'negative_sentiment': -0.3
        }
        
        print("🚀 통합 워런 버핏 스코어카드 시스템 초기화 완료")
    
    def validate_databases(self):
        """필요한 데이터베이스들이 존재하는지 확인"""
        if not self.dart_db_path.exists():
            print(f"❌ DART 데이터베이스가 없습니다: {self.dart_db_path}")
            print("먼저 DART 데이터 수집을 실행해주세요.")
            exit(1)
        
        if not self.stock_db_path.exists():
            print(f"❌ 주식 데이터베이스가 없습니다: {self.stock_db_path}")
            print("먼저 주식 데이터 수집을 실행해주세요.")
            exit(1)
        
        # 뉴스 DB는 선택사항 (없어도 기본+기술분석만으로 동작)
        if not self.news_db_path.exists():
            print(f"⚠️ 뉴스 데이터베이스가 없습니다: {self.news_db_path}")
            print("뉴스 감정분석 점수는 0점으로 처리됩니다.")
    
    def query_dart_db(self, query, params=None):
        """DART DB 쿼리 실행"""
        try:
            with sqlite3.connect(self.dart_db_path) as conn:
                if params:
                    return pd.read_sql_query(query, conn, params=params)
                else:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"❌ DART DB 쿼리 실패: {e}")
            return pd.DataFrame()
    
    def query_stock_db(self, query, params=None):
        """주식 DB 쿼리 실행"""
        try:
            with sqlite3.connect(self.stock_db_path) as conn:
                if params:
                    return pd.read_sql_query(query, conn, params=params)
                else:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"❌ 주식 DB 쿼리 실패: {e}")
            return pd.DataFrame()
    
    def query_news_db(self, query, params=None):
        """뉴스 DB 쿼리 실행"""
        try:
            if not self.news_db_path.exists():
                return pd.DataFrame()
            
            with sqlite3.connect(self.news_db_path) as conn:
                if params:
                    return pd.read_sql_query(query, conn, params=params)
                else:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            return pd.DataFrame()
    
    def calculate_fundamental_score(self, stock_code, year='2023'):
        """📊 기본분석 점수 계산 (45점 만점)"""
        try:
            # 재무데이터 조회
            query = """
                SELECT fs.account_nm, fs.thstrm_amount, fs.bsns_year, fs.fs_nm
                FROM financial_statements fs
                JOIN company_info ci ON fs.corp_code = ci.corp_code
                WHERE ci.stock_code = ? AND fs.bsns_year = ?
                ORDER BY fs.ord
            """
            
            financial_data = self.query_dart_db(query, (stock_code, year))
            
            if financial_data.empty:
                return {'score': 0, 'details': {}}
            
            # 계정과목 추출
            accounts = {}
            for _, row in financial_data.iterrows():
                try:
                    amount = float(str(row['thstrm_amount']).replace(',', ''))
                    accounts[row['account_nm']] = amount
                except:
                    continue
            
            # 연속 흑자 년수 계산
            consecutive_profits = self.count_consecutive_profit_years(stock_code)
            
            fundamental_score = 0
            details = {}
            
            # 1. 수익성 (20점) - 워런 버핏 최우선
            roe = 0
            if '당기순이익' in accounts and '자본총계' in accounts and accounts['자본총계'] != 0:
                roe = (accounts['당기순이익'] / accounts['자본총계']) * 100
                details['ROE'] = roe
                
                if roe >= self.quality_criteria['excellent_roe']:  # 20% 이상
                    fundamental_score += 20
                elif roe >= self.quality_criteria['good_roe']:     # 15% 이상
                    fundamental_score += 16
                elif roe >= self.quality_criteria['min_roe']:      # 10% 이상
                    fundamental_score += 10
            
            # 2. 안정성 (15점)
            debt_ratio = 999
            if '부채총계' in accounts and '자본총계' in accounts and accounts['자본총계'] != 0:
                debt_ratio = (accounts['부채총계'] / accounts['자본총계']) * 100
                details['부채비율'] = debt_ratio
                
                if debt_ratio <= self.quality_criteria['excellent_debt_ratio']:  # 30% 이하
                    fundamental_score += 10
                elif debt_ratio <= self.quality_criteria['max_debt_ratio']:      # 50% 이하
                    fundamental_score += 7
                elif debt_ratio <= 100:  # 100% 이하
                    fundamental_score += 3
            
            # 3. 수익성 지속성 (10점) - 연속 흑자
            details['연속흑자'] = consecutive_profits
            if consecutive_profits >= 10:  # 10년 이상
                fundamental_score += 10
            elif consecutive_profits >= self.quality_criteria['min_profit_years']:  # 5년 이상
                fundamental_score += 7
            elif consecutive_profits >= 3:  # 3년 이상
                fundamental_score += 4
            
            return {
                'score': min(fundamental_score, 45),  # 최대 45점
                'details': details
            }
            
        except Exception as e:
            print(f"⚠️ {stock_code} 기본분석 점수 계산 오류: {e}")
            return {'score': 0, 'details': {}}
    
    def calculate_technical_score(self, stock_code, days=252):
        """📈 기술분석 점수 계산 (30점 만점)"""
        try:
            # 최근 1년간 주가 데이터 조회
            query = """
                SELECT date, open, high, low, close, volume
                FROM stock_prices 
                WHERE symbol = ?
                AND date >= date('now', '-{} days')
                ORDER BY date
            """.format(days + 50)  # 기술지표 계산을 위해 여유분 추가
            
            price_data = self.query_stock_db(query, (stock_code,))
            
            if len(price_data) < 50:  # 최소 50일 데이터 필요
                return {'score': 0, 'details': {}}
            
            # 데이터 준비
            close_prices = pd.Series(price_data['close'].values, 
                                   index=pd.to_datetime(price_data['date']))
            high_prices = pd.Series(price_data['high'].values, 
                                  index=pd.to_datetime(price_data['date']))
            low_prices = pd.Series(price_data['low'].values, 
                                 index=pd.to_datetime(price_data['date']))
            
            # 기술지표 계산
            rsi = TechnicalIndicators.calculate_rsi(close_prices)
            macd_data = TechnicalIndicators.calculate_macd(close_prices)
            bb_data = TechnicalIndicators.calculate_bollinger_bands(close_prices)
            sma_20 = TechnicalIndicators.calculate_sma(close_prices, 20)
            sma_60 = TechnicalIndicators.calculate_sma(close_prices, 60)
            
            # 최신 값들 추출
            current_price = close_prices.iloc[-1]
            current_rsi = rsi.iloc[-1] if not rsi.empty else 50
            current_macd = macd_data['macd'].iloc[-1] if len(macd_data['macd']) > 0 else 0
            current_signal = macd_data['signal'].iloc[-1] if len(macd_data['signal']) > 0 else 0
            current_bb_pos = bb_data['bb_position'].iloc[-1] if not bb_data['bb_position'].empty else 0.5
            current_sma_20 = sma_20.iloc[-1] if not sma_20.empty else current_price
            current_sma_60 = sma_60.iloc[-1] if not sma_60.empty else current_price
            
            technical_score = 0
            details = {}
            
            # 1. RSI 분석 (8점) - 과매수/과매도 신호
            details['RSI'] = current_rsi
            if 30 <= current_rsi <= 70:  # 중립 구간 (좋음)
                technical_score += 8
            elif 20 <= current_rsi < 30:  # 과매도 (매수 기회)
                technical_score += 6
            elif 70 < current_rsi <= 80:  # 과매수 (주의)
                technical_score += 4
            elif current_rsi < 20:  # 극심한 과매도 (강한 매수 신호)
                technical_score += 10  # 보너스
            
            # 2. MACD 분석 (8점) - 추세 전환 신호
            details['MACD'] = current_macd
            details['MACD_Signal'] = current_signal
            macd_histogram = current_macd - current_signal
            
            if macd_histogram > 0 and current_macd > current_signal:  # 상승 추세
                technical_score += 8
            elif macd_histogram > 0:  # 상승 전환 조짐
                technical_score += 6
            elif abs(macd_histogram) < 0.1:  # 중립
                technical_score += 4
            
            # 3. 볼린저 밴드 분석 (7점) - 가격 위치
            details['BB_Position'] = current_bb_pos
            if 0.2 <= current_bb_pos <= 0.8:  # 정상 범위
                technical_score += 7
            elif current_bb_pos < 0.2:  # 하단 근처 (매수 기회)
                technical_score += 9  # 보너스
            elif current_bb_pos > 0.8:  # 상단 근처 (과매수)
                technical_score += 3
            
            # 4. 이동평균 분석 (7점) - 장기 추세
            details['Price_vs_SMA20'] = (current_price / current_sma_20 - 1) * 100
            details['Price_vs_SMA60'] = (current_price / current_sma_60 - 1) * 100
            
            ma_score = 0
            if current_price > current_sma_20 > current_sma_60:  # 완벽한 상승 배열
                ma_score = 7
            elif current_price > current_sma_20:  # 단기 상승
                ma_score = 5
            elif current_price > current_sma_60:  # 장기적으로는 상승
                ma_score = 4
            else:  # 하락 추세
                ma_score = 2
            
            technical_score += ma_score
            
            return {
                'score': min(technical_score, 30),  # 최대 30점
                'details': details
            }
            
        except Exception as e:
            print(f"⚠️ {stock_code} 기술분석 점수 계산 오류: {e}")
            return {'score': 0, 'details': {}}
    
    def calculate_sentiment_score(self, stock_code, days=30):
        """📰 뉴스 감정분석 점수 계산 (25점 만점)"""
        try:
            if not self.news_db_path.exists():
                return {'score': 0, 'details': {'error': '뉴스 DB 없음'}}
            
            # 최근 30일간 뉴스 감정 분석 조회
            query = """
                SELECT sentiment_score, sentiment_label, news_category, 
                       long_term_relevance, pub_date
                FROM news_articles
                WHERE stock_code = ? 
                AND sentiment_score IS NOT NULL
                AND DATE(pub_date) >= DATE('now', '-{} days')
                ORDER BY pub_date DESC
            """.format(days)
            
            news_data = self.query_news_db(query, (stock_code,))
            
            if news_data.empty:
                return {'score': 0, 'details': {'news_count': 0}}
            
            sentiment_score = 0
            details = {}
            
            # 뉴스 개수 및 품질 평가
            total_news = len(news_data)
            fundamental_news = len(news_data[news_data['news_category'] == 'fundamental'])
            
            details['total_news'] = total_news
            details['fundamental_news'] = fundamental_news
            
            # 1. 뉴스 양 점수 (5점)
            if total_news >= 10:
                sentiment_score += 5
            elif total_news >= 5:
                sentiment_score += 3
            elif total_news >= 1:
                sentiment_score += 1
            
            # 2. 펀더멘털 뉴스 비중 (5점)
            if fundamental_news >= 3:
                sentiment_score += 5
            elif fundamental_news >= 1:
                sentiment_score += 3
            
            # 3. 평균 감정 점수 (15점)
            avg_sentiment = news_data['sentiment_score'].mean()
            details['avg_sentiment'] = avg_sentiment
            
            if avg_sentiment >= self.quality_criteria['positive_sentiment']:  # 0.3 이상
                sentiment_score += 15
            elif avg_sentiment >= 0.1:  # 약간 긍정
                sentiment_score += 12
            elif avg_sentiment >= -0.1:  # 중립
                sentiment_score += 8
            elif avg_sentiment >= self.quality_criteria['negative_sentiment']:  # -0.3 이상
                sentiment_score += 5
            else:  # 매우 부정적
                sentiment_score += 2
            
            return {
                'score': min(sentiment_score, 25),  # 최대 25점
                'details': details
            }
            
        except Exception as e:
            return {'score': 0, 'details': {'error': str(e)}}
    
    def count_consecutive_profit_years(self, stock_code):
        """🏆 연속 흑자 년수 계산"""
        try:
            query = """
                SELECT fs.bsns_year, fs.thstrm_amount
                FROM financial_statements fs
                JOIN company_info ci ON fs.corp_code = ci.corp_code
                WHERE ci.stock_code = ? AND fs.account_nm = '당기순이익'
                ORDER BY fs.bsns_year DESC
                LIMIT 10
            """
            
            profit_data = self.query_dart_db(query, (stock_code,))
            
            if profit_data.empty:
                return 0
            
            consecutive_years = 0
            for _, row in profit_data.iterrows():
                try:
                    amount = float(str(row['thstrm_amount']).replace(',', ''))
                    if amount > 0:
                        consecutive_years += 1
                    else:
                        break
                except:
                    break
            
            return consecutive_years
            
        except Exception as e:
            return 0
    
    def calculate_integrated_score(self, stock_code):
        """🚀 통합 워런 버핏 점수 계산 (100점 만점)"""
        
        # 각 영역별 점수 계산
        fundamental_result = self.calculate_fundamental_score(stock_code)
        technical_result = self.calculate_technical_score(stock_code)
        sentiment_result = self.calculate_sentiment_score(stock_code)
        
        # 총점 계산
        total_score = (fundamental_result['score'] + 
                      technical_result['score'] + 
                      sentiment_result['score'])
        
        # 등급 부여
        if total_score >= 85:
            grade = 'A+'  # 워런 버핏 + 기술적으로 완벽
        elif total_score >= 75:
            grade = 'A'   # 매우 우수
        elif total_score >= 65:
            grade = 'B+'  # 양호
        elif total_score >= 55:
            grade = 'B'   # 보통
        elif total_score >= 45:
            grade = 'C+'  # 주의
        else:
            grade = 'C'   # 부적합
        
        # 투자 신호 생성
        investment_signal = self.generate_investment_signal(
            fundamental_result, technical_result, sentiment_result, total_score
        )
        
        return {
            'stock_code': stock_code,
            'total_score': total_score,
            'grade': grade,
            'investment_signal': investment_signal,
            'scores': {
                'fundamental': fundamental_result['score'],
                'technical': technical_result['score'],
                'sentiment': sentiment_result['score']
            },
            'details': {
                'fundamental': fundamental_result['details'],
                'technical': technical_result['details'],
                'sentiment': sentiment_result['details']
            }
        }
    
    def generate_investment_signal(self, fundamental, technical, sentiment, total_score):
        """🎯 투자 신호 생성"""
        fund_score = fundamental['score']
        tech_score = technical['score']
        sent_score = sentiment['score']
        
        # 워런 버핏 스타일: 기본분석이 우수하면 기술적 신호 가중
        if fund_score >= 35:  # 기본분석 우수 (45점 만점 중 35점)
            if tech_score >= 20:  # 기술적으로도 좋음
                if total_score >= 80:
                    return 'STRONG_BUY'
                else:
                    return 'BUY'
            elif tech_score >= 15:  # 기술적으로 보통
                return 'ACCUMULATE'  # 분할 매수
            else:
                return 'WATCH'  # 관찰
        
        elif fund_score >= 25:  # 기본분석 보통
            if tech_score >= 20:  # 기술적으로 좋음
                return 'BUY'
            else:
                return 'HOLD'
        
        else:  # 기본분석 부족
            if tech_score >= 25:  # 기술적으로만 좋음 (단기 기회)
                return 'TRADE'  # 단기 거래
            else:
                return 'AVOID'  # 회피
    
    def find_integrated_gems(self, min_score=70, limit=30):
        """💎 통합 분석 기반 우량주 발굴"""
        print(f"💎 통합 워런 버핏 시스템으로 우량주 발굴 중... (최소 {min_score}점)")
        
        # 모든 기업 조회
        companies = self.query_dart_db("""
            SELECT DISTINCT stock_code, corp_name
            FROM company_info
            WHERE stock_code IS NOT NULL AND stock_code != ''
            ORDER BY stock_code
        """)
        
        integrated_gems = []
        
        print(f"📊 총 {len(companies)}개 기업 통합 분석 중...")
        
        for idx, row in companies.iterrows():
            stock_code = row['stock_code']
            corp_name = row['corp_name']
            
            # 진행률 표시
            if (idx + 1) % 50 == 0:
                print(f"⏳ 진행률: {idx + 1}/{len(companies)} ({(idx + 1)/len(companies)*100:.1f}%)")
            
            try:
                result = self.calculate_integrated_score(stock_code)
                
                if result['total_score'] >= min_score:
                    gem = {
                        '순위': len(integrated_gems) + 1,
                        '종목코드': stock_code,
                        '기업명': corp_name,
                        '통합점수': result['total_score'],
                        '등급': result['grade'],
                        '투자신호': result['investment_signal'],
                        '기본분석': result['scores']['fundamental'],
                        '기술분석': result['scores']['technical'],
                        '감정분석': result['scores']['sentiment']
                    }
                    
                    # 상세 정보 추가
                    if 'ROE' in result['details']['fundamental']:
                        gem['ROE'] = round(result['details']['fundamental']['ROE'], 1)
                    if 'RSI' in result['details']['technical']:
                        gem['RSI'] = round(result['details']['technical']['RSI'], 1)
                    
                    integrated_gems.append(gem)
                    
                    # A+ 등급 발견시 알림
                    if result['grade'] == 'A+':
                        print(f"🚀 A+ 완벽 종목 발견! {corp_name}({stock_code}): {result['total_score']:.1f}점")
                
            except Exception as e:
                continue
        
        # 점수순 정렬
        if integrated_gems:
            gems_df = pd.DataFrame(integrated_gems)
            gems_df = gems_df.sort_values('통합점수', ascending=False).head(limit)
            gems_df['순위'] = range(1, len(gems_df) + 1)
            
            return gems_df
        else:
            return pd.DataFrame()
    
    def create_comprehensive_report(self, stock_code):
        """📋 종목별 완전한 통합 분석 리포트"""
        
        # 기업 정보 조회
        company_info = self.query_dart_db("""
            SELECT corp_name, ceo_nm, ind_tp
            FROM company_info
            WHERE stock_code = ?
        """, (stock_code,))
        
        if company_info.empty:
            print(f"❌ {stock_code} 기업 정보를 찾을 수 없습니다.")
            return
        
        corp_name = company_info.iloc[0]['corp_name']
        
        print("=" * 100)
        print(f"🚀 {corp_name} ({stock_code}) 통합 워런 버핏 분석 리포트")
        print("=" * 100)
        print("📊 분석 방법: 기본분석(45%) + 기술분석(30%) + 뉴스감정분석(25%)")
        print()
        
        # 통합 점수 계산
        result = self.calculate_integrated_score(stock_code)
        
        # 1. 종합 결과
        print(f"🎯 종합 평가:")
        print(f"   📊 통합 점수: {result['total_score']:.1f}/100점")
        print(f"   🏆 등급: {result['grade']}")
        print(f"   🎯 투자 신호: {result['investment_signal']}")
        print()
        
        # 신호별 투자 의견
        signal_opinions = {
            'STRONG_BUY': "🚀 적극 매수 - 기본+기술분석 모두 우수",
            'BUY': "✅ 매수 추천 - 좋은 투자 기회",
            'ACCUMULATE': "📈 분할 매수 - 장기적 관점에서 수집",
            'WATCH': "👀 관찰 대기 - 기술적 신호 개선 시 매수",
            'HOLD': "⏸️ 보유 유지 - 현 상황 지속 관찰",
            'TRADE': "⚡ 단기 거래 - 기술적 기회만 활용",
            'AVOID': "❌ 투자 회피 - 더 좋은 기회 발굴"
        }
        
        print(f"💡 투자 의견: {signal_opinions.get(result['investment_signal'], '분석 필요')}")
        print()
        
        # 2. 영역별 상세 점수
        scores = result['scores']
        print(f"📈 영역별 상세 점수:")
        print(f"   📊 기본분석: {scores['fundamental']}/45점 ({scores['fundamental']/45*100:.1f}%)")
        print(f"   📈 기술분석: {scores['technical']}/30점 ({scores['technical']/30*100:.1f}%)")
        print(f"   📰 감정분석: {scores['sentiment']}/25점 ({scores['sentiment']/25*100:.1f}%)")
        print()
        
        # 3. 기본분석 상세 내용
        fund_details = result['details']['fundamental']
        if fund_details:
            print(f"📊 기본분석 상세:")
            if 'ROE' in fund_details:
                print(f"   🏆 ROE: {fund_details['ROE']:.1f}%")
            if '부채비율' in fund_details:
                print(f"   🛡️ 부채비율: {fund_details['부채비율']:.1f}%")
            if '연속흑자' in fund_details:
                print(f"   📅 연속흑자: {fund_details['연속흑자']}년")
            print()
        
        # 4. 기술분석 상세 내용
        tech_details = result['details']['technical']
        if tech_details:
            print(f"📈 기술분석 상세:")
            if 'RSI' in tech_details:
                rsi = tech_details['RSI']
                rsi_comment = "과매도" if rsi < 30 else "과매수" if rsi > 70 else "중립"
                print(f"   📊 RSI: {rsi:.1f} ({rsi_comment})")
            
            if 'BB_Position' in tech_details:
                bb_pos = tech_details['BB_Position']
                bb_comment = "하단근처" if bb_pos < 0.3 else "상단근처" if bb_pos > 0.7 else "중간"
                print(f"   📏 볼린저밴드: {bb_pos:.2f} ({bb_comment})")
            
            if 'Price_vs_SMA20' in tech_details:
                sma_diff = tech_details['Price_vs_SMA20']
                sma_comment = "상승" if sma_diff > 0 else "하락"
                print(f"   📈 20일선 대비: {sma_diff:+.1f}% ({sma_comment})")
            print()
        
        # 5. 감정분석 상세 내용
        sent_details = result['details']['sentiment']
        if sent_details and 'error' not in sent_details:
            print(f"📰 뉴스 감정분석 상세:")
            if 'total_news' in sent_details:
                print(f"   📰 총 뉴스: {sent_details['total_news']}건")
            if 'fundamental_news' in sent_details:
                print(f"   📊 펀더멘털 뉴스: {sent_details['fundamental_news']}건")
            if 'avg_sentiment' in sent_details:
                avg_sent = sent_details['avg_sentiment']
                sent_comment = "긍정적" if avg_sent > 0.1 else "부정적" if avg_sent < -0.1 else "중립적"
                print(f"   😊 평균 감정: {avg_sent:.3f} ({sent_comment})")
            print()
        
        # 6. 투자 액션 플랜
        print(f"🎯 구체적 투자 액션 플랜:")
        
        signal = result['investment_signal']
        if signal == 'STRONG_BUY':
            print(f"   🚀 즉시 포트폴리오 비중 확대 검토")
            print(f"   💰 추천 비중: 5-8% (공격적 투자)")
            print(f"   📅 보유 기간: 장기 (5년+)")
        elif signal == 'BUY':
            print(f"   ✅ 적극적 매수 진행")
            print(f"   💰 추천 비중: 3-5%")
            print(f"   📈 추가 하락시 물타기 고려")
        elif signal == 'ACCUMULATE':
            print(f"   📈 분할 매수 전략 (3-4회)")
            print(f"   💰 초기 비중: 1-2%")
            print(f"   ⏰ 매수 주기: 2-4주 간격")
        elif signal == 'WATCH':
            print(f"   👀 워치리스트 등록")
            print(f"   📊 기술적 지표 개선 시 매수")
            print(f"   🎯 목표: RSI 30 이하 또는 BB 하단 접촉")
        else:
            print(f"   ⏳ 현재 매수 시점 아님")
            print(f"   🔍 더 좋은 기회 발굴 필요")
        
        print("=" * 100)
    
    def visualize_integrated_analysis(self, gems_df, top_n=15):
        """📊 통합 분석 결과 시각화"""
        if gems_df.empty:
            print("❌ 시각화할 데이터가 없습니다.")
            return
        
        top_stocks = gems_df.head(top_n)
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(f'🚀 통합 워런 버핏 시스템 TOP {top_n} 분석', fontsize=16, fontweight='bold')
        
        # 1. 통합 점수 분포
        ax1.barh(range(len(top_stocks)), top_stocks['통합점수'], 
                color='skyblue', alpha=0.7)
        ax1.set_yticks(range(len(top_stocks)))
        ax1.set_yticklabels(top_stocks['기업명'], fontsize=10)
        ax1.set_xlabel('통합 점수')
        ax1.set_title('종목별 통합 워런 버핏 점수')
        ax1.grid(axis='x', alpha=0.3)
        
        # 점수 텍스트 추가
        for i, score in enumerate(top_stocks['통합점수']):
            ax1.text(score + 1, i, f'{score:.1f}', 
                    va='center', fontweight='bold')
        
        # 2. 영역별 점수 분포
        categories = ['기본분석', '기술분석', '감정분석']
        avg_scores = [
            top_stocks['기본분석'].mean(),
            top_stocks['기술분석'].mean(),
            top_stocks['감정분석'].mean()
        ]
        max_scores = [45, 30, 25]
        
        x = range(len(categories))
        bars = ax2.bar(x, avg_scores, color=['#FF6B6B', '#4ECDC4', '#45B7D1'], alpha=0.7)
        ax2.set_xticks(x)
        ax2.set_xticklabels(categories)
        ax2.set_ylabel('평균 점수')
        ax2.set_title('영역별 평균 점수')
        ax2.grid(axis='y', alpha=0.3)
        
        # 만점 기준선
        for i, (score, max_score) in enumerate(zip(avg_scores, max_scores)):
            ax2.axhline(y=max_score, color='red', linestyle='--', alpha=0.3)
            ax2.text(i, score + 1, f'{score:.1f}', ha='center', va='bottom', fontweight='bold')
        
        # 3. 투자 신호 분포
        signal_counts = top_stocks['투자신호'].value_counts()
        colors = {'STRONG_BUY': '#FF6B6B', 'BUY': '#4ECDC4', 'ACCUMULATE': '#45B7D1', 
                 'WATCH': '#FFA07A', 'HOLD': '#96CEB4', 'TRADE': '#FECA57', 'AVOID': '#95A5A6'}
        pie_colors = [colors.get(signal, '#95A5A6') for signal in signal_counts.index]
        
        ax3.pie(signal_counts.values, labels=signal_counts.index, autopct='%1.1f%%',
                colors=pie_colors, startangle=90)
        ax3.set_title('투자 신호 분포')
        
        # 4. 등급 분포
        grade_counts = top_stocks['등급'].value_counts()
        grade_colors = {'A+': '#FF6B6B', 'A': '#4ECDC4', 'B+': '#45B7D1', 
                       'B': '#FFA07A', 'C+': '#96CEB4', 'C': '#FECA57'}
        pie_colors = [grade_colors.get(grade, '#95A5A6') for grade in grade_counts.index]
        
        ax4.pie(grade_counts.values, labels=grade_counts.index, autopct='%1.1f%%',
                colors=pie_colors, startangle=90)
        ax4.set_title('등급 분포')
        
        plt.tight_layout()
        plt.show()
        
        # 통계 요약
        print(f"\n📊 TOP {top_n} 통합 분석 요약:")
        print(f"   평균 통합점수: {top_stocks['통합점수'].mean():.1f}점")
        print(f"   평균 기본분석: {top_stocks['기본분석'].mean():.1f}/45점")
        print(f"   평균 기술분석: {top_stocks['기술분석'].mean():.1f}/30점")
        print(f"   평균 감정분석: {top_stocks['감정분석'].mean():.1f}/25점")
        
        if 'ROE' in top_stocks.columns:
            print(f"   평균 ROE: {top_stocks['ROE'].mean():.1f}%")
        if 'RSI' in top_stocks.columns:
            print(f"   평균 RSI: {top_stocks['RSI'].mean():.1f}")


def main():
    """메인 실행 함수"""
    
    print("🚀 통합 워런 버핏 스코어카드 시스템")
    print("=" * 80)
    print("📊 기본분석(45%) + 기술분석(30%) + 뉴스감정분석(25%)")
    print("🎯 완전한 워런 버핏 + 기술적 분석 통합 시스템")
    print("=" * 80)
    
    try:
        scorecard = IntegratedBuffettScorecard()
        
        while True:
            print("\n🎯 원하는 기능을 선택하세요:")
            print("1. 통합 분석 우량주 TOP 30 발굴")
            print("2. 특정 종목 완전 분석")
            print("3. A+ 등급 완벽 종목 찾기")
            print("4. 투자 신호별 종목 분류")
            print("5. 통합 분석 결과 시각화")
            print("6. 커스텀 조건 스크리닝")
            print("0. 종료")
            
            choice = input("\n선택하세요 (0-6): ").strip()
            
            if choice == '0':
                print("👋 통합 워런 버핏 시스템을 종료합니다.")
                break
            
            elif choice == '1':
                print("\n💎 통합 분석으로 우량주 발굴 중...")
                gems_df = scorecard.find_integrated_gems(min_score=70, limit=30)
                
                if not gems_df.empty:
                    print(f"\n🚀 발견된 통합 우량주: {len(gems_df)}개")
                    print("=" * 130)
                    display_columns = ['순위', '기업명', '종목코드', '통합점수', '등급', '투자신호', 
                                     '기본분석', '기술분석', '감정분석']
                    if 'ROE' in gems_df.columns:
                        display_columns.append('ROE')
                    if 'RSI' in gems_df.columns:
                        display_columns.append('RSI')
                    
                    print(gems_df[display_columns].to_string(index=False))
                    print("=" * 130)
                    
                    # 신호별 요약
                    signal_summary = gems_df['투자신호'].value_counts()
                    print(f"\n🎯 투자 신호 분포:")
                    for signal, count in signal_summary.items():
                        print(f"   {signal}: {count}개")
                else:
                    print("❌ 조건을 만족하는 종목을 찾지 못했습니다.")
            
            elif choice == '2':
                stock_code = input("\n분석할 종목코드를 입력하세요 (예: 005930): ").strip()
                if stock_code:
                    scorecard.create_comprehensive_report(stock_code)
                else:
                    print("❌ 올바른 종목코드를 입력해주세요.")
            
            elif choice == '3':
                print("\n🌟 A+ 등급 완벽 종목 발굴 중...")
                gems_df = scorecard.find_integrated_gems(min_score=85, limit=15)
                
                if not gems_df.empty:
                    print(f"\n🏆 A+ 등급 완벽 종목: {len(gems_df)}개")
                    print("🚀 기본분석, 기술분석, 감정분석 모두 우수한 종목들입니다!")
                    print("=" * 130)
                    print(gems_df[['순위', '기업명', '통합점수', '등급', '투자신호', 
                                  '기본분석', '기술분석', '감정분석']].to_string(index=False))
                    print("=" * 130)
                else:
                    print("❌ A+ 등급 종목을 찾지 못했습니다.")
                    print("💡 기준을 낮춰서 다시 시도해보세요.")
            
            elif choice == '4':
                print("\n🎯 투자 신호별 종목 분류 중...")
                gems_df = scorecard.find_integrated_gems(min_score=60, limit=50)
                
                if not gems_df.empty:
                    signals = gems_df['투자신호'].unique()
                    
                    for signal in ['STRONG_BUY', 'BUY', 'ACCUMULATE', 'WATCH']:
                        signal_stocks = gems_df[gems_df['투자신호'] == signal]
                        if not signal_stocks.empty:
                            print(f"\n{signal} 신호 종목 ({len(signal_stocks)}개):")
                            print("-" * 80)
                            for _, stock in signal_stocks.head(10).iterrows():
                                print(f"  {stock['기업명']} ({stock['종목코드']}): {stock['통합점수']:.1f}점")
                else:
                    print("❌ 분석 가능한 종목이 없습니다.")
            
            elif choice == '5':
                if 'gems_df' in locals() and not gems_df.empty:
                    print("\n📊 통합 분석 결과 시각화 중...")
                    scorecard.visualize_integrated_analysis(gems_df)
                else:
                    print("❌ 먼저 종목 발굴을 실행해주세요.")
            
            elif choice == '6':
                print("\n🔧 커스텀 스크리닝 조건:")
                try:
                    min_score = int(input("최소 통합 점수 (기본 70): ").strip() or "70")
                    min_fundamental = int(input("최소 기본분석 점수 (기본 30): ").strip() or "30")
                    min_technical = int(input("최소 기술분석 점수 (기본 15): ").strip() or "15")
                    limit = int(input("최대 결과 개수 (기본 20): ").strip() or "20")
                    
                    gems_df = scorecard.find_integrated_gems(min_score=min_score, limit=limit*2)
                    
                    if not gems_df.empty:
                        # 추가 필터링
                        filtered_df = gems_df[
                            (gems_df['기본분석'] >= min_fundamental) & 
                            (gems_df['기술분석'] >= min_technical)
                        ].head(limit)
                        
                        if not filtered_df.empty:
                            print(f"\n🎯 커스텀 조건 만족 종목: {len(filtered_df)}개")
                            print(filtered_df[['순위', '기업명', '통합점수', '등급', '투자신호', 
                                             '기본분석', '기술분석']].to_string(index=False))
                        else:
                            print("❌ 커스텀 조건을 만족하는 종목이 없습니다.")
                    else:
                        print("❌ 기본 조건을 만족하는 종목이 없습니다.")
                        
                except ValueError:
                    print("❌ 올바른 숫자를 입력해주세요.")
            
            else:
                print("❌ 올바른 번호를 선택해주세요.")
    
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("💡 필요한 데이터가 충분히 수집되었는지 확인해주세요.")


if __name__ == "__main__":
    main()