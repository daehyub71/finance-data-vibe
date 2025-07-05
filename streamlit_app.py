"""
🚀 Finance Data Vibe - 통합 시각적 대시보드
워런 버핏 스타일 가치투자를 위한 완전한 데이터 분석 시스템

실행 방법:
1. 터미널에서: streamlit run dashboard.py
2. 브라우저에서 자동으로 http://localhost:8501 열림

필요 패키지:
pip install streamlit plotly pandas sqlite3 numpy seaborn matplotlib

작성자: Finance Data Vibe Team
최종 업데이트: 2025-07-05
"""

import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import os
from pathlib import Path
import json

# 페이지 설정
st.set_page_config(
    page_title="Finance Data Vibe Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f4e79, #2d5a87);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .status-good { color: #10b981; }
    .status-warning { color: #f59e0b; }
    .status-error { color: #ef4444; }
</style>
""", unsafe_allow_html=True)

class FinanceDashboard:
    def __init__(self):
        """대시보드 초기화"""
        self.project_root = Path(__file__).parent
        self.data_dir = self.project_root / 'data'
        
        # 데이터베이스 경로들
        self.stock_db = self.data_dir / 'stock_data.db'
        self.dart_db = self.data_dir / 'dart_data.db'
        self.finance_db = self.project_root / 'finance_data.db'
        
        # 프로젝트 구조 정보
        self.structure_file = self.project_root / 'project_structure_report.json'
        
    def load_project_structure(self):
        """프로젝트 구조 정보 로드"""
        try:
            with open(self.structure_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    
    def get_database_info(self):
        """데이터베이스 정보 수집"""
        db_info = {}
        
        # Stock Database
        if self.stock_db.exists():
            try:
                conn = sqlite3.connect(self.stock_db)
                cursor = conn.cursor()
                
                # 테이블 정보
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                
                db_info['stock'] = {
                    'path': str(self.stock_db),
                    'size': self.stock_db.stat().st_size / (1024*1024),  # MB
                    'tables': tables,
                    'records': {}
                }
                
                # 각 테이블의 레코드 수
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    db_info['stock']['records'][table] = count
                
                conn.close()
            except Exception as e:
                db_info['stock'] = {'error': str(e)}
        
        # DART Database
        if self.dart_db.exists():
            try:
                conn = sqlite3.connect(self.dart_db)
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                
                db_info['dart'] = {
                    'path': str(self.dart_db),
                    'size': self.dart_db.stat().st_size / (1024*1024),
                    'tables': tables,
                    'records': {}
                }
                
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    db_info['dart']['records'][table] = count
                
                conn.close()
            except Exception as e:
                db_info['dart'] = {'error': str(e)}
        
        # Finance Database (뉴스)
        if self.finance_db.exists():
            try:
                conn = sqlite3.connect(self.finance_db)
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                
                db_info['finance'] = {
                    'path': str(self.finance_db),
                    'size': self.finance_db.stat().st_size / (1024*1024),
                    'tables': tables,
                    'records': {}
                }
                
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    db_info['finance']['records'][table] = count
                
                conn.close()
            except Exception as e:
                db_info['finance'] = {'error': str(e)}
        
        return db_info
    
    def load_stock_data_sample(self, limit=20):
        """주식 데이터 샘플 로드"""
        if not self.stock_db.exists():
            return None
        
        try:
            conn = sqlite3.connect(self.stock_db)
            
            # 종목 정보
            stock_info = pd.read_sql_query(
                "SELECT * FROM stock_info ORDER BY market_cap DESC LIMIT ?", 
                conn, 
                params=[limit]
            )
            
            # 최근 가격 데이터 (상위 5개 종목)
            if len(stock_info) > 0:
                top_symbols = stock_info['symbol'].head(5).tolist()
                placeholders = ','.join(['?' for _ in top_symbols])
                
                price_data = pd.read_sql_query(
                    f"""
                    SELECT sp.*, si.name 
                    FROM stock_prices sp
                    JOIN stock_info si ON sp.symbol = si.symbol
                    WHERE sp.symbol IN ({placeholders})
                    AND sp.date >= date('now', '-30 days')
                    ORDER BY sp.symbol, sp.date
                    """,
                    conn,
                    params=top_symbols
                )
                price_data['date'] = pd.to_datetime(price_data['date'])
            else:
                price_data = pd.DataFrame()
            
            conn.close()
            return stock_info, price_data
        except Exception as e:
            st.error(f"주식 데이터 로드 오류: {e}")
            return None, None
    
    def load_dart_data_sample(self):
        """DART 데이터 샘플 로드"""
        if not self.dart_db.exists():
            return None, None, None
        
        try:
            conn = sqlite3.connect(self.dart_db)
            
            # 기업 정보
            company_info = pd.read_sql_query(
                "SELECT * FROM company_info LIMIT 20", 
                conn
            )
            
            # 공시 정보
            disclosure_info = pd.read_sql_query(
                """
                SELECT * FROM disclosure_info 
                ORDER BY rcept_dt DESC 
                LIMIT 50
                """, 
                conn
            )
            
            # 재무제표 (최신)
            financial_data = pd.read_sql_query(
                """
                SELECT * FROM financial_statements 
                ORDER BY bsns_year DESC, reprt_code DESC
                LIMIT 30
                """, 
                conn
            )
            
            conn.close()
            return company_info, disclosure_info, financial_data
        except Exception as e:
            st.error(f"DART 데이터 로드 오류: {e}")
            return None, None, None
    
    def load_news_data_sample(self):
        """뉴스 데이터 샘플 로드"""
        if not self.finance_db.exists():
            return None
        
        try:
            conn = sqlite3.connect(self.finance_db)
            
            news_data = pd.read_sql_query(
                """
                SELECT * FROM news_articles 
                ORDER BY pub_date DESC 
                LIMIT 50
                """, 
                conn
            )
            
            if len(news_data) > 0:
                news_data['pub_date'] = pd.to_datetime(news_data['pub_date'])
            
            conn.close()
            return news_data
        except Exception as e:
            st.error(f"뉴스 데이터 로드 오류: {e}")
            return None

def main():
    # 대시보드 인스턴스 생성
    dashboard = FinanceDashboard()
    
    # 헤더
    st.markdown("""
    <div class="main-header">
        <h1>📈 Finance Data Vibe Dashboard</h1>
        <p>워런 버핏 스타일 가치투자를 위한 완전한 데이터 분석 시스템</p>
        <p>🎯 2,759개 종목 | 📋 DART 공시정보 | 📰 뉴스 감정분석 | 💡 기술적 분석</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 사이드바 - 네비게이션
    st.sidebar.title("🧭 대시보드 메뉴")
    
    pages = {
        "📊 프로젝트 개요": "overview",
        "💾 데이터베이스 현황": "database",
        "📈 주식 데이터 분석": "stocks",
        "📋 DART 공시정보": "dart",
        "📰 뉴스 감정분석": "news",
        "🎯 워런 버핏 스크리닝": "buffett",
        "📁 프로젝트 구조": "structure"
    }
    
    selected_page = st.sidebar.selectbox(
        "페이지 선택",
        list(pages.keys()),
        index=0
    )
    
    page_key = pages[selected_page]
    
    # 페이지별 렌더링
    if page_key == "overview":
        render_overview_page(dashboard)
    elif page_key == "database":
        render_database_page(dashboard)
    elif page_key == "stocks":
        render_stocks_page(dashboard)
    elif page_key == "dart":
        render_dart_page(dashboard)
    elif page_key == "news":
        render_news_page(dashboard)
    elif page_key == "buffett":
        render_buffett_page(dashboard)
    elif page_key == "structure":
        render_structure_page(dashboard)

def render_overview_page(dashboard):
    """프로젝트 개요 페이지"""
    st.header("📊 프로젝트 개요 및 현황")
    
    # 데이터베이스 정보 로드
    db_info = dashboard.get_database_info()
    
    # 핵심 지표 카드
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_stocks = db_info.get('stock', {}).get('records', {}).get('stock_info', 0)
        st.metric(
            label="📈 수집된 종목 수",
            value=f"{total_stocks:,}개",
            delta="전체 상장주식"
        )
    
    with col2:
        dart_companies = db_info.get('dart', {}).get('records', {}).get('company_info', 0)
        st.metric(
            label="📋 DART 기업정보",
            value=f"{dart_companies:,}개",
            delta="공시 연동 완료"
        )
    
    with col3:
        news_count = db_info.get('finance', {}).get('records', {}).get('news_articles', 0)
        st.metric(
            label="📰 뉴스 기사 수",
            value=f"{news_count:,}건",
            delta="감정분석 준비"
        )
    
    with col4:
        total_size = sum([
            db_info.get('stock', {}).get('size', 0),
            db_info.get('dart', {}).get('size', 0),
            db_info.get('finance', {}).get('size', 0)
        ])
        st.metric(
            label="💾 총 데이터 크기",
            value=f"{total_size:.1f}MB",
            delta="고품질 데이터"
        )
    
    # 프로젝트 진행 상황
    st.subheader("🚀 프로젝트 진행 현황")
    
    progress_data = {
        'Sprint': ['환경구축', '데이터수집', 'DART연동', '뉴스수집', '기술분석', '기본분석', '대시보드', '최적화'],
        '완료도': [100, 100, 100, 95, 30, 40, 60, 0],
        '상태': ['완료', '완료', '완료', '거의완료', '진행중', '진행중', '진행중', '계획']
    }
    
    progress_df = pd.DataFrame(progress_data)
    
    fig = px.bar(
        progress_df,
        x='Sprint',
        y='완료도',
        color='완료도',
        color_continuous_scale='RdYlGn',
        title="📈 Sprint별 진행 현황",
        text='완료도'
    )
    fig.update_traces(texttemplate='%{text}%', textposition='outside')
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # 주요 성과
    st.subheader("🏆 주요 성과")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.success("✅ **완료된 작업들**")
        achievements = [
            "2,759개 전 종목 데이터 수집 완료",
            "CSV + SQLite DB 이중 저장 시스템",
            "DART API 완전 연동 (재무제표 포함)",
            "네이버 뉴스 API 완전 연동",
            "환경변수 기반 보안 인증 시스템",
            "멀티스레딩 기반 대량 데이터 처리",
            "실무급 에러 처리 및 로깅 시스템"
        ]
        for achievement in achievements:
            st.write(f"• {achievement}")
    
    with col2:
        st.info("🔄 **진행 중인 작업들**")
        ongoing = [
            "감정 분석 모델 적용",
            "기술적 분석 지표 구현 (30개+)",
            "워런 버핏 스타일 스크리닝",
            "인터랙티브 차트 시스템",
            "백테스팅 프레임워크",
            "포트폴리오 최적화 엔진",
            "실시간 알림 시스템"
        ]
        for item in ongoing:
            st.write(f"• {item}")

def render_database_page(dashboard):
    """데이터베이스 현황 페이지"""
    st.header("💾 데이터베이스 현황")
    
    db_info = dashboard.get_database_info()
    
    # 데이터베이스별 상세 정보
    for db_name, info in db_info.items():
        if 'error' in info:
            st.error(f"❌ {db_name.upper()} 데이터베이스 연결 오류: {info['error']}")
            continue
        
        with st.expander(f"🗄️ {db_name.upper()} 데이터베이스", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("파일 크기", f"{info['size']:.1f}MB")
            
            with col2:
                st.metric("테이블 수", f"{len(info['tables'])}개")
            
            with col3:
                total_records = sum(info['records'].values())
                st.metric("총 레코드", f"{total_records:,}건")
            
            # 테이블별 상세 정보
            st.write("**📋 테이블별 레코드 수:**")
            table_df = pd.DataFrame([
                {'테이블명': table, '레코드수': count}
                for table, count in info['records'].items()
            ])
            
            if len(table_df) > 0:
                fig = px.pie(
                    table_df,
                    values='레코드수',
                    names='테이블명',
                    title=f"{db_name.upper()} 데이터베이스 구성"
                )
                st.plotly_chart(fig, use_container_width=True)

def render_stocks_page(dashboard):
    """주식 데이터 분석 페이지"""
    st.header("📈 주식 데이터 분석")
    
    stock_info, price_data = dashboard.load_stock_data_sample()
    
    if stock_info is None:
        st.error("주식 데이터를 로드할 수 없습니다.")
        return
    
    # 상위 종목 정보
    st.subheader("🏆 시가총액 상위 종목")
    
    # 시가총액 포맷팅
    if 'market_cap' in stock_info.columns:
        stock_info['시가총액(억원)'] = (stock_info['market_cap'] / 100000000).round(0)
    
    display_columns = ['name', '시가총액(억원)', 'sector', 'industry'] if 'sector' in stock_info.columns else ['name', '시가총액(억원)']
    st.dataframe(
        stock_info[display_columns].head(10),
        use_container_width=True
    )
    
    # 가격 차트
    if price_data is not None and len(price_data) > 0:
        st.subheader("📊 최근 30일 주가 동향 (상위 5개 종목)")
        
        fig = px.line(
            price_data,
            x='date',
            y='close',
            color='name',
            title="주가 추이",
            labels={'close': '종가 (원)', 'date': '날짜'}
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        # 거래량 차트
        st.subheader("📊 거래량 동향")
        fig_volume = px.bar(
            price_data,
            x='date',
            y='volume',
            color='name',
            title="일별 거래량",
            labels={'volume': '거래량', 'date': '날짜'}
        )
        fig_volume.update_layout(height=400)
        st.plotly_chart(fig_volume, use_container_width=True)

def render_dart_page(dashboard):
    """DART 공시정보 페이지"""
    st.header("📋 DART 공시정보 분석")
    
    company_info, disclosure_info, financial_data = dashboard.load_dart_data_sample()
    
    if company_info is None:
        st.error("DART 데이터를 로드할 수 없습니다.")
        return
    
    # 기업 정보
    st.subheader("🏢 등록된 기업 정보")
    if len(company_info) > 0:
        st.dataframe(
            company_info[['corp_name', 'corp_cls', 'est_dt', 'stock_code']].head(10),
            use_container_width=True
        )
    
    # 최근 공시 정보
    if disclosure_info is not None and len(disclosure_info) > 0:
        st.subheader("📋 최근 공시 현황")
        
        # 공시 유형별 분포
        if 'report_nm' in disclosure_info.columns:
            disclosure_counts = disclosure_info['report_nm'].value_counts().head(10)
            
            fig = px.bar(
                x=disclosure_counts.index,
                y=disclosure_counts.values,
                title="📊 공시 유형별 건수 (최근 50건)"
            )
            fig.update_xaxes(tickangle=45)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # 최근 공시 목록
        display_cols = ['corp_name', 'report_nm', 'rcept_dt'] if all(col in disclosure_info.columns for col in ['corp_name', 'report_nm', 'rcept_dt']) else disclosure_info.columns.tolist()[:3]
        st.dataframe(
            disclosure_info[display_cols].head(10),
            use_container_width=True
        )
    
    # 재무 데이터
    if financial_data is not None and len(financial_data) > 0:
        st.subheader("💰 재무제표 데이터 현황")
        st.write(f"수집된 재무데이터: {len(financial_data)}건")
        
        if 'account_nm' in financial_data.columns:
            # 계정과목별 분포
            account_counts = financial_data['account_nm'].value_counts().head(15)
            
            fig = px.bar(
                x=account_counts.values,
                y=account_counts.index,
                orientation='h',
                title="📊 재무제표 계정과목 분포"
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

def render_news_page(dashboard):
    """뉴스 감정분석 페이지"""
    st.header("📰 뉴스 감정분석")
    
    news_data = dashboard.load_news_data_sample()
    
    if news_data is None:
        st.error("뉴스 데이터를 로드할 수 없습니다.")
        return
    
    if len(news_data) == 0:
        st.warning("아직 뉴스 데이터가 수집되지 않았습니다.")
        st.info("뉴스 수집을 실행하려면: `python examples/basic_examples/06_full_news_collector.py`")
        return
    
    st.success(f"📊 총 {len(news_data)}건의 뉴스 데이터가 수집되었습니다!")
    
    # 일별 뉴스 수집 현황
    if 'pub_date' in news_data.columns:
        st.subheader("📅 일별 뉴스 수집 현황")
        
        daily_counts = news_data.groupby(news_data['pub_date'].dt.date).size().reset_index()
        daily_counts.columns = ['날짜', '뉴스건수']
        
        fig = px.bar(
            daily_counts,
            x='날짜',
            y='뉴스건수',
            title="일별 뉴스 수집 건수"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 종목별 뉴스 분포
    if 'query' in news_data.columns:
        st.subheader("📊 종목별 뉴스 분포")
        
        query_counts = news_data['query'].value_counts().head(20)
        
        fig = px.pie(
            values=query_counts.values,
            names=query_counts.index,
            title="상위 20개 검색어별 뉴스 분포"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 최근 뉴스 목록
    st.subheader("📰 최근 뉴스 헤드라인")
    
    display_cols = ['title', 'pub_date', 'query'] if all(col in news_data.columns for col in ['title', 'pub_date', 'query']) else news_data.columns.tolist()[:3]
    st.dataframe(
        news_data[display_cols].head(20),
        use_container_width=True
    )
    
    # 감정 분석 프리뷰 (향후 구현 예정)
    st.subheader("🎯 감정 분석 (구현 예정)")
    st.info("""
    **다음 기능들이 곧 추가됩니다:**
    - 📊 뉴스 감정 점수 계산 (-1.0 ~ 1.0)
    - 📈 종목별 감정 트렌드 분석
    - 🚨 감정 급변 알림 시스템
    - 📋 감정 기반 투자 신호 생성
    """)

def render_buffett_page(dashboard):
    """워런 버핏 스크리닝 페이지"""
    st.header("🎯 워런 버핏 스타일 가치투자 스크리닝")
    
    st.info("""
    **워런 버핏 투자 철학 기반 종목 스크리닝**
    
    현재 DART 데이터를 활용하여 다음 지표들을 분석할 수 있습니다:
    """)
    
    # 분석 가능한 지표들
    col1, col2 = st.columns(2)
    
    with col1:
        st.success("✅ **현재 분석 가능한 지표**")
        available_metrics = [
            "ROE (자기자본이익률)",
            "부채비율",
            "유동비율",
            "영업이익률",
            "매출액 증가율",
            "당기순이익 증가율",
            "PER (현재가 기준)",
            "PBR (현재가 기준)"
        ]
        for metric in available_metrics:
            st.write(f"• {metric}")
    
    with col2:
        st.warning("🔄 **구현 예정 지표**")
        upcoming_metrics = [
            "소유주 이익 (Owner Earnings)",
            "내재가치 성장률",
            "경제적 해자 분석",
            "FCF (잉여현금흐름)",
            "ROIC (투하자본이익률)",
            "Graham Number",
            "Piotroski F-Score",
            "Magic Formula Ranking"
        ]
        for metric in upcoming_metrics:
            st.write(f"• {metric}")
    
    # 샘플 스크리닝 결과
    st.subheader("📊 샘플 스크리닝 결과 (데모)")
    
    # 가상의 스크리닝 데이터 (실제로는 DB에서 계산)
    sample_data = {
        '종목명': ['삼성전자', 'SK하이닉스', 'NAVER', '현대차', '삼성SDI'],
        'ROE(%)': [12.5, 15.8, 11.2, 8.9, 14.3],
        '부채비율(%)': [45.2, 52.1, 23.4, 67.8, 41.2],
        'PER': [18.5, 22.1, 25.4, 8.2, 19.7],
        'PBR': [1.8, 2.1, 2.9, 0.9, 2.3],
        '버핏점수': [75, 82, 68, 64, 78]
    }
    
    sample_df = pd.DataFrame(sample_data)
    
    # 버핏 점수 기준 정렬
    sample_df = sample_df.sort_values('버핏점수', ascending=False)
    
    st.dataframe(sample_df, use_container_width=True)
    
    # 버핏 점수 차트
    fig = px.bar(
        sample_df,
        x='종목명',
        y='버핏점수',
        color='버핏점수',
        color_continuous_scale='RdYlGn',
        title="📊 워런 버핏 스타일 종합 점수",
        text='버핏점수'
    )
    fig.update_traces(texttemplate='%{text}점', textposition='outside')
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    st.info("""
    **📝 스크리닝 기준 (예시)**
    - ROE > 15%: 우수한 자기자본 수익률
    - 부채비율 < 50%: 안정적인 재무구조  
    - PER < 20: 적정 밸류에이션
    - PBR < 3: 장부가치 대비 합리적 가격
    - 매출/이익 성장률 > 5%: 지속적 성장
    """)

def render_structure_page(dashboard):
    """프로젝트 구조 페이지"""
    st.header("📁 프로젝트 구조 분석")
    
    structure_data = dashboard.load_project_structure()
    
    if structure_data is None:
        st.error("프로젝트 구조 정보를 로드할 수 없습니다.")
        st.info("구조 분석을 실행하려면: `python project_structure_analyzer.py`")
        return
    
    # 전체 통계
    stats = structure_data.get('statistics', {})
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📁 총 파일 수", f"{stats.get('total_files', 0):,}개")
    
    with col2:
        total_size_mb = stats.get('total_size', 0) / (1024*1024)
        st.metric("💾 총 크기", f"{total_size_mb:.1f}MB")
    
    with col3:
        python_files = stats.get('file_types', {}).get('.py', 0)
        st.metric("🐍 Python 파일", f"{python_files}개")
    
    with col4:
        csv_files = stats.get('file_types', {}).get('.csv', 0)
        st.metric("📄 CSV 파일", f"{csv_files:,}개")
    
    # 파일 유형별 분포
    st.subheader("📊 파일 유형별 분포")
    
    file_types = stats.get('file_types', {})
    if file_types:
        # CSV 파일이 너무 많으므로 별도 처리
        other_types = {k: v for k, v in file_types.items() if k != '.csv'}
        
        if other_types:
            fig = px.pie(
                values=list(other_types.values()),
                names=list(other_types.keys()),
                title="파일 유형별 분포 (CSV 제외)"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # CSV 파일 별도 표시
        if '.csv' in file_types:
            st.info(f"📄 **CSV 데이터 파일**: {file_types['.csv']:,}개 (주식 종목별 일별 데이터)")
    
    # 중요 파일들
    important_files = structure_data.get('important_files', [])
    if important_files:
        st.subheader("⭐ 중요 파일들")
        
        important_df = pd.DataFrame(important_files)
        if len(important_df) > 0:
            st.dataframe(important_df, use_container_width=True)
    
    # 데이터베이스 정보
    databases = structure_data.get('databases', [])
    if databases:
        st.subheader("🗄️ 데이터베이스 현황")
        
        db_df = pd.DataFrame(databases)
        st.dataframe(db_df, use_container_width=True)
    
    # 프로젝트 구조 텍스트
    with st.expander("🌳 전체 프로젝트 구조 보기"):
        if 'tree_structure' in structure_data:
            st.text(structure_data['tree_structure'])
        else:
            st.info("프로젝트 구조 정보가 없습니다.")

if __name__ == "__main__":
    main()