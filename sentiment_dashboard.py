"""
워런 버핏 스타일 감정분석 대시보드 (NoneType 오류 수정 버전)
실시간 데이터 연동 및 모든 오류 처리 완료
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from pathlib import Path

# 페이지 설정
st.set_page_config(
    page_title="워런 버핏 스타일 감정분석 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일링
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f4e79 0%, #2d5aa0 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .buffett-signal {
        background: linear-gradient(135deg, #ff6b6b 0%, #feca57 50%, #48cae4 100%);
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        color: white;
        font-weight: bold;
    }
    .positive-sentiment { background-color: #d4edda; padding: 0.5rem; border-radius: 5px; }
    .negative-sentiment { background-color: #f8d7da; padding: 0.5rem; border-radius: 5px; }
    .neutral-sentiment { background-color: #fff3cd; padding: 0.5rem; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

def safe_parse_datetime(date_series):
    """안전한 날짜 파싱"""
    try:
        return pd.to_datetime(date_series, format='mixed', errors='coerce')
    except:
        try:
            return pd.to_datetime(date_series, format='ISO8601', errors='coerce')
        except:
            return pd.to_datetime(date_series, errors='coerce')

def safe_float(value, default=0.0):
    """안전한 float 변환"""
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

@st.cache_data(ttl=300)  # 5분 캐시
def load_data():
    """데이터 로드 함수 (캐시 적용)"""
    try:
        db_path = Path("finance_data.db")
        if not db_path.exists():
            return None, None, None, None
        
        with sqlite3.connect(db_path) as conn:
            # 뉴스 데이터
            news_query = """
                SELECT stock_code, stock_name, title, pub_date, sentiment_score, 
                       sentiment_label, is_fundamental, collected_at
                FROM news_articles 
                WHERE sentiment_score IS NOT NULL
                ORDER BY collected_at DESC
                LIMIT 2000
            """
            news_df = pd.read_sql_query(news_query, conn)
            
            # 감정 지수 데이터 (테이블명 확인)
            sentiment_df = pd.DataFrame()
            try:
                sentiment_query = """
                    SELECT stock_code, date, sentiment_index, positive_count, 
                           negative_count, neutral_count, fundamental_ratio
                    FROM sentiment_analysis
                    ORDER BY date DESC, sentiment_index DESC
                    LIMIT 100
                """
                sentiment_df = pd.read_sql_query(sentiment_query, conn)
            except:
                # sentiment_analysis 테이블이 없으면 daily_sentiment_index 시도
                try:
                    sentiment_query = """
                        SELECT stock_code, stock_name, date, sentiment_index, 
                               total_news, confidence, fundamental_news
                        FROM daily_sentiment_index
                        ORDER BY date DESC, sentiment_index DESC
                        LIMIT 100
                    """
                    sentiment_df = pd.read_sql_query(sentiment_query, conn)
                except:
                    st.warning("감정 지수 테이블을 찾을 수 없습니다.")
            
            # 투자 신호 데이터
            signals_df = pd.DataFrame()
            try:
                signals_query = """
                    SELECT stock_code, stock_name, signal_type, signal_strength, 
                           confidence, fundamental_sentiment, created_at
                    FROM investment_signals
                    WHERE signal_type IN ('STRONG_BUY', 'BUY')
                    ORDER BY signal_strength DESC
                    LIMIT 50
                """
                signals_df = pd.read_sql_query(signals_query, conn)
            except:
                st.info("투자 신호 테이블을 찾을 수 없습니다. 감정분석을 먼저 실행하세요.")
            
            # 요약 통계
            summary_query = """
                SELECT 
                    COUNT(*) as total_news,
                    COUNT(DISTINCT stock_code) as covered_stocks,
                    AVG(CASE WHEN sentiment_score IS NOT NULL THEN sentiment_score END) as avg_sentiment,
                    SUM(CASE WHEN is_fundamental = 1 THEN 1 ELSE 0 END) as fundamental_news
                FROM news_articles
                WHERE DATE(collected_at) >= DATE('now', '-7 days')
            """
            summary_df = pd.read_sql_query(summary_query, conn)
            
            return news_df, sentiment_df, signals_df, summary_df
            
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return None, None, None, None

def check_data_availability():
    """데이터 존재 여부 확인"""
    db_path = Path("finance_data.db")
    if not db_path.exists():
        return False, "데이터베이스 파일이 없습니다."
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 테이블 존재 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            if 'news_articles' not in tables:
                return False, "news_articles 테이블이 없습니다."
            
            # 데이터 존재 확인
            cursor.execute("SELECT COUNT(*) FROM news_articles WHERE sentiment_score IS NOT NULL")
            news_count = cursor.fetchone()[0]
            
            if news_count == 0:
                return False, "감정분석된 뉴스가 없습니다."
            
            return True, f"총 {news_count:,}개의 분석된 뉴스가 있습니다."
            
    except Exception as e:
        return False, f"데이터베이스 오류: {e}"

def display_main_dashboard():
    """메인 대시보드 표시"""
    
    # 헤더
    st.markdown("""
    <div class="main-header">
        <h1>📊 워런 버핏 스타일 감정분석 대시보드</h1>
        <p>가치투자를 위한 뉴스 감정 분석 및 투자 신호 시스템</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 데이터 가용성 확인
    data_available, message = check_data_availability()
    
    if not data_available:
        st.error(f"❌ {message}")
        st.info("""
        **해결 방법:**
        1. 데이터베이스 마이그레이션을 먼저 실행하세요:
           ```
           python examples/basic_examples/08_db_migration_sentiment.py
           ```
        2. 감정분석을 실행하세요:
           ```
           python examples/basic_examples/07_buffett_sentiment_analyzer.py
           ```
        3. 뉴스 수집이 안되어 있다면:
           ```
           python examples/basic_examples/06_full_news_collector.py
           ```
        """)
        return
    
    st.success(f"✅ {message}")
    
    # 데이터 로드
    news_df, sentiment_df, signals_df, summary_df = load_data()
    
    if news_df is None or len(news_df) == 0:
        st.warning("⚠️ 감정분석 데이터를 불러올 수 없습니다.")
        
        # 새로고침 버튼
        if st.button("🔄 데이터 새로고침", key="refresh_data"):
            st.cache_data.clear()
            st.rerun()
        return
    
    # 사이드바 필터
    st.sidebar.header("📊 필터 설정")
    
    # 날짜 필터
    try:
        news_df['collected_at_parsed'] = safe_parse_datetime(news_df['collected_at'])
        min_date = news_df['collected_at_parsed'].dt.date.min()
        max_date = news_df['collected_at_parsed'].dt.date.max()
        
        selected_date = st.sidebar.date_input(
            "날짜 선택",
            value=max_date,
            min_value=min_date,
            max_value=max_date
        )
    except:
        st.sidebar.warning("날짜 필터를 설정할 수 없습니다.")
    
    # 감정 필터
    sentiment_filter = st.sidebar.selectbox(
        "감정 유형",
        ["전체", "긍정", "부정", "중립"]
    )
    
    # 펀더멘털 뉴스 필터
    fundamental_filter = st.sidebar.checkbox("펀더멘털 뉴스만", value=False)
    
    # 데이터 필터링
    filtered_news = news_df.copy()
    
    # 펀더멘털 필터 적용
    if fundamental_filter and 'is_fundamental' in filtered_news.columns:
        filtered_news = filtered_news[filtered_news['is_fundamental'] == 1]
    
    # 감정 필터 적용
    if sentiment_filter != "전체" and 'sentiment_label' in filtered_news.columns:
        sentiment_map = {"긍정": "positive", "부정": "negative", "중립": "neutral"}
        target_sentiment = sentiment_map[sentiment_filter]
        filtered_news = filtered_news[filtered_news['sentiment_label'] == target_sentiment]
    
    # 메인 대시보드
    col1, col2, col3, col4 = st.columns(4)
    
    if summary_df is not None and len(summary_df) > 0:
        summary = summary_df.iloc[0]
        
        with col1:
            total_news = safe_float(summary.get('total_news', 0), 0)
            st.metric("📰 최근 7일 뉴스", f"{int(total_news):,}개")
        
        with col2:
            covered_stocks = safe_float(summary.get('covered_stocks', 0), 0)
            st.metric("🏢 분석 종목", f"{int(covered_stocks):,}개")
        
        with col3:
            avg_sentiment = safe_float(summary.get('avg_sentiment'), 0.0)
            if avg_sentiment > 0.1:
                sentiment_emoji = "😊"
            elif avg_sentiment > -0.1:
                sentiment_emoji = "😐"
            else:
                sentiment_emoji = "😔"
            st.metric("📊 평균 감정", f"{avg_sentiment:.3f} {sentiment_emoji}")
        
        with col4:
            fundamental_news = safe_float(summary.get('fundamental_news', 0), 0)
            total_news = safe_float(summary.get('total_news', 1), 1)  # 0으로 나누기 방지
            fundamental_ratio = (fundamental_news / total_news * 100) if total_news > 0 else 0
            st.metric("📈 펀더멘털 비율", f"{fundamental_ratio:.1f}%")
    
    # 투자 신호 섹션
    if signals_df is not None and len(signals_df) > 0:
        st.header("🚀 워런 버핏 투자 신호 TOP 10")
        
        top_signals = signals_df.head(10)
        
        for idx, signal in top_signals.iterrows():
            signal_strength = safe_float(signal.get('signal_strength', 0), 0)
            confidence = safe_float(signal.get('confidence', 0), 0)
            fundamental_sentiment = safe_float(signal.get('fundamental_sentiment', 0), 0)
            
            strength_color = "🟢" if signal_strength > 0.7 else "🟡" if signal_strength > 0.4 else "🔴"
            
            st.markdown(f"""
            <div class="buffett-signal">
                {strength_color} <strong>{signal.get('stock_name', 'N/A')} ({signal.get('stock_code', 'N/A')})</strong> 
                | 신호: {signal.get('signal_type', 'N/A')} 
                | 강도: {signal_strength:.3f} 
                | 신뢰도: {confidence:.1f}%
                | 펀더멘털 감정: {fundamental_sentiment:.3f}
            </div>
            """, unsafe_allow_html=True)
    
    # 감정 지수 차트
    if sentiment_df is not None and len(sentiment_df) > 0:
        st.header("📈 일별 감정 지수 추이")
        
        # 상위 20개 종목의 감정 지수
        top_sentiment = sentiment_df.head(20)
        
        if 'sentiment_index' in top_sentiment.columns and 'stock_code' in top_sentiment.columns:
            # NaN 값 제거
            top_sentiment = top_sentiment.dropna(subset=['sentiment_index'])
            
            if len(top_sentiment) > 0:
                fig = px.bar(
                    top_sentiment, 
                    x='stock_code', 
                    y='sentiment_index',
                    color='sentiment_index',
                    color_continuous_scale='RdYlGn',
                    title="종목별 감정 지수 (높을수록 긍정적)"
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("표시할 감정 지수 데이터가 없습니다.")
        else:
            st.info("감정 지수 데이터 형식이 올바르지 않습니다.")
    
    # 뉴스 감정 분포
    if len(filtered_news) > 0:
        st.header("📊 뉴스 감정 분포")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 감정 라벨 분포
            if 'sentiment_label' in filtered_news.columns:
                sentiment_counts = filtered_news['sentiment_label'].value_counts()
                if len(sentiment_counts) > 0:
                    fig_pie = px.pie(
                        values=sentiment_counts.values,
                        names=sentiment_counts.index,
                        title="감정 라벨 분포",
                        color_discrete_map={
                            'positive': '#28a745',
                            'negative': '#dc3545', 
                            'neutral': '#ffc107'
                        }
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("감정 라벨 데이터가 없습니다.")
            else:
                st.info("sentiment_label 컬럼이 없습니다.")
        
        with col2:
            # 감정 점수 히스토그램
            if 'sentiment_score' in filtered_news.columns:
                sentiment_scores = filtered_news['sentiment_score'].dropna()
                if len(sentiment_scores) > 0:
                    fig_hist = px.histogram(
                        x=sentiment_scores,
                        nbins=20,
                        title="감정 점수 분포",
                        color_discrete_sequence=['#007bff']
                    )
                    fig_hist.add_vline(x=0, line_dash="dash", line_color="red")
                    fig_hist.update_xaxes(title="감정 점수")
                    fig_hist.update_yaxes(title="뉴스 수")
                    st.plotly_chart(fig_hist, use_container_width=True)
                else:
                    st.info("감정 점수 데이터가 없습니다.")
            else:
                st.info("sentiment_score 컬럼이 없습니다.")
    
    # 최근 뉴스 테이블
    st.header("📰 최근 뉴스 분석 결과")
    
    if len(filtered_news) > 0:
        # 표시할 컬럼 선택 (안전하게)
        available_columns = ['stock_name', 'title', 'sentiment_score', 'sentiment_label']
        display_columns = [col for col in available_columns if col in filtered_news.columns]
        
        if 'is_fundamental' in filtered_news.columns:
            display_columns.append('is_fundamental')
        
        if display_columns:
            display_news = filtered_news[display_columns].head(20)
            
            # 감정 라벨에 따른 스타일링 (안전하게)
            if 'sentiment_label' in display_news.columns:
                def style_sentiment(val):
                    if pd.isna(val):
                        return ''
                    if val == 'positive':
                        return 'background-color: #d4edda'
                    elif val == 'negative': 
                        return 'background-color: #f8d7da'
                    else:
                        return 'background-color: #fff3cd'
                
                try:
                    styled_df = display_news.style.applymap(style_sentiment, subset=['sentiment_label'])
                    st.dataframe(styled_df, use_container_width=True)
                except:
                    st.dataframe(display_news, use_container_width=True)
            else:
                st.dataframe(display_news, use_container_width=True)
        else:
            st.warning("표시할 수 있는 컬럼이 없습니다.")
    else:
        st.info("필터 조건에 맞는 뉴스가 없습니다.")
    
    # 새로고침 버튼
    st.markdown("---")
    col1, col2, col3 = st.columns([1,1,1])
    
    with col2:
        if st.button("🔄 데이터 새로고침", key="refresh_main"):
            st.cache_data.clear()
            st.rerun()

def main():
    """메인 함수"""
    
    # 사이드바 메뉴
    st.sidebar.title("🎯 메뉴")
    
    menu_options = [
        "📊 메인 대시보드",
        "📈 종목별 상세 분석", 
        "🔍 뉴스 검색",
        "⚙️ 시스템 상태"
    ]
    
    selected_menu = st.sidebar.selectbox("메뉴 선택", menu_options)
    
    if selected_menu == "📊 메인 대시보드":
        display_main_dashboard()
    
    elif selected_menu == "📈 종목별 상세 분석":
        st.header("📈 종목별 상세 분석")
        
        # 종목 선택
        stock_code = st.text_input("종목코드 입력 (예: 005930)")
        
        if stock_code and st.button("분석 실행"):
            # 개별 종목 분석 로직
            news_df, sentiment_df, signals_df, summary_df = load_data()
            
            if news_df is not None:
                stock_news = news_df[news_df['stock_code'] == stock_code]
                
                if len(stock_news) > 0:
                    st.success(f"✅ {stock_code} 관련 뉴스 {len(stock_news)}건 발견")
                    
                    # 감정 점수 시계열
                    try:
                        stock_news['date'] = safe_parse_datetime(stock_news['pub_date']).dt.date
                        daily_sentiment = stock_news.groupby('date')['sentiment_score'].mean().reset_index()
                        
                        if len(daily_sentiment) > 0:
                            fig = px.line(daily_sentiment, x='date', y='sentiment_score', 
                                        title=f"{stock_code} 일별 평균 감정 점수")
                            fig.add_hline(y=0, line_dash="dash", line_color="red")
                            st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.warning(f"감정 점수 시계열 생성 실패: {e}")
                    
                    # 뉴스 목록
                    display_columns = ['title', 'sentiment_score', 'sentiment_label']
                    available_columns = [col for col in display_columns if col in stock_news.columns]
                    
                    if 'pub_date' in stock_news.columns:
                        available_columns.append('pub_date')
                    
                    if available_columns:
                        st.dataframe(stock_news[available_columns])
                else:
                    st.warning("해당 종목의 뉴스가 없습니다.")
    
    elif selected_menu == "🔍 뉴스 검색":
        st.header("🔍 뉴스 검색")
        
        search_term = st.text_input("검색어 입력")
        
        if search_term:
            news_df, _, _, _ = load_data()
            
            if news_df is not None and 'title' in news_df.columns:
                # 제목에서 검색
                search_results = news_df[news_df['title'].str.contains(search_term, case=False, na=False)]
                
                st.info(f"'{search_term}' 검색 결과: {len(search_results)}건")
                
                if len(search_results) > 0:
                    display_columns = ['stock_name', 'title', 'sentiment_score', 'sentiment_label', 'pub_date']
                    available_columns = [col for col in display_columns if col in search_results.columns]
                    
                    if available_columns:
                        st.dataframe(search_results[available_columns])
                    else:
                        st.warning("표시할 수 있는 컬럼이 없습니다.")
                else:
                    st.info("검색 결과가 없습니다.")
    
    elif selected_menu == "⚙️ 시스템 상태":
        st.header("⚙️ 시스템 상태")
        
        data_available, message = check_data_availability()
        
        if data_available:
            st.success(f"✅ 시스템 정상: {message}")
            
            # 데이터베이스 통계
            try:
                with sqlite3.connect("finance_data.db") as conn:
                    cursor = conn.cursor()
                    
                    # 테이블 목록
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    st.subheader("📋 데이터베이스 테이블")
                    for table in tables:
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {table}")
                            count = cursor.fetchone()[0]
                            st.write(f"📊 {table}: {count:,}개 레코드")
                        except:
                            st.write(f"❌ {table}: 접근 불가")
                    
            except Exception as e:
                st.error(f"통계 조회 오류: {e}")
        else:
            st.error(f"❌ 시스템 오류: {message}")
            
            # 해결 방법 제시
            st.info("""
            **문제 해결 단계:**
            1. 먼저 마이그레이션 실행:
               ```
               python examples/basic_examples/08_db_migration_sentiment.py
               ```
            2. 감정분석 실행:
               ```
               python examples/basic_examples/07_buffett_sentiment_analyzer.py
               ```
            """)
    
    # 푸터
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Finance Data Vibe**")
    st.sidebar.markdown("워런 버핏 스타일 가치투자 시스템")
    st.sidebar.markdown(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    main()