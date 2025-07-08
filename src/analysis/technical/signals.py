"""
src/analysis/technical/signals.py

워런 버핏 스타일 매매 신호 생성 시스템
기본분석(45%) : 기술분석(30%) : 뉴스분석(25%) 비율 반영

🎯 핵심 목표:
- 가치투자 최적화 매매 신호
- 장기투자 타이밍 최적화
- 리스크 관리 신호
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR
    from src.analysis.technical.indicators import (
        LongTermTrendIndicators, ValueInvestingMomentum, 
        VolatilityBasedEntry, ValueTimingSignals
    )
except ImportError:
    DATA_DIR = Path("data")


class SignalType(Enum):
    """신호 유형"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    WEAK_BUY = "weak_buy"
    HOLD = "hold"
    WEAK_SELL = "weak_sell"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class SignalStrength(Enum):
    """신호 강도"""
    VERY_STRONG = 5
    STRONG = 4
    MODERATE = 3
    WEAK = 2
    VERY_WEAK = 1


@dataclass
class TradingSignal:
    """매매 신호 데이터 클래스"""
    stock_code: str
    signal_type: SignalType
    strength: SignalStrength
    confidence: float  # 0-100
    entry_price: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    position_size: float = 1.0  # 권장 포지션 크기 (0-1)
    timeframe: str = "장기"  # 투자 기간
    reasons: List[str] = None
    risk_level: str = "중간"
    created_at: datetime = None
    
    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []
        if self.created_at is None:
            self.created_at = datetime.now()


class ValueInvestingSignalGenerator:
    """워런 버핏 스타일 신호 생성기"""
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.stock_db_path = self.data_dir / 'stock_data.db'
        self.dart_db_path = self.data_dir / 'dart_data.db'
        
        # 지표 계산기 초기화
        self.trend_indicators = LongTermTrendIndicators()
        self.momentum_indicators = ValueInvestingMomentum()
        self.volatility_indicators = VolatilityBasedEntry()
        self.value_timing = ValueTimingSignals()
    
    def generate_comprehensive_signal(self, stock_code: str) -> TradingSignal:
        """종합 매매 신호 생성"""
        try:
            # 1. 기본 데이터 수집
            price_data = self._get_price_data(stock_code)
            if price_data.empty:
                return self._create_neutral_signal(stock_code, "데이터 부족")
            
            # 2. 버핏 스코어 확인 (기본분석 45%)
            buffett_score = self._get_buffett_score(stock_code)
            fundamental_weight = 0.45
            
            # 3. 기술적 지표 계산 (기술분석 30%)
            technical_signals = self._calculate_technical_signals(price_data)
            technical_weight = 0.30
            
            # 4. 뉴스 감정 분석 (뉴스분석 25%)
            sentiment_score = self._get_sentiment_score(stock_code)
            sentiment_weight = 0.25
            
            # 5. 종합 신호 계산
            signal = self._combine_signals(
                stock_code, price_data, buffett_score, technical_signals, 
                sentiment_score, fundamental_weight, technical_weight, sentiment_weight
            )
            
            return signal
            
        except Exception as e:
            print(f"❌ 신호 생성 실패 ({stock_code}): {e}")
            return self._create_neutral_signal(stock_code, f"오류: {e}")
    
    def _get_price_data(self, stock_code: str) -> pd.DataFrame:
        """주가 데이터 조회"""
        try:
            with sqlite3.connect(self.stock_db_path) as conn:
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
    
    def _get_buffett_score(self, stock_code: str) -> float:
        """버핏 스코어 조회"""
        try:
            with sqlite3.connect(self.dart_db_path) as conn:
                query = """
                    SELECT fs.account_nm, fs.thstrm_amount
                    FROM financial_statements fs
                    JOIN company_info ci ON fs.corp_code = ci.corp_code
                    WHERE ci.stock_code = ? AND fs.bsns_year = '2023'
                    AND fs.account_nm IN ('자산총계', '부채총계', '자본총계', '당기순이익')
                """
                result = pd.read_sql_query(query, conn, params=(stock_code,))
                
                if result.empty:
                    return 50.0
                
                # 간단한 스코어 계산
                accounts = {}
                for _, row in result.iterrows():
                    try:
                        amount = float(str(row['thstrm_amount']).replace(',', ''))
                        accounts[row['account_nm']] = amount
                    except:
                        continue
                
                score = 50.0
                
                # ROE 계산
                if '당기순이익' in accounts and '자본총계' in accounts and accounts['자본총계'] > 0:
                    roe = accounts['당기순이익'] / accounts['자본총계'] * 100
                    if roe >= 20: score += 25
                    elif roe >= 15: score += 20
                    elif roe >= 10: score += 15
                    elif roe >= 5: score += 10
                
                # 부채비율 계산
                if '부채총계' in accounts and '자본총계' in accounts and accounts['자본총계'] > 0:
                    debt_ratio = accounts['부채총계'] / accounts['자본총계'] * 100
                    if debt_ratio <= 30: score += 20
                    elif debt_ratio <= 50: score += 15
                    elif debt_ratio <= 100: score += 10
                
                return min(100.0, score)
                
        except Exception as e:
            return 50.0
    
    def _calculate_technical_signals(self, price_data: pd.DataFrame) -> Dict:
        """기술적 지표 기반 신호 계산"""
        signals = {
            'trend_signal': 0,
            'momentum_signal': 0,
            'volatility_signal': 0,
            'overall_technical': 0,
            'reasons': []
        }
        
        try:
            # 추세 신호
            ma_data = self.trend_indicators.moving_average_200(price_data['close'])
            if ma_data:
                if ma_data['price_vs_ma_pct'] > 5 and ma_data['ma_slope_pct'] > 0:
                    signals['trend_signal'] = 2  # 강한 상승 추세
                    signals['reasons'].append("200일선 위 강세")
                elif ma_data['price_vs_ma_pct'] > 0:
                    signals['trend_signal'] = 1  # 약한 상승 추세
                    signals['reasons'].append("200일선 위")
                elif ma_data['price_vs_ma_pct'] < -10:
                    signals['trend_signal'] = -2  # 강한 하락 (매수 기회)
                    signals['reasons'].append("200일선 대비 큰 하락")
                elif ma_data['price_vs_ma_pct'] < 0:
                    signals['trend_signal'] = -1  # 약한 하락
                    signals['reasons'].append("200일선 아래")
            
            # 모멘텀 신호
            rsi_data = self.momentum_indicators.rsi_monthly(price_data['close'])
            if rsi_data:
                if rsi_data['rsi'] <= 30:
                    signals['momentum_signal'] = 2  # 강한 과매도 (매수)
                    signals['reasons'].append(f"RSI 과매도 ({rsi_data['rsi']:.1f})")
                elif rsi_data['rsi'] <= 40:
                    signals['momentum_signal'] = 1  # 약한 과매도
                    signals['reasons'].append(f"RSI 낮음 ({rsi_data['rsi']:.1f})")
                elif rsi_data['rsi'] >= 70:
                    signals['momentum_signal'] = -2  # 강한 과매수 (매도)
                    signals['reasons'].append(f"RSI 과매수 ({rsi_data['rsi']:.1f})")
                elif rsi_data['rsi'] >= 60:
                    signals['momentum_signal'] = -1  # 약한 과매수
                    signals['reasons'].append(f"RSI 높음 ({rsi_data['rsi']:.1f})")
            
            # 변동성 신호
            bb_data = self.volatility_indicators.bollinger_bands_value(price_data['close'])
            if bb_data:
                if bb_data['lower_touch']:
                    signals['volatility_signal'] = 2  # 하단 터치 (매수)
                    signals['reasons'].append("볼린저밴드 하단 터치")
                elif bb_data['band_position_pct'] < 25:
                    signals['volatility_signal'] = 1  # 하위 구간
                    signals['reasons'].append("볼린저밴드 하위 구간")
                elif bb_data['upper_touch']:
                    signals['volatility_signal'] = -2  # 상단 터치 (매도)
                    signals['reasons'].append("볼린저밴드 상단 터치")
                elif bb_data['band_position_pct'] > 75:
                    signals['volatility_signal'] = -1  # 상위 구간
                    signals['reasons'].append("볼린저밴드 상위 구간")
            
            # 종합 기술적 신호
            signals['overall_technical'] = (
                signals['trend_signal'] + 
                signals['momentum_signal'] + 
                signals['volatility_signal']
            ) / 3
            
        except Exception as e:
            print(f"⚠️ 기술적 신호 계산 오류: {e}")
        
        return signals
    
    def _get_sentiment_score(self, stock_code: str) -> float:
        """뉴스 감정 점수 조회"""
        try:
            news_db_path = self.data_dir / 'news_data.db'
            if not news_db_path.exists():
                return 0.0
            
            with sqlite3.connect(news_db_path) as conn:
                query = """
                    SELECT AVG(sentiment_score) as avg_sentiment
                    FROM news_articles
                    WHERE stock_code = ?
                    AND DATE(collected_at) >= DATE('now', '-7 days')
                """
                result = pd.read_sql_query(query, conn, params=(stock_code,))
                
                if not result.empty and result.iloc[0]['avg_sentiment'] is not None:
                    return result.iloc[0]['avg_sentiment']
                else:
                    return 0.0
        except:
            return 0.0
    
    def _combine_signals(self, stock_code: str, price_data: pd.DataFrame, 
                        buffett_score: float, technical_signals: Dict, 
                        sentiment_score: float, fund_weight: float, 
                        tech_weight: float, sent_weight: float) -> TradingSignal:
        """신호 통합 및 최종 판단"""
        
        current_price = price_data['close'].iloc[-1]
        reasons = []
        
        # 1. 기본분석 점수 (45%)
        if buffett_score >= 85:
            fundamental_signal = 2
            reasons.append(f"우수한 펀더멘털 ({buffett_score:.0f}점)")
        elif buffett_score >= 75:
            fundamental_signal = 1
            reasons.append(f"양호한 펀더멘털 ({buffett_score:.0f}점)")
        elif buffett_score >= 60:
            fundamental_signal = 0
            reasons.append(f"보통 펀더멘털 ({buffett_score:.0f}점)")
        elif buffett_score >= 40:
            fundamental_signal = -1
            reasons.append(f"약한 펀더멘털 ({buffett_score:.0f}점)")
        else:
            fundamental_signal = -2
            reasons.append(f"부족한 펀더멘털 ({buffett_score:.0f}점)")
        
        # 2. 기술분석 점수 (30%)
        tech_signal = technical_signals['overall_technical']
        reasons.extend(technical_signals['reasons'])
        
        # 3. 뉴스 감정 점수 (25%)
        if sentiment_score > 0.2:
            sentiment_signal = 1
            reasons.append("긍정적 뉴스 감정")
        elif sentiment_score < -0.2:
            sentiment_signal = -1
            reasons.append("부정적 뉴스 감정")
        else:
            sentiment_signal = 0
            reasons.append("중립적 뉴스 감정")
        
        # 4. 가중 평균 계산
        weighted_score = (
            fundamental_signal * fund_weight +
            tech_signal * tech_weight +
            sentiment_signal * sent_weight
        )
        
        # 5. 신호 유형 결정
        if weighted_score >= 1.5:
            signal_type = SignalType.STRONG_BUY
            strength = SignalStrength.VERY_STRONG
            confidence = min(95, 70 + weighted_score * 10)
            position_size = 1.0
            risk_level = "낮음"
        elif weighted_score >= 1.0:
            signal_type = SignalType.BUY
            strength = SignalStrength.STRONG
            confidence = min(85, 60 + weighted_score * 10)
            position_size = 0.8
            risk_level = "낮음"
        elif weighted_score >= 0.5:
            signal_type = SignalType.WEAK_BUY
            strength = SignalStrength.MODERATE
            confidence = min(75, 50 + weighted_score * 10)
            position_size = 0.6
            risk_level = "보통"
        elif weighted_score >= -0.5:
            signal_type = SignalType.HOLD
            strength = SignalStrength.WEAK
            confidence = 50
            position_size = 0.3
            risk_level = "보통"
        elif weighted_score >= -1.0:
            signal_type = SignalType.WEAK_SELL
            strength = SignalStrength.WEAK
            confidence = min(75, 50 - weighted_score * 10)
            position_size = 0.0
            risk_level = "높음"
        else:
            signal_type = SignalType.SELL
            strength = SignalStrength.STRONG
            confidence = min(85, 60 - weighted_score * 10)
            position_size = 0.0
            risk_level = "높음"
        
        # 6. 목표가 및 손절가 계산
        target_price, stop_loss = self._calculate_price_targets(
            current_price, signal_type, buffett_score, price_data
        )
        
        # 7. 투자 기간 설정
        if buffett_score >= 75:
            timeframe = "장기 (2-5년)"
        elif buffett_score >= 60:
            timeframe = "중기 (1-2년)"
        else:
            timeframe = "단기 (3-6개월)"
        
        return TradingSignal(
            stock_code=stock_code,
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            entry_price=current_price,
            target_price=target_price,
            stop_loss=stop_loss,
            position_size=position_size,
            timeframe=timeframe,
            reasons=reasons,
            risk_level=risk_level,
            created_at=datetime.now()
        )
    
    def _calculate_price_targets(self, current_price: float, signal_type: SignalType, 
                               buffett_score: float, price_data: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        """목표가 및 손절가 계산"""
        target_price = None
        stop_loss = None
        
        try:
            # ATR 기반 변동성 계산
            high = price_data['high']
            low = price_data['low']
            close = price_data['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            
            if signal_type in [SignalType.STRONG_BUY, SignalType.BUY, SignalType.WEAK_BUY]:
                # 매수 신호 - 목표가 설정
                if buffett_score >= 80:
                    # 우량주는 보수적 목표가 (20-30%)
                    target_multiplier = 1.2 + (buffett_score - 80) / 100
                else:
                    # 일반주는 적극적 목표가 (10-20%)
                    target_multiplier = 1.1 + max(0, buffett_score - 60) / 200
                
                target_price = current_price * target_multiplier
                
                # 손절가 (2 ATR 또는 -15% 중 더 보수적)
                atr_stop = current_price - (atr * 2)
                percent_stop = current_price * 0.85
                stop_loss = max(atr_stop, percent_stop)
            
            elif signal_type in [SignalType.WEAK_SELL, SignalType.SELL]:
                # 매도 신호 - 손절가만 설정
                stop_loss = current_price * 1.05  # 5% 상승 시 재평가
                
        except Exception as e:
            print(f"⚠️ 목표가 계산 오류: {e}")
        
        return target_price, stop_loss
    
    def _create_neutral_signal(self, stock_code: str, reason: str) -> TradingSignal:
        """중립 신호 생성"""
        return TradingSignal(
            stock_code=stock_code,
            signal_type=SignalType.HOLD,
            strength=SignalStrength.WEAK,
            confidence=0,
            entry_price=0,
            reasons=[reason],
            created_at=datetime.now()
        )


class PortfolioSignalManager:
    """포트폴리오 차원의 신호 관리"""
    
    def __init__(self):
        self.signal_generator = ValueInvestingSignalGenerator()
        self.data_dir = Path(DATA_DIR)
    
    def generate_portfolio_signals(self, stock_codes: List[str]) -> Dict[str, TradingSignal]:
        """포트폴리오 전체 신호 생성"""
        signals = {}
        
        print(f"📊 {len(stock_codes)}개 종목 신호 생성 중...")
        
        for stock_code in stock_codes:
            try:
                signal = self.signal_generator.generate_comprehensive_signal(stock_code)
                signals[stock_code] = signal
            except Exception as e:
                print(f"❌ {stock_code} 신호 생성 실패: {e}")
                signals[stock_code] = self.signal_generator._create_neutral_signal(
                    stock_code, f"오류: {e}"
                )
        
        return signals
    
    def get_top_signals(self, signals: Dict[str, TradingSignal], 
                       signal_types: List[SignalType] = None, 
                       min_confidence: float = 70, 
                       top_n: int = 10) -> List[TradingSignal]:
        """상위 신호 필터링"""
        
        if signal_types is None:
            signal_types = [SignalType.STRONG_BUY, SignalType.BUY, SignalType.WEAK_BUY]
        
        filtered_signals = []
        
        for signal in signals.values():
            if (signal.signal_type in signal_types and 
                signal.confidence >= min_confidence):
                filtered_signals.append(signal)
        
        # 신뢰도 순으로 정렬
        filtered_signals.sort(key=lambda x: x.confidence, reverse=True)
        
        return filtered_signals[:top_n]
    
    def generate_daily_watchlist(self) -> List[TradingSignal]:
        """일일 관심종목 리스트 생성"""
        try:
            # 주요 종목 리스트 (실제로는 DB에서 조회)
            major_stocks = [
                '005930', '000660', '035420', '005380', '006400',
                '051910', '035720', '207940', '068270', '096770'
            ]
            
            # 신호 생성
            signals = self.generate_portfolio_signals(major_stocks)
            
            # 매수 신호만 필터링
            buy_signals = self.get_top_signals(
                signals, 
                [SignalType.STRONG_BUY, SignalType.BUY], 
                min_confidence=75
            )
            
            return buy_signals
            
        except Exception as e:
            print(f"❌ 관심종목 생성 실패: {e}")
            return []
    
    def print_signal_summary(self, signals: Dict[str, TradingSignal]):
        """신호 요약 출력"""
        print("\n📊 신호 생성 요약")
        print("=" * 60)
        
        # 신호 유형별 집계
        signal_counts = {}
        for signal in signals.values():
            signal_type = signal.signal_type.value
            signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
        
        for signal_type, count in signal_counts.items():
            print(f"{signal_type}: {count}개")
        
        # 높은 신뢰도 신호
        high_confidence = [s for s in signals.values() if s.confidence >= 80]
        if high_confidence:
            print(f"\n🔥 고신뢰도 신호 ({len(high_confidence)}개):")
            for signal in sorted(high_confidence, key=lambda x: x.confidence, reverse=True):
                print(f"  {signal.stock_code}: {signal.signal_type.value} ({signal.confidence:.0f}%)")


def main():
    """메인 실행 함수"""
    
    print("🚀 워런 버핏 스타일 매매 신호 생성기")
    print("=" * 60)
    
    signal_generator = ValueInvestingSignalGenerator()
    portfolio_manager = PortfolioSignalManager()
    
    while True:
        print("\n📊 신호 생성 메뉴:")
        print("1. 개별 종목 신호 생성")
        print("2. 포트폴리오 신호 생성")
        print("3. 일일 관심종목 생성")
        print("4. 테스트 (삼성전자)")
        print("0. 종료")
        
        choice = input("\n선택하세요 (0-4): ").strip()
        
        if choice == '0':
            print("👋 신호 생성기를 종료합니다.")
            break
            
        elif choice == '1':
            stock_code = input("종목코드를 입력하세요 (예: 005930): ").strip()
            if stock_code:
                signal = signal_generator.generate_comprehensive_signal(stock_code)
                
                print(f"\n📊 {stock_code} 매매 신호:")
                print("=" * 50)
                print(f"🎯 신호: {signal.signal_type.value}")
                print(f"💪 강도: {signal.strength.value}/5")
                print(f"🔥 신뢰도: {signal.confidence:.0f}%")
                print(f"💰 진입가: {signal.entry_price:,.0f}원")
                if signal.target_price:
                    print(f"🎯 목표가: {signal.target_price:,.0f}원")
                if signal.stop_loss:
                    print(f"🛑 손절가: {signal.stop_loss:,.0f}원")
                print(f"📊 포지션 크기: {signal.position_size*100:.0f}%")
                print(f"⏰ 투자 기간: {signal.timeframe}")
                print(f"⚖️ 리스크: {signal.risk_level}")
                print("\n📋 신호 근거:")
                for reason in signal.reasons:
                    print(f"  • {reason}")
        
        elif choice == '2':
            stock_codes = input("종목코드를 쉼표로 구분해서 입력 (예: 005930,000660): ").strip()
            if stock_codes:
                codes = [code.strip() for code in stock_codes.split(',')]
                signals = portfolio_manager.generate_portfolio_signals(codes)
                portfolio_manager.print_signal_summary(signals)
        
        elif choice == '3':
            print("\n🔍 일일 관심종목 생성 중...")
            watchlist = portfolio_manager.generate_daily_watchlist()
            
            if watchlist:
                print(f"\n📋 오늘의 관심종목 ({len(watchlist)}개):")
                print("=" * 60)
                for i, signal in enumerate(watchlist, 1):
                    print(f"{i}. {signal.stock_code}")
                    print(f"   신호: {signal.signal_type.value} ({signal.confidence:.0f}%)")
                    print(f"   진입가: {signal.entry_price:,.0f}원")
                    if signal.target_price:
                        print(f"   목표가: {signal.target_price:,.0f}원")
                    print(f"   주요 근거: {signal.reasons[0] if signal.reasons else 'N/A'}")
                    print()
            else:
                print("❌ 오늘은 추천할 만한 종목이 없습니다.")
        
        elif choice == '4':
            print("\n🧪 삼성전자(005930) 테스트...")
            signal = signal_generator.generate_comprehensive_signal('005930')
            
            print(f"\n📊 삼성전자 매매 신호:")
            print("=" * 50)
            print(f"🎯 신호: {signal.signal_type.value}")
            print(f"💪 강도: {signal.strength.value}/5")
            print(f"🔥 신뢰도: {signal.confidence:.0f}%")
            print(f"💰 현재가: {signal.entry_price:,.0f}원")
            if signal.target_price:
                print(f"🎯 목표가: {signal.target_price:,.0f}원 (+{(signal.target_price/signal.entry_price-1)*100:.1f}%)")
            if signal.stop_loss:
                print(f"🛑 손절가: {signal.stop_loss:,.0f}원 ({(signal.stop_loss/signal.entry_price-1)*100:.1f}%)")
            print(f"📊 포지션 크기: {signal.position_size*100:.0f}%")
            print(f"⏰ 투자 기간: {signal.timeframe}")
            print(f"⚖️ 리스크: {signal.risk_level}")
            print("\n📋 신호 근거:")
            for reason in signal.reasons:
                print(f"  • {reason}")
        
        else:
            print("❌ 올바른 번호를 선택해주세요.")


if __name__ == "__main__":
    main()