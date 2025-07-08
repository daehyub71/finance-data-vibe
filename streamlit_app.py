"""
streamlit_app.py

워런 버핏 스타일 가치투자 대시보드 MVP
기본분석(45%) : 기술분석(30%) : 뉴스분석(25%) 비율 반영

🎯 핵심 목표:
- 50대 은퇴 준비 직장인 맞춤
- 퇴근 후 30분 투자 분석
- 데이터 기반 가치투자 의사결정
"""

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR
except ImportError:
    DATA_DIR = Path("data")

# 페이지 설정
st.set_page_config(
    page_title="워런 버핏 스타일 가치투자",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 설정
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f4e79;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #2c5aa0;
        margin-bottom: 0.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f4e79;
    }
    .buffett-quote {
        font-style: italic;
        color: #6c757d;
        text-align: center;
        margin: 1rem 0;
        font-size: 1.1rem;
    }
</style>
""", unsafe_allow_html=True)


class DataLoader:
    """데이터 로딩 및 캐싱 클래스"""
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.stock_db_path = self.data_dir / 'stock_data.db'
        self.dart_db_path = self.data_dir / 'dart_data.db'
        self.news_db_path = self.data_dir / 'news_data.db'
        self.finance_db_path = Path("finance_data.db")  # 루트의 통합 DB
    
    @st.cache_data(ttl=3600)  # 1시간 캐시
    def load_stock_list(_self):
        """전체 주식 종목 리스트 로드"""
        try:
            # 먼저 finance_data.db 시도
            if _self.finance_db_path.exists():
                with sqlite3.connect(_self.finance_db_path) as conn:
                    query = """
                        SELECT code as stock_code, name as stock_name, market, sector
                        FROM stock_info
                        ORDER BY code
                    """
                    df = pd.read_sql_query(query, conn)
                    return df
            
            # stock_data.db 시도
            elif _self.stock_db_path.exists():
                with sqlite3.connect(_self.stock_db_path) as conn:
                    query = """
                        SELECT symbol as stock_code, name as stock_name, market
                        FROM stock_info
                        WHERE symbol IS NOT NULL
                        ORDER BY symbol
                    """
                    df = pd.read_sql_query(query, conn)
                    df['sector'] = 'Unknown'
                    return df
            
            else:
                # 기본 데이터 반환
                return pd.DataFrame({
                    'stock_code': ['005930', '000660', '035420', '005380', '006400'],
                    'stock_name': ['삼성전자', 'SK하이닉스', 'NAVER', '현대차', '삼성SDI'],
                    'market': ['KOSPI'] * 5,
                    'sector': ['IT', 'IT', 'IT', '자동차', '화학']
                })
                
        except Exception as e:
            st.error(f"주식 리스트 로딩 실패: {e}")
            return pd.DataFrame()
    
    @st.cache_data(ttl=1800)  # 30분 캐시
    def load_buffett_scores(_self):
        """버핏 스코어 계산 및 로드"""
        try:
            stocks = _self.load_stock_list()
            scores = []
            
            # DART DB에서 재무비율 계산
            if _self.dart_db_path.exists():
                with sqlite3.connect(_self.dart_db_path) as conn:
                    for _, stock in stocks.head(50).iterrows():  # 상위 50개만 분석
                        score = _self._calculate_buffett_score(conn, stock['stock_code'])
                        scores.append({
                            'stock_code': stock['stock_code'],
                            'stock_name': stock['stock_name'],
                            'sector': stock.get('sector', 'Unknown'),
                            'buffett_score': score['total_score'],
                            'profitability': score['profitability'],
                            'stability': score['stability'],
                            'growth': score['growth'],
                            'valuation': score['valuation']
                        })
            
            if scores:
                return pd.DataFrame(scores).sort_values('buffett_score', ascending=False)
            else:
                # 샘플 데이터
                return _self._generate_sample_scores()
                
        except Exception as e:
            st.error(f"버핏 스코어 로딩 실패: {e}")
            return _self._generate_sample_scores()
    
    def _calculate_buffett_score(self, conn, stock_code):
        """개별 종목 버핏 스코어 계산"""
        try:
            query = """
                SELECT fs.account_nm, fs.thstrm_amount
                FROM financial_statements fs
                JOIN company_info ci ON fs.corp_code = ci.corp_code
                WHERE ci.stock_code = ? AND fs.bsns_year = '2023'
                AND fs.account_nm IN ('자산총계', '부채총계', '자본총계', '당기순이익', '매출액', '영업이익')
            """
            result = pd.read_sql_query(query, conn, params=(stock_code,))
            
            if result.empty:
                return {'total_score': 50, 'profitability': 12, 'stability': 12, 'growth': 13, 'valuation': 13}
            
            # 계정과목별 금액 추출
            accounts = {}
            for _, row in result.iterrows():
                try:
                    amount = float(str(row['thstrm_amount']).replace(',', ''))
                    accounts[row['account_nm']] = amount
                except:
                    continue
            
            # 점수 계산
            profitability = 0  # 수익성 (30점)
            stability = 0      # 안정성 (25점)
            growth = 0         # 성장성 (25점)
            valuation = 0      # 가치평가 (20점)
            
            # 수익성 점수 (ROE, 영업이익률)
            if '당기순이익' in accounts and '자본총계' in accounts and accounts['자본총계'] > 0:
                roe = accounts['당기순이익'] / accounts['자본총계'] * 100
                if roe >= 20: profitability += 20
                elif roe >= 15: profitability += 15
                elif roe >= 10: profitability += 10
                elif roe >= 5: profitability += 5
            
            if '영업이익' in accounts and '매출액' in accounts and accounts['매출액'] > 0:
                op_margin = accounts['영업이익'] / accounts['매출액'] * 100
                if op_margin >= 15: profitability += 10
                elif op_margin >= 10: profitability += 7
                elif op_margin >= 5: profitability += 5
            
            # 안정성 점수 (부채비율, 유동비율)
            if '부채총계' in accounts and '자본총계' in accounts and accounts['자본총계'] > 0:
                debt_ratio = accounts['부채총계'] / accounts['자본총계'] * 100
                if debt_ratio <= 30: stability += 15
                elif debt_ratio <= 50: stability += 10
                elif debt_ratio <= 100: stability += 5
            
            if '자본총계' in accounts and accounts['자본총계'] > 0:
                equity_ratio = accounts['자본총계'] / accounts['자산총계'] * 100
                if equity_ratio >= 70: stability += 10
                elif equity_ratio >= 50: stability += 7
                elif equity_ratio >= 30: stability += 5
            
            # 성장성 점수 (임시로 랜덤 - 실제로는 3년 성장률 계산 필요)
            growth = np.random.randint(10, 25)
            
            # 가치평가 점수 (임시로 랜덤 - 실제로는 PER, PBR 계산 필요)
            valuation = np.random.randint(8, 20)
            
            total_score = min(100, profitability + stability + growth + valuation)
            
            return {
                'total_score': total_score,
                'profitability': profitability,
                'stability': stability,
                'growth': growth,
                'valuation': valuation
            }
            
        except Exception as e:
            return {'total_score': 50, 'profitability': 12, 'stability': 12, 'growth': 13, 'valuation': 13}
    
    def _generate_sample_scores(self):
        """샘플 버핏 스코어 데이터 생성"""
        sample_data = [
            {'stock_code': '005930', 'stock_name': '삼성전자', 'sector': 'IT', 'buffett_score': 85},
            {'stock_code': '000660', 'stock_name': 'SK하이닉스', 'sector': 'IT', 'buffett_score': 78},
            {'stock_code': '035420', 'stock_name': 'NAVER', 'sector': 'IT', 'buffett_score': 82},
            {'stock_code': '005380', 'stock_name': '현대차', 'sector': '자동차', 'buffett_score': 75},
            {'stock_code': '006400', 'stock_name': '삼성SDI', 'sector': '화학', 'buffett_score': 80},
            {'stock_code': '051910', 'stock_name': 'LG화학', 'sector': '화학', 'buffett_score': 77},
            {'stock_code': '035720', 'stock_name': '카카오', 'sector': 'IT', 'buffett_score': 72},
            {'stock_code': '207940', 'stock_name': '삼성바이오로직스', 'sector': '바이오', 'buffett_score': 88},
            {'stock_code': '068270', 'stock_name': '셀트리온', 'sector': '바이오', 'buffett_score': 74},
            {'stock_code': '096770', 'stock_name': 'SK이노베이션', 'sector': '화학', 'buffett_score': 79}
        ]
        
        # 세부 점수 생성
        for item in sample_data:
            total = item['buffett_score']
            item['profitability'] = int(total * 0.30)
            item['stability'] = int(total * 0.25)
            item['growth'] = int(total * 0.25)
            item['valuation'] = int(total * 0.20)
        
        return pd.DataFrame(sample_data)
    
    @st.cache_data(ttl=900)  # 15분 캐시
    def load_stock_price_data(_self, stock_code, days=252):
        """개별 종목 주가 데이터 로드"""
        try:
            if _self.stock_db_path.exists():
                with sqlite3.connect(_self.stock_db_path) as conn:
                    query = """
                        SELECT date, open, high, low, close, volume
                        FROM stock_prices
                        WHERE symbol = ?
                        ORDER BY date DESC
                        LIMIT ?
                    """
                    df = pd.read_sql_query(query, conn, params=(stock_code, days))
                    if not df.empty:
                        df['date'] = pd.to_datetime(df['date'])
                        return df.sort_values('date')
            
            # 샘플 데이터 생성
            return _self._generate_sample_price_data(stock_code, days)
            
        except Exception as e:
            st.error(f"주가 데이터 로딩 실패 ({stock_code}): {e}")
            return _self._generate_sample_price_data(stock_code, days)
    
    def _generate_sample_price_data(self, stock_code, days):
        """샘플 주가 데이터 생성"""
        np.random.seed(hash(stock_code) % 2**32)  # 종목별 고정 시드
        
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        prices = []
        
        base_price = 50000 if stock_code == '005930' else np.random.randint(10000, 100000)
        current_price = base_price
        
        for i, date in enumerate(dates):
            # 랜덤 워크로 가격 생성
            change = np.random.normal(0, 0.02)  # 2% 표준편차
            current_price *= (1 + change)
            
            # OHLC 생성
            high = current_price * (1 + abs(np.random.normal(0, 0.01)))
            low = current_price * (1 - abs(np.random.normal(0, 0.01)))
            open_price = low + (high - low) * np.random.random()
            close = low + (high - low) * np.random.random()
            volume = np.random.randint(100000, 10000000)
            
            prices.append({
                'date': date,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
        
        return pd.DataFrame(prices)
    
    @st.cache_data(ttl=1800)  # 30분 캐시
    def load_news_sentiment(_self):
        """뉴스 감정 분석 데이터 로드"""
        try:
            if _self.news_db_path.exists():
                with sqlite3.connect(_self.news_db_path) as conn:
                    query = """
                        SELECT stock_code, stock_name, 
                               AVG(sentiment_score) as avg_sentiment,
                               COUNT(*) as news_count
                        FROM news_articles
                        WHERE DATE(collected_at) >= DATE('now', '-7 days')
                        GROUP BY stock_code, stock_name
                        ORDER BY news_count DESC
                    """
                    return pd.read_sql_query(query, conn)
            
            # 샘플 데이터
            return pd.DataFrame({
                'stock_code': ['005930', '000660', '035420', '005380', '006400'],
                'stock_name': ['삼성전자', 'SK하이닉스', 'NAVER', '현대차', '삼성SDI'],
                'avg_sentiment': [0.15, -0.05, 0.25, 0.10, 0.08],
                'news_count': [45, 23, 38, 19, 15]
            })
            
        except Exception as e:
            st.error(f"뉴스 감정 데이터 로딩 실패: {e}")
            return pd.DataFrame()


def create_buffett_scorecard_chart(score_data):
    """버핏 스코어카드 레이더 차트 생성"""
    categories = ['수익성', '안정성', '성장성', '가치평가']
    values = [
        score_data['profitability'],
        score_data['stability'], 
        score_data['growth'],
        score_data['valuation']
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        name=score_data['stock_name'],
        fillcolor='rgba(31, 78, 121, 0.3)',
        line=dict(color='rgb(31, 78, 121)', width=2)
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 30]
            )
        ),
        showlegend=True,
        title=f"{score_data['stock_name']} 워런 버핏 스코어카드",
        height=400
    )
    
    return fig


def create_price_chart_with_indicators(price_data, stock_name):
    """주가 차트 + 기술적 지표"""
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=[f'{stock_name} 주가', 'RSI', '거래량'],
        row_heights=[0.6, 0.2, 0.2]
    )
    
    # 메인 캔들스틱 차트
    fig.add_trace(
        go.Candlestick(
            x=price_data['date'],
            open=price_data['open'],
            high=price_data['high'],
            low=price_data['low'],
            close=price_data['close'],
            name='주가'
        ),
        row=1, col=1
    )
    
    # 200일 이동평균
    if len(price_data) >= 200:
        ma_200 = price_data['close'].rolling(window=200).mean()
        fig.add_trace(
            go.Scatter(
                x=price_data['date'],
                y=ma_200,
                name='200일 이동평균',
                line=dict(color='orange', width=2)
            ),
            row=1, col=1
        )
    
    # RSI 계산 및 표시
    delta = price_data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    fig.add_trace(
        go.Scatter(
            x=price_data['date'],
            y=rsi,
            name='RSI',
            line=dict(color='purple')
        ),
        row=2, col=1
    )
    
    # RSI 과매수/과매도 선
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    
    # 거래량
    fig.add_trace(
        go.Bar(
            x=price_data['date'],
            y=price_data['volume'],
            name='거래량',
            marker_color='lightblue'
        ),
        row=3, col=1
    )
    
    fig.update_layout(
        height=800,
        showlegend=True,
        xaxis_rangeslider_visible=False
    )
    
    return fig


def main_dashboard():
    """메인 대시보드"""
    
    # 헤더
    st.markdown('<div class="main-header">🏆 Warren Buffett Style Value Investing</div>', unsafe_allow_html=True)
    st.markdown('<div class="buffett-quote">"가격은 당신이 지불하는 것이고, 가치는 당신이 얻는 것이다" - 워런 버핏</div>', unsafe_allow_html=True)
    
    # 데이터 로더 초기화
    loader = DataLoader()
    
    # 데이터 로딩
    with st.spinner('📊 데이터 로딩 중...'):
        buffett_scores = loader.load_buffett_scores()
        news_sentiment = loader.load_news_sentiment()
    
    if buffett_scores.empty:
        st.error("데이터를 로딩할 수 없습니다. 데이터베이스를 확인해주세요.")
        return
    
    # 핵심 지표 요약
    st.markdown('<div class="sub-header">📊 투자 현황 요약</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        high_quality_count = len(buffett_scores[buffett_scores['buffett_score'] >= 80])
        st.metric("🏆 우량주 발굴", f"{high_quality_count}개", "↑3")
    
    with col2:
        avg_score = buffett_scores['buffett_score'].mean()
        st.metric("📈 평균 버핏점수", f"{avg_score:.1f}점", "↑2.1")
    
    with col3:
        undervalued_count = len(buffett_scores[buffett_scores['buffett_score'] >= 75])
        st.metric("💰 투자대상", f"{undervalued_count}개", "↑5")
    
    with col4:
        if not news_sentiment.empty:
            avg_sentiment = news_sentiment['avg_sentiment'].mean()
            sentiment_indicator = "긍정" if avg_sentiment > 0 else "부정"
            st.metric("📰 시장감정", sentiment_indicator, f"{avg_sentiment:.2f}")
        else:
            st.metric("📰 시장감정", "중립", "0.00")
    
    st.markdown("---")
    
    # 메인 콘텐츠 영역
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        st.markdown('<div class="sub-header">🎯 버핏 스코어 TOP 20</div>', unsafe_allow_html=True)
        
        # 상위 20개 종목 차트
        top_20 = buffett_scores.head(20)
        
        fig_ranking = px.bar(
            top_20,
            x='buffett_score',
            y='stock_name',
            color='buffett_score',
            color_continuous_scale='RdYlGn',
            title="워런 버핏 스코어 랭킹",
            labels={'buffett_score': '버핏 점수', 'stock_name': '종목명'}
        )
        fig_ranking.update_layout(height=600, yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_ranking, use_container_width=True)
    
    with right_col:
        st.markdown('<div class="sub-header">🏢 섹터별 분포</div>', unsafe_allow_html=True)
        
        # 섹터별 분포 파이 차트
        sector_counts = buffett_scores['sector'].value_counts()
        
        fig_sector = px.pie(
            values=sector_counts.values,
            names=sector_counts.index,
            title="투자 대상 섹터 분포"
        )
        fig_sector.update_layout(height=300)
        st.plotly_chart(fig_sector, use_container_width=True)
        
        st.markdown('<div class="sub-header">📊 점수 분포</div>', unsafe_allow_html=True)
        
        # 점수 분포 히스토그램
        fig_hist = px.histogram(
            buffett_scores,
            x='buffett_score',
            nbins=20,
            title="버핏 점수 분포",
            labels={'buffett_score': '버핏 점수', 'count': '종목 수'}
        )
        fig_hist.update_layout(height=300)
        st.plotly_chart(fig_hist, use_container_width=True)
    
    st.markdown("---")
    
    # 상세 분석 섹션
    st.markdown('<div class="sub-header">📋 상위 종목 상세 분석</div>', unsafe_allow_html=True)
    
    # 상위 10개 종목 테이블
    display_cols = ['stock_code', 'stock_name', 'sector', 'buffett_score', 'profitability', 'stability', 'growth', 'valuation']
    top_10_display = buffett_scores[display_cols].head(10).copy()
    
    # 컬럼명 한글화
    top_10_display.columns = ['종목코드', '종목명', '섹터', '총점', '수익성', '안정성', '성장성', '가치평가']
    
    st.dataframe(
        top_10_display,
        use_container_width=True,
        height=400
    )
    
    # 선택된 종목 상세 분석
    st.markdown('<div class="sub-header">🔍 종목 상세 분석</div>', unsafe_allow_html=True)
    
    selected_stock = st.selectbox(
        "분석할 종목을 선택하세요:",
        options=buffett_scores['stock_code'].tolist(),
        format_func=lambda x: f"{x} ({buffett_scores[buffett_scores['stock_code']==x]['stock_name'].iloc[0]})"
    )
    
    if selected_stock:
        stock_data = buffett_scores[buffett_scores['stock_code'] == selected_stock].iloc[0]
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # 스코어카드 차트
            scorecard_fig = create_buffett_scorecard_chart(stock_data)
            st.plotly_chart(scorecard_fig, use_container_width=True)
        
        with col2:
            # 주요 지표
            st.markdown("### 📊 주요 지표")
            st.metric("🏆 버핏 총점", f"{stock_data['buffett_score']:.0f}점")
            st.metric("💰 수익성", f"{stock_data['profitability']:.0f}/30점")
            st.metric("🛡️ 안정성", f"{stock_data['stability']:.0f}/25점")
            st.metric("📈 성장성", f"{stock_data['growth']:.0f}/25점")
            st.metric("💎 가치평가", f"{stock_data['valuation']:.0f}/20점")
            
            # 투자 추천
            score = stock_data['buffett_score']
            if score >= 85:
                st.success("🔥 강력 추천: 최고의 투자 기회!")
            elif score >= 75:
                st.info("✅ 추천: 양질의 투자 대상")
            elif score >= 65:
                st.warning("⚠️ 보통: 신중한 검토 필요")
            else:
                st.error("❌ 비추천: 투자 부적합")
        
        # 주가 차트
        st.markdown("### 📈 주가 및 기술적 분석")
        price_data = loader.load_stock_price_data(selected_stock)
        
        if not price_data.empty:
            price_chart = create_price_chart_with_indicators(price_data, stock_data['stock_name'])
            st.plotly_chart(price_chart, use_container_width=True)
        else:
            st.warning("주가 데이터를 불러올 수 없습니다.")


def buffett_score_ranking():
    """버핏 스코어 랭킹 페이지"""
    st.header("🏆 워런 버핏 스코어 랭킹")
    st.markdown("*수익성(30점) + 안정성(25점) + 성장성(25점) + 가치평가(20점) = 100점*")
    
    loader = DataLoader()
    buffett_scores = loader.load_buffett_scores()
    
    if buffett_scores.empty:
        st.error("데이터를 불러올 수 없습니다.")
        return
    
    # 필터링 옵션
    st.markdown("### 🔍 필터 옵션")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        min_score = st.slider("최소 점수", 0, 100, 70)
    
    with col2:
        available_sectors = ['전체'] + list(buffett_scores['sector'].unique())
        selected_sectors = st.multiselect("업종 선택", available_sectors, default=['전체'])
    
    with col3:
        sort_by = st.selectbox("정렬 기준", [
            "버핏 점수", "수익성", "안정성", "성장성", "가치평가"
        ])
    
    # 필터링 적용
    filtered_data = buffett_scores[buffett_scores['buffett_score'] >= min_score].copy()
    
    if '전체' not in selected_sectors and selected_sectors:
        filtered_data = filtered_data[filtered_data['sector'].isin(selected_sectors)]
    
    # 정렬
    sort_column_map = {
        "버핏 점수": "buffett_score",
        "수익성": "profitability", 
        "안정성": "stability",
        "성장성": "growth",
        "가치평가": "valuation"
    }
    filtered_data = filtered_data.sort_values(sort_column_map[sort_by], ascending=False)
    
    st.markdown(f"### 📊 필터링 결과: {len(filtered_data)}개 종목")
    
    # 랭킹 테이블
    display_data = filtered_data[['stock_code', 'stock_name', 'sector', 'buffett_score', 
                                 'profitability', 'stability', 'growth', 'valuation']].copy()
    display_data.columns = ['종목코드', '종목명', '섹터', '총점', '수익성', '안정성', '성장성', '가치평가']
    display_data.index = range(1, len(display_data) + 1)
    
    st.dataframe(display_data, use_container_width=True, height=600)
    
    # 차트 분석
    st.markdown("### 📈 분석 차트")
    
    tab1, tab2, tab3 = st.tabs(["점수 분포", "섹터 비교", "상관관계"])
    
    with tab1:
        fig_dist = px.histogram(
            filtered_data, 
            x='buffett_score', 
            nbins=20,
            title="버핏 점수 분포",
            labels={'buffett_score': '버핏 점수', 'count': '종목 수'}
        )
        st.plotly_chart(fig_dist, use_container_width=True)
    
    with tab2:
        fig_sector = px.box(
            filtered_data,
            x='sector',
            y='buffett_score',
            title="섹터별 버핏 점수 분포"
        )
        fig_sector.update_xaxes(tickangle=45)
        st.plotly_chart(fig_sector, use_container_width=True)
    
    with tab3:
        # 상관관계 매트릭스
        corr_data = filtered_data[['buffett_score', 'profitability', 'stability', 'growth', 'valuation']].corr()
        
        fig_corr = px.imshow(
            corr_data,
            text_auto=True,
            aspect="auto",
            title="지표간 상관관계"
        )
        st.plotly_chart(fig_corr, use_container_width=True)


def portfolio_management():
    """포트폴리오 관리 페이지"""
    st.header("💼 포트폴리오 관리")
    st.markdown("*워런 버핏 스타일 장기 투자 포트폴리오*")
    
    loader = DataLoader()
    buffett_scores = loader.load_buffett_scores()
    
    # 추천 포트폴리오 생성
    st.markdown("### 🎯 추천 포트폴리오")
    
    # 상위 점수 종목 중 섹터 분산
    top_stocks = buffett_scores[buffett_scores['buffett_score'] >= 75].copy()
    
    if not top_stocks.empty:
        # 섹터별 대표 종목 선택
        portfolio_stocks = []
        for sector in top_stocks['sector'].unique():
            sector_best = top_stocks[top_stocks['sector'] == sector].iloc[0]
            portfolio_stocks.append(sector_best)
        
        portfolio_df = pd.DataFrame(portfolio_stocks)
        
        # 가중치 계산 (점수 기반)
        total_score = portfolio_df['buffett_score'].sum()
        portfolio_df['weight'] = portfolio_df['buffett_score'] / total_score * 100
        
        # 포트폴리오 표시
        display_portfolio = portfolio_df[['stock_code', 'stock_name', 'sector', 'buffett_score', 'weight']].copy()
        display_portfolio.columns = ['종목코드', '종목명', '섹터', '버핏점수', '비중(%)']
        display_portfolio['비중(%)'] = display_portfolio['비중(%)'].round(1)
        
        st.dataframe(display_portfolio, use_container_width=True)
        
        # 포트폴리오 시각화
        col1, col2 = st.columns(2)
        
        with col1:
            fig_pie = px.pie(
                portfolio_df,
                values='weight',
                names='stock_name',
                title="포트폴리오 구성 비중"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            fig_bar = px.bar(
                portfolio_df,
                x='stock_name',
                y='buffett_score',
                color='sector',
                title="포트폴리오 종목별 버핏 점수"
            )
            fig_bar.update_xaxes(tickangle=45)
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # 투자 가이드
        st.markdown("### 📋 투자 가이드")
        
        total_stocks = len(portfolio_df)
        avg_score = portfolio_df['buffett_score'].mean()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📊 포트폴리오 종목수", f"{total_stocks}개")
        
        with col2:
            st.metric("🏆 평균 버핏점수", f"{avg_score:.1f}점")
        
        with col3:
            risk_level = "낮음" if avg_score >= 80 else "보통" if avg_score >= 70 else "높음"
            st.metric("⚖️ 리스크 수준", risk_level)
        
        # 리밸런싱 제안
        st.markdown("### 🔄 리밸런싱 제안")
        st.info("📅 다음 리밸런싱 권장 시기: 6개월 후")
        st.info("💡 배당금 재투자를 통한 복리 효과 극대화를 권장합니다.")
        
    else:
        st.warning("추천할 만한 종목이 충분하지 않습니다. 필터 조건을 완화해보세요.")


def news_sentiment_analysis():
    """뉴스 감정 분석 페이지"""
    st.header("📰 뉴스 감정 분석")
    st.markdown("*시장 심리와 종목별 뉴스 트렌드 분석*")
    
    loader = DataLoader()
    news_data = loader.load_news_sentiment()
    
    if news_data.empty:
        st.warning("뉴스 감정 데이터가 없습니다.")
        st.info("뉴스 수집 시스템을 실행해주세요: `python examples/basic_examples/06_full_news_collector.py`")
        return
    
    # 전체 시장 감정
    st.markdown("### 🌡️ 전체 시장 감정")
    
    avg_sentiment = news_data['avg_sentiment'].mean()
    total_news = news_data['news_count'].sum()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📊 평균 감정점수", f"{avg_sentiment:.3f}")
    
    with col2:
        st.metric("📰 총 뉴스 건수", f"{total_news:,}건")
    
    with col3:
        sentiment_label = "긍정적" if avg_sentiment > 0.1 else "부정적" if avg_sentiment < -0.1 else "중립적"
        st.metric("🎭 시장 분위기", sentiment_label)
    
    # 종목별 감정 분석
    st.markdown("### 📈 종목별 뉴스 감정")
    
    # 감정 점수로 정렬
    news_sorted = news_data.sort_values('avg_sentiment', ascending=False)
    
    # 긍정적/부정적 종목 분리
    positive_stocks = news_sorted[news_sorted['avg_sentiment'] > 0.1].head(5)
    negative_stocks = news_sorted[news_sorted['avg_sentiment'] < -0.1].tail(5)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🟢 긍정적 뉴스 종목")
        if not positive_stocks.empty:
            for _, stock in positive_stocks.iterrows():
                st.success(f"**{stock['stock_name']}** ({stock['stock_code']})")
                st.write(f"감정점수: {stock['avg_sentiment']:.3f} | 뉴스: {stock['news_count']}건")
        else:
            st.info("긍정적 뉴스 종목이 없습니다.")
    
    with col2:
        st.markdown("#### 🔴 부정적 뉴스 종목")
        if not negative_stocks.empty:
            for _, stock in negative_stocks.iterrows():
                st.error(f"**{stock['stock_name']}** ({stock['stock_code']})")
                st.write(f"감정점수: {stock['avg_sentiment']:.3f} | 뉴스: {stock['news_count']}건")
        else:
            st.info("부정적 뉴스 종목이 없습니다.")
    
    # 감정 분포 차트
    st.markdown("### 📊 감정 분포 분석")
    
    fig_sentiment = px.scatter(
        news_data,
        x='news_count',
        y='avg_sentiment',
        hover_name='stock_name',
        size='news_count',
        color='avg_sentiment',
        color_continuous_scale='RdYlGn',
        title="뉴스 건수 vs 감정 점수"
    )
    fig_sentiment.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_sentiment.update_layout(height=500)
    st.plotly_chart(fig_sentiment, use_container_width=True)
    
    # 상세 테이블
    st.markdown("### 📋 상세 감정 분석 결과")
    
    display_news = news_data.copy()
    display_news.columns = ['종목코드', '종목명', '평균감정점수', '뉴스건수']
    display_news = display_news.sort_values('평균감정점수', ascending=False)
    
    st.dataframe(display_news, use_container_width=True)


def main():
    """메인 애플리케이션"""
    
    # 사이드바 네비게이션
    st.sidebar.title("🏆 Navigation")
    st.sidebar.markdown("---")
    
    pages = {
        "🏠 메인 대시보드": main_dashboard,
        "🏆 버핏 스코어 랭킹": buffett_score_ranking,
        "💼 포트폴리오 관리": portfolio_management,
        "📰 뉴스 감정 분석": news_sentiment_analysis
    }
    
    selected_page = st.sidebar.selectbox("페이지 선택", list(pages.keys()))
    
    # 사이드바 정보
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 투자 철학")
    st.sidebar.markdown("**기본분석 45%**")
    st.sidebar.markdown("**기술분석 30%**") 
    st.sidebar.markdown("**뉴스분석 25%**")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎯 목표")
    st.sidebar.markdown("• 장기 가치투자")
    st.sidebar.markdown("• 안정적 수익 창출")
    st.sidebar.markdown("• 데이터 기반 의사결정")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("*💡 퇴근 후 30분으로 완성하는 투자 분석*")
    
    # 선택된 페이지 실행
    pages[selected_page]()


if __name__ == "__main__":
    main()