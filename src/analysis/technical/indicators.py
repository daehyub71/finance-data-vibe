"""
src/analysis/technical/indicators.py

워런 버핏 스타일 가치투자를 위한 기술적 분석 지표
기본분석(45%) : 기술분석(30%) : 뉴스분석(25%) 비율 반영

📈 핵심 목표:
- 장기투자 최적화 타이밍 제공
- 우량주 매수 기회 포착
- 가치투자 관점의 기술적 신호
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR
except ImportError:
    DATA_DIR = Path("data")


class LongTermTrendIndicators:
    """워런 버핏용 장기 추세 분석"""
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.stock_db_path = self.data_dir / 'stock_data.db'
    
    def moving_average_200(self, prices):
        """200일 이동평균 - 장기 트렌드 확인"""
        if len(prices) < 200:
            return None
        
        ma_200 = prices.rolling(window=200).mean()
        current_price = prices.iloc[-1]
        current_ma = ma_200.iloc[-1]
        
        # 현재가 vs 200일선 위치
        price_vs_ma = (current_price / current_ma - 1) * 100
        
        # 200일선 기울기 (최근 20일간 변화)
        ma_slope = (ma_200.iloc[-1] - ma_200.iloc[-21]) / ma_200.iloc[-21] * 100
        
        # 200일선 터치 횟수 (최근 1년)
        recent_year = prices.tail(252) if len(prices) >= 252 else prices
        ma_recent = ma_200.tail(252) if len(ma_200) >= 252 else ma_200
        
        # 200일선 ±2% 범위 터치 횟수
        touch_upper = sum((recent_year > ma_recent * 1.02) & (recent_year.shift(1) <= ma_recent.shift(1) * 1.02))
        touch_lower = sum((recent_year < ma_recent * 0.98) & (recent_year.shift(1) >= ma_recent.shift(1) * 0.98))
        
        return {
            'ma_200': current_ma,
            'price_vs_ma_pct': price_vs_ma,
            'ma_slope_pct': ma_slope,
            'touch_count': touch_upper + touch_lower,
            'trend_direction': 'up' if price_vs_ma > 0 and ma_slope > 0 else 'down' if price_vs_ma < 0 and ma_slope < 0 else 'sideways'
        }
    
    def price_position_analysis(self, prices):
        """52주 고저가 대비 현재 위치"""
        # 52주 = 252 거래일
        period = min(252, len(prices))
        recent_prices = prices.tail(period)
        
        high_52w = recent_prices.max()
        low_52w = recent_prices.min()
        current_price = prices.iloc[-1]
        
        # 현재가가 52주 범위에서 몇 % 위치인지
        if high_52w != low_52w:
            position_pct = (current_price - low_52w) / (high_52w - low_52w) * 100
        else:
            position_pct = 50.0
        
        # 신고가/신저가 갱신 여부 (최근 5일)
        recent_5d = prices.tail(5)
        is_new_high = current_price >= high_52w * 0.999  # 오차 허용
        is_new_low = current_price <= low_52w * 1.001
        
        # 신고가 대비 하락률
        drawdown_from_high = (current_price / high_52w - 1) * 100
        
        return {
            'high_52w': high_52w,
            'low_52w': low_52w,
            'position_pct': position_pct,
            'is_new_high': is_new_high,
            'is_new_low': is_new_low,
            'drawdown_from_high_pct': drawdown_from_high,
            'range_amplitude_pct': (high_52w / low_52w - 1) * 100
        }
    
    def trend_strength(self, high, low, close):
        """추세 강도 측정 (ADX)"""
        if len(close) < 15:
            return None
        
        # True Range 계산
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Directional Movement 계산
        dm_plus = np.where((high - high.shift(1)) > (low.shift(1) - low), 
                          np.maximum(high - high.shift(1), 0), 0)
        dm_minus = np.where((low.shift(1) - low) > (high - high.shift(1)), 
                           np.maximum(low.shift(1) - low, 0), 0)
        
        # 14일 평활 평균
        atr = tr.rolling(window=14).mean()
        di_plus = pd.Series(dm_plus).rolling(window=14).mean() / atr * 100
        di_minus = pd.Series(dm_minus).rolling(window=14).mean() / atr * 100
        
        # ADX 계산
        dx = abs(di_plus - di_minus) / (di_plus + di_minus) * 100
        adx = dx.rolling(window=14).mean()
        
        current_adx = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
        current_di_plus = di_plus.iloc[-1] if not pd.isna(di_plus.iloc[-1]) else 0
        current_di_minus = di_minus.iloc[-1] if not pd.isna(di_minus.iloc[-1]) else 0
        
        # 추세 강도 해석
        if current_adx > 25:
            trend_strength = 'strong'
        elif current_adx > 20:
            trend_strength = 'moderate'
        else:
            trend_strength = 'weak'
        
        # 추세 방향
        trend_direction = 'bullish' if current_di_plus > current_di_minus else 'bearish'
        
        return {
            'adx': current_adx,
            'di_plus': current_di_plus,
            'di_minus': current_di_minus,
            'trend_strength': trend_strength,
            'trend_direction': trend_direction
        }


class ValueInvestingMomentum:
    """가치투자 매수 타이밍용 모멘텀"""
    
    def rsi_monthly(self, prices, period=20):
        """월간 RSI - 장기 과매도 확인 (20일 = 대략 1개월)"""
        if len(prices) < period + 1:
            return None
        
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        
        # RSI 신호 해석
        if current_rsi <= 30:
            signal = 'oversold'  # 매수 고려
            strength = 'strong'
        elif current_rsi <= 40:
            signal = 'oversold'
            strength = 'moderate'
        elif current_rsi >= 70:
            signal = 'overbought'  # 관망
            strength = 'strong'
        elif current_rsi >= 60:
            signal = 'overbought'
            strength = 'moderate'
        else:
            signal = 'neutral'
            strength = 'weak'
        
        return {
            'rsi': current_rsi,
            'signal': signal,
            'strength': strength,
            'rsi_series': rsi.tail(60)  # 최근 3개월 추이
        }
    
    def stochastic_weekly(self, high, low, close, k_period=14, d_period=3):
        """주간 스토캐스틱 - 매수 타이밍"""
        if len(close) < k_period:
            return None
        
        # %K 계산
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k_percent = (close - lowest_low) / (highest_high - lowest_low) * 100
        
        # %D 계산 (3일 이동평균)
        d_percent = k_percent.rolling(window=d_period).mean()
        
        current_k = k_percent.iloc[-1]
        current_d = d_percent.iloc[-1]
        prev_k = k_percent.iloc[-2] if len(k_percent) > 1 else current_k
        prev_d = d_percent.iloc[-2] if len(d_percent) > 1 else current_d
        
        # 골든크로스/데드크로스 확인
        golden_cross = (prev_k <= prev_d) and (current_k > current_d) and (current_k < 30)
        dead_cross = (prev_k >= prev_d) and (current_k < current_d) and (current_k > 70)
        
        # 신호 생성
        if golden_cross:
            signal = 'buy'
            strength = 'strong'
        elif current_k < 20 and current_d < 20:
            signal = 'buy'
            strength = 'moderate'
        elif dead_cross:
            signal = 'sell'
            strength = 'strong'
        elif current_k > 80 and current_d > 80:
            signal = 'sell'
            strength = 'moderate'
        else:
            signal = 'neutral'
            strength = 'weak'
        
        return {
            'k_percent': current_k,
            'd_percent': current_d,
            'signal': signal,
            'strength': strength,
            'golden_cross': golden_cross,
            'dead_cross': dead_cross
        }
    
    def macd_long_term(self, prices, fast=26, slow=52, signal=18):
        """장기 MACD - 추세 전환점 (일반적인 12-26-9 대신 26-52-18 사용)"""
        if len(prices) < slow:
            return None
        
        # 지수이동평균 계산
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        
        # MACD 라인
        macd_line = ema_fast - ema_slow
        
        # 신호선
        signal_line = macd_line.ewm(span=signal).mean()
        
        # 히스토그램
        histogram = macd_line - signal_line
        
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        current_histogram = histogram.iloc[-1]
        prev_histogram = histogram.iloc[-2] if len(histogram) > 1 else current_histogram
        
        # 신호 생성
        macd_bullish = current_macd > current_signal
        histogram_bullish = current_histogram > prev_histogram
        zero_line_cross = (prev_histogram <= 0) and (current_histogram > 0)
        
        if zero_line_cross:
            signal_type = 'strong_buy'
        elif macd_bullish and histogram_bullish:
            signal_type = 'buy'
        elif not macd_bullish and not histogram_bullish:
            signal_type = 'sell'
        else:
            signal_type = 'neutral'
        
        return {
            'macd': current_macd,
            'signal': current_signal,
            'histogram': current_histogram,
            'signal_type': signal_type,
            'zero_line_cross': zero_line_cross,
            'macd_bullish': macd_bullish
        }


class VolatilityBasedEntry:
    """변동성 활용 진입점 최적화"""
    
    def bollinger_bands_value(self, prices, period=20, std_dev=2):
        """볼린저 밴드 가치투자 활용"""
        if len(prices) < period:
            return None
        
        # 중심선 (20일 이동평균)
        middle_band = prices.rolling(window=period).mean()
        
        # 표준편차
        std = prices.rolling(window=period).std()
        
        # 상단/하단 밴드
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        
        current_price = prices.iloc[-1]
        current_upper = upper_band.iloc[-1]
        current_lower = lower_band.iloc[-1]
        current_middle = middle_band.iloc[-1]
        
        # 밴드 위치 계산 (%)
        band_position = (current_price - current_lower) / (current_upper - current_lower) * 100
        
        # 밴드 터치 확인
        lower_touch = current_price <= current_lower * 1.01  # 1% 오차 허용
        upper_touch = current_price >= current_upper * 0.99
        
        # 밴드 수축/확장 (변동성 상태)
        band_width = (current_upper - current_lower) / current_middle * 100
        avg_band_width = ((upper_band - lower_band) / middle_band * 100).tail(50).mean()
        
        squeeze = band_width < avg_band_width * 0.8  # 밴드 수축
        expansion = band_width > avg_band_width * 1.2  # 밴드 확장
        
        # 매매 신호
        if lower_touch and not squeeze:
            signal = 'buy'  # 하단 터치 + 정상 변동성
            strength = 'strong'
        elif band_position < 25:
            signal = 'buy'
            strength = 'moderate'
        elif upper_touch:
            signal = 'sell'
            strength = 'strong'
        elif band_position > 75:
            signal = 'sell'
            strength = 'moderate'
        else:
            signal = 'neutral'
            strength = 'weak'
        
        return {
            'upper_band': current_upper,
            'middle_band': current_middle,
            'lower_band': current_lower,
            'band_position_pct': band_position,
            'band_width': band_width,
            'squeeze': squeeze,
            'expansion': expansion,
            'signal': signal,
            'strength': strength,
            'lower_touch': lower_touch,
            'upper_touch': upper_touch
        }
    
    def atr_position_sizing(self, high, low, close, period=14):
        """ATR 기반 포지션 사이징"""
        if len(close) < period:
            return None
        
        # True Range 계산
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR (Average True Range)
        atr = tr.rolling(window=period).mean()
        current_atr = atr.iloc[-1]
        current_price = close.iloc[-1]
        
        # ATR 기반 변동성 측정
        atr_pct = (current_atr / current_price) * 100
        
        # 포지션 사이징 가이드
        if atr_pct < 1.5:
            risk_level = 'low'
            position_size = 'large'  # 안정적이므로 큰 포지션
        elif atr_pct < 3.0:
            risk_level = 'medium'
            position_size = 'medium'
        else:
            risk_level = 'high'
            position_size = 'small'  # 변동성 높으므로 작은 포지션
        
        # 손절가 제안 (2 ATR)
        stop_loss_long = current_price - (current_atr * 2)
        stop_loss_short = current_price + (current_atr * 2)
        
        return {
            'atr': current_atr,
            'atr_pct': atr_pct,
            'risk_level': risk_level,
            'position_size': position_size,
            'stop_loss_long': stop_loss_long,
            'stop_loss_short': stop_loss_short
        }
    
    def volatility_breakout(self, high, low, close, period=20):
        """변동성 돌파 매수"""
        if len(close) < period:
            return None
        
        # 최근 N일간 최고가/최저가
        recent_high = high.rolling(window=period).max()
        recent_low = low.rolling(window=period).min()
        
        current_price = close.iloc[-1]
        current_high_level = recent_high.iloc[-2]  # 전일까지의 최고가
        current_low_level = recent_low.iloc[-2]   # 전일까지의 최저가
        
        # 돌파 확인
        upside_breakout = current_price > current_high_level
        downside_breakout = current_price < current_low_level
        
        # 거래량 확인이 필요하지만 여기서는 가격만으로
        # 박스권 크기
        box_size = (current_high_level - current_low_level) / current_low_level * 100
        
        # 박스권 위치
        box_position = (current_price - current_low_level) / (current_high_level - current_low_level) * 100
        
        # 신호 생성
        if upside_breakout and box_size > 10:  # 의미있는 박스권 돌파
            signal = 'breakout_buy'
            strength = 'strong'
        elif downside_breakout and box_size > 10:
            signal = 'breakdown_sell'
            strength = 'strong'
        elif box_position > 80:
            signal = 'near_resistance'
            strength = 'moderate'
        elif box_position < 20:
            signal = 'near_support'
            strength = 'moderate'
        else:
            signal = 'neutral'
            strength = 'weak'
        
        return {
            'resistance_level': current_high_level,
            'support_level': current_low_level,
            'box_size_pct': box_size,
            'box_position_pct': box_position,
            'upside_breakout': upside_breakout,
            'downside_breakout': downside_breakout,
            'signal': signal,
            'strength': strength
        }


class ValueTimingSignals:
    """워런 버핏 스타일 타이밍 신호"""
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.stock_db_path = self.data_dir / 'stock_data.db'
        self.dart_db_path = self.data_dir / 'dart_data.db'
        self.news_db_path = self.data_dir / 'news_data.db'
        
        # 지표 계산기 초기화
        self.trend_indicators = LongTermTrendIndicators()
        self.momentum_indicators = ValueInvestingMomentum()
        self.volatility_indicators = VolatilityBasedEntry()
    
    def get_stock_price_data(self, stock_code):
        """주가 데이터 조회"""
        try:
            with sqlite3.connect(self.stock_db_path) as conn:
                query = """
                    SELECT date, open, high, low, close, volume
                    FROM stock_prices
                    WHERE symbol = ?
                    ORDER BY date
                """
                df = pd.read_sql_query(query, conn, params=(stock_code,))
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                return df
        except Exception as e:
            print(f"❌ 주가 데이터 조회 실패 ({stock_code}): {e}")
            return pd.DataFrame()
    
    def get_buffett_score(self, stock_code):
        """버핏 스코어 조회 (임시로 간단한 계산)"""
        try:
            with sqlite3.connect(self.dart_db_path) as conn:
                # 기본적인 재무비율만 계산 (실제로는 더 복잡한 로직 필요)
                query = """
                    SELECT fs.account_nm, fs.thstrm_amount
                    FROM financial_statements fs
                    JOIN company_info ci ON fs.corp_code = ci.corp_code
                    WHERE ci.stock_code = ? AND fs.bsns_year = '2023'
                    AND fs.account_nm IN ('자산총계', '부채총계', '자본총계', '당기순이익', '매출액')
                """
                result = pd.read_sql_query(query, conn, params=(stock_code,))
                
                if result.empty:
                    return 50  # 기본값
                
                # 간단한 스코어 계산 (실제로는 더 정교한 로직 필요)
                accounts = {}
                for _, row in result.iterrows():
                    try:
                        amount = float(str(row['thstrm_amount']).replace(',', ''))
                        accounts[row['account_nm']] = amount
                    except:
                        continue
                
                score = 50  # 기본 점수
                
                # ROE 계산
                if '당기순이익' in accounts and '자본총계' in accounts and accounts['자본총계'] > 0:
                    roe = accounts['당기순이익'] / accounts['자본총계'] * 100
                    if roe >= 15:
                        score += 20
                    elif roe >= 10:
                        score += 10
                
                # 부채비율 계산
                if '부채총계' in accounts and '자본총계' in accounts and accounts['자본총계'] > 0:
                    debt_ratio = accounts['부채총계'] / accounts['자본총계'] * 100
                    if debt_ratio <= 30:
                        score += 20
                    elif debt_ratio <= 50:
                        score += 10
                
                return min(100, score)
                
        except Exception as e:
            print(f"❌ 버핏 스코어 계산 실패 ({stock_code}): {e}")
            return 50
    
    def get_news_sentiment(self, stock_code):
        """뉴스 감정 점수 조회"""
        try:
            if not Path(self.news_db_path).exists():
                return 0.0
            
            with sqlite3.connect(self.news_db_path) as conn:
                query = """
                    SELECT AVG(sentiment_score) as avg_sentiment
                    FROM news_articles
                    WHERE stock_code = ?
                    AND DATE(published_date) >= DATE('now', '-7 days')
                """
                result = pd.read_sql_query(query, conn, params=(stock_code,))
                
                if not result.empty and result.iloc[0]['avg_sentiment'] is not None:
                    return result.iloc[0]['avg_sentiment']
                else:
                    return 0.0
                    
        except Exception as e:
            print(f"❌ 뉴스 감정 조회 실패 ({stock_code}): {e}")
            return 0.0
    
    def quality_dip_signal(self, stock_code):
        """우량주 일시 급락 매수 신호"""
        try:
            # 1. 주가 데이터 조회
            price_data = self.get_stock_price_data(stock_code)
            if price_data.empty:
                return None
            
            # 2. 버핏 스코어 확인
            buffett_score = self.get_buffett_score(stock_code)
            
            # 3. 기술적 지표 계산
            ma_data = self.trend_indicators.moving_average_200(price_data['close'])
            rsi_data = self.momentum_indicators.rsi_monthly(price_data['close'])
            
            # 4. 뉴스 감정 확인
            sentiment_score = self.get_news_sentiment(stock_code)
            
            if not ma_data or not rsi_data:
                return None
            
            # 5. 신호 조건 확인
            is_quality_stock = buffett_score >= 80
            is_significant_dip = ma_data['price_vs_ma_pct'] <= -15
            is_oversold = rsi_data['rsi'] <= 30
            is_sentiment_negative = sentiment_score < -0.2
            
            # 신호 강도 계산
            signal_strength = 0
            conditions = []
            
            if is_quality_stock:
                signal_strength += 40
                conditions.append(f"우량주 (버핏스코어: {buffett_score:.0f}점)")
            
            if is_significant_dip:
                signal_strength += 30
                conditions.append(f"200일선 대비 {ma_data['price_vs_ma_pct']:.1f}% 하락")
            
            if is_oversold:
                signal_strength += 20
                conditions.append(f"RSI 과매도 ({rsi_data['rsi']:.1f})")
            
            if is_sentiment_negative:
                signal_strength += 10
                conditions.append(f"뉴스 감정 악화 ({sentiment_score:.2f})")
            
            # 최종 신호 판정
            if signal_strength >= 70:
                signal_type = 'strong_buy'
                recommendation = "🔥 강력한 매수 신호! 최고의 매수 기회"
            elif signal_strength >= 50:
                signal_type = 'buy'
                recommendation = "✅ 매수 신호, 분할 매수 고려"
            elif signal_strength >= 30:
                signal_type = 'watch'
                recommendation = "👀 관심 종목, 추가 하락 시 매수 준비"
            else:
                signal_type = 'neutral'
                recommendation = "😐 중립, 조건 미충족"
            
            return {
                'signal_type': signal_type,
                'signal_strength': signal_strength,
                'recommendation': recommendation,
                'conditions_met': conditions,
                'buffett_score': buffett_score,
                'price_vs_ma': ma_data['price_vs_ma_pct'],
                'rsi': rsi_data['rsi'],
                'sentiment': sentiment_score,
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"❌ 우량주 급락 신호 분석 실패 ({stock_code}): {e}")
            return None
    
    def accumulation_signal(self, stock_code):
        """장기 누적 매수 신호"""
        try:
            price_data = self.get_stock_price_data(stock_code)
            if price_data.empty:
                return None
            
            # 기술적 지표 계산
            position_data = self.trend_indicators.price_position_analysis(price_data['close'])
            bb_data = self.volatility_indicators.bollinger_bands_value(price_data['close'])
            volatility_data = self.volatility_indicators.volatility_breakout(
                price_data['high'], price_data['low'], price_data['close']
            )
            
            if not all([position_data, bb_data, volatility_data]):
                return None
            
            # 누적 매수 조건
            is_lower_range = position_data['position_pct'] <= 30  # 52주 범위 하위 30%
            is_near_support = volatility_data['box_position_pct'] <= 25  # 박스권 하단
            is_low_volatility = bb_data['squeeze']  # 밴드 수축 (변동성 감소)
            
            # 거래량 증가는 별도 구현 필요 (여기서는 생략)
            
            signal_strength = 0
            conditions = []
            
            if is_lower_range:
                signal_strength += 35
                conditions.append(f"52주 범위 하위 ({position_data['position_pct']:.1f}%)")
            
            if is_near_support:
                signal_strength += 30
                conditions.append(f"박스권 하단 근접 ({volatility_data['box_position_pct']:.1f}%)")
            
            if is_low_volatility:
                signal_strength += 25
                conditions.append("변동성 수축 (볼린저밴드)")
            
            # 추가: 펀더멘털 개선 확인 (간단히 버핏 스코어로 대체)
            buffett_score = self.get_buffett_score(stock_code)
            if buffett_score >= 70:
                signal_strength += 10
                conditions.append(f"양호한 펀더멘털 ({buffett_score:.0f}점)")
            
            # 신호 판정
            if signal_strength >= 70:
                signal_type = 'accumulate'
                recommendation = "📈 누적 매수 시작 - 분할 매수 전략"
            elif signal_strength >= 50:
                signal_type = 'prepare'
                recommendation = "🎯 매수 준비 - 추가 신호 대기"
            else:
                signal_type = 'neutral'
                recommendation = "😐 누적 매수 조건 미충족"
            
            return {
                'signal_type': signal_type,
                'signal_strength': signal_strength,
                'recommendation': recommendation,
                'conditions_met': conditions,
                'position_in_52w_range': position_data['position_pct'],
                'support_level': volatility_data['support_level'],
                'resistance_level': volatility_data['resistance_level'],
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"❌ 누적 매수 신호 분석 실패 ({stock_code}): {e}")
            return None
    
    def breakout_continuation(self, stock_code):
        """상승 돌파 지속 신호"""
        try:
            price_data = self.get_stock_price_data(stock_code)
            if price_data.empty:
                return None
            
            # 기술적 지표 계산
            breakout_data = self.volatility_indicators.volatility_breakout(
                price_data['high'], price_data['low'], price_data['close']
            )
            trend_data = self.trend_indicators.trend_strength(
                price_data['high'], price_data['low'], price_data['close']
            )
            ma_data = self.trend_indicators.moving_average_200(price_data['close'])
            
            if not all([breakout_data, trend_data, ma_data]):
                return None
            
            # 돌파 지속 조건
            is_upside_breakout = breakout_data['upside_breakout']
            is_strong_trend = trend_data['adx'] > 25 and trend_data['trend_direction'] == 'bullish'
            is_above_ma = ma_data['price_vs_ma_pct'] > 5  # 200일선 위 5% 이상
            
            # 실적 개선은 간단히 버핏 스코어로 대체
            buffett_score = self.get_buffett_score(stock_code)
            is_fundamental_good = buffett_score >= 70
            
            signal_strength = 0
            conditions = []
            
            if is_upside_breakout:
                signal_strength += 40
                conditions.append(f"상향 돌파 (저항선: {breakout_data['resistance_level']:.0f}원)")
            
            if is_strong_trend:
                signal_strength += 30
                conditions.append(f"강한 상승 추세 (ADX: {trend_data['adx']:.1f})")
            
            if is_above_ma:
                signal_strength += 20
                conditions.append(f"200일선 위 ({ma_data['price_vs_ma_pct']:.1f}%)")
            
            if is_fundamental_good:
                signal_strength += 10
                conditions.append(f"견조한 펀더멘털 ({buffett_score:.0f}점)")
            
            # 신호 판정
            if signal_strength >= 80:
                signal_type = 'strong_continuation'
                recommendation = "🚀 강력한 상승 지속 - 추가 매수 고려"
            elif signal_strength >= 60:
                signal_type = 'continuation'
                recommendation = "📈 상승 지속 가능성 - 보유 지속"
            elif signal_strength >= 40:
                signal_type = 'weak_continuation'
                recommendation = "⚠️ 약한 지속성 - 신중한 접근"
            else:
                signal_type = 'neutral'
                recommendation = "😐 지속 조건 미충족"
            
            return {
                'signal_type': signal_type,
                'signal_strength': signal_strength,
                'recommendation': recommendation,
                'conditions_met': conditions,
                'breakout_level': breakout_data['resistance_level'],
                'trend_strength': trend_data['adx'],
                'ma_position': ma_data['price_vs_ma_pct'],
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"❌ 돌파 지속 신호 분석 실패 ({stock_code}): {e}")
            return None


class TechnicalAnalysisEngine:
    """통합 기술적 분석 엔진"""
    
    def __init__(self):
        self.value_timing = ValueTimingSignals()
    
    def comprehensive_analysis(self, stock_code):
        """종목별 종합 기술적 분석"""
        print(f"📊 {stock_code} 종합 기술적 분석 중...")
        
        results = {
            'stock_code': stock_code,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'quality_dip': self.value_timing.quality_dip_signal(stock_code),
            'accumulation': self.value_timing.accumulation_signal(stock_code),
            'breakout_continuation': self.value_timing.breakout_continuation(stock_code)
        }
        
        # 종합 판단
        signals = []
        if results['quality_dip'] and results['quality_dip']['signal_type'] in ['strong_buy', 'buy']:
            signals.append(results['quality_dip'])
        if results['accumulation'] and results['accumulation']['signal_type'] in ['accumulate', 'prepare']:
            signals.append(results['accumulation'])
        if results['breakout_continuation'] and results['breakout_continuation']['signal_type'] in ['strong_continuation', 'continuation']:
            signals.append(results['breakout_continuation'])
        
        if signals:
            # 가장 강한 신호 선택
            strongest_signal = max(signals, key=lambda x: x['signal_strength'])
            results['recommendation'] = strongest_signal['recommendation']
            results['overall_signal'] = strongest_signal['signal_type']
            results['confidence'] = strongest_signal['signal_strength']
        else:
            results['recommendation'] = "😐 특별한 신호 없음 - 관망"
            results['overall_signal'] = 'neutral'
            results['confidence'] = 0
        
        return results


def main():
    """메인 실행 함수"""
    
    print("📈 워런 버핏 스타일 기술적 분석 엔진")
    print("=" * 60)
    
    # 분석 엔진 초기화
    analyzer = TechnicalAnalysisEngine()
    
    while True:
        print("\n🎯 기술적 분석 메뉴:")
        print("1. 개별 종목 종합 분석")
        print("2. 우량주 급락 신호 스캔")
        print("3. 누적 매수 신호 스캔")
        print("4. 돌파 지속 신호 스캔")
        print("5. 테스트 (삼성전자)")
        print("0. 종료")
        
        choice = input("\n선택하세요 (0-5): ").strip()
        
        if choice == '0':
            print("👋 분석을 종료합니다.")
            break
            
        elif choice == '1':
            stock_code = input("종목코드를 입력하세요 (예: 005930): ").strip()
            if stock_code:
                result = analyzer.comprehensive_analysis(stock_code)
                
                print(f"\n📊 {stock_code} 종합 분석 결과:")
                print("=" * 50)
                print(f"🎯 전체 추천: {result['recommendation']}")
                print(f"📈 종합 신호: {result['overall_signal']}")
                print(f"🔥 신뢰도: {result['confidence']}/100")
                
                # 개별 신호 결과
                for signal_name, signal_data in result.items():
                    if isinstance(signal_data, dict) and 'recommendation' in signal_data:
                        print(f"\n{signal_name.replace('_', ' ').title()}:")
                        print(f"  추천: {signal_data['recommendation']}")
                        if 'conditions_met' in signal_data:
                            print(f"  조건: {', '.join(signal_data['conditions_met'])}")
        
        elif choice == '5':
            # 삼성전자 테스트
            print("\n🧪 삼성전자(005930) 테스트 분석...")
            result = analyzer.comprehensive_analysis('005930')
            
            print("\n📊 삼성전자 분석 결과:")
            print("=" * 50)
            print(f"🎯 전체 추천: {result['recommendation']}")
            print(f"📈 종합 신호: {result['overall_signal']}")
            print(f"🔥 신뢰도: {result['confidence']}/100")
            
            if result['quality_dip']:
                print(f"\n우량주 급락 신호: {result['quality_dip']['recommendation']}")
            if result['accumulation']:
                print(f"누적 매수 신호: {result['accumulation']['recommendation']}")
            if result['breakout_continuation']:
                print(f"돌파 지속 신호: {result['breakout_continuation']['recommendation']}")
        
        else:
            print("❌ 아직 구현되지 않은 기능입니다.")


if __name__ == "__main__":
    main()