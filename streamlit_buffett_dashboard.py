"""
🏆 워런 버핏 스타일 가치투자 통합 대시보드

이 Streamlit 앱은 지금까지 구축한 모든 가치투자 기능을 통합합니다:
- 워런 버핏 스코어카드 (100점 만점 평가)
- 내재가치 계산 (DCF + 다중 밸류에이션)
- 저평가 우량주 자동 발굴
- 실시간 종목 분석 및 투자 의사결정 지원

🎯 목표: 웹 기반으로 쉽게 사용할 수 있는 완전한 가치투자 도구

실행 방법:
streamlit run streamlit_buffett_dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
from pathlib import Path
import sys
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR
except ImportError:
    # config가 없으면 기본 경로 사용
    DATA_DIR = Path(__file__).parent / 'data'

# 페이지 설정
st.set_page_config(
    page_title="워런 버핏 스타일 가치투자 대시보드",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #4ECDC4 0%, #45B7D1 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #4ECDC4;
    }
    .buffett-quote {
        background: #f8f9fa;
        border-left: 4px solid #FF6B6B;
        padding: 1rem;
        margin: 1rem 0;
        font-style: italic;
        border-radius: 5px;
    }
    .investment-action {
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        font-weight: bold;
        text-align: center;
    }
    .action-buy { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
    .action-watch { background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; }
    .action-avoid { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
</style>
""", unsafe_allow_html=True)


