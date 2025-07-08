"""
src/analysis/technical/value_timing.py

워런 버핏 스타일 가치투자 타이밍 최적화 시스템
"시장은 단기적으로는 투표기계이지만, 장기적으로는 체중계이다" - 벤저민 그레이엄

🎯 핵심 목표:
- 가치주 매수 최적 타이밍 포착
- 시장 비효율성 활용
- 감정적 과반응 시점 식별
- 장기투자 관점 진입점 최적화
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR
    from src.analysis.technical.indicators import (
        LongTermTrendIndicators, ValueInvestingMomentum, VolatilityBasedEntry
    )
except ImportError:
    DATA_DIR = Path("data")


class TimingOpportunityType(Enum):
    """타이밍 기회 유형"""
    GOLDEN_OPPORTUNITY = "golden_opportunity"  # 황금 기회
    EXCELLENT_TIMING = "excellent_timing"      # 우수한 타이밍
    GOOD_TIMING = "good_timing"               # 좋은 타이밍
    AVERAGE_TIMING = "average_timing"         # 평균적 타이밍
    POOR_TIMING = "poor_timing"               # 나쁜 타이밍
    AVOID_TIMING = "avoid_timing"             # 피해야 할 타이밍


@dataclass
class ValueTimingAnalysis:
    """가치투자 타이밍 분석 결과"""
    stock_code: str
    opportunity_type: TimingOpportunityType
    timing_score: float  # 0-100
    value_discount: float  # 할인율 (%)
    risk_reward_ratio: float  # 위험 대비 수익 비율
    entry_urgency: str  # 진입 시급성
    accumulation_strategy: str  # 누적 매수 전략
    key_factors: List[str]
    market_inefficiency: Dict[str, float]
    optimal_entry_price: float
    safety_margin: float  # 안전마진 (%)
    expected_return: float  # 기대수익률 (%)
    investment_horizon: str  # 투자 기간
    confidence_level: float  # 신뢰도 (%)
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class MarketInefficiencyDetector:
    """시장 비효율성 탐지기"""
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.stock_db_path = self.data_dir / 'stock_data.db'
        self.dart_db_path = self.data_dir / 'dart_data.db'
        self.news_db_path = self.data_dir / 'news_data.db'
    
    def detect_sentiment_overreaction(self, stock_code: str) -> Dict[str, float]:
        """감정적 과반응 탐지"""
        try:
            # 최근 뉴스 감정과 주가 변동 비교
            price_data = self._get_recent_price_data(stock_code, 30)
            news_sentiment = self._get_recent_news_sentiment(stock_code, 30)
            
            if price_data.empty or not news_sentiment:
                return {'overreaction_score': 0, 'direction': 'neutral'}
            
            # 30일간 주가 변동률
            price_change = (price_data['close'].iloc[-1] / price_data['close'].iloc[0] - 1) * 100
            
            # 감정 점수와 주가 변동의 괴리
            expected_price_change = news_sentiment * 10  # 감정 점수 * 10%
            
            # 과반응 점수 계산
            deviation = abs(price_change - expected_price_change)
            overreaction_score = min(100, deviation * 2)
            
            # 과반응 방향
            if price_change < expected_price_change - 5:
                direction = 'oversold'  # 과매도
            elif price_change > expected_price_change + 5:
                direction = 'overbought'  # 과매수
            else:
                direction = 'neutral'
            
            return {
                'overreaction_score': overreaction_score,
                'direction': direction,
                'price_change': price_change,
                'expected_change': expected_price_change,
                'sentiment_score': news_sentiment
            }
            
        except Exception as e:
            return {'overreaction_score': 0, 'direction': 'neutral'}
    
    def detect_fundamental_price_gap(self, stock_code: str) -> Dict[str, float]:
        """펀더멘털과 주가 간 괴리 탐지"""
        try:
            # 현재 주가
            current_price = self._get_current_price(stock_code)
            if not current_price:
                return {'gap_score': 0, 'direction': 'neutral'}
            
            # 내재가치 추정
            intrinsic_value = self._estimate_intrinsic_value(stock_code)
            if not intrinsic_value:
                return {'gap_score': 0, 'direction': 'neutral'}
            
            # 괴리율 계산
            gap_ratio = (current_price / intrinsic_value - 1) * 100
            gap_score = min(100, abs(gap_ratio))
            
            # 방향성
            if gap_ratio < -20:
                direction = 'undervalued'  # 저평가
            elif gap_ratio > 20:
                direction = 'overvalued'  # 고평가
            else:
                direction = 'fairvalued'  # 적정평가
            
            return {
                'gap_score': gap_score,
                'direction': direction,
                'current_price': current_price,
                'intrinsic_value': intrinsic_value,
                'gap_ratio': gap_ratio
            }
            
        except Exception as e:
            return {'gap_score': 0, 'direction': 'neutral'}
    
    def detect_technical_fundamental_divergence(self, stock_code: str) -> Dict[str, float]:
        """기술적 지표와 펀더멘털 간 다이버전스 탐지"""
        try:
            # 기술적 신호 강도
            technical_signal = self._get_technical_signal_strength(stock_code)
            
            # 펀더멘털 신호 강도
            fundamental_signal = self._get_fundamental_signal_strength(stock_code)
            
            # 다이버전스 점수
            divergence = abs(technical_signal - fundamental_signal)
            divergence_score = min(100, divergence * 50)
            
            # 기회 방향
            if fundamental_signal > technical_signal + 0.5:
                opportunity = 'technical_lag'  # 기술적 지표가 뒤처짐
            elif technical_signal > fundamental_signal + 0.5:
                opportunity = 'fundamental_lag'  # 펀더멘털이 뒤처짐
            else:
                opportunity = 'aligned'  # 일치
            
            return {
                'divergence_score': divergence_score,
                'opportunity': opportunity,
                'technical_signal': technical_signal,
                'fundamental_signal': fundamental_signal
            }
            
        except Exception as e:
            return {'divergence_score': 0, 'opportunity': 'aligned'}
    
    def _get_recent_price_data(self, stock_code: str, days: int) -> pd.DataFrame:
        """최근 주가 데이터 조회"""
        try:
            with sqlite3.connect(self.stock_db_path) as conn:
                query = """
                    SELECT date, close, volume
                    FROM stock_prices
                    WHERE symbol = ?
                    ORDER BY date DESC
                    LIMIT ?
                """
                df = pd.read_sql_query(query, conn, params=(stock_code, days))
                return df.sort_values('date') if not df.empty else pd.DataFrame()
        except:
            return pd.DataFrame()
    
    def _get_recent_news_sentiment(self, stock_code: str, days: int) -> float:
        """최근 뉴스 감정 점수 조회"""
        try:
            if not self.news_db_path.exists():
                return 0.0
            
            with sqlite3.connect(self.news_db_path) as conn:
                query = """
                    SELECT AVG(sentiment_score) as avg_sentiment
                    FROM news_articles
                    WHERE stock_code = ?
                    AND DATE(collected_at) >= DATE('now', '-{} days')
                """.format(days)
                result = pd.read_sql_query(query, conn, params=(stock_code,))
                
                if not result.empty and result.iloc[0]['avg_sentiment'] is not None:
                    return result.iloc[0]['avg_sentiment']
                return 0.0
        except:
            return 0.0
    
    def _get_current_price(self, stock_code: str) -> Optional[float]:
        """현재 주가 조회"""
        try:
            price_data = self._get_recent_price_data(stock_code, 1)
            return price_data['close'].iloc[-1] if not price_data.empty else None
        except:
            return None
    
    def _estimate_intrinsic_value(self, stock_code: str) -> Optional[float]:
        """간단한 내재가치 추정"""
        try:
            with sqlite3.connect(self.dart_db_path) as conn:
                query = """
                    SELECT fs.account_nm, fs.thstrm_amount
                    FROM financial_statements fs
                    JOIN company_info ci ON fs.corp_code = ci.corp_code
                    WHERE ci.stock_code = ? AND fs.bsns_year = '2023'
                    AND fs.account_nm IN ('당기순이익', '자본총계', '매출액')
                """
                result = pd.read_sql_query(query, conn, params=(stock_code,))
                
                if result.empty:
                    return None
                
                accounts = {}
                for _, row in result.iterrows():
                    try:
                        amount = float(str(row['thstrm_amount']).replace(',', ''))
                        accounts[row['account_nm']] = amount
                    except:
                        continue
                
                # 간단한 PER 기반 내재가치 (적정 PER 15배 가정)
                if '당기순이익' in accounts and accounts['당기순이익'] > 0:
                    # 발행주식수는 임시로 100만주로 가정 (실제로는 정확한 데이터 필요)
                    shares_outstanding = 1000000
                    eps = accounts['당기순이익'] / shares_outstanding
                    fair_per = 15  # 적정 PER
                    return eps * fair_per
                
                return None
                
        except Exception as e:
            return None
    
    def _get_technical_signal_strength(self, stock_code: str) -> float:
        """기술적 신호 강도 (-1 ~ 1)"""
        try:
            price_data = self._get_recent_price_data(stock_code, 50)
            if price_data.empty:
                return 0.0
            
            # RSI 기반 신호
            delta = price_data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            # RSI를 -1 ~ 1 신호로 변환
            if current_rsi <= 30:
                return 1.0  # 강한 매수
            elif current_rsi <= 40:
                return 0.5  # 약한 매수
            elif current_rsi >= 70:
                return -1.0  # 강한 매도
            elif current_rsi >= 60:
                return -0.5  # 약한 매도
            else:
                return 0.0  # 중립
                
        except Exception as e:
            return 0.0
    
    def _get_fundamental_signal_strength(self, stock_code: str) -> float:
        """펀더멘털 신호 강도 (-1 ~ 1)"""
        try:
            with sqlite3.connect(self.dart_db_path) as conn:
                query = """
                    SELECT fs.account_nm, fs.thstrm_amount
                    FROM financial_statements fs
                    JOIN company_info ci ON fs.corp_code = ci.corp_code
                    WHERE ci.stock_code = ? AND fs.bsns_year = '2023'
                    AND fs.account_nm IN ('당기순이익', '자본총계', '부채총계')
                """
                result = pd.read_sql_query(query, conn, params=(stock_code,))
                
                if result.empty:
                    return 0.0
                
                accounts = {}
                for _, row in result.iterrows():
                    try:
                        amount = float(str(row['thstrm_amount']).replace(',', ''))
                        accounts[row['account_nm']] = amount
                    except:
                        continue
                
                signal = 0.0
                
                # ROE 평가
                if '당기순이익' in accounts and '자본총계' in accounts and accounts['자본총계'] > 0:
                    roe = accounts['당기순이익'] / accounts['자본총계'] * 100
                    if roe >= 20:
                        signal += 0.5
                    elif roe >= 15:
                        signal += 0.3
                    elif roe >= 10:
                        signal += 0.1
                    elif roe < 0:
                        signal -= 0.5
                
                # 부채비율 평가
                if '부채총계' in accounts and '자본총계' in accounts and accounts['자본총계'] > 0:
                    debt_ratio = accounts['부채총계'] / accounts['자본총계'] * 100
                    if debt_ratio <= 30:
                        signal += 0.3
                    elif debt_ratio <= 50:
                        signal += 0.1
                    elif debt_ratio > 100:
                        signal -= 0.3
                
                return max(-1.0, min(1.0, signal))
                
        except Exception as e:
            return 0.0


class ValueTimingOptimizer:
    """가치투자 타이밍 최적화기"""
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.inefficiency_detector = MarketInefficiencyDetector()
        
        # 지표 계산기
        self.trend_indicators = LongTermTrendIndicators()
        self.momentum_indicators = ValueInvestingMomentum()
        self.volatility_indicators = VolatilityBasedEntry()
    
    def analyze_value_timing(self, stock_code: str) -> ValueTimingAnalysis:
        """종합 가치투자 타이밍 분석"""
        try:
            # 1. 시장 비효율성 분석
            sentiment_analysis = self.inefficiency_detector.detect_sentiment_overreaction(stock_code)
            fundamental_gap = self.inefficiency_detector.detect_fundamental_price_gap(stock_code)
            divergence_analysis = self.inefficiency_detector.detect_technical_fundamental_divergence(stock_code)
            
            # 2. 기술적 분석
            technical_analysis = self._analyze_technical_timing(stock_code)
            
            # 3. 펀더멘털 분석
            fundamental_analysis = self._analyze_fundamental_timing(stock_code)
            
            # 4. 종합 타이밍 점수 계산
            timing_score = self._calculate_timing_score(
                sentiment_analysis, fundamental_gap, divergence_analysis,
                technical_analysis, fundamental_analysis
            )
            
            # 5. 타이밍 기회 분류
            opportunity_type = self._classify_opportunity(timing_score, fundamental_gap)
            
            # 6. 투자 전략 수립
            strategy = self._develop_investment_strategy(
                stock_code, timing_score, sentiment_analysis, fundamental_gap
            )
            
            return ValueTimingAnalysis(
                stock_code=stock_code,
                opportunity_type=opportunity_type,
                timing_score=timing_score,
                value_discount=fundamental_gap.get('gap_ratio', 0),
                risk_reward_ratio=strategy['risk_reward_ratio'],
                entry_urgency=strategy['entry_urgency'],
                accumulation_strategy=strategy['accumulation_strategy'],
                key_factors=strategy['key_factors'],
                market_inefficiency={
                    'sentiment_overreaction': sentiment_analysis.get('overreaction_score', 0),
                    'fundamental_gap': fundamental_gap.get('gap_score', 0),
                    'technical_divergence': divergence_analysis.get('divergence_score', 0)
                },
                optimal_entry_price=strategy['optimal_entry_price'],
                safety_margin=strategy['safety_margin'],
                expected_return=strategy['expected_return'],
                investment_horizon=strategy['investment_horizon'],
                confidence_level=strategy['confidence_level']
            )
            
        except Exception as e:
            print(f"❌ 타이밍 분석 실패 ({stock_code}): {e}")
            return self._create_default_analysis(stock_code)
    
    def _analyze_technical_timing(self, stock_code: str) -> Dict:
        """기술적 타이밍 분석"""
        try:
            price_data = self._get_price_data(stock_code)
            if price_data.empty:
                return {'score': 50, 'signals': []}
            
            signals = []
            score = 50
            
            # 200일 이동평균 분석
            ma_data = self.trend_indicators.moving_average_200(price_data['close'])
            if ma_data:
                if ma_data['price_vs_ma_pct'] < -15:
                    score += 20
                    signals.append("200일선 대비 큰 하락 (매수 기회)")
                elif ma_data['price_vs_ma_pct'] < -5:
                    score += 10
                    signals.append("200일선 하회")
            
            # RSI 분석
            rsi_data = self.momentum_indicators.rsi_monthly(price_data['close'])
            if rsi_data:
                if rsi_data['rsi'] <= 30:
                    score += 20
                    signals.append(f"RSI 과매도 ({rsi_data['rsi']:.1f})")
                elif rsi_data['rsi'] <= 40:
                    score += 10
                    signals.append(f"RSI 낮음 ({rsi_data['rsi']:.1f})")
            
            # 볼린저 밴드 분석
            bb_data = self.volatility_indicators.bollinger_bands_value(price_data['close'])
            if bb_data:
                if bb_data['lower_touch']:
                    score += 15
                    signals.append("볼린저밴드 하단 터치")
                elif bb_data['band_position_pct'] < 25:
                    score += 10
                    signals.append("볼린저밴드 하위 구간")
            
            return {
                'score': min(100, max(0, score)),
                'signals': signals
            }
            
        except Exception as e:
            return {'score': 50, 'signals': []}
    
    def _analyze_fundamental_timing(self, stock_code: str) -> Dict:
        """펀더멘털 타이밍 분석"""
        try:
            # ROE, 부채비율 등 기본 지표 확인
            with sqlite3.connect(self.data_dir / 'dart_data.db') as conn:
                query = """
                    SELECT fs.account_nm, fs.thstrm_amount
                    FROM financial_statements fs
                    JOIN company_info ci ON fs.corp_code = ci.corp_code
                    WHERE ci.stock_code = ? AND fs.bsns_year = '2023'
                    AND fs.account_nm IN ('당기순이익', '자본총계', '부채총계', '매출액')
                """
                result = pd.read_sql_query(query, conn, params=(stock_code,))
                
                if result.empty:
                    return {'score': 50, 'factors': []}
                
                accounts = {}
                for _, row in result.iterrows():
                    try:
                        amount = float(str(row['thstrm_amount']).replace(',', ''))
                        accounts[row['account_nm']] = amount
                    except:
                        continue
                
                score = 50
                factors = []
                
                # ROE 평가
                if '당기순이익' in accounts and '자본총계' in accounts and accounts['자본총계'] > 0:
                    roe = accounts['당기순이익'] / accounts['자본총계'] * 100
                    if roe >= 20:
                        score += 25
                        factors.append(f"우수한 ROE ({roe:.1f}%)")
                    elif roe >= 15:
                        score += 20
                        factors.append(f"양호한 ROE ({roe:.1f}%)")
                    elif roe >= 10:
                        score += 10
                        factors.append(f"보통 ROE ({roe:.1f}%)")
                    elif roe < 0:
                        score -= 20
                        factors.append(f"적자 ROE ({roe:.1f}%)")
                
                # 부채비율 평가
                if '부채총계' in accounts and '자본총계' in accounts and accounts['자본총계'] > 0:
                    debt_ratio = accounts['부채총계'] / accounts['자본총계'] * 100
                    if debt_ratio <= 30:
                        score += 20
                        factors.append(f"낮은 부채비율 ({debt_ratio:.1f}%)")
                    elif debt_ratio <= 50:
                        score += 10
                        factors.append(f"적정 부채비율 ({debt_ratio:.1f}%)")
                    elif debt_ratio > 100:
                        score -= 15
                        factors.append(f"높은 부채비율 ({debt_ratio:.1f}%)")
                
                return {
                    'score': min(100, max(0, score)),
                    'factors': factors
                }
                
        except Exception as e:
            return {'score': 50, 'factors': []}
    
    def _calculate_timing_score(self, sentiment_analysis: Dict, fundamental_gap: Dict,
                              divergence_analysis: Dict, technical_analysis: Dict,
                              fundamental_analysis: Dict) -> float:
        """종합 타이밍 점수 계산"""
        
        # 기본 점수
        base_score = 50
        
        # 감정적 과반응 보너스
        if sentiment_analysis.get('direction') == 'oversold':
            base_score += sentiment_analysis.get('overreaction_score', 0) * 0.3
        
        # 펀더멘털 갭 보너스
        if fundamental_gap.get('direction') == 'undervalued':
            base_score += fundamental_gap.get('gap_score', 0) * 0.4
        
        # 다이버전스 보너스
        if divergence_analysis.get('opportunity') == 'technical_lag':
            base_score += divergence_analysis.get('divergence_score', 0) * 0.2
        
        # 기술적 분석 반영
        technical_score = technical_analysis.get('score', 50)
        base_score += (technical_score - 50) * 0.3
        
        # 펀더멘털 분석 반영
        fundamental_score = fundamental_analysis.get('score', 50)
        base_score += (fundamental_score - 50) * 0.5
        
        return min(100, max(0, base_score))
    
    def _classify_opportunity(self, timing_score: float, fundamental_gap: Dict) -> TimingOpportunityType:
        """타이밍 기회 분류"""
        
        # 펀더멘털 할인율 확인
        gap_ratio = fundamental_gap.get('gap_ratio', 0)
        is_undervalued = fundamental_gap.get('direction') == 'undervalued'
        
        if timing_score >= 90 and is_undervalued and gap_ratio < -30:
            return TimingOpportunityType.GOLDEN_OPPORTUNITY
        elif timing_score >= 80 and is_undervalued:
            return TimingOpportunityType.EXCELLENT_TIMING
        elif timing_score >= 70:
            return TimingOpportunityType.GOOD_TIMING
        elif timing_score >= 50:
            return TimingOpportunityType.AVERAGE_TIMING
        elif timing_score >= 30:
            return TimingOpportunityType.POOR_TIMING
        else:
            return TimingOpportunityType.AVOID_TIMING
    
    def _develop_investment_strategy(self, stock_code: str, timing_score: float,
                                   sentiment_analysis: Dict, fundamental_gap: Dict) -> Dict:
        """투자 전략 수립"""
        
        current_price = self._get_current_price(stock_code)
        if not current_price:
            current_price = 50000  # 기본값
        
        # 리스크 수익 비율 계산
        potential_upside = max(10, abs(fundamental_gap.get('gap_ratio', 10)))
        downside_risk = max(5, 15 - (timing_score - 50) / 10)
        risk_reward_ratio = potential_upside / downside_risk
        
        # 진입 시급성
        if timing_score >= 85:
            entry_urgency = "매우 높음 - 즉시 매수"
        elif timing_score >= 75:
            entry_urgency = "높음 - 빠른 매수"
        elif timing_score >= 65:
            entry_urgency = "보통 - 분할 매수"
        elif timing_score >= 50:
            entry_urgency = "낮음 - 관망"
        else:
            entry_urgency = "없음 - 피하기"
        
        # 누적 매수 전략
        if timing_score >= 80:
            accumulation_strategy = "적극적 누적 매수 (주 1회)"
        elif timing_score >= 70:
            accumulation_strategy = "점진적 누적 매수 (2주 1회)"
        elif timing_score >= 60:
            accumulation_strategy = "신중한 누적 매수 (월 1회)"
        else:
            accumulation_strategy = "누적 매수 보류"
        
        # 핵심 요인
        key_factors = []
        if sentiment_analysis.get('direction') == 'oversold':
            key_factors.append("시장 감정 과매도")
        if fundamental_gap.get('direction') == 'undervalued':
            key_factors.append(f"내재가치 대비 {abs(fundamental_gap.get('gap_ratio', 0)):.0f}% 할인")
        if timing_score >= 75:
            key_factors.append("기술적 지표 매수 신호")
        
        # 최적 진입가
        optimal_entry_price = current_price * (1 - max(0.05, min(0.15, (100 - timing_score) / 500)))
        
        # 안전마진
        safety_margin = min(50, max(20, 60 - timing_score / 2))
        
        # 기대수익률
        expected_return = min(100, max(5, potential_upside * 0.7))
        
        # 투자 기간
        if timing_score >= 80:
            investment_horizon = "3-5년 (장기)"
        elif timing_score >= 60:
            investment_horizon = "1-3년 (중기)"
        else:
            investment_horizon = "6개월-1년 (단기)"
        
        # 신뢰도
        confidence_level = min(95, max(30, timing_score * 0.9))
        
        return {
            'risk_reward_ratio': risk_reward_ratio,
            'entry_urgency': entry_urgency,
            'accumulation_strategy': accumulation_strategy,
            'key_factors': key_factors,
            'optimal_entry_price': optimal_entry_price,
            'safety_margin': safety_margin,
            'expected_return': expected_return,
            'investment_horizon': investment_horizon,
            'confidence_level': confidence_level
        }
    
    def _get_price_data(self, stock_code: str) -> pd.DataFrame:
        """주가 데이터 조회"""
        try:
            with sqlite3.connect(self.data_dir / 'stock_data.db') as conn:
                query = """
                    SELECT date, open, high, low, close, volume
                    FROM stock_prices
                    WHERE symbol = ?
                    ORDER BY date DESC
                    LIMIT 252
                """
                df = pd.read_sql_query(query, conn, params=(stock_code,))
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    return df.sort_values('date')
                return pd.DataFrame()
        except:
            return pd.DataFrame()
    
    def _get_current_price(self, stock_code: str) -> Optional[float]:
        """현재 주가 조회"""
        try:
            price_data = self._get_price_data(stock_code)
            return price_data['close'].iloc[-1] if not price_data.empty else None
        except:
            return None
    
    def _create_default_analysis(self, stock_code: str) -> ValueTimingAnalysis:
        """기본 분석 결과 생성"""
        return ValueTimingAnalysis(
            stock_code=stock_code,
            opportunity_type=TimingOpportunityType.AVERAGE_TIMING,
            timing_score=50.0,
            value_discount=0.0,
            risk_reward_ratio=1.0,
            entry_urgency="데이터 부족",
            accumulation_strategy="분석 불가",
            key_factors=["데이터 부족으로 분석 제한"],
            market_inefficiency={'sentiment_overreaction': 0, 'fundamental_gap': 0, 'technical_divergence': 0},
            optimal_entry_price=0.0,
            safety_margin=30.0,
            expected_return=10.0,
            investment_horizon="중기 (1-3년)",
            confidence_level=30.0
        )


class ValueTimingScanner:
    """가치투자 타이밍 스캐너"""
    
    def __init__(self):
        self.optimizer = ValueTimingOptimizer()
        self.data_dir = Path(DATA_DIR)
    
    def scan_market_opportunities(self, stock_codes: List[str] = None) -> List[ValueTimingAnalysis]:
        """시장 전체 타이밍 기회 스캔"""
        
        if stock_codes is None:
            # 기본 대형주 리스트
            stock_codes = [
                '005930', '000660', '035420', '005380', '006400',
                '051910', '035720', '207940', '068270', '096770',
                '003550', '034730', '012330', '066570', '323410'
            ]
        
        print(f"🔍 {len(stock_codes)}개 종목 타이밍 분석 중...")
        
        analyses = []
        for stock_code in stock_codes:
            try:
                analysis = self.optimizer.analyze_value_timing(stock_code)
                analyses.append(analysis)
            except Exception as e:
                print(f"❌ {stock_code} 분석 실패: {e}")
        
        # 타이밍 점수순으로 정렬
        analyses.sort(key=lambda x: x.timing_score, reverse=True)
        
        return analyses
    
    def find_golden_opportunities(self, min_timing_score: float = 80) -> List[ValueTimingAnalysis]:
        """황금 투자 기회 발굴"""
        
        print("🔍 황금 투자 기회 스캔 중...")
        
        # 대형주 + 중형주 스캔
        large_cap_stocks = [
            '005930', '000660', '035420', '005380', '006400',
            '051910', '035720', '207940', '068270', '096770'
        ]
        
        mid_cap_stocks = [
            '018260', '036570', '251270', '028300', '042700',
            '047810', '090430', '086280', '064350', '011070'
        ]
        
        all_stocks = large_cap_stocks + mid_cap_stocks
        analyses = self.scan_market_opportunities(all_stocks)
        
        # 고득점 종목만 필터링
        golden_opportunities = [
            analysis for analysis in analyses 
            if analysis.timing_score >= min_timing_score
        ]
        
        return golden_opportunities
    
    def generate_weekly_timing_report(self) -> Dict:
        """주간 타이밍 리포트 생성"""
        
        print("📊 주간 타이밍 리포트 생성 중...")
        
        # 전체 시장 스캔
        analyses = self.find_golden_opportunities(min_timing_score=70)
        
        # 기회 유형별 분류
        opportunities_by_type = {}
        for analysis in analyses:
            opp_type = analysis.opportunity_type.value
            if opp_type not in opportunities_by_type:
                opportunities_by_type[opp_type] = []
            opportunities_by_type[opp_type].append(analysis)
        
        # 섹터별 분석 (간단히 임의 분류)
        sector_analysis = self._analyze_by_sector(analyses)
        
        # 시장 비효율성 요약
        market_inefficiency_summary = self._summarize_market_inefficiency(analyses)
        
        return {
            'total_analyzed': len(analyses),
            'opportunities_by_type': opportunities_by_type,
            'sector_analysis': sector_analysis,
            'market_inefficiency': market_inefficiency_summary,
            'top_picks': analyses[:5] if analyses else [],
            'generated_at': datetime.now()
        }
    
    def _analyze_by_sector(self, analyses: List[ValueTimingAnalysis]) -> Dict:
        """섹터별 분석 (임시 구현)"""
        # 실제로는 종목-섹터 매핑 테이블이 필요
        sector_mapping = {
            '005930': 'IT', '000660': 'IT', '035420': 'IT',
            '005380': '자동차', '006400': '화학', '051910': '화학',
            '035720': 'IT', '207940': '바이오', '068270': '바이오',
            '096770': '화학'
        }
        
        sector_scores = {}
        for analysis in analyses:
            sector = sector_mapping.get(analysis.stock_code, '기타')
            if sector not in sector_scores:
                sector_scores[sector] = []
            sector_scores[sector].append(analysis.timing_score)
        
        # 섹터별 평균 점수
        sector_summary = {}
        for sector, scores in sector_scores.items():
            sector_summary[sector] = {
                'avg_score': np.mean(scores),
                'count': len(scores),
                'best_score': max(scores),
                'recommendation': '적극투자' if np.mean(scores) >= 80 else '선별투자' if np.mean(scores) >= 65 else '관망'
            }
        
        return sector_summary
    
    def _summarize_market_inefficiency(self, analyses: List[ValueTimingAnalysis]) -> Dict:
        """시장 비효율성 요약"""
        if not analyses:
            return {}
        
        # 감정적 과반응 평균
        sentiment_scores = [a.market_inefficiency['sentiment_overreaction'] for a in analyses]
        avg_sentiment_overreaction = np.mean(sentiment_scores)
        
        # 펀더멘털 갭 평균
        fundamental_scores = [a.market_inefficiency['fundamental_gap'] for a in analyses]
        avg_fundamental_gap = np.mean(fundamental_scores)
        
        # 기술적 다이버전스 평균
        technical_scores = [a.market_inefficiency['technical_divergence'] for a in analyses]
        avg_technical_divergence = np.mean(technical_scores)
        
        return {
            'sentiment_overreaction': avg_sentiment_overreaction,
            'fundamental_gap': avg_fundamental_gap,
            'technical_divergence': avg_technical_divergence,
            'overall_inefficiency': (avg_sentiment_overreaction + avg_fundamental_gap + avg_technical_divergence) / 3,
            'market_status': self._interpret_market_status(avg_sentiment_overreaction, avg_fundamental_gap)
        }
    
    def _interpret_market_status(self, sentiment_score: float, fundamental_score: float) -> str:
        """시장 상태 해석"""
        if sentiment_score >= 60 and fundamental_score >= 60:
            return "매우 비효율적 - 절호의 기회"
        elif sentiment_score >= 40 or fundamental_score >= 40:
            return "비효율적 - 좋은 기회"
        elif sentiment_score >= 20 or fundamental_score >= 20:
            return "약간 비효율적 - 선별적 기회"
        else:
            return "효율적 - 기회 제한적"


def main():
    """메인 실행 함수"""
    
    print("🎯 워런 버핏 스타일 가치투자 타이밍 최적화")
    print("=" * 60)
    
    optimizer = ValueTimingOptimizer()
    scanner = ValueTimingScanner()
    
    while True:
        print("\n🔍 타이밍 분석 메뉴:")
        print("1. 개별 종목 타이밍 분석")
        print("2. 황금 투자 기회 스캔")
        print("3. 주간 타이밍 리포트")
        print("4. 시장 비효율성 분석")
        print("5. 테스트 (삼성전자)")
        print("0. 종료")
        
        choice = input("\n선택하세요 (0-5): ").strip()
        
        if choice == '0':
            print("👋 타이밍 분석을 종료합니다.")
            break
            
        elif choice == '1':
            stock_code = input("종목코드를 입력하세요 (예: 005930): ").strip()
            if stock_code:
                analysis = optimizer.analyze_value_timing(stock_code)
                
                print(f"\n🎯 {stock_code} 가치투자 타이밍 분석")
                print("=" * 60)
                print(f"🏆 기회 유형: {analysis.opportunity_type.value}")
                print(f"📊 타이밍 점수: {analysis.timing_score:.1f}/100")
                print(f"💰 할인율: {analysis.value_discount:.1f}%")
                print(f"⚖️ 위험수익비: {analysis.risk_reward_ratio:.2f}")
                print(f"🔥 진입 시급성: {analysis.entry_urgency}")
                print(f"📈 누적매수 전략: {analysis.accumulation_strategy}")
                print(f"💎 최적 진입가: {analysis.optimal_entry_price:,.0f}원")
                print(f"🛡️ 안전마진: {analysis.safety_margin:.1f}%")
                print(f"🎯 기대수익률: {analysis.expected_return:.1f}%")
                print(f"⏰ 투자 기간: {analysis.investment_horizon}")
                print(f"🔒 신뢰도: {analysis.confidence_level:.1f}%")
                
                print(f"\n📋 핵심 요인:")
                for factor in analysis.key_factors:
                    print(f"  • {factor}")
                
                print(f"\n🌊 시장 비효율성:")
                print(f"  • 감정적 과반응: {analysis.market_inefficiency['sentiment_overreaction']:.1f}")
                print(f"  • 펀더멘털 갭: {analysis.market_inefficiency['fundamental_gap']:.1f}")
                print(f"  • 기술적 다이버전스: {analysis.market_inefficiency['technical_divergence']:.1f}")
        
        elif choice == '2':
            golden_opportunities = scanner.find_golden_opportunities()
            
            if golden_opportunities:
                print(f"\n🏆 황금 투자 기회 ({len(golden_opportunities)}개)")
                print("=" * 80)
                
                for i, analysis in enumerate(golden_opportunities[:10], 1):
                    print(f"{i}. {analysis.stock_code}")
                    print(f"   타이밍 점수: {analysis.timing_score:.1f}/100")
                    print(f"   기회 유형: {analysis.opportunity_type.value}")
                    print(f"   할인율: {analysis.value_discount:.1f}%")
                    print(f"   기대수익률: {analysis.expected_return:.1f}%")
                    print(f"   진입 시급성: {analysis.entry_urgency}")
                    print()
            else:
                print("❌ 현재 황금 투자 기회가 없습니다.")
        
        elif choice == '3':
            report = scanner.generate_weekly_timing_report()
            
            print(f"\n📊 주간 타이밍 리포트")
            print("=" * 60)
            print(f"분석 종목 수: {report['total_analyzed']}개")
            print(f"생성 시간: {report['generated_at'].strftime('%Y-%m-%d %H:%M:%S')}")
            
            print(f"\n🎯 기회 유형별 분포:")
            for opp_type, analyses in report['opportunities_by_type'].items():
                print(f"  {opp_type}: {len(analyses)}개")
            
            print(f"\n🏢 섹터별 분석:")
            for sector, data in report['sector_analysis'].items():
                print(f"  {sector}: 평균 {data['avg_score']:.1f}점 ({data['count']}개) - {data['recommendation']}")
            
            print(f"\n🌊 시장 비효율성:")
            inefficiency = report['market_inefficiency']
            print(f"  전체 비효율성: {inefficiency['overall_inefficiency']:.1f}")
            print(f"  시장 상태: {inefficiency['market_status']}")
            
            if report['top_picks']:
                print(f"\n🔥 이번 주 추천 종목:")
                for i, analysis in enumerate(report['top_picks'], 1):
                    print(f"  {i}. {analysis.stock_code} (점수: {analysis.timing_score:.1f})")
        
        elif choice == '4':
            print("\n🌊 시장 비효율성 상세 분석...")
            analyses = scanner.scan_market_opportunities()
            
            if analyses:
                # 가장 비효율적인 종목들
                inefficient_stocks = sorted(
                    analyses, 
                    key=lambda x: sum(x.market_inefficiency.values()), 
                    reverse=True
                )[:5]
                
                print(f"\n🎯 가장 비효율적인 종목 TOP 5:")
                for i, analysis in enumerate(inefficient_stocks, 1):
                    total_inefficiency = sum(analysis.market_inefficiency.values())
                    print(f"{i}. {analysis.stock_code}")
                    print(f"   전체 비효율성: {total_inefficiency:.1f}")
                    print(f"   감정 과반응: {analysis.market_inefficiency['sentiment_overreaction']:.1f}")
                    print(f"   펀더멘털 갭: {analysis.market_inefficiency['fundamental_gap']:.1f}")
                    print(f"   기술적 다이버전스: {analysis.market_inefficiency['technical_divergence']:.1f}")
                    print()
        
        elif choice == '5':
            print("\n🧪 삼성전자(005930) 타이밍 분석...")
            analysis = optimizer.analyze_value_timing('005930')
            
            print(f"\n🎯 삼성전자 가치투자 타이밍 분석")
            print("=" * 60)
            print(f"🏆 기회 유형: {analysis.opportunity_type.value}")
            print(f"📊 타이밍 점수: {analysis.timing_score:.1f}/100")
            print(f"💰 할인율: {analysis.value_discount:.1f}%")
            print(f"🔥 진입 시급성: {analysis.entry_urgency}")
            print(f"📈 누적매수 전략: {analysis.accumulation_strategy}")
            print(f"🎯 기대수익률: {analysis.expected_return:.1f}%")
            print(f"⏰ 투자 기간: {analysis.investment_horizon}")
            
            if analysis.key_factors:
                print(f"\n📋 핵심 요인:")
                for factor in analysis.key_factors:
                    print(f"  • {factor}")
        
        else:
            print("❌ 올바른 번호를 선택해주세요.")


if __name__ == "__main__":
    main()