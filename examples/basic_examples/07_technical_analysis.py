"""
examples/basic_examples/07_technical_analysis.py

기술적 분석 시스템 실행 스크립트
가치투자를 위한 기술적 분석 도구를 쉽게 사용할 수 있습니다.

사용법:
python examples/basic_examples/07_technical_analysis.py
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import sqlite3
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR
    from src.analysis.technical.technical_analysis import ValueInvestingTechnicalAnalyzer
    import talib
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError as e:
    print(f"❌ 패키지 설치 필요: {e}")
    print("다음 명령어를 실행하세요:")
    print("pip install talib plotly")
    print("pip install --upgrade TA-Lib")
    exit(1)

# 한글 폰트 설정 (Windows)
try:
    plt.rcParams['font.family'] = 'Malgun Gothic'  # 맑은 고딕
    plt.rcParams['axes.unicode_minus'] = False
except:
    try:
        plt.rcParams['font.family'] = 'NanumGothic'  # 나눔고딕
        plt.rcParams['axes.unicode_minus'] = False
    except:
        plt.rcParams['font.family'] = 'Batang'  # 바탕체
        plt.rcParams['axes.unicode_minus'] = False

print("✅ 한글 폰트 설정 완료")

class SimpleTechnicalAnalyzer:
    """
    간단한 기술적 분석기
    
    복잡한 기능보다는 실용적이고 빠른 분석에 중점을 둡니다.
    """
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.stock_db_path = self.data_dir / 'stock_data.db'
        print("✅ 간단 기술적 분석기 초기화 완료")
    
    def get_stock_data(self, symbol, days=200):
        """주식 데이터 조회"""
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
                
                df = df.sort_values('date')
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                
                return df
                
        except Exception as e:
            print(f"❌ 데이터 조회 실패: {e}")
            return None
    
    def calculate_basic_indicators(self, df):
        """기본 기술적 지표 계산"""
        if df is None or len(df) < 50:
            print("⚠️ 데이터가 부족합니다")
            return None
        
        indicators = df.copy()
        
        try:
            # 이동평균선
            indicators['SMA_5'] = talib.SMA(df['Close'], timeperiod=5)
            indicators['SMA_20'] = talib.SMA(df['Close'], timeperiod=20)
            indicators['SMA_60'] = talib.SMA(df['Close'], timeperiod=60)
            
            # RSI
            indicators['RSI'] = talib.RSI(df['Close'], timeperiod=14)
            
            # MACD
            macd, macd_signal, macd_hist = talib.MACD(df['Close'])
            indicators['MACD'] = macd
            indicators['MACD_Signal'] = macd_signal
            indicators['MACD_Hist'] = macd_hist
            
            # 볼린저 밴드
            bb_upper, bb_middle, bb_lower = talib.BBANDS(df['Close'])
            indicators['BB_Upper'] = bb_upper
            indicators['BB_Middle'] = bb_middle
            indicators['BB_Lower'] = bb_lower
            
            return indicators
            
        except Exception as e:
            print(f"❌ 지표 계산 실패: {e}")
            return None
    
    def find_signals(self, indicators):
        """매매 신호 찾기"""
        if indicators is None:
            return None
        
        df = indicators.copy()
        signals = pd.DataFrame(index=df.index)
        
        # 골든크로스/데드크로스
        signals['Golden_Cross'] = (df['SMA_5'] > df['SMA_20']) & (df['SMA_5'].shift(1) <= df['SMA_20'].shift(1))
        signals['Dead_Cross'] = (df['SMA_5'] < df['SMA_20']) & (df['SMA_5'].shift(1) >= df['SMA_20'].shift(1))
        
        # RSI 신호
        signals['RSI_Oversold'] = df['RSI'] < 30
        signals['RSI_Overbought'] = df['RSI'] > 70
        
        # 볼린저 밴드 신호
        signals['BB_Lower_Touch'] = df['Close'] < df['BB_Lower']
        signals['BB_Upper_Touch'] = df['Close'] > df['BB_Upper']
        
        # MACD 신호
        signals['MACD_Bullish'] = (df['MACD'] > df['MACD_Signal']) & (df['MACD'].shift(1) <= df['MACD_Signal'].shift(1))
        signals['MACD_Bearish'] = (df['MACD'] < df['MACD_Signal']) & (df['MACD'].shift(1) >= df['MACD_Signal'].shift(1))
        
        # 종합 매수/매도 신호
        buy_conditions = ['Golden_Cross', 'RSI_Oversold', 'BB_Lower_Touch', 'MACD_Bullish']
        sell_conditions = ['Dead_Cross', 'RSI_Overbought', 'BB_Upper_Touch', 'MACD_Bearish']
        
        signals['Buy_Score'] = signals[buy_conditions].sum(axis=1)
        signals['Sell_Score'] = signals[sell_conditions].sum(axis=1)
        
        signals['Strong_Buy'] = signals['Buy_Score'] >= 2
        signals['Strong_Sell'] = signals['Sell_Score'] >= 2
        
        return signals
    
    def create_simple_chart(self, symbol, indicators, signals):
        """간단한 차트 생성"""
        if indicators is None or signals is None:
            return None
        
        # 최근 100일 데이터
        df = indicators.tail(100)
        sig = signals.tail(100)
        
        fig, axes = plt.subplots(3, 1, figsize=(15, 12))
        fig.suptitle(f'{symbol} 기술적 분석 차트', fontsize=16)
        
        # 1. 가격 차트
        ax1 = axes[0]
        ax1.plot(df.index, df['Close'], label='종가', color='black', linewidth=2)
        ax1.plot(df.index, df['SMA_5'], label='5일 이평', color='red', alpha=0.7)
        ax1.plot(df.index, df['SMA_20'], label='20일 이평', color='blue', alpha=0.7)
        ax1.plot(df.index, df['SMA_60'], label='60일 이평', color='green', alpha=0.7)
        
        # 볼린저 밴드
        ax1.fill_between(df.index, df['BB_Upper'], df['BB_Lower'], alpha=0.1, color='gray')
        ax1.plot(df.index, df['BB_Upper'], color='gray', linestyle='--', alpha=0.5)
        ax1.plot(df.index, df['BB_Lower'], color='gray', linestyle='--', alpha=0.5)
        
        # 매수/매도 신호
        buy_signals = sig[sig['Strong_Buy']].index
        sell_signals = sig[sig['Strong_Sell']].index
        
        if len(buy_signals) > 0:
            ax1.scatter(buy_signals, df.loc[buy_signals, 'Close'], 
                       marker='^', color='red', s=100, label='매수신호', zorder=5)
        
        if len(sell_signals) > 0:
            ax1.scatter(sell_signals, df.loc[sell_signals, 'Close'], 
                       marker='v', color='blue', s=100, label='매도신호', zorder=5)
        
        ax1.set_title('가격 & 이동평균')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. RSI 차트
        ax2 = axes[1]
        ax2.plot(df.index, df['RSI'], label='RSI', color='purple', linewidth=2)
        ax2.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='과매수(70)')
        ax2.axhline(y=30, color='green', linestyle='--', alpha=0.7, label='과매도(30)')
        ax2.axhline(y=50, color='gray', linestyle='-', alpha=0.5)
        ax2.set_title('RSI (상대강도지수)')
        ax2.set_ylim(0, 100)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. MACD 차트
        ax3 = axes[2]
        ax3.plot(df.index, df['MACD'], label='MACD', color='blue', linewidth=2)
        ax3.plot(df.index, df['MACD_Signal'], label='Signal', color='red', linewidth=2)
        
        # MACD 히스토그램
        colors = ['red' if x >= 0 else 'blue' for x in df['MACD_Hist']]
        ax3.bar(df.index, df['MACD_Hist'], color=colors, alpha=0.7, label='Histogram')
        
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax3.set_title('MACD')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        return fig
    
    def analyze_stock_simple(self, symbol):
        """종목 간단 분석"""
        print(f"\n🔍 {symbol} 기술적 분석 시작...")
        
        # 데이터 조회
        df = self.get_stock_data(symbol, days=200)
        if df is None:
            print(f"❌ {symbol} 데이터를 찾을 수 없습니다.")
            return None
        
        # 지표 계산
        indicators = self.calculate_basic_indicators(df)
        if indicators is None:
            return None
        
        # 신호 찾기
        signals = self.find_signals(indicators)
        if signals is None:
            return None
        
        # 현재 상태 분석
        latest = indicators.iloc[-1]
        latest_signals = signals.iloc[-1]
        
        print(f"📊 {symbol} 분석 결과")
        print("=" * 40)
        print(f"현재가: {latest['Close']:,.0f}원")
        print(f"5일 이평: {latest['SMA_5']:,.0f}원")
        print(f"20일 이평: {latest['SMA_20']:,.0f}원")
        print(f"60일 이평: {latest['SMA_60']:,.0f}원")
        print(f"RSI: {latest['RSI']:.1f}")
        
        print(f"\n🚦 현재 신호:")
        if latest_signals['Strong_Buy']:
            print("🔴 강력 매수 신호!")
        elif latest_signals['Strong_Sell']:
            print("🔵 강력 매도 신호!")
        elif latest_signals['Buy_Score'] > 0:
            print(f"🟡 약한 매수 신호 (점수: {latest_signals['Buy_Score']}/4)")
        elif latest_signals['Sell_Score'] > 0:
            print(f"🟡 약한 매도 신호 (점수: {latest_signals['Sell_Score']}/4)")
        else:
            print("⚪ 중립")
        
        print(f"\n📈 기술적 상태:")
        if latest['SMA_5'] > latest['SMA_20']:
            print("✅ 단기 상승 추세 (5일선 > 20일선)")
        else:
            print("❌ 단기 하락 추세 (5일선 < 20일선)")
        
        if latest['RSI'] > 70:
            print("⚠️ RSI 과매수 구간")
        elif latest['RSI'] < 30:
            print("💡 RSI 과매도 구간")
        else:
            print("🎯 RSI 중립 구간")
        
        if latest['Close'] < latest['BB_Lower']:
            print("💡 볼린저밴드 하단 이탈 (매수 고려)")
        elif latest['Close'] > latest['BB_Upper']:
            print("⚠️ 볼린저밴드 상단 이탈 (매도 고려)")
        
        print("=" * 40)
        
        # 차트 생성
        chart_choice = input("\n차트를 보시겠습니까? (y/N): ").strip().lower()
        if chart_choice == 'y':
            self.create_simple_chart(symbol, indicators, signals)
        
        return {
            'indicators': indicators,
            'signals': signals,
            'analysis': {
                'symbol': symbol,
                'current_price': latest['Close'],
                'sma_5': latest['SMA_5'],
                'sma_20': latest['SMA_20'],
                'sma_60': latest['SMA_60'],
                'rsi': latest['RSI'],
                'buy_score': latest_signals['Buy_Score'],
                'sell_score': latest_signals['Sell_Score'],
                'strong_buy': latest_signals['Strong_Buy'],
                'strong_sell': latest_signals['Strong_Sell']
            }
        }
    
    def scan_market_signals(self, limit=20):
        """시장 전체 신호 스캔"""
        print("🔍 시장 전체 매매 신호 스캔 중...")
        
        try:
            with sqlite3.connect(self.stock_db_path) as conn:
                query = """
                    SELECT DISTINCT symbol, name 
                    FROM stock_info 
                    ORDER BY symbol
                    LIMIT ?
                """
                stocks_df = pd.read_sql_query(query, conn, params=(limit,))
        except Exception as e:
            print(f"❌ 종목 리스트 조회 실패: {e}")
            return None
        
        signals_summary = []
        
        for _, stock in stocks_df.iterrows():
            symbol = stock['symbol']
            name = stock['name']
            
            try:
                df = self.get_stock_data(symbol, days=100)
                if df is None or len(df) < 50:
                    continue
                
                indicators = self.calculate_basic_indicators(df)
                if indicators is None:
                    continue
                
                signals = self.find_signals(indicators)
                if signals is None:
                    continue
                
                latest = indicators.iloc[-1]
                latest_signals = signals.iloc[-1]
                
                if latest_signals['Strong_Buy'] or latest_signals['Strong_Sell'] or latest_signals['Buy_Score'] >= 2:
                    signal_type = "강력매수" if latest_signals['Strong_Buy'] else \
                                 "강력매도" if latest_signals['Strong_Sell'] else \
                                 f"매수({latest_signals['Buy_Score']})"
                    
                    signals_summary.append({
                        'symbol': symbol,
                        'name': name,
                        'price': latest['Close'],
                        'rsi': latest['RSI'],
                        'signal': signal_type,
                        'buy_score': latest_signals['Buy_Score'],
                        'sell_score': latest_signals['Sell_Score']
                    })
            
            except Exception as e:
                continue
        
        if signals_summary:
            signals_df = pd.DataFrame(signals_summary)
            signals_df = signals_df.sort_values(['buy_score', 'rsi'], ascending=[False, True])
            
            print(f"\n📊 발견된 매매 신호: {len(signals_df)}개")
            print("=" * 70)
            print(f"{'종목코드':<8} {'종목명':<15} {'현재가':<10} {'RSI':<6} {'신호':<10}")
            print("-" * 70)
            
            for _, row in signals_df.head(15).iterrows():
                print(f"{row['symbol']:<8} {row['name']:<15} {row['price']:>8,.0f} {row['rsi']:>5.1f} {row['signal']:<10}")
            
            return signals_df
        else:
            print("❌ 현재 특별한 매매 신호가 없습니다.")
            return None


def main():
    """메인 실행 함수"""
    
    print("🚀 Finance Data Vibe - 기술적 분석 시스템")
    print("📊 기본분석(45%) : 기술분석(30%) : 뉴스분석(25%)")
    print("=" * 60)
    
    try:
        while True:
            print("\n📈 원하는 기능을 선택하세요:")
            print("1. 간단 종목 기술적 분석")
            print("2. 고급 종목 기술적 분석 (가치투자 최적화)")
            print("3. 시장 전체 신호 스캔")
            print("4. 복수 종목 비교 분석")
            print("5. Streamlit 대시보드 실행")
            print("0. 종료")
            
            choice = input("\n선택하세요 (0-5): ").strip()
            
            if choice == '0':
                print("👋 분석을 종료합니다.")
                break
            
            elif choice == '1':
                # 간단 분석
                analyzer = SimpleTechnicalAnalyzer()
                symbol = input("종목코드를 입력하세요 (예: 005930): ").strip()
                if symbol:
                    result = analyzer.analyze_stock_simple(symbol)
                    if result:
                        print("✅ 간단 분석 완료!")
                    else:
                        print("❌ 분석 실패")
            
            elif choice == '2':
                # 고급 분석
                analyzer = ValueInvestingTechnicalAnalyzer()
                symbol = input("종목코드를 입력하세요 (예: 005930): ").strip()
                if symbol:
                    result = analyzer.analyze_stock_timing(symbol)
                    if result:
                        print("✅ 고급 분석 완료!")
                        
                        # 차트 선택
                        chart_choice = input("인터랙티브 차트를 보시겠습니까? (y/N): ").strip().lower()
                        if chart_choice == 'y':
                            fig = analyzer.create_technical_chart(
                                symbol, 
                                result['indicators'], 
                                result['signals']
                            )
                            if fig:
                                fig.show()
                                print("✅ 차트가 브라우저에서 열렸습니다!")
                    else:
                        print("❌ 분석 실패")
            
            elif choice == '3':
                # 시장 전체 스캔
                analyzer_type = input("분석 유형을 선택하세요 (1:간단, 2:고급): ").strip()
                limit = int(input("스캔할 종목 수를 입력하세요 (기본값: 50): ").strip() or "50")
                
                if analyzer_type == '2':
                    analyzer = ValueInvestingTechnicalAnalyzer()
                    signals = analyzer.scan_value_buying_opportunities(limit)
                else:
                    analyzer = SimpleTechnicalAnalyzer()
                    signals = analyzer.scan_market_signals(limit)
                
                if signals is not None and len(signals) > 0:
                    detail_choice = input("\n특정 종목을 상세 분석하시겠습니까? (종목코드 입력 또는 N): ").strip()
                    if detail_choice.upper() != 'N' and detail_choice:
                        if analyzer_type == '2':
                            analyzer.analyze_stock_timing(detail_choice)
                        else:
                            analyzer.analyze_stock_simple(detail_choice)
            
            elif choice == '4':
                # 복수 종목 비교
                symbols_input = input("비교할 종목들을 입력하세요 (쉼표로 구분, 예: 005930,000660,035420): ").strip()
                if symbols_input:
                    symbols = [s.strip() for s in symbols_input.split(',')]
                    analyzer_type = input("분석 유형을 선택하세요 (1:간단, 2:고급): ").strip()
                    
                    if analyzer_type == '2':
                        analyzer = ValueInvestingTechnicalAnalyzer()
                    else:
                        analyzer = SimpleTechnicalAnalyzer()
                    
                    print(f"\n📊 {len(symbols)}개 종목 비교 분석")
                    print("=" * 80)
                    
                    for symbol in symbols:
                        try:
                            if analyzer_type == '2':
                                result = analyzer.analyze_stock_timing(symbol)
                            else:
                                result = analyzer.analyze_stock_simple(symbol)
                        except:
                            print(f"{symbol}: 분석 실패")
            
            elif choice == '5':
                # Streamlit 대시보드 실행
                print("\n🌐 Streamlit 대시보드를 실행합니다...")
                print("터미널에서 다음 명령어를 실행하세요:")
                print("streamlit run examples/basic_examples/07_technical_dashboard.py")
                print("\n또는 대시보드 파일을 별도로 저장한 후 실행하세요.")
            
            else:
                print("❌ 올바른 번호를 선택해주세요.")
    
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("필요한 패키지가 설치되었는지 확인해주세요:")
        print("pip install talib plotly streamlit")


if __name__ == "__main__":
    main()