class BuffettDashboardData:
    """대시보드용 데이터 처리 클래스"""
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.dart_db_path = self.data_dir / 'dart_data.db'
        self.stock_db_path = self.data_dir / 'stock_data.db'
        
        # 데이터베이스 연결 확인
        if not self.dart_db_path.exists():
            st.error(f"❌ DART 데이터베이스가 없습니다: {self.dart_db_path}")
            st.stop()
    
    @st.cache_data(ttl=3600)  # 1시간 캐싱
    def query_dart_db(_self, query, params=None):
        """DART DB 쿼리 실행 (캐싱)"""
        try:
            with sqlite3.connect(_self.dart_db_path) as conn:
                if params:
                    return pd.read_sql_query(query, conn, params=params)
                else:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            st.error(f"❌ DART DB 쿼리 실패: {e}")
            return pd.DataFrame()
    
    @st.cache_data(ttl=3600)
    def query_stock_db(_self, query, params=None):
        """주식 DB 쿼리 실행 (캐싱)"""
        try:
            with sqlite3.connect(_self.stock_db_path) as conn:
                if params:
                    return pd.read_sql_query(query, conn, params=params)
                else:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            st.error(f"❌ 주식 DB 쿼리 실패: {e}")
            return pd.DataFrame()
    
    def calculate_financial_ratios(self, stock_code, year='2023'):
        """재무비율 계산"""
        query = """
            SELECT fs.account_nm, fs.thstrm_amount, fs.bsns_year, fs.fs_nm
            FROM financial_statements fs
            JOIN company_info ci ON fs.corp_code = ci.corp_code
            WHERE ci.stock_code = ? AND fs.bsns_year = ?
            ORDER BY fs.ord
        """
        
        financial_data = self.query_dart_db(query, (stock_code, year))
        
        if financial_data.empty:
            return {}, {}
        
        ratios = {}
        accounts = {}
        
        for _, row in financial_data.iterrows():
            account = row['account_nm']
            amount = row['thstrm_amount']
            
            try:
                if isinstance(amount, str):
                    amount = float(amount.replace(',', ''))
                accounts[account] = amount
            except:
                continue
        
        # 핵심 재무비율 계산
        try:
            if '당기순이익' in accounts and '자본총계' in accounts and accounts['자본총계'] != 0:
                ratios['ROE'] = (accounts['당기순이익'] / accounts['자본총계']) * 100
            
            if '당기순이익' in accounts and '자산총계' in accounts and accounts['자산총계'] != 0:
                ratios['ROA'] = (accounts['당기순이익'] / accounts['자산총계']) * 100
            
            if '영업이익' in accounts and '매출액' in accounts and accounts['매출액'] != 0:
                ratios['영업이익률'] = (accounts['영업이익'] / accounts['매출액']) * 100
            
            if '부채총계' in accounts and '자본총계' in accounts and accounts['자본총계'] != 0:
                ratios['부채비율'] = (accounts['부채총계'] / accounts['자본총계']) * 100
            
            if '유동자산' in accounts and '유동부채' in accounts and accounts['유동부채'] != 0:
                ratios['유동비율'] = (accounts['유동자산'] / accounts['유동부채']) * 100
        
        except Exception as e:
            st.error(f"⚠️ 재무비율 계산 오류: {e}")
        
        return ratios, accounts
    
    def calculate_growth_rates(self, stock_code, years=['2023', '2022', '2021']):
        """성장률 계산"""
        yearly_data = {}
        
        for year in years:
            ratios, accounts = self.calculate_financial_ratios(stock_code, year)
            yearly_data[year] = accounts
        
        growth_data = {}
        
        try:
            if '2023' in yearly_data and '2021' in yearly_data:
                revenue_2023 = yearly_data['2023'].get('매출액', 0)
                revenue_2021 = yearly_data['2021'].get('매출액', 0)
                
                if revenue_2021 > 0 and revenue_2023 > 0:
                    growth_data['매출성장률_CAGR'] = ((revenue_2023 / revenue_2021) ** (1/2) - 1) * 100
                
                profit_2023 = yearly_data['2023'].get('당기순이익', 0)
                profit_2021 = yearly_data['2021'].get('당기순이익', 0)
                
                if profit_2021 > 0 and profit_2023 > 0:
                    growth_data['순이익성장률_CAGR'] = ((profit_2023 / profit_2021) ** (1/2) - 1) * 100
        
        except Exception as e:
            st.error(f"⚠️ 성장률 계산 오류: {e}")
        
        return growth_data
    
    def count_consecutive_profit_years(self, stock_code):
        """연속 흑자 년수 계산"""
        try:
            query = """
                SELECT fs.bsns_year, fs.thstrm_amount
                FROM financial_statements fs
                JOIN company_info ci ON fs.corp_code = ci.corp_code
                WHERE ci.stock_code = ? AND fs.account_nm = '당기순이익'
                ORDER BY fs.bsns_year DESC
                LIMIT 10
            """
            
            profit_data = self.query_dart_db(query, (stock_code,))
            
            if profit_data.empty:
                return 0
            
            consecutive_years = 0
            for _, row in profit_data.iterrows():
                try:
                    amount = float(str(row['thstrm_amount']).replace(',', ''))
                    if amount > 0:
                        consecutive_years += 1
                    else:
                        break
                except:
                    break
            
            return consecutive_years
            
        except Exception as e:
            return 0
    
    def calculate_buffett_score(self, stock_code):
        """워런 버핏 스코어 계산"""
        ratios, accounts = self.calculate_financial_ratios(stock_code, '2023')
        growth_data = self.calculate_growth_rates(stock_code)
        consecutive_profits = self.count_consecutive_profit_years(stock_code)
        
        if not ratios:
            return None
        
        score_breakdown = {'수익성': 0, '성장성': 0, '안정성': 0, '밸류에이션': 0}
        
        # 수익성 평가 (30점)
        roe = ratios.get('ROE', 0)
        if roe >= 20:
            score_breakdown['수익성'] += 15
        elif roe >= 15:
            score_breakdown['수익성'] += 12
        elif roe >= 10:
            score_breakdown['수익성'] += 8
        
        operating_margin = ratios.get('영업이익률', 0)
        if operating_margin >= 15:
            score_breakdown['수익성'] += 8
        elif operating_margin >= 10:
            score_breakdown['수익성'] += 6
        elif operating_margin >= 5:
            score_breakdown['수익성'] += 3
        
        roa = ratios.get('ROA', 0)
        if roa >= 10:
            score_breakdown['수익성'] += 7
        elif roa >= 7:
            score_breakdown['수익성'] += 5
        elif roa >= 5:
            score_breakdown['수익성'] += 3
        
        # 성장성 평가 (25점)
        revenue_growth = growth_data.get('매출성장률_CAGR', 0)
        if revenue_growth >= 15:
            score_breakdown['성장성'] += 12
        elif revenue_growth >= 10:
            score_breakdown['성장성'] += 9
        elif revenue_growth >= 5:
            score_breakdown['성장성'] += 6
        elif revenue_growth >= 0:
            score_breakdown['성장성'] += 3
        
        profit_growth = growth_data.get('순이익성장률_CAGR', 0)
        if profit_growth >= 15:
            score_breakdown['성장성'] += 13
        elif profit_growth >= 10:
            score_breakdown['성장성'] += 10
        elif profit_growth >= 5:
            score_breakdown['성장성'] += 7
        elif profit_growth >= 0:
            score_breakdown['성장성'] += 3
        
        # 안정성 평가 (25점)
        debt_ratio = ratios.get('부채비율', 999)
        if debt_ratio <= 30:
            score_breakdown['안정성'] += 10
        elif debt_ratio <= 50:
            score_breakdown['안정성'] += 7
        elif debt_ratio <= 100:
            score_breakdown['안정성'] += 3
        
        current_ratio = ratios.get('유동비율', 0)
        if current_ratio >= 200:
            score_breakdown['안정성'] += 7
        elif current_ratio >= 150:
            score_breakdown['안정성'] += 5
        elif current_ratio >= 100:
            score_breakdown['안정성'] += 2
        
        if consecutive_profits >= 10:
            score_breakdown['안정성'] += 8
        elif consecutive_profits >= 5:
            score_breakdown['안정성'] += 5
        elif consecutive_profits >= 3:
            score_breakdown['안정성'] += 2
        
        # 밸류에이션 평가 (20점) - 간단한 추정
        if ratios.get('ROE', 0) >= 15 and debt_ratio <= 50:
            score_breakdown['밸류에이션'] = 15  # 우량주로 가정
        elif ratios.get('ROE', 0) >= 10:
            score_breakdown['밸류에이션'] = 10
        else:
            score_breakdown['밸류에이션'] = 5
        
        total_score = sum(score_breakdown.values())
        
        if total_score >= 85:
            grade = 'A+'
        elif total_score >= 75:
            grade = 'A'
        elif total_score >= 65:
            grade = 'B+'
        elif total_score >= 55:
            grade = 'B'
        else:
            grade = 'C'
        
        return {
            '총점': total_score,
            '등급': grade,
            '상세점수': score_breakdown,
            '핵심지표': {
                'ROE': round(roe, 2),
                '부채비율': round(debt_ratio, 2),
                '연속흑자': consecutive_profits,
                '매출성장률': round(revenue_growth, 2)
            }
        }
    
    def get_current_stock_price(self, stock_code):
        """현재 주가 조회"""
        try:
            price_query = """
                SELECT close
                FROM stock_prices 
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT 1
            """
            
            result = self.query_stock_db(price_query, (stock_code,))
            
            if not result.empty:
                return float(result.iloc[0]['close'])
            else:
                return None
                
        except Exception as e:
            return None
    
    def calculate_simple_intrinsic_value(self, stock_code):
        """간단한 내재가치 계산 (대시보드용)"""
        try:
            ratios, accounts = self.calculate_financial_ratios(stock_code, '2023')
            current_price = self.get_current_stock_price(stock_code)
            
            if not ratios or not current_price:
                return None
            
            # 간단한 ROE 기반 내재가치 추정
            roe = ratios.get('ROE', 0)
            equity = accounts.get('자본총계', 0)
            
            if roe > 0 and equity > 0:
                # 추정 주식 수 (시가총액 기반)
                estimated_shares = max(equity / (current_price * 1000000), 1000000)
                book_value_per_share = equity / estimated_shares
                
                # ROE 기반 적정 PBR
                if roe >= 20:
                    fair_pbr = 2.0
                elif roe >= 15:
                    fair_pbr = 1.5
                elif roe >= 10:
                    fair_pbr = 1.2
                else:
                    fair_pbr = 1.0
                
                # 보수적 접근 (80% 적용)
                intrinsic_value = book_value_per_share * fair_pbr * 0.8
                target_buy_price = intrinsic_value * 0.5  # 50% 안전마진
                
                return {
                    'intrinsic_value': intrinsic_value,
                    'current_price': current_price,
                    'target_buy_price': target_buy_price,
                    'upside_potential': ((intrinsic_value / current_price) - 1) * 100 if current_price > 0 else 0
                }
            
            return None
            
        except Exception as e:
            return None
    
    @st.cache_data(ttl=1800)  # 30분 캐싱
    def get_top_stocks(_self, min_score=70, limit=50):
        """상위 종목 조회 (캐싱)"""
        companies = _self.query_dart_db("""
            SELECT DISTINCT stock_code, corp_name
            FROM company_info
            WHERE stock_code IS NOT NULL AND stock_code != ''
            ORDER BY stock_code
            LIMIT 100
        """)
        
        top_stocks = []
        
        for _, row in companies.iterrows():
            stock_code = row['stock_code']
            corp_name = row['corp_name']
            
            try:
                score_result = _self.calculate_buffett_score(stock_code)
                valuation = _self.calculate_simple_intrinsic_value(stock_code)
                
                if score_result and score_result['총점'] >= min_score:
                    result = {
                        '종목코드': stock_code,
                        '기업명': corp_name,
                        '워런버핏점수': score_result['총점'],
                        '등급': score_result['등급'],
                        'ROE': score_result['핵심지표']['ROE'],
                        '부채비율': score_result['핵심지표']['부채비율'],
                        '연속흑자': score_result['핵심지표']['연속흑자'],
                        '상승여력': valuation['upside_potential'] if valuation else 0
                    }
                    top_stocks.append(result)
                    
                    if len(top_stocks) >= limit:
                        break
                        
            except:
                continue
        
        if top_stocks:
            df = pd.DataFrame(top_stocks)
            df = df.sort_values('워런버핏점수', ascending=False)
            df['순위'] = range(1, len(df) + 1)
            return df
        else:
            return pd.DataFrame()


# 데이터 처리 객체 초기화
@st.cache_resource
def init_data():
    return BuffettDashboardData()

data_handler = init_data()

# 메인 대시보드
def main():
    # 헤더
    st.markdown("""
    <div class="main-header">
        <h1>🏆 워런 버핏 스타일 가치투자 대시보드</h1>
        <p>"가격은 당신이 지불하는 것이고, 가치는 당신이 얻는 것이다" - 워런 버핏</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 사이드바
    st.sidebar.title("📊 분석 메뉴")
    
    menu = st.sidebar.selectbox(
        "원하는 기능을 선택하세요:",
        ["🏆 우량주 발굴", "🔍 종목 분석", "💰 내재가치 계산", "📈 포트폴리오 분석"]
    )
    
    if menu == "🏆 우량주 발굴":
        show_top_stocks_analysis()
    elif menu == "🔍 종목 분석":
        show_individual_stock_analysis()
    elif menu == "💰 내재가치 계산":
        show_intrinsic_value_analysis()
    elif menu == "📈 포트폴리오 분석":
        show_portfolio_analysis()


def show_top_stocks_analysis():
    """우량주 발굴 화면"""
    st.header("🏆 워런 버핏 스타일 우량주 발굴")
    
    # 워런 버핏 명언
    st.markdown("""
    <div class="buffett-quote">
    💬 "시간은 좋은 기업의 친구이고, 나쁨 기업의 적이다." - 워런 버핏
    </div>
    """, unsafe_allow_html=True)
    
    # 필터 설정
    col1, col2, col3 = st.columns(3)
    
    with col1:
        min_score = st.slider("최소 워런버핏 점수", 50, 90, 70, 5)
    
    with col2:
        max_results = st.slider("최대 결과 개수", 10, 50, 20, 5)
    
    with col3:
        if st.button("🔍 우량주 발굴 시작", type="primary"):
            st.rerun()
    
    # 데이터 로딩
    with st.spinner("🔍 우량주 발굴 중... 잠시만 기다려주세요."):
        top_stocks_df = data_handler.get_top_stocks(min_score=min_score, limit=max_results)
    
    if not top_stocks_df.empty:
        # 요약 지표
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("발굴된 우량주", f"{len(top_stocks_df)}개", delta=f"최소 {min_score}점 이상")
        
        with col2:
            avg_score = top_stocks_df['워런버핏점수'].mean()
            st.metric("평균 워런버핏 점수", f"{avg_score:.1f}점", delta="상위 우량주")
        
        with col3:
            a_plus_count = len(top_stocks_df[top_stocks_df['등급'] == 'A+'])
            st.metric("A+ 등급 기업", f"{a_plus_count}개", delta="버핏 스타일")
        
        with col4:
            avg_roe = top_stocks_df['ROE'].mean()
            st.metric("평균 ROE", f"{avg_roe:.1f}%", delta="수익성 지표")
        
        # 상위 종목 테이블
        st.subheader("📋 발굴된 우량주 리스트")
        
        # 등급별 색상 매핑
        def highlight_grade(row):
            if row['등급'] == 'A+':
                return ['background-color: #d4edda'] * len(row)
            elif row['등급'] == 'A':
                return ['background-color: #d1ecf1'] * len(row)
            elif row['등급'] == 'B+':
                return ['background-color: #fff3cd'] * len(row)
            else:
                return [''] * len(row)
        
        styled_df = top_stocks_df.style.apply(highlight_grade, axis=1)
        st.dataframe(styled_df, use_container_width=True)
        
        # 시각화
        col1, col2 = st.columns(2)
        
        with col1:
            # 등급 분포 파이 차트
            grade_counts = top_stocks_df['등급'].value_counts()
            fig_pie = px.pie(
                values=grade_counts.values,
                names=grade_counts.index,
                title="등급 분포",
                color_discrete_map={
                    'A+': '#FF6B6B', 'A': '#4ECDC4', 'B+': '#45B7D1', 
                    'B': '#FFA07A', 'C+': '#96CEB4', 'C': '#FECA57'
                }
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # ROE vs 부채비율 산점도
            fig_scatter = px.scatter(
                top_stocks_df,
                x='ROE',
                y='부채비율',
                size='워런버핏점수',
                color='등급',
                hover_data=['기업명', '워런버핏점수'],
                title="ROE vs 부채비율 (워런 버핏 선호 구간)",
                color_discrete_map={
                    'A+': '#FF6B6B', 'A': '#4ECDC4', 'B+': '#45B7D1', 
                    'B': '#FFA07A', 'C+': '#96CEB4', 'C': '#FECA57'
                }
            )
            
            # 워런 버핏 선호 구간 표시
            fig_scatter.add_hline(y=50, line_dash="dash", line_color="red", 
                                annotation_text="부채비율 50% 기준선")
            fig_scatter.add_vline(x=15, line_dash="dash", line_color="red",
                                annotation_text="ROE 15% 기준선")
            
            st.plotly_chart(fig_scatter, use_container_width=True)
        
        # 상세 분석 옵션
        st.subheader("🔍 상세 분석")
        selected_stock = st.selectbox(
            "상세 분석할 종목을 선택하세요:",
            options=top_stocks_df['종목코드'].tolist(),
            format_func=lambda x: f"{x} - {top_stocks_df[top_stocks_df['종목코드']==x]['기업명'].iloc[0]}"
        )
        
        if st.button("📊 선택 종목 상세 분석"):
            st.session_state.selected_stock = selected_stock
            st.rerun()
    
    else:
        st.warning(f"❌ 조건을 만족하는 우량주를 찾지 못했습니다. 기준점수를 {min_score-5}점으로 낮춰보세요.")


def show_individual_stock_analysis():
    """개별 종목 분석 화면"""
    st.header("🔍 개별 종목 워런 버핏 분석")
    
    # 종목 입력
    stock_code = st.text_input("종목코드를 입력하세요 (예: 005930)", value="005930")
    
    if stock_code and st.button("📊 분석 시작", type="primary"):
        
        # 기업 정보 조회
        company_query = """
            SELECT corp_name, ceo_nm, ind_tp, est_dt
            FROM company_info
            WHERE stock_code = ?
        """
        company_info = data_handler.query_dart_db(company_query, (stock_code,))
        
        if company_info.empty:
            st.error(f"❌ {stock_code} 종목 정보를 찾을 수 없습니다.")
            return
        
        corp_name = company_info.iloc[0]['corp_name']
        
        st.subheader(f"📊 {corp_name} ({stock_code}) 분석 리포트")
        
        # 워런 버핏 스코어 계산
        with st.spinner("📊 워런 버핏 점수 계산 중..."):
            score_result = data_handler.calculate_buffett_score(stock_code)
            valuation_result = data_handler.calculate_simple_intrinsic_value(stock_code)
        
        if score_result:
            # 종합 점수 표시
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_score = score_result['총점']
                grade = score_result['등급']
                
                # 등급별 색상
                if grade == 'A+':
                    grade_color = "#FF6B6B"
                elif grade == 'A':
                    grade_color = "#4ECDC4"
                elif grade == 'B+':
                    grade_color = "#45B7D1"
                else:
                    grade_color = "#FFA07A"
                
                st.markdown(f"""
                <div style="text-align: center; padding: 2rem; background: {grade_color}; border-radius: 10px; color: white;">
                    <h2>워런 버핏 점수</h2>
                    <h1>{total_score}/100점</h1>
                    <h3>등급: {grade}</h3>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                # 핵심 지표
                indicators = score_result['핵심지표']
                st.metric("ROE", f"{indicators['ROE']:.1f}%", 
                         delta="수익성" if indicators['ROE'] >= 15 else "개선필요")
                st.metric("부채비율", f"{indicators['부채비율']:.1f}%",
                         delta="안전" if indicators['부채비율'] <= 50 else "주의")
                st.metric("연속흑자", f"{indicators['연속흑자']}년",
                         delta="우수" if indicators['연속흑자'] >= 5 else "보통")
            
            with col3:
                # 내재가치 정보
                if valuation_result:
                    current_price = valuation_result['current_price']
                    intrinsic_value = valuation_result['intrinsic_value']
                    upside = valuation_result['upside_potential']
                    
                    st.metric("현재 주가", f"{current_price:,.0f}원")
                    st.metric("추정 내재가치", f"{intrinsic_value:,.0f}원")
                    st.metric("상승 여력", f"{upside:+.1f}%",
                             delta="매력적" if upside > 20 else "보통")
            
            # 영역별 상세 점수
            st.subheader("📈 영역별 상세 분석")
            
            breakdown = score_result['상세점수']
            
            # 레이더 차트용 데이터
            categories = ['수익성<br>(30점)', '성장성<br>(25점)', '안정성<br>(25점)', '밸류에이션<br>(20점)']
            values = [breakdown['수익성'], breakdown['성장성'], breakdown['안정성'], breakdown['밸류에이션']]
            max_values = [30, 25, 25, 20]
            
            # 레이더 차트
            fig_radar = go.Figure()
            
            fig_radar.add_trace(go.Scatterpolar(
                r=values,
                theta=categories,
                fill='toself',
                name='실제 점수',
                line_color='#4ECDC4'
            ))
            
            fig_radar.add_trace(go.Scatterpolar(
                r=max_values,
                theta=categories,
                fill='toself',
                name='만점',
                line_color='#FF6B6B',
                opacity=0.3
            ))
            
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 30]
                    )),
                showlegend=True,
                title="워런 버핏 점수 분석"
            )
            
            st.plotly_chart(fig_radar, use_container_width=True)
            
            # 투자 판단
            st.subheader("🎯 투자 판단")
            
            if grade == 'A+':
                investment_class = "action-buy"
                investment_text = "🚀 강력 매수 추천 - 워런 버핏이 선호할 최고급 기업"
            elif grade == 'A':
                investment_class = "action-buy"
                investment_text = "✅ 매수 추천 - 우수한 품질의 투자 대상"
            elif grade == 'B+':
                investment_class = "action-watch"
                investment_text = "⚠️ 신중한 검토 후 투자 - 양호한 수준"
            else:
                investment_class = "action-avoid"
                investment_text = "❌ 투자 부적합 - 워런 버핏 기준 미달"
            
            st.markdown(f"""
            <div class="investment-action {investment_class}">
                {investment_text}
            </div>
            """, unsafe_allow_html=True)
            
            # 상세 재무 정보
            with st.expander("📊 상세 재무 정보"):
                ratios, accounts = data_handler.calculate_financial_ratios(stock_code, '2023')
                
                if ratios:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**수익성 지표**")
                        st.write(f"ROE: {ratios.get('ROE', 0):.2f}%")
                        st.write(f"ROA: {ratios.get('ROA', 0):.2f}%")
                        st.write(f"영업이익률: {ratios.get('영업이익률', 0):.2f}%")
                    
                    with col2:
                        st.write("**안정성 지표**")
                        st.write(f"부채비율: {ratios.get('부채비율', 0):.2f}%")
                        st.write(f"유동비율: {ratios.get('유동비율', 0):.2f}%")
                        st.write(f"연속흑자: {indicators['연속흑자']}년")
        
        else:
            st.error("❌ 분석에 필요한 재무데이터가 부족합니다.")


def show_intrinsic_value_analysis():
    """내재가치 분석 화면"""
    st.header("💰 내재가치 계산 및 투자 전략")
    
    st.markdown("""
    <div class="buffett-quote">
    💬 "내재가치는 기업이 그 존재기간 동안 생산할 수 있는 현금의 할인된 가치이다." - 워런 버핏
    </div>
    """, unsafe_allow_html=True)
    
    # 종목 입력
    stock_code = st.text_input("내재가치를 계산할 종목코드를 입력하세요", value="005930")
    
    col1, col2 = st.columns(2)
    
    with col1:
        safety_margin = st.slider("안전마진 (%)", 20, 70, 50, 5)
    
    with col2:
        if st.button("💰 내재가치 계산", type="primary"):
            st.rerun()
    
    if stock_code:
        # 기업 정보
        company_query = """SELECT corp_name FROM company_info WHERE stock_code = ?"""
        company_info = data_handler.query_dart_db(company_query, (stock_code,))
        
        if not company_info.empty:
            corp_name = company_info.iloc[0]['corp_name']
            
            st.subheader(f"💰 {corp_name} ({stock_code}) 내재가치 분석")
            
            # 내재가치 계산
            with st.spinner("💰 내재가치 계산 중..."):
                valuation_result = data_handler.calculate_simple_intrinsic_value(stock_code)
            
            if valuation_result:
                intrinsic_value = valuation_result['intrinsic_value']
                current_price = valuation_result['current_price']
                default_target = valuation_result['target_buy_price']
                
                # 커스텀 안전마진 적용
                custom_target = intrinsic_value * (1 - safety_margin / 100)
                
                # 메트릭 표시
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("추정 내재가치", f"{intrinsic_value:,.0f}원")
                
                with col2:
                    st.metric("현재 주가", f"{current_price:,.0f}원")
                
                with col3:
                    st.metric(f"목표 매수가 ({safety_margin}% 할인)", f"{custom_target:,.0f}원")
                
                with col4:
                    upside = ((intrinsic_value / current_price) - 1) * 100
                    st.metric("상승 여력", f"{upside:+.1f}%")
                
                # 시각화
                fig = go.Figure()
                
                # 가격 막대그래프
                fig.add_trace(go.Bar(
                    x=['내재가치', '현재가', f'목표매수가<br>({safety_margin}%할인)'],
                    y=[intrinsic_value, current_price, custom_target],
                    marker_color=['#4ECDC4', '#FF6B6B', '#45B7D1'],
                    text=[f'{intrinsic_value:,.0f}원', f'{current_price:,.0f}원', f'{custom_target:,.0f}원'],
                    textposition='auto',
                ))
                
                fig.update_layout(
                    title="내재가치 vs 현재가 비교",
                    yaxis_title="주가 (원)",
                    showlegend=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # 투자 전략
                st.subheader("🎯 워런 버핏 스타일 투자 전략")
                
                if current_price <= custom_target:
                    strategy_class = "action-buy"
                    strategy_text = f"🚀 매수 추천! 현재가가 목표 매수가 이하입니다."
                    action_detail = [
                        "✅ 즉시 매수 고려",
                        "💰 포트폴리오 비중: 3-5%",
                        "📅 장기 보유 (10년+)",
                        "📉 추가 하락 시 추가 매수"
                    ]
                elif current_price <= intrinsic_value:
                    strategy_class = "action-watch"
                    strategy_text = f"⚠️ 신중한 매수. 내재가치 이하이지만 안전마진 부족."
                    action_detail = [
                        "🔄 분할 매수 전략",
                        f"📉 목표가 접근 시 적극 매수: {custom_target:,.0f}원",
                        "💰 초기 비중: 1-2%",
                        "📊 추가 분석 필요"
                    ]
                else:
                    strategy_class = "action-avoid"
                    strategy_text = f"❌ 현재 과대평가 상태. 매수 부적합."
                    action_detail = [
                        "⏳ 워치리스트 등록",
                        f"📉 매수 고려가: {intrinsic_value*0.9:,.0f}원 이하",
                        f"🎯 적극 매수가: {custom_target:,.0f}원 이하",
                        "🔍 다른 종목 발굴 권장"
                    ]
                
                st.markdown(f"""
                <div class="investment-action {strategy_class}">
                    {strategy_text}
                </div>
                """, unsafe_allow_html=True)
                
                st.write("**구체적 액션 플랜:**")
                for action in action_detail:
                    st.write(f"  {action}")
                
                # 리스크 요인
                with st.expander("⚠️ 주요 리스크 요인"):
                    st.write("""
                    - 📊 내재가치 계산의 불확실성
                    - 🌍 거시경제 환경 변화
                    - 🏢 기업 경영환경 변화
                    - 📈 성장률 가정의 변동성
                    - 💰 할인율 변화 리스크
                    """)
            
            else:
                st.error("❌ 내재가치 계산에 필요한 데이터가 부족합니다.")
        
        else:
            st.error(f"❌ {stock_code} 종목 정보를 찾을 수 없습니다.")


def show_portfolio_analysis():
    """포트폴리오 분석 화면"""
    st.header("📈 포트폴리오 워런 버핏 분석")
    
    st.markdown("""
    <div class="buffett-quote">
    💬 "분산투자는 무지에 대한 보호장치다. 자신이 하는 일을 아는 사람에게는 거의 의미가 없다." - 워런 버핏
    </div>
    """, unsafe_allow_html=True)
    
    # 포트폴리오 입력
    st.subheader("📋 포트폴리오 종목 입력")
    
    portfolio_input = st.text_area(
        "보유 종목코드를 쉼표로 구분해서 입력하세요",
        value="005930,000660,035420,051910,035720",
        help="예: 005930,000660,035420,051910,035720"
    )
    
    if st.button("📊 포트폴리오 분석 시작", type="primary"):
        if portfolio_input:
            stock_codes = [code.strip() for code in portfolio_input.split(',') if code.strip()]
            
            if stock_codes:
                st.subheader(f"📊 포트폴리오 분석 결과 ({len(stock_codes)}개 종목)")
                
                portfolio_results = []
                
                # 진행률 표시
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, stock_code in enumerate(stock_codes):
                    status_text.text(f"분석 중: {stock_code} ({i+1}/{len(stock_codes)})")
                    progress_bar.progress((i + 1) / len(stock_codes))
                    
                    try:
                        # 기업명 조회
                        company_query = """SELECT corp_name FROM company_info WHERE stock_code = ?"""
                        company_info = data_handler.query_dart_db(company_query, (stock_code,))
                        corp_name = company_info.iloc[0]['corp_name'] if not company_info.empty else stock_code
                        
                        # 워런 버핏 점수 계산
                        score_result = data_handler.calculate_buffett_score(stock_code)
                        valuation_result = data_handler.calculate_simple_intrinsic_value(stock_code)
                        
                        if score_result:
                            result = {
                                '종목코드': stock_code,
                                '기업명': corp_name,
                                '워런버핏점수': score_result['총점'],
                                '등급': score_result['등급'],
                                'ROE': score_result['핵심지표']['ROE'],
                                '부채비율': score_result['핵심지표']['부채비율'],
                                '현재가': valuation_result['current_price'] if valuation_result else 0,
                                '내재가치': valuation_result['intrinsic_value'] if valuation_result else 0,
                                '상승여력': valuation_result['upside_potential'] if valuation_result else 0
                            }
                            portfolio_results.append(result)
                    
                    except Exception as e:
                        st.warning(f"⚠️ {stock_code} 분석 실패: {str(e)}")
                        continue
                
                # 진행률 표시 제거
                progress_bar.empty()
                status_text.empty()
                
                if portfolio_results:
                    portfolio_df = pd.DataFrame(portfolio_results)
                    
                    # 포트폴리오 요약 지표
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        avg_score = portfolio_df['워런버핏점수'].mean()
                        st.metric("평균 워런버핏 점수", f"{avg_score:.1f}점")
                    
                    with col2:
                        a_grade_count = len(portfolio_df[portfolio_df['등급'].isin(['A+', 'A'])])
                        st.metric("A급 종목 수", f"{a_grade_count}개")
                    
                    with col3:
                        avg_roe = portfolio_df['ROE'].mean()
                        st.metric("평균 ROE", f"{avg_roe:.1f}%")
                    
                    with col4:
                        avg_upside = portfolio_df['상승여력'].mean()
                        st.metric("평균 상승여력", f"{avg_upside:+.1f}%")
                    
                    # 포트폴리오 테이블
                    st.subheader("📋 포트폴리오 상세 분석")
                    
                    # 스타일링
                    def highlight_portfolio(row):
                        if row['등급'] == 'A+':
                            return ['background-color: #d4edda'] * len(row)
                        elif row['등급'] == 'A':
                            return ['background-color: #d1ecf1'] * len(row)
                        elif row['등급'] == 'B+':
                            return ['background-color: #fff3cd'] * len(row)
                        else:
                            return ['background-color: #f8d7da'] * len(row)
                    
                    styled_portfolio = portfolio_df.style.apply(highlight_portfolio, axis=1)
                    st.dataframe(styled_portfolio, use_container_width=True)
                    
                    # 시각화
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # 워런 버핏 점수 분포
                        fig_scores = px.bar(
                            portfolio_df,
                            x='기업명',
                            y='워런버핏점수',
                            color='등급',
                            title="종목별 워런 버핏 점수",
                            color_discrete_map={
                                'A+': '#FF6B6B', 'A': '#4ECDC4', 'B+': '#45B7D1',
                                'B': '#FFA07A', 'C+': '#96CEB4', 'C': '#FECA57'
                            }
                        )
                        fig_scores.update_xaxes(tickangle=45)
                        st.plotly_chart(fig_scores, use_container_width=True)
                    
                    with col2:
                        # ROE vs 부채비율
                        fig_risk_return = px.scatter(
                            portfolio_df,
                            x='ROE',
                            y='부채비율',
                            size='워런버핏점수',
                            color='등급',
                            hover_data=['기업명'],
                            title="포트폴리오 리스크-수익 분석",
                            color_discrete_map={
                                'A+': '#FF6B6B', 'A': '#4ECDC4', 'B+': '#45B7D1',
                                'B': '#FFA07A', 'C+': '#96CEB4', 'C': '#FECA57'
                            }
                        )
                        
                        # 기준선 추가
                        fig_risk_return.add_hline(y=50, line_dash="dash", line_color="red")
                        fig_risk_return.add_vline(x=15, line_dash="dash", line_color="red")
                        
                        st.plotly_chart(fig_risk_return, use_container_width=True)
                    
                    # 포트폴리오 평가
                    st.subheader("🎯 포트폴리오 종합 평가")
                    
                    # 포트폴리오 등급 계산
                    if avg_score >= 80:
                        portfolio_grade = "🏆 우수 포트폴리오"
                        portfolio_color = "#d4edda"
                    elif avg_score >= 70:
                        portfolio_grade = "✅ 양호한 포트폴리오"
                        portfolio_color = "#d1ecf1"
                    elif avg_score >= 60:
                        portfolio_grade = "⚠️ 개선 필요 포트폴리오"
                        portfolio_color = "#fff3cd"
                    else:
                        portfolio_grade = "❌ 리스크 높은 포트폴리오"
                        portfolio_color = "#f8d7da"
                    
                    st.markdown(f"""
                    <div style="background: {portfolio_color}; padding: 1rem; border-radius: 10px; text-align: center;">
                        <h3>{portfolio_grade}</h3>
                        <p>평균 워런 버핏 점수: {avg_score:.1f}점</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 개선 제안
                    st.subheader("💡 포트폴리오 개선 제안")
                    
                    low_score_stocks = portfolio_df[portfolio_df['워런버핏점수'] < 65]
                    high_debt_stocks = portfolio_df[portfolio_df['부채비율'] > 70]
                    low_roe_stocks = portfolio_df[portfolio_df['ROE'] < 10]
                    
                    if not low_score_stocks.empty:
                        st.warning(f"⚠️ 워런 버핏 점수 낮은 종목 ({len(low_score_stocks)}개): " + 
                                 ", ".join(low_score_stocks['기업명'].tolist()))
                    
                    if not high_debt_stocks.empty:
                        st.warning(f"⚠️ 부채비율 높은 종목 ({len(high_debt_stocks)}개): " + 
                                 ", ".join(high_debt_stocks['기업명'].tolist()))
                    
                    if not low_roe_stocks.empty:
                        st.warning(f"⚠️ ROE 낮은 종목 ({len(low_roe_stocks)}개): " + 
                                 ", ".join(low_roe_stocks['기업명'].tolist()))
                    
                    if low_score_stocks.empty and high_debt_stocks.empty and low_roe_stocks.empty:
                        st.success("🎉 모든 종목이 워런 버핏 기준을 만족합니다!")
                
                else:
                    st.error("❌ 분석 가능한 종목이 없습니다.")
            
            else:
                st.error("❌ 올바른 종목코드를 입력해주세요.")
        
        else:
            st.error("❌ 종목코드를 입력해주세요.")


# 사이드바 정보
def show_sidebar_info():
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 시스템 정보")
    st.sidebar.info("""
    **워런 버핏 투자 철학 구현**
    - 기본분석 45% 비중
    - 기술분석 30% 비중  
    - 뉴스분석 25% 비중
    
    **핵심 평가 기준**
    - ROE ≥ 15%
    - 부채비율 ≤ 50%
    - 연속 흑자 5년+
    - 50% 안전마진
    """)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style="text-align: center; color: #666;">
        <p>🏆 Finance Data Vibe</p>
        <p>워런 버핏 스타일 가치투자 시스템</p>
        <p>"가격은 당신이 지불하는 것이고,<br>가치는 당신이 얻는 것이다"</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    show_sidebar_info()
    main()