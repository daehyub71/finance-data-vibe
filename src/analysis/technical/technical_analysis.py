"""
📈 기술적 분석 시스템 (가치투자 최적화 버전)
src/analysis/technical/technical_analysis.py

이 모듈은 워런 버핏 스타일 가치투자를 위한 기술적 분석 도구입니다.
기본분석(45%) : 기술분석(30%) : 뉴스분석(25%) 비율에 맞춰 설계되었습니다.

주요 기능:
1. 장기투자 최적화 지표 (200일 이평, 52주 신고가/신저가)
2. 가치투자 매수 타이밍 (기술적 과매도 + 저평가 확인)
3. 분할매수 시스템 (Dollar Cost Averaging)
4. 리밸런싱 알고리즘 (연 2회 포트폴리오 조정)

🎯 목표: 가치 저평가 종목의 최적 매수 타이밍 포착
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import talib
except ImportError as e:
    print(f"❌ 패키지 설치 필요: {e}")
    print("pip install plotly talib 실행하세요!")
    exit(1)


class ValueInvestingTechnicalAnalyzer:
    """
    가치투자 최적화 기술적 분석기
    
    워런 버핏 스타일 장기투자를 위한 기술적 지표와 
    매수 타이밍 최적화 도구를 제공합니다.
    """
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.stock_db_path = self.data_dir / 'stock_data.db'
        self.dart_db_path = self.data_dir / 'dart_data.db'
        
        # 가치투자 기술지표 설정
        self.long_term_indicators = {
            'sma_periods': [20, 60, 120, 200],  # 장기 이동평균
            'ema_periods': [12, 26, 50],        # 지수이동평균
            'rsi_period': 14,                   # RSI
            'macd_periods': (12, 26, 9),        # MACD
            'bb_period': 20,                    # 볼린저밴드
            'volume_sma': 30                    # 거래량 이평
        }
        
        # 워런 버핏 스타일 매수 기준
        self.buying_criteria = {
            'oversold_rsi': 30,           # RSI 과매도
            'below_bb_lower': True,       # 볼린저밴드 하단 이하
            'below_200sma': 0.95,         # 200일선 대비 5% 이하
            'volume_surge': 1.5,          # 평균 거래량 1.5배 이상
            '52w_low_ratio': 0.2          # 52주 최저가 대비 20% 이내
        }
        
        print("✅ 가치투자 기술적 분석기 초기화 완료")
    
    def get_stock_data(self, symbol, days=500):
        """주식 데이터 조회 (기술적 분석용 충분한 기간)"""
        try:
            with sqlite3.connect(self.stock_db_path) as conn:
                query = """
                    SELECT date, open, high, low, close, volume
                    FROM stock_prices 
                    WHERE symbol = ?
                    ORDER BY date DESC
                    LIMIT ?
                """
                
                df = pd.read_sql_query(query, conn, params=(symbol, days))
                
                if df.empty:
                    return None
                
                # 날짜순 정렬 및 인덱스 설정
                df = df.sort_values('date')
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                
                # 컬럼명 표준화 (TA-Lib 호환)
                df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                
                return df
                
        except Exception as e:
            print(f"❌ 데이터 조회 실패 ({symbol}): {e}")
            return None
    
    def calculate_long_term_indicators(self, df):
        """장기투자 최적화 기술적 지표 계산"""
        if df is None or len(df) < 200:
            print("⚠️ 데이터가 부족합니다 (최소 200일 필요)")
            return None
        
        indicators = df.copy()
        
        try:
            # 1. 장기 이동평균선들 (추세 확인용)
            for period in self.long_term_indicators['sma_periods']:
                indicators[f'SMA_{period}'] = talib.SMA(df['Close'], timeperiod=period)
            
            # 2. 지수이동평균 (단기 반응성)
            for period in self.long_term_indicators['ema_periods']:
                indicators[f'EMA_{period}'] = talib.EMA(df['Close'], timeperiod=period)
            
            # 3. MACD (추세 전환 신호)
            macd, macd_signal, macd_hist = talib.MACD(
                df['Close'], 
                fastperiod=self.long_term_indicators['macd_periods'][0],
                slowperiod=self.long_term_indicators['macd_periods'][1],
                signalperiod=self.long_term_indicators['macd_periods'][2]
            )
            indicators['MACD'] = macd
            indicators['MACD_Signal'] = macd_signal
            indicators['MACD_Hist'] = macd_hist
            
            # 4. RSI (과매수/과매도)
            indicators['RSI'] = talib.RSI(df['Close'], timeperiod=self.long_term_indicators['rsi_period'])
            
            # 5. 볼린저 밴드 (변동성 구간)
            bb_upper, bb_middle, bb_lower = talib.BBANDS(
                df['Close'], 
                timeperiod=self.long_term_indicators['bb_period']
            )
            indicators['BB_Upper'] = bb_upper
            indicators['BB_Middle'] = bb_middle
            indicators['BB_Lower'] = bb_lower
            indicators['BB_Width'] = (bb_upper - bb_lower) / bb_middle * 100
            
            # 6. 거래량 지표
            indicators['Volume_SMA'] = talib.SMA(df['Volume'], timeperiod=self.long_term_indicators['volume_sma'])
            indicators['Volume_Ratio'] = df['Volume'] / indicators['Volume_SMA']
            
            # 7. 가격 포지션 지표
            indicators['Price_vs_200SMA'] = df['Close'] / indicators['SMA_200']
            indicators['52W_High'] = df['High'].rolling(window=252).max()
            indicators['52W_Low'] = df['Low'].rolling(window=252).min()
            indicators['52W_Position'] = (df['Close'] - indicators['52W_Low']) / (indicators['52W_High'] - indicators['52W_Low'])
            
            # 8. ATR (Average True Range) - 변동성 측정
            indicators['ATR'] = talib.ATR(df['High'], df['Low'], df['Close'], timeperiod=14)
            indicators['ATR_Percent'] = indicators['ATR'] / df['Close'] * 100
            
            print(f"✅ 기술적 지표 계산 완료 ({len(indicators)}일)")
            return indicators
            
        except Exception as e:
            print(f"❌ 기술적 지표 계산 실패: {e}")
            return None
    
    def identify_value_buying_signals(self, indicators_df):
        """가치투자 매수 신호 식별"""
        if indicators_df is None:
            return None
        
        df = indicators_df.copy()
        
        # 워런 버핏 스타일 매수 조건들
        signals = pd.DataFrame(index=df.index)
        
        # 1. 기술적 과매도 조건
        signals['RSI_Oversold'] = df['RSI'] < self.buying_criteria['oversold_rsi']
        signals['Below_BB_Lower'] = df['Close'] < df['BB_Lower']
        signals['Below_200SMA'] = df['Price_vs_200SMA'] < self.buying_criteria['below_200sma']
        
        # 2. 52주 저점 근처 (장기 관점 저점)
        signals['Near_52W_Low'] = df['52W_Position'] < self.buying_criteria['52w_low_ratio']
        
        # 3. 거래량 급증 (관심도 증가)
        signals['Volume_Surge'] = df['Volume_Ratio'] > self.buying_criteria['volume_surge']
        
        # 4. MACD 바닥 신호
        signals['MACD_Bullish'] = (df['MACD'] > df['MACD_Signal']) & (df['MACD'].shift(1) <= df['MACD_Signal'].shift(1))
        
        # 5. 종합 매수 신호 (3개 이상 조건 만족)
        technical_conditions = ['RSI_Oversold', 'Below_BB_Lower', 'Below_200SMA', 'Near_52W_Low']
        signals['Technical_Score'] = signals[technical_conditions].sum(axis=1)
        signals['Strong_Buy_Signal'] = (signals['Technical_Score'] >= 3) & signals['Volume_Surge']
        signals['Moderate_Buy_Signal'] = (signals['Technical_Score'] >= 2) & signals['Volume_Surge']
        
        # 6. 분할매수 구간 설정
        signals['DCA_Zone'] = signals['Technical_Score'] >= 2  # Dollar Cost Averaging 구간
        
        return signals
    
    def calculate_position_sizing(self, indicators_df, total_capital=10000000):
        """포지션 사이징 계산 (ATR 기반 리스크 관리)"""
        if indicators_df is None:
            return None
        
        df = indicators_df.copy()
        
        # 1. ATR 기반 리스크 계산
        risk_per_share = df['ATR'] * 2  # 2 ATR을 손절 기준으로
        risk_percent = 0.02  # 계좌의 2%를 리스크로 설정
        
        # 2. 적정 매수 수량 계산
        risk_amount = total_capital * risk_percent
        position_size = risk_amount / risk_per_share
        position_value = position_size * df['Close']
        
        # 3. 최대 포지션 제한 (계좌의 20%)
        max_position_value = total_capital * 0.2
        position_value = np.minimum(position_value, max_position_value)
        
        df['Suggested_Shares'] = position_value / df['Close']
        df['Position_Value'] = position_value
        df['Risk_Per_Share'] = risk_per_share
        
        return df
    
    def create_technical_chart(self, symbol, indicators_df, signals_df):
        """가치투자 기술적 분석 차트 생성"""
        if indicators_df is None or signals_df is None:
            return None
        
        # 최근 200일 데이터만 차트에 표시
        df = indicators_df.tail(200).copy()
        sig = signals_df.tail(200).copy()
        
        # 서브플롯 생성
        fig = make_subplots(
            rows=4, cols=1,
            row_heights=[0.5, 0.2, 0.15, 0.15],
            subplot_titles=(
                f'{symbol} 가격 & 장기 이동평균',
                '거래량 & 신호',
                'RSI & 과매수/과매도',
                'MACD & 추세 전환'
            ),
            vertical_spacing=0.05,
            shared_xaxes=True
        )
        
        # 1. 메인 가격 차트
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'],
            name='가격',
            increasing_line_color='red',
            decreasing_line_color='blue'
        ), row=1, col=1)
        
        # 장기 이동평균선들
        colors = ['orange', 'purple', 'brown', 'black']
        for i, period in enumerate([20, 60, 120, 200]):
            fig.add_trace(go.Scatter(
                x=df.index, y=df[f'SMA_{period}'],
                line=dict(color=colors[i], width=1),
                name=f'SMA {period}일'
            ), row=1, col=1)
        
        # 볼린저 밴드
        fig.add_trace(go.Scatter(
            x=df.index, y=df['BB_Upper'],
            line=dict(color='gray', width=1, dash='dash'),
            name='볼린저 상단', showlegend=False
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df['BB_Lower'],
            line=dict(color='gray', width=1, dash='dash'),
            fill='tonexty', fillcolor='rgba(128,128,128,0.1)',
            name='볼린저 하단'
        ), row=1, col=1)
        
        # 매수 신호 표시
        buy_signals = sig[sig['Strong_Buy_Signal']].index
        if len(buy_signals) > 0:
            fig.add_trace(go.Scatter(
                x=buy_signals,
                y=df.loc[buy_signals, 'Close'],
                mode='markers',
                marker=dict(symbol='triangle-up', size=15, color='red'),
                name='강력 매수 신호'
            ), row=1, col=1)
        
        moderate_buy_signals = sig[sig['Moderate_Buy_Signal'] & ~sig['Strong_Buy_Signal']].index
        if len(moderate_buy_signals) > 0:
            fig.add_trace(go.Scatter(
                x=moderate_buy_signals,
                y=df.loc[moderate_buy_signals, 'Close'],
                mode='markers',
                marker=dict(symbol='circle', size=10, color='orange'),
                name='중간 매수 신호'
            ), row=1, col=1)
        
        # 2. 거래량 차트
        colors = ['red' if close >= open else 'blue' 
                 for close, open in zip(df['Close'], df['Open'])]
        
        fig.add_trace(go.Bar(
            x=df.index, y=df['Volume'],
            marker_color=colors,
            name='거래량', opacity=0.7
        ), row=2, col=1)
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df['Volume_SMA'],
            line=dict(color='black', width=2),
            name='거래량 이평'
        ), row=2, col=1)
        
        # 3. RSI 차트
        fig.add_trace(go.Scatter(
            x=df.index, y=df['RSI'],
            line=dict(color='purple', width=2),
            name='RSI'
        ), row=3, col=1)
        
        # RSI 과매수/과매도 라인
        fig.add_hline(y=70, line_dash="dash", line_color="red", 
                     annotation_text="과매수", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", 
                     annotation_text="과매도", row=3, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color="gray", row=3, col=1)
        
        # 4. MACD 차트
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MACD'],
            line=dict(color='blue', width=2),
            name='MACD'
        ), row=4, col=1)
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MACD_Signal'],
            line=dict(color='red', width=2),
            name='MACD Signal'
        ), row=4, col=1)
        
        # MACD 히스토그램
        colors = ['red' if val >= 0 else 'blue' for val in df['MACD_Hist']]
        fig.add_trace(go.Bar(
            x=df.index, y=df['MACD_Hist'],
            marker_color=colors,
            name='MACD Hist', opacity=0.7
        ), row=4, col=1)
        
        # 레이아웃 설정
        fig.update_layout(
            title=f'📈 {symbol} 가치투자 기술적 분석 (최근 200일)',
            xaxis_rangeslider_visible=False,
            height=1000,
            showlegend=True,
            template='plotly_white'
        )
        
        # Y축 레이블
        fig.update_yaxes(title_text="가격 (원)", row=1, col=1)
        fig.update_yaxes(title_text="거래량", row=2, col=1)
        fig.update_yaxes(title_text="RSI", row=3, col=1)
        fig.update_yaxes(title_text="MACD", row=4, col=1)
        
        return fig
    
    def analyze_stock_timing(self, symbol):
        """특정 종목의 매수 타이밍 종합 분석"""
        print(f"\n🔍 {symbol} 기술적 분석 시작...")
        
        # 1. 데이터 조회
        df = self.get_stock_data(symbol, days=500)
        if df is None:
            return None
        
        # 2. 기술적 지표 계산
        indicators = self.calculate_long_term_indicators(df)
        if indicators is None:
            return None
        
        # 3. 매수 신호 식별
        signals = self.identify_value_buying_signals(indicators)
        if signals is None:
            return None
        
        # 4. 포지션 사이징
        indicators = self.calculate_position_sizing(indicators)
        
        # 5. 현재 상태 분석
        latest = indicators.iloc[-1]
        latest_signals = signals.iloc[-1]
        
        analysis_result = {
            'symbol': symbol,
            'analysis_date': latest.name,
            'current_price': latest['Close'],
            'price_vs_200sma': latest['Price_vs_200SMA'],
            '52w_position': latest['52W_Position'],
            'rsi': latest['RSI'],
            'technical_score': latest_signals['Technical_Score'],
            'strong_buy_signal': latest_signals['Strong_Buy_Signal'],
            'moderate_buy_signal': latest_signals['Moderate_Buy_Signal'],
            'dca_zone': latest_signals['DCA_Zone'],
            'suggested_shares': latest['Suggested_Shares'],
            'position_value': latest['Position_Value'],
            'atr_risk': latest['ATR_Percent']
        }
        
        # 6. 분석 결과 출력
        self.print_analysis_summary(analysis_result)
        
        return {
            'indicators': indicators,
            'signals': signals,
            'analysis': analysis_result
        }
    
    def print_analysis_summary(self, analysis):
        """분석 결과 요약 출력"""
        print(f"\n📊 {analysis['symbol']} 기술적 분석 결과")
        print("=" * 50)
        print(f"📅 분석일: {analysis['analysis_date'].strftime('%Y-%m-%d')}")
        print(f"💰 현재가: {analysis['current_price']:,.0f}원")
        print(f"📈 200일선 대비: {analysis['price_vs_200sma']:.3f} ({(analysis['price_vs_200sma']-1)*100:+.1f}%)")
        print(f"📊 52주 포지션: {analysis['52w_position']:.1%}")
        print(f"🎯 RSI: {analysis['rsi']:.1f}")
        print(f"⚡ 기술적 점수: {analysis['technical_score']}/4")
        
        print(f"\n🚦 투자 신호:")
        if analysis['strong_buy_signal']:
            print("🔴 강력 매수 신호! (3개 이상 조건 만족)")
        elif analysis['moderate_buy_signal']:
            print("🟡 중간 매수 신호 (2개 조건 만족)")
        elif analysis['dca_zone']:
            print("🟢 분할매수 구간 (DCA 고려)")
        else:
            print("⚪ 관망 구간")
        
        print(f"\n💼 포지션 제안:")
        print(f"   권장 매수 수량: {analysis['suggested_shares']:.0f}주")
        print(f"   투자 금액: {analysis['position_value']:,.0f}원")
        print(f"   일일 변동성: ±{analysis['atr_risk']:.1f}%")
        print("=" * 50)
    
    def scan_value_buying_opportunities(self, top_n=20):
        """전체 종목 중 가치투자 매수 기회 스캔"""
        print("🔍 전체 종목 기술적 매수 기회 스캔 중...")
        
        # 종목 리스트 가져오기
        try:
            with sqlite3.connect(self.stock_db_path) as conn:
                stocks_query = """
                    SELECT DISTINCT symbol, name 
                    FROM stock_info 
                    ORDER BY symbol
                """
                stocks_df = pd.read_sql_query(stocks_query, conn)
        except Exception as e:
            print(f"❌ 종목 리스트 조회 실패: {e}")
            return None
        
        opportunities = []
        
        for _, stock in stocks_df.head(50).iterrows():  # 테스트를 위해 50개로 제한
            symbol = stock['symbol']
            name = stock['name']
            
            try:
                # 간단한 분석 (상세 분석은 시간 소요)
                df = self.get_stock_data(symbol, days=300)
                if df is None or len(df) < 200:
                    continue
                
                indicators = self.calculate_long_term_indicators(df)
                if indicators is None:
                    continue
                
                signals = self.identify_value_buying_signals(indicators)
                if signals is None:
                    continue
                
                # 최근 상태 확인
                latest = indicators.iloc[-1]
                latest_signals = signals.iloc[-1]
                
                if latest_signals['Strong_Buy_Signal'] or latest_signals['Moderate_Buy_Signal']:
                    opportunities.append({
                        'symbol': symbol,
                        'name': name,
                        'current_price': latest['Close'],
                        'price_vs_200sma': latest['Price_vs_200SMA'],
                        '52w_position': latest['52W_Position'],
                        'rsi': latest['RSI'],
                        'technical_score': latest_signals['Technical_Score'],
                        'signal_type': 'Strong' if latest_signals['Strong_Buy_Signal'] else 'Moderate'
                    })
                
            except Exception as e:
                continue
        
        if opportunities:
            opportunities_df = pd.DataFrame(opportunities)
            opportunities_df = opportunities_df.sort_values(['technical_score', 'rsi'], ascending=[False, True])
            
            print(f"\n🎯 발견된 기술적 매수 기회: {len(opportunities_df)}개")
            print("=" * 80)
            print(opportunities_df.head(top_n).to_string(index=False))
            
            return opportunities_df
        else:
            print("❌ 현재 기술적 매수 기회가 없습니다.")
            return None
    
    def create_portfolio_rebalancing_plan(self, portfolio_symbols, target_weights=None):
        """포트폴리오 리밸런싱 계획 수립"""
        if target_weights is None:
            # 동일 비중 기본값
            target_weights = {symbol: 1/len(portfolio_symbols) for symbol in portfolio_symbols}
        
        print("📊 포트폴리오 리밸런싱 분석 중...")
        
        portfolio_analysis = {}
        
        for symbol in portfolio_symbols:
            analysis_result = self.analyze_stock_timing(symbol)
            if analysis_result:
                portfolio_analysis[symbol] = analysis_result['analysis']
        
        # 리밸런싱 추천
        print(f"\n📈 포트폴리오 리밸런싱 권장사항:")
        print("=" * 60)
        
        for symbol, analysis in portfolio_analysis.items():
            weight = target_weights.get(symbol, 0)
            print(f"\n🏢 {symbol}:")
            print(f"   목표 비중: {weight:.1%}")
            print(f"   기술적 점수: {analysis['technical_score']}/4")
            
            if analysis['strong_buy_signal']:
                print(f"   💡 추천: 비중 확대 고려 (강력 매수 신호)")
            elif analysis['moderate_buy_signal']:
                print(f"   💡 추천: 현재 비중 유지 (중간 매수 신호)")
            else:
                print(f"   💡 추천: 비중 축소 고려 (신호 없음)")
        
        return portfolio_analysis