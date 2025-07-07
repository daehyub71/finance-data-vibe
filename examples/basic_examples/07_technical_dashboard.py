"""
📊 Streamlit 기술적 분석 대시보드
examples/basic_examples/07_technical_dashboard.py

실행 방법:
streamlit run examples/basic_examples/07_technical_dashboard.py

이 대시보드는 가치투자 중심의 기술적 분석 도구입니다.
웹 브라우저에서 실시간으로 차트를 확인하고 매수 신호를 포착할 수 있습니다.
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
from datetime import datetime, timedelta

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# 페이지 설정
st.set_page_config(
    page_title="Finance Data Vibe - 기술적 분석",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

try:
    from src.analysis.technical.technical_analysis import ValueInvestingTechnicalAnalyzer
    from config.settings import DATA_DIR
except ImportError:
    st.error("❌ 모듈을 가져올 수 없습니다. 프로젝트 구조를 확인해주세요.")
    st.stop()

# 캐싱을 위한 데이터 로더
@st.cache_data(ttl=300)  # 5분 캐시
def get_stock_list():
    """종목 리스트 조회"""
    try:
        data_dir = Path(DATA_DIR)
        stock_db_path = data_dir / 'stock_data.db'
        
        with sqlite3.connect(stock_db_path) as conn:
            query = """
                SELECT DISTINCT symbol, name 
                FROM stock_info 
                WHERE symbol IS NOT NULL 
                ORDER BY symbol
            """
            df = pd.read_sql_query(query, conn)
            return df
    except Exception as e:
        st.error(f"종목 리스트 조회 실패: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)  # 10분 캐시
def analyze_stock_cached(symbol):
    """종목 분석 (캐시된)"""
    analyzer = ValueInvestingTechnicalAnalyzer()
    return analyzer.analyze_stock_timing(symbol)

def main():
    """메인 대시보드"""
    
    # 헤더
    st.title("📈 Finance Data Vibe")
    st.subheader("가치투자 기술적 분석 대시보드")
    
    # 철학 표시
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 기본분석", "45%", help="워런 버핏 스타일 가치 평가")
    with col2:
        st.metric("📈 기술분석", "30%", help="매수 타이밍 최적화")
    with col3:
        st.metric("📰 감정분석", "25%", help="시장 심리 보조 지표")
    
    st.markdown("---")
    
    # 사이드바 - 종목 선택
    st.sidebar.header("🔍 분석 설정")
    
    # 종목 리스트 로드
    stocks_df = get_stock_list()
    if stocks_df.empty:
        st.error("종목 데이터를 불러올 수 없습니다.")
        return
    
    # 종목 선택
    stock_options = [f"{row['symbol']} - {row['name']}" for _, row in stocks_df.iterrows()]
    selected_stock = st.sidebar.selectbox(
        "📊 분석할 종목을 선택하세요",
        stock_options,
        index=0
    )
    
    if selected_stock:
        symbol = selected_stock.split(' - ')[0]
        stock_name = selected_stock.split(' - ')[1]
        
        # 분석 기간 선택
        analysis_period = st.sidebar.selectbox(
            "📅 분석 기간",
            ["최근 6개월", "최근 1년", "최근 2년"],
            index=1
        )
        
        period_days = {"최근 6개월": 180, "최근 1년": 365, "최근 2년": 730}
        days = period_days[analysis_period]
        
        # 실시간 분석 버튼
        if st.sidebar.button("🔄 분석 실행", type="primary"):
            st.cache_data.clear()  # 캐시 클리어
        
        # 메인 컨텐츠
        tab1, tab2, tab3, tab4 = st.tabs(["📊 종합 분석", "📈 차트 분석", "🎯 매수 신호", "📋 포트폴리오"])
        
        with tab1:
            # 종합 분석
            st.header(f"📊 {stock_name} ({symbol}) 종합 분석")
            
            with st.spinner("분석 중..."):
                result = analyze_stock_cached(symbol)
            
            if result:
                analysis = result['analysis']
                
                # 메트릭 표시
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "현재가", 
                        f"{analysis['current_price']:,.0f}원",
                        help="실시간 주가"
                    )
                
                with col2:
                    price_vs_200sma = analysis['price_vs_200sma']
                    delta_200sma = f"{(price_vs_200sma-1)*100:+.1f}%"
                    st.metric(
                        "200일선 대비", 
                        f"{price_vs_200sma:.3f}",
                        delta_200sma,
                        help="장기 추세 대비 현재 위치"
                    )
                
                with col3:
                    rsi = analysis['rsi']
                    rsi_status = "과매도" if rsi < 30 else "과매수" if rsi > 70 else "중립"
                    st.metric(
                        "RSI", 
                        f"{rsi:.1f}",
                        rsi_status,
                        help="상대강도지수 (30 이하 과매도, 70 이상 과매수)"
                    )
                
                with col4:
                    w52_pos = analysis['52w_position']
                    st.metric(
                        "52주 포지션", 
                        f"{w52_pos:.1%}",
                        help="52주 최고가-최저가 구간에서의 현재 위치"
                    )
                
                # 투자 신호
                st.subheader("🚦 투자 신호")
                
                signal_col1, signal_col2 = st.columns(2)
                
                with signal_col1:
                    if analysis['strong_buy_signal']:
                        st.success("🔴 **강력 매수 신호!**")
                        st.info("3개 이상의 기술적 조건이 만족되었습니다.")
                    elif analysis['moderate_buy_signal']:
                        st.warning("🟡 **중간 매수 신호**")
                        st.info("2개의 기술적 조건이 만족되었습니다.")
                    elif analysis['dca_zone']:
                        st.info("🟢 **분할매수 구간**")
                        st.info("Dollar Cost Averaging을 고려해보세요.")
                    else:
                        st.info("⚪ **관망 구간**")
                        st.info("현재는 매수 신호가 없습니다.")
                
                with signal_col2:
                    # 기술적 점수 진행바
                    score = analysis['technical_score']
                    st.metric("기술적 점수", f"{score}/4")
                    st.progress(score / 4)
                    
                    # 위험도
                    risk = analysis['atr_risk']
                    risk_level = "높음" if risk > 3 else "중간" if risk > 1.5 else "낮음"
                    st.metric("일일 변동성", f"±{risk:.1f}%", risk_level)
                
                # 포지션 제안
                st.subheader("💼 포지션 제안")
                pos_col1, pos_col2 = st.columns(2)
                
                with pos_col1:
                    st.metric("권장 매수 수량", f"{analysis['suggested_shares']:.0f}주")
                    st.metric("투자 금액", f"{analysis['position_value']:,.0f}원")
                
                with pos_col2:
                    st.info("**포지션 사이징 기준**")
                    st.write("- 계좌의 2% 리스크 기준")
                    st.write("- 최대 포지션: 계좌의 20%")
                    st.write("- ATR 기반 손절 기준")
            
            else:
                st.error("분석 데이터를 불러올 수 없습니다.")
        
        with tab2:
            # 차트 분석
            st.header(f"📈 {stock_name} 기술적 차트")
            
            if result:
                indicators = result['indicators']
                signals = result['signals']
                
                # 차트 생성
                analyzer = ValueInvestingTechnicalAnalyzer()
                fig = analyzer.create_technical_chart(symbol, indicators, signals)
                
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("차트를 생성할 수 없습니다.")
            else:
                st.error("차트 데이터를 불러올 수 없습니다.")
        
        with tab3:
            # 매수 신호 상세
            st.header("🎯 매수 신호 상세 분석")
            
            if result:
                signals = result['signals']
                indicators = result['indicators']
                
                # 최근 30일간 신호 요약
                recent_signals = signals.tail(30)
                recent_indicators = indicators.tail(30)
                
                st.subheader("📅 최근 30일 신호 현황")
                
                signal_summary = {
                    "강력 매수 신호": recent_signals['Strong_Buy_Signal'].sum(),
                    "중간 매수 신호": recent_signals['Moderate_Buy_Signal'].sum(),
                    "분할매수 구간": recent_signals['DCA_Zone'].sum(),
                    "평균 기술적 점수": recent_signals['Technical_Score'].mean()
                }
                
                col1, col2, col3, col4 = st.columns(4)
                cols = [col1, col2, col3, col4]
                
                for i, (key, value) in enumerate(signal_summary.items()):
                    with cols[i]:
                        if key == "평균 기술적 점수":
                            st.metric(key, f"{value:.1f}/4")
                        else:
                            st.metric(key, f"{value}일")
                
                # 신호 발생 날짜들 표시
                st.subheader("📋 신호 발생 이력")
                
                strong_buy_dates = recent_signals[recent_signals['Strong_Buy_Signal']].index
                moderate_buy_dates = recent_signals[recent_signals['Moderate_Buy_Signal'] & ~recent_signals['Strong_Buy_Signal']].index
                
                if len(strong_buy_dates) > 0:
                    st.success("🔴 **강력 매수 신호 발생일:**")
                    for date in strong_buy_dates[-5:]:  # 최근 5개만
                        price = recent_indicators.loc[date, 'Close']
                        st.write(f"- {date.strftime('%Y-%m-%d')}: {price:,.0f}원")
                
                if len(moderate_buy_dates) > 0:
                    st.warning("🟡 **중간 매수 신호 발생일:**")
                    for date in moderate_buy_dates[-5:]:  # 최근 5개만
                        price = recent_indicators.loc[date, 'Close']
                        st.write(f"- {date.strftime('%Y-%m-%d')}: {price:,.0f}원")
        
        with tab4:
            # 포트폴리오 관리
            st.header("📋 포트폴리오 관리")
            
            st.subheader("🎯 포트폴리오 구성")
            
            # 포트폴리오 입력
            portfolio_input = st.text_area(
                "보유 종목을 입력하세요 (한 줄에 하나씩)",
                placeholder="005930\n000660\n035420",
                height=100
            )
            
            if portfolio_input:
                portfolio_symbols = [line.strip() for line in portfolio_input.split('\n') if line.strip()]
                
                if st.button("📊 포트폴리오 분석"):
                    st.write("분석 중...")
                    
                    analyzer = ValueInvestingTechnicalAnalyzer()
                    
                    portfolio_results = []
                    
                    for symbol in portfolio_symbols:
                        try:
                            result = analyze_stock_cached(symbol)
                            if result:
                                analysis = result['analysis']
                                # 종목명 조회
                                stock_info = stocks_df[stocks_df['symbol'] == symbol]
                                name = stock_info.iloc[0]['name'] if not stock_info.empty else symbol
                                
                                portfolio_results.append({
                                    '종목코드': symbol,
                                    '종목명': name,
                                    '현재가': f"{analysis['current_price']:,.0f}원",
                                    '200일선 대비': f"{(analysis['price_vs_200sma']-1)*100:+.1f}%",
                                    'RSI': f"{analysis['rsi']:.1f}",
                                    '기술적점수': f"{analysis['technical_score']}/4",
                                    '투자신호': '강력매수' if analysis['strong_buy_signal'] else '중간매수' if analysis['moderate_buy_signal'] else '관망'
                                })
                        except:
                            continue
                    
                    if portfolio_results:
                        portfolio_df = pd.DataFrame(portfolio_results)
                        st.dataframe(portfolio_df, use_container_width=True)
                        
                        # 리밸런싱 제안
                        st.subheader("⚖️ 리밸런싱 제안")
                        
                        strong_buy_count = len([r for r in portfolio_results if r['투자신호'] == '강력매수'])
                        moderate_buy_count = len([r for r in portfolio_results if r['투자신호'] == '중간매수'])
                        
                        if strong_buy_count > 0:
                            st.success(f"🔴 **비중 확대 고려**: {strong_buy_count}개 종목에서 강력 매수 신호")
                        
                        if moderate_buy_count > 0:
                            st.warning(f"🟡 **현 비중 유지**: {moderate_buy_count}개 종목에서 중간 매수 신호")
                        
                        watch_count = len(portfolio_results) - strong_buy_count - moderate_buy_count
                        if watch_count > 0:
                            st.info(f"⚪ **비중 축소 고려**: {watch_count}개 종목이 관망 구간")

    # 사이드바 - 추가 정보
    st.sidebar.markdown("---")
    st.sidebar.header("📚 도움말")
    
    with st.sidebar.expander("🔍 신호 해석"):
        st.write("""
        **🔴 강력 매수**: 3개 이상 조건 만족
        - RSI 과매도 + 볼린저밴드 하단
        - 200일선 대비 5% 이하
        - 52주 저점 근처
        - 거래량 급증
        
        **🟡 중간 매수**: 2개 조건 만족
        
        **🟢 분할매수**: DCA 구간
        """)
    
    with st.sidebar.expander("💡 사용 팁"):
        st.write("""
        1. 기본분석으로 우량주 선별
        2. 기술적 분석으로 매수 타이밍
        3. 분할매수로 리스크 분산
        4. 장기 보유 원칙 유지
        """)

    st.sidebar.markdown("---")
    st.sidebar.info("**Finance Data Vibe v1.0**\n가치투자 기술적 분석 시스템")

if __name__ == "__main__":
    main()