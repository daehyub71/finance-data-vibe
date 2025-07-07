"""
📈 워런 버핏 스타일 기술적 분석 시스템
TA-Lib 없이 가치투자 최적화 기술 지표 구현

기본분석(45%) : 기술분석(30%) : 뉴스분석(25%) 비율 반영
장기투자 관점의 기술 지표만 선별 구현
"""

import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class BuffettStyleTechnicalAnalysis:
    """
    워런 버핏 스타일 기술적 분석 시스템
    
    가치투자에 최적화된 기술 지표들만 선별 구현:
    - 장기 추세 지표 (200일 이동평균)
    - 모멘텀 지표 (RSI, 스토캐스틱)
    - 변동성 지표 (볼린저 밴드)
    - 거래량 지표 (OBV)
    """
    
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.stock_db_path = self.data_dir / 'stock_data.db'
        
        # 워런 버핏 스타일 매매 기준
        self.value_criteria = {
            'oversold_rsi': 30,      # RSI 30 이하 시 관심
            'ma200_support': 0.95,   # 200일선 5% 이내 지지
            'bb_lower_touch': 0.02,  # 볼린저밴드 하단 2% 이내
            'volume_surge': 1.5      # 거래량 1.5배 이상 급증
        }
        
        print("✅ 워런 버핏 스타일 기술적 분석 시스템 초기화 완료")
    
    def get_stock_data(self, symbol, days=500):
        """주식 데이터 조회 (장기 분석용)"""
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
                
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').set_index('date')
                
                return df
                
        except Exception as e:
            print(f"❌ 데이터 조회 실패: {e}")
            return None
    
    def calculate_moving_averages(self, df):
        """이동평균선 계산 (장기투자 핵심)"""
        # 워런 버핏이 중시하는 장기 이동평균
        df['MA20'] = df['close'].rolling(window=20).mean()    # 단기 추세
        df['MA60'] = df['close'].rolling(window=60).mean()    # 중기 추세  
        df['MA200'] = df['close'].rolling(window=200).mean()  # 장기 추세 (핵심)
        
        # 200일선 대비 현재가 위치 (중요 지표)
        df['price_vs_ma200'] = (df['close'] / df['MA200'] - 1) * 100
        
        # 이동평균 정배열 여부 (상승 추세 확인)
        df['ma_golden_cross'] = (df['MA20'] > df['MA60']) & (df['MA60'] > df['MA200'])
        
        return df
    
    def calculate_rsi(self, df, period=14):
        """RSI 계산 (과매수/과매도 판단)"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 워런 버핏 스타일: RSI 30 이하에서만 매수 관심
        df['rsi_oversold'] = df['RSI'] < self.value_criteria['oversold_rsi']
        
        return df
    
    def calculate_stochastic(self, df, k_period=14, d_period=3):
        """스토캐스틱 계산 (장기 매수 타이밍)"""
        lowest_low = df['low'].rolling(window=k_period).min()
        highest_high = df['high'].rolling(window=k_period).max()
        
        df['%K'] = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
        df['%D'] = df['%K'].rolling(window=d_period).mean()
        
        # 20 이하에서 골든크로스 시 매수 신호
        df['stoch_oversold'] = (df['%K'] < 20) & (df['%D'] < 20)
        df['stoch_golden_cross'] = (df['%K'] > df['%D']) & df['stoch_oversold'].shift(1)
        
        return df
    
    def calculate_bollinger_bands(self, df, period=20, std_dev=2):
        """볼린저 밴드 계산 (변동성 분석)"""
        df['BB_Middle'] = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        
        df['BB_Upper'] = df['BB_Middle'] + (std * std_dev)
        df['BB_Lower'] = df['BB_Middle'] - (std * std_dev)
        
        # 볼린저밴드 위치 계산 (0~1, 0.5가 중앙)
        df['BB_Position'] = (df['close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
        
        # 하단 터치 시 매수 관심 (워런 버핏: 공포할 때 매수)
        df['bb_lower_touch'] = df['BB_Position'] < self.value_criteria['bb_lower_touch']
        
        return df
    
    def calculate_obv(self, df):
        """OBV (On Balance Volume) 계산"""
        obv = [0]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.append(obv[-1] + df['volume'].iloc[i])
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.append(obv[-1] - df['volume'].iloc[i])
            else:
                obv.append(obv[-1])
        
        df['OBV'] = obv
        df['OBV_MA'] = df['OBV'].rolling(window=20).mean()
        
        # OBV 상승 다이버전스 (가격은 하락, OBV는 상승)
        df['obv_divergence'] = (df['OBV'] > df['OBV_MA']) & (df['close'] < df['MA20'])
        
        return df
    
    def calculate_volume_analysis(self, df):
        """거래량 분석 (관심도 측정)"""
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # 거래량 급증 (관심 증가 신호)
        df['volume_surge'] = df['volume_ratio'] > self.value_criteria['volume_surge']
        
        return df
    
    def generate_buffett_signals(self, df):
        """워런 버핏 스타일 매매 신호 생성"""
        
        # 🟢 매수 신호 (모든 조건 만족 시)
        buy_conditions = [
            df['rsi_oversold'],           # RSI 과매도
            df['bb_lower_touch'],         # 볼린저밴드 하단 터치
            df['price_vs_ma200'] > -20,   # 200일선 대비 20% 이내 하락
            df['volume_surge']            # 거래량 급증
        ]
        
        df['buffett_buy_signal'] = pd.concat(buy_conditions, axis=1).all(axis=1)
        
        # 🔵 관심 신호 (부분 조건 만족)
        interest_conditions = [
            df['rsi_oversold'],
            df['price_vs_ma200'] > -15,   # 200일선 대비 15% 이내
        ]
        
        df['buffett_interest'] = pd.concat(interest_conditions, axis=1).all(axis=1)
        
        # 🔴 매도 경고 (기술적 악화)
        sell_warning_conditions = [
            df['RSI'] > 70,               # RSI 과매수
            df['close'] < df['MA200'] * 0.9,  # 200일선 10% 하향 이탈
            ~df['ma_golden_cross']        # 이평선 정배열 깨짐
        ]
        
        df['sell_warning'] = pd.concat(sell_warning_conditions, axis=1).any(axis=1)
        
        return df
    
    def analyze_stock(self, symbol):
        """종목별 종합 기술적 분석"""
        print(f"📈 {symbol} 워런 버핏 스타일 기술적 분석")
        print("=" * 50)
        
        # 데이터 가져오기
        df = self.get_stock_data(symbol)
        if df is None:
            print("❌ 데이터가 없습니다.")
            return None
        
        # 모든 지표 계산
        df = self.calculate_moving_averages(df)
        df = self.calculate_rsi(df)
        df = self.calculate_stochastic(df)
        df = self.calculate_bollinger_bands(df)
        df = self.calculate_obv(df)
        df = self.calculate_volume_analysis(df)
        df = self.generate_buffett_signals(df)
        
        # 최신 상태 분석
        latest = df.iloc[-1]
        
        print(f"📅 분석 기준일: {latest.name.strftime('%Y-%m-%d')}")
        print(f"💰 현재가: {latest['close']:,}원")
        print()
        
        # 장기 추세 분석
        print("🔍 장기 추세 분석 (워런 버핏 관점)")
        print(f"   📊 200일 이동평균: {latest['MA200']:,.0f}원")
        print(f"   📈 200일선 대비: {latest['price_vs_ma200']:+.1f}%")
        print(f"   ✅ 이평선 정배열: {'예' if latest['ma_golden_cross'] else '아니오'}")
        print()
        
        # 모멘텀 분석
        print("⚡ 모멘텀 분석")
        print(f"   📉 RSI(14): {latest['RSI']:.1f}")
        print(f"   📊 스토캐스틱 %K: {latest['%K']:.1f}")
        print(f"   🎯 과매도 상태: {'예' if latest['rsi_oversold'] else '아니오'}")
        print()
        
        # 변동성 분석
        print("📊 볼린저 밴드 분석")
        print(f"   🔺 상단: {latest['BB_Upper']:,.0f}원")
        print(f"   ➖ 중앙: {latest['BB_Middle']:,.0f}원")  
        print(f"   🔻 하단: {latest['BB_Lower']:,.0f}원")
        print(f"   📍 현재 위치: {latest['BB_Position']:.2f} (0=하단, 1=상단)")
        print()
        
        # 거래량 분석
        print("📊 거래량 분석")
        print(f"   📈 오늘 거래량: {latest['volume']:,}주")
        print(f"   📊 평균 대비: {latest['volume_ratio']:.1f}배")
        print(f"   🚀 거래량 급증: {'예' if latest['volume_surge'] else '아니오'}")
        print()
        
        # 워런 버핏 신호 종합
        print("🎯 워런 버핏 스타일 종합 판단")
        if latest['buffett_buy_signal']:
            print("   🟢 매수 신호: 강력 추천!")
            print("      └ 과매도 + 볼린저밴드 하단 + 거래량 급증")
        elif latest['buffett_interest']:
            print("   🔵 관심 종목: 지켜볼 만함")
            print("      └ 일부 조건 만족, 추가 하락 시 매수 고려")
        elif latest['sell_warning']:
            print("   🔴 매도 경고: 기술적 악화")
            print("      └ 과매수 또는 장기 지지선 이탈")
        else:
            print("   ⚪ 중립: 특별한 신호 없음")
        print()
        
        # 최근 신호 이력
        recent_signals = df[['buffett_buy_signal', 'buffett_interest', 'sell_warning']].tail(10)
        buy_signals = recent_signals['buffett_buy_signal'].sum()
        interest_signals = recent_signals['buffett_interest'].sum()
        
        print(f"📅 최근 10일간 신호")
        print(f"   🟢 매수 신호: {buy_signals}회")
        print(f"   🔵 관심 신호: {interest_signals}회")
        
        return df
    
    def create_technical_chart(self, symbol, df=None):
        """기술적 분석 차트 생성"""
        if df is None:
            df = self.analyze_stock(symbol)
            if df is None:
                return
        
        # 최근 120일 데이터만 표시
        df_chart = df.tail(120).copy()
        
        # 차트 설정
        plt.style.use('default')
        fig, axes = plt.subplots(4, 1, figsize=(15, 12))
        fig.suptitle(f'{symbol} 워런 버핏 스타일 기술적 분석 차트', fontsize=16, fontweight='bold')
        
        # 1. 주가 + 이동평균 + 볼린저밴드
        ax1 = axes[0]
        ax1.plot(df_chart.index, df_chart['close'], label='종가', linewidth=2, color='black')
        ax1.plot(df_chart.index, df_chart['MA20'], label='MA20', alpha=0.7, color='blue')
        ax1.plot(df_chart.index, df_chart['MA60'], label='MA60', alpha=0.7, color='orange')
        ax1.plot(df_chart.index, df_chart['MA200'], label='MA200', alpha=0.8, color='red', linewidth=2)
        
        # 볼린저밴드
        ax1.fill_between(df_chart.index, df_chart['BB_Upper'], df_chart['BB_Lower'], 
                        alpha=0.1, color='gray', label='볼린저밴드')
        ax1.plot(df_chart.index, df_chart['BB_Upper'], '--', alpha=0.5, color='gray')
        ax1.plot(df_chart.index, df_chart['BB_Lower'], '--', alpha=0.5, color='gray')
        
        # 매수 신호 표시
        buy_signals = df_chart[df_chart['buffett_buy_signal']]
        ax1.scatter(buy_signals.index, buy_signals['close'], 
                   color='green', s=100, marker='^', label='매수신호', zorder=5)
        
        ax1.set_title('주가 + 이동평균 + 볼린저밴드')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. RSI
        ax2 = axes[1]
        ax2.plot(df_chart.index, df_chart['RSI'], label='RSI(14)', color='purple', linewidth=2)
        ax2.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='과매수(70)')
        ax2.axhline(y=30, color='green', linestyle='--', alpha=0.7, label='과매도(30)')
        ax2.axhline(y=50, color='gray', linestyle='-', alpha=0.3)
        ax2.set_ylim(0, 100)
        ax2.set_title('RSI (상대강도지수)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. 스토캐스틱
        ax3 = axes[2]
        ax3.plot(df_chart.index, df_chart['%K'], label='%K', color='blue')
        ax3.plot(df_chart.index, df_chart['%D'], label='%D', color='red')
        ax3.axhline(y=80, color='red', linestyle='--', alpha=0.7, label='과매수')
        ax3.axhline(y=20, color='green', linestyle='--', alpha=0.7, label='과매도')
        ax3.set_ylim(0, 100)
        ax3.set_title('스토캐스틱')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 4. 거래량
        ax4 = axes[3]
        colors = ['red' if vol > avg else 'blue' for vol, avg in 
                 zip(df_chart['volume'], df_chart['volume_ma'])]
        ax4.bar(df_chart.index, df_chart['volume'], color=colors, alpha=0.7, label='거래량')
        ax4.plot(df_chart.index, df_chart['volume_ma'], color='orange', 
                linewidth=2, label='거래량 MA20')
        ax4.set_title('거래량')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
    
    def screen_buffett_opportunities(self, min_signals=2):
        """워런 버핏 스타일 기회 종목 스크리닝"""
        print("🔍 워런 버핏 스타일 기술적 기회 종목 스크리닝")
        print("=" * 60)
        
        try:
            # 모든 종목 리스트 가져오기
            with sqlite3.connect(self.stock_db_path) as conn:
                stocks_query = """
                    SELECT DISTINCT symbol, name 
                    FROM stock_info 
                    WHERE symbol IS NOT NULL 
                    ORDER BY symbol
                    LIMIT 50
                """
                stocks_df = pd.read_sql_query(stocks_query, conn)
            
            opportunities = []
            
            for _, stock in stocks_df.iterrows():
                symbol = stock['symbol']
                name = stock['name']
                
                try:
                    df = self.get_stock_data(symbol, days=200)
                    if df is None or len(df) < 100:
                        continue
                    
                    # 기술적 지표 계산
                    df = self.calculate_moving_averages(df)
                    df = self.calculate_rsi(df)
                    df = self.calculate_bollinger_bands(df)
                    df = self.calculate_volume_analysis(df)
                    df = self.generate_buffett_signals(df)
                    
                    latest = df.iloc[-1]
                    
                    # 최근 신호 개수 계산
                    recent_signals = df.tail(5)
                    buy_signal_count = recent_signals['buffett_buy_signal'].sum()
                    interest_count = recent_signals['buffett_interest'].sum()
                    
                    signal_score = buy_signal_count * 2 + interest_count
                    
                    if signal_score >= min_signals:
                        opportunities.append({
                            'symbol': symbol,
                            'name': name,
                            'current_price': latest['close'],
                            'ma200_diff': latest['price_vs_ma200'],
                            'rsi': latest['RSI'],
                            'bb_position': latest['BB_Position'],
                            'volume_ratio': latest['volume_ratio'],
                            'signal_score': signal_score,
                            'buy_signals': buy_signal_count,
                            'interest_signals': interest_count
                        })
                
                except Exception as e:
                    continue
            
            # 결과 정렬 및 출력
            opportunities = sorted(opportunities, key=lambda x: x['signal_score'], reverse=True)
            
            if opportunities:
                print(f"📊 발견된 기회 종목: {len(opportunities)}개")
                print()
                
                for i, opp in enumerate(opportunities[:10], 1):
                    print(f"🏆 {i}. {opp['symbol']} ({opp['name']})")
                    print(f"   💰 현재가: {opp['current_price']:,}원")
                    print(f"   📊 200일선 대비: {opp['ma200_diff']:+.1f}%")
                    print(f"   📉 RSI: {opp['rsi']:.1f}")
                    print(f"   📍 볼린저밴드 위치: {opp['bb_position']:.2f}")
                    print(f"   📈 거래량 비율: {opp['volume_ratio']:.1f}배")
                    print(f"   🎯 신호 점수: {opp['signal_score']}점 (매수:{opp['buy_signals']}, 관심:{opp['interest_signals']})")
                    print()
            else:
                print("❌ 현재 조건을 만족하는 종목이 없습니다.")
                
            return opportunities
            
        except Exception as e:
            print(f"❌ 스크리닝 실패: {e}")
            return []


def main():
    """메인 실행 함수"""
    print("🚀 워런 버핏 스타일 기술적 분석 시스템")
    print("=" * 60)
    print("📊 기본분석(45%) : 기술분석(30%) : 뉴스분석(25%)")
    print("🎯 장기투자 관점의 기술적 매수 타이밍 포착")
    print()
    
    # 분석 시스템 초기화
    analyzer = BuffettStyleTechnicalAnalysis()
    
    while True:
        print("\n📈 원하는 기능을 선택하세요:")
        print("1. 개별 종목 기술적 분석")
        print("2. 종목 기술적 분석 차트")
        print("3. 워런 버핏 기회 종목 스크리닝")
        print("4. 삼성전자 분석 (예시)")
        print("0. 종료")
        
        choice = input("\n선택하세요 (0-4): ").strip()
        
        if choice == '0':
            print("👋 분석을 종료합니다.")
            break
            
        elif choice == '1':
            symbol = input("종목코드를 입력하세요 (예: 005930): ").strip()
            if symbol:
                analyzer.analyze_stock(symbol)
            
        elif choice == '2':
            symbol = input("종목코드를 입력하세요 (예: 005930): ").strip()
            if symbol:
                analyzer.create_technical_chart(symbol)
            
        elif choice == '3':
            print("🔍 워런 버핏 스타일 기회 종목 스크리닝 중...")
            analyzer.screen_buffett_opportunities()
            
        elif choice == '4':
            print("📊 삼성전자 기술적 분석 (예시)")
            analyzer.analyze_stock('005930')
            
        else:
            print("❌ 올바른 번호를 선택해주세요.")


if __name__ == "__main__":
    main()