"""
간단한 뉴스 대시보드 (기본 테이블만 사용)
sentiment_analysis, investment_signals 테이블 없이도 작동
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
    page_title="뉴스 감정분석 대시보드",
    page_icon="📰",
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
    .positive-sentiment { 
        background-color: #d4edda; 
        padding: 0.5rem; 
        border-radius: 5px; 
        margin: 0.2rem 0;
    }
    .negative-sentiment { 
        background-color: #f8d7da; 
        padding: 0.5rem; 
        border-radius: 5px; 
        margin: 0.2rem 0;
    }
    .neutral-sentiment { 
        background-color: #fff3cd; 
        padding: 0.5rem; 
        border-radius: 5px; 
        margin: 0.2rem 0;
    }
</style>
""", unsafe_allow_html=True)

def safe_parse_date(date_series):
    """안전한 날짜 파싱 (여러 형식 지원)"""
    try:
        # 먼저 mixed 형식으로 시도
        return pd.to_datetime(date_series, format='mixed', errors='coerce')
    except:
        try:
            # ISO8601 형식으로 시도
            return pd.to_datetime(date_series, format='ISO8601', errors='coerce')
        except:
            try:
                # 기본 파서로 시도
                return pd.to_datetime(date_series, errors='coerce')
            except:
                # 마지막 수단: 현재 날짜로 대체
                return pd.to_datetime('today')

@st.cache_data(ttl=300)  # 5분 캐시
def load_news_data():
    """뉴스 데이터만 로드"""
    try:
        db_path = Path("finance_data.db")
        if not db_path.exists():
            return None, None
        
        with sqlite3.connect(db_path) as conn:
            # 기본 뉴스 데이터
            news_query = """
                SELECT stock_code, stock_name, title, pub_date, sentiment_score, 
                       sentiment_label, collected_at, link, source
                FROM news_articles 
                ORDER BY collected_at DESC
                LIMIT 1000
            """
            news_df = pd.read_sql_query(news_query, conn)
            
            # 요약 통계
            summary_query = """
                SELECT 
                    COUNT(*) as total_news,
                    COUNT(DISTINCT stock_code) as covered_stocks,
                    AVG(sentiment_score) as avg_sentiment,
                    MAX(collected_at) as last_update
                FROM news_articles
                WHERE DATE(collected_at) >= DATE('now', '-7 days')
            """
            summary_df = pd.read_sql_query(summary_query, conn)
            
            return news_df, summary_df
            
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return None, None

def check_basic_data():
    """기본 데이터 존재 여부 확인"""
    db_path = Path("finance_data.db")
    if not db_path.exists():
        return False, "데이터베이스 파일이 없습니다."
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # news_articles 테이블 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='news_articles'")
            if not cursor.fetchone():
                return False, "news_articles 테이블이 없습니다."
            
            # 뉴스 데이터 확인
            cursor.execute("SELECT COUNT(*) FROM news_articles")
            news_count = cursor.fetchone()[0]
            
            if news_count == 0:
                return False, "수집된 뉴스가 없습니다."
            
            return True, f"총 {news_count:,}개의 뉴스가 있습니다."
            
    except Exception as e:
        return False, f"데이터베이스 오류: {e}"

def display_main_dashboard():
    """메인 대시보드 표시"""
    
    # 헤더
    st.markdown("""
    <div class="main-header">
        <h1>📰 뉴스 감정분석 대시보드</h1>
        <p>수집된 뉴스 데이터 분석 및 감정 지수 확인</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 데이터 가용성 확인
    data_available, message = check_basic_data()
    
    if not data_available:
        st.error(f"❌ {message}")
        st.info("""
        **해결 방법:**
        1. 뉴스 수집을 먼저 실행하세요:
           ```
           python examples/basic_examples/06_full_news_collector.py
           ```
        2. 감정분석을 실행하세요:
           ```
           python examples/basic_examples/07_buffett_sentiment_analyzer.py
           ```
        """)
        return
    
    st.success(f"✅ {message}")
    
    # 데이터 로드
    news_df, summary_df = load_news_data()
    
    if news_df is None or len(news_df) == 0:
        st.warning("⚠️ 뉴스 데이터를 불러올 수 없습니다.")
        
        # 새로고침 버튼
        if st.button("🔄 데이터 새로고침", key="refresh_data"):
            st.cache_data.clear()
            st.experimental_rerun()
        return
    
    # 사이드바 필터
    st.sidebar.header("📊 필터 설정")
    
    # 감정 필터
    sentiment_filter = st.sidebar.selectbox(
        "감정 유형",
        ["전체", "긍정", "부정", "중립"]
    )
    
    # 날짜 필터
    days_back = st.sidebar.slider("몇 일 전까지", 1, 30, 7)
    
    # 데이터 필터링
    filtered_news = news_df.copy()
    
    # 날짜 필터링
    cutoff_date = datetime.now() - timedelta(days=days_back)
    filtered_news = filtered_news[pd.to_datetime(filtered_news['collected_at']) >= cutoff_date]
    
    # 감정 필터링
    if sentiment_filter != "전체":
        sentiment_map = {"긍정": "positive", "부정": "negative", "중립": "neutral"}
        filtered_news = filtered_news[filtered_news['sentiment_label'] == sentiment_map[sentiment_filter]]
    
    # 메인 지표
    col1, col2, col3, col4 = st.columns(4)
    
    if summary_df is not None and len(summary_df) > 0:
        summary = summary_df.iloc[0]
        
        with col1:
            st.metric("📰 최근 7일 뉴스", f"{summary['total_news']:,}개")
        
        with col2:
            st.metric("🏢 분석 종목", f"{summary['covered_stocks']:,}개")
        
        with col3:
            if pd.notna(summary['avg_sentiment']):
                avg_sentiment = summary['avg_sentiment']
                sentiment_emoji = "😊" if avg_sentiment > 0.1 else "😐" if avg_sentiment > -0.1 else "😔"
                st.metric("📊 평균 감정", f"{avg_sentiment:.3f} {sentiment_emoji}")
            else:
                st.metric("📊 평균 감정", "분석 중...")
        
        with col4:
            if pd.notna(summary['last_update']):
                try:
                    last_update = safe_parse_date(pd.Series([summary['last_update']])).iloc[0]
                    hours_ago = (datetime.now() - last_update).total_seconds() / 3600
                    st.metric("🕐 마지막 업데이트", f"{hours_ago:.1f}시간 전")
                except:
                    st.metric("🕐 마지막 업데이트", "시간 계산 오류")
            else:
                st.metric("🕐 마지막 업데이트", "알 수 없음")
    
    # 감정 분석이 된 뉴스만 필터링
    analyzed_news = filtered_news[filtered_news['sentiment_score'].notna()]
    
    if len(analyzed_news) == 0:
        st.warning("⚠️ 감정분석된 뉴스가 없습니다. 먼저 감정분석을 실행해주세요.")
        st.code("python examples/basic_examples/07_buffett_sentiment_analyzer.py")
        return
    
    # 감정 분포 차트
    st.header("📊 감정 분포 분석")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 감정 라벨 분포
        if 'sentiment_label' in analyzed_news.columns:
            sentiment_counts = analyzed_news['sentiment_label'].value_counts()
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
    
    with col2:
        # 감정 점수 히스토그램
        sentiment_scores = analyzed_news['sentiment_score'].dropna()
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
    
    # 종목별 감정 점수
    st.header("📈 종목별 평균 감정 점수")
    
    if len(analyzed_news) > 0:
        stock_sentiment = analyzed_news.groupby(['stock_code', 'stock_name'])['sentiment_score'].agg(['mean', 'count']).reset_index()
        stock_sentiment = stock_sentiment[stock_sentiment['count'] >= 2]  # 2개 이상 뉴스가 있는 종목만
        stock_sentiment = stock_sentiment.sort_values('mean', ascending=False).head(20)
        
        if len(stock_sentiment) > 0:
            fig_bar = px.bar(
                stock_sentiment,
                x='stock_code',
                y='mean',
                hover_data=['stock_name', 'count'],
                title="종목별 평균 감정 점수 (상위 20개)",
                color='mean',
                color_continuous_scale='RdYlGn'
            )
            fig_bar.update_xaxes(title="종목코드")
            fig_bar.update_yaxes(title="평균 감정 점수")
            fig_bar.add_hline(y=0, line_dash="dash", line_color="red")
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("종목별 감정 분석을 위한 충분한 데이터가 없습니다.")
    
    # 일별 감정 추이
    st.header("📅 일별 감정 추이")
    
    if len(analyzed_news) > 0:
        try:
            # 안전한 날짜 파싱
            analyzed_news['date'] = safe_parse_date(analyzed_news['pub_date']).dt.date
            
            # 날짜가 유효한 것만 필터링
            analyzed_news = analyzed_news[analyzed_news['date'].notna()]
            
            if len(analyzed_news) > 0:
                daily_sentiment = analyzed_news.groupby('date')['sentiment_score'].agg(['mean', 'count']).reset_index()
                daily_sentiment = daily_sentiment.sort_values('date')
                
                if len(daily_sentiment) > 0:
                    fig_line = px.line(
                        daily_sentiment,
                        x='date',
                        y='mean',
                        title="일별 평균 감정 점수",
                        hover_data=['count']
                    )
                    fig_line.add_hline(y=0, line_dash="dash", line_color="red")
                    fig_line.update_xaxes(title="날짜")
                    fig_line.update_yaxes(title="평균 감정 점수")
                    st.plotly_chart(fig_line, use_container_width=True)
                else:
                    st.info("일별 감정 추이를 생성할 수 있는 데이터가 없습니다.")
            else:
                st.info("유효한 날짜 데이터가 없습니다.")
        except Exception as e:
            st.warning(f"일별 감정 추이 생성 중 오류: {e}")
            st.info("날짜 형식 문제로 일별 추이를 표시할 수 없습니다.")
    
    # 최근 뉴스 테이블
    st.header("📰 최근 뉴스 분석 결과")
    
    if len(analyzed_news) > 0:
        # 표시할 컬럼 선택
        display_columns = ['stock_name', 'title', 'sentiment_score', 'sentiment_label', 'pub_date', 'source']
        available_columns = [col for col in display_columns if col in analyzed_news.columns]
        
        display_news = analyzed_news[available_columns].head(20)
        
        # 감정 라벨 표시 개선
        if 'sentiment_label' in display_news.columns:
            def format_sentiment(row):
                score = row.get('sentiment_score', 0)
                label = row.get('sentiment_label', 'unknown')
                
                if label == 'positive':
                    return f"😊 긍정 ({score:.3f})"
                elif label == 'negative':
                    return f"😔 부정 ({score:.3f})"
                else:
                    return f"😐 중립 ({score:.3f})"
            
            display_news = display_news.copy()
            display_news['감정분석'] = display_news.apply(format_sentiment, axis=1)
            display_news = display_news.drop(['sentiment_score', 'sentiment_label'], axis=1, errors='ignore')
        
        st.dataframe(display_news, use_container_width=True)
    else:
        st.info("표시할 뉴스가 없습니다.")
    
    # 새로고침 버튼
    st.markdown("---")
    col1, col2, col3 = st.columns([1,1,1])
    
    with col2:
        if st.button("🔄 데이터 새로고침", key="refresh_main"):
            st.cache_data.clear()
            st.experimental_rerun()

def main():
    """메인 함수"""
    
    # 사이드바 메뉴
    st.sidebar.title("🎯 메뉴")
    
    menu_options = [
        "📊 뉴스 감정 대시보드",
        "🔍 뉴스 검색",
        "⚙️ 시스템 상태"
    ]
    
    selected_menu = st.sidebar.selectbox("메뉴 선택", menu_options)
    
    if selected_menu == "📊 뉴스 감정 대시보드":
        display_main_dashboard()
    
    elif selected_menu == "🔍 뉴스 검색":
        st.header("🔍 뉴스 검색")
        
        search_term = st.text_input("검색어 입력")
        
        if search_term:
            news_df, _ = load_news_data()
            
            if news_df is not None:
                # 제목에서 검색
                search_results = news_df[news_df['title'].str.contains(search_term, case=False, na=False)]
                
                st.info(f"'{search_term}' 검색 결과: {len(search_results)}건")
                
                if len(search_results) > 0:
                    # 안전한 컬럼 선택
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
        
        data_available, message = check_basic_data()
        
        if data_available:
            st.success(f"✅ 시스템 정상: {message}")
            
            # 데이터베이스 통계
            try:
                with sqlite3.connect("finance_data.db") as conn:
                    cursor = conn.cursor()
                    
                    # 테이블 목록
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    st.subheader("데이터베이스 테이블")
                    for table in tables:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        st.write(f"📋 {table}: {count:,}개 레코드")
                    
                    # 최근 뉴스 수집 상태
                    if 'news_articles' in tables:
                        cursor.execute("""
                            SELECT DATE(collected_at) as date, COUNT(*) as count
                            FROM news_articles
                            WHERE DATE(collected_at) >= DATE('now', '-7 days')
                            GROUP BY DATE(collected_at)
                            ORDER BY date DESC
                        """)
                        recent_collection = cursor.fetchall()
                        
                        if recent_collection:
                            st.subheader("최근 7일 뉴스 수집 현황")
                            for date, count in recent_collection:
                                st.write(f"📅 {date}: {count:,}건")
                    
            except Exception as e:
                st.error(f"통계 조회 오류: {e}")
        else:
            st.error(f"❌ 시스템 오류: {message}")
    
    # 푸터
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Finance Data Vibe**")
    st.sidebar.markdown("뉴스 기반 감정분석 시스템")
    st.sidebar.markdown(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    main()