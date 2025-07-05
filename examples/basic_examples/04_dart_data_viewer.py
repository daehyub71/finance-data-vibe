"""
📊 DART 데이터 조회 및 분석 도구

이 모듈은 수집된 DART 데이터를 조회하고 분석하는 기능을 제공합니다.

주요 기능:
1. 수집된 데이터 현황 확인
2. 기업별 재무제표 조회
3. 재무비율 계산 및 분석
4. 종목 스크리닝
5. 데이터 품질 검증

🎯 목표: 수집된 DART 데이터 완전 활용
"""

import sys
from pathlib import Path
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR
    import matplotlib.font_manager as fm
    
    # 한글 폰트 설정
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False
except ImportError as e:
    print(f"❌ 패키지 설치 필요: {e}")
    exit(1)


class DARTDataAnalyzer:
    """
    DART 데이터 분석기
    
    수집된 DART 데이터를 조회하고 분석하는 기능을 제공합니다.
    """
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.dart_db_path = self.data_dir / 'dart_data.db'
        self.stock_db_path = self.data_dir / 'stock_data.db'
        
        if not self.dart_db_path.exists():
            print(f"❌ DART 데이터베이스가 없습니다: {self.dart_db_path}")
            print("먼저 DART 데이터 수집을 실행해주세요.")
            exit(1)
        
        print(f"✅ DART 데이터베이스 연결: {self.dart_db_path}")
    
    def query_dart_db(self, query, params=None):
        """DART DB 쿼리 실행"""
        try:
            with sqlite3.connect(self.dart_db_path) as conn:
                if params:
                    return pd.read_sql_query(query, conn, params=params)
                else:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"❌ DART DB 쿼리 실패: {e}")
            return pd.DataFrame()
    
    def query_stock_db(self, query, params=None):
        """주식 DB 쿼리 실행"""
        try:
            with sqlite3.connect(self.stock_db_path) as conn:
                if params:
                    return pd.read_sql_query(query, conn, params=params)
                else:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"❌ 주식 DB 쿼리 실패: {e}")
            return pd.DataFrame()
    
    def get_data_summary(self):
        """📊 수집된 데이터 현황 요약"""
        print("📊 DART 데이터 수집 현황")
        print("=" * 50)
        
        # 기업 정보 현황
        company_count = self.query_dart_db("SELECT COUNT(*) as count FROM company_info")
        print(f"🏢 수집된 기업 수: {company_count.iloc[0]['count']:,}개")
        
        # 공시정보 현황
        disclosure_count = self.query_dart_db("SELECT COUNT(*) as count FROM disclosure_info")
        print(f"📋 공시정보 건수: {disclosure_count.iloc[0]['count']:,}건")
        
        # 재무제표 현황
        financial_count = self.query_dart_db("SELECT COUNT(*) as count FROM financial_statements")
        print(f"💰 재무제표 건수: {financial_count.iloc[0]['count']:,}건")
        
        # 연도별 재무데이터 현황
        yearly_data = self.query_dart_db("""
            SELECT bsns_year, COUNT(*) as count
            FROM financial_statements
            GROUP BY bsns_year
            ORDER BY bsns_year DESC
        """)
        
        if not yearly_data.empty:
            print(f"\n📅 연도별 재무데이터:")
            for _, row in yearly_data.iterrows():
                print(f"   {row['bsns_year']}년: {row['count']:,}건")
        
        # 업종별 현황
        industry_data = self.query_dart_db("""
            SELECT ind_tp, COUNT(*) as count
            FROM company_info
            WHERE ind_tp IS NOT NULL AND ind_tp != ''
            GROUP BY ind_tp
            ORDER BY count DESC
            LIMIT 10
        """)
        
        if not industry_data.empty:
            print(f"\n🏭 주요 업종별 기업 수:")
            for _, row in industry_data.iterrows():
                print(f"   {row['ind_tp']}: {row['count']}개")
        
        print("=" * 50)
    
    def get_company_list(self, limit=20):
        """📋 수집된 기업 리스트 조회"""
        query = """
            SELECT stock_code, corp_name, ceo_nm, ind_tp, est_dt
            FROM company_info
            WHERE stock_code IS NOT NULL AND stock_code != ''
            ORDER BY corp_name
            LIMIT ?
        """
        return self.query_dart_db(query, (limit,))
    
    def get_company_detail(self, stock_code):
        """🏢 특정 기업의 상세 정보 조회"""
        query = """
            SELECT *
            FROM company_info
            WHERE stock_code = ?
        """
        return self.query_dart_db(query, (stock_code,))
    
    def get_financial_data(self, stock_code, year=None):
        """💰 특정 기업의 재무데이터 조회"""
        base_query = """
            SELECT fs.account_nm, fs.thstrm_amount, fs.bsns_year, fs.fs_nm
            FROM financial_statements fs
            JOIN company_info ci ON fs.corp_code = ci.corp_code
            WHERE ci.stock_code = ?
        """
        
        params = [stock_code]
        
        if year:
            base_query += " AND fs.bsns_year = ?"
            params.append(year)
        
        base_query += " ORDER BY fs.bsns_year DESC, fs.ord"
        
        return self.query_dart_db(base_query, params)
    
    def calculate_financial_ratios(self, stock_code, year):
        """📊 재무비율 계산"""
        financial_data = self.get_financial_data(stock_code, year)
        
        if financial_data.empty:
            return {}
        
        # 주요 계정과목 추출
        ratios = {}
        accounts = {}
        
        for _, row in financial_data.iterrows():
            account = row['account_nm']
            amount = row['thstrm_amount']
            
            # 금액 문자열을 숫자로 변환
            try:
                if isinstance(amount, str):
                    # 쉼표 제거 후 숫자 변환
                    amount = float(amount.replace(',', ''))
                accounts[account] = amount
            except:
                continue
        
        # 주요 재무비율 계산
        try:
            # ROE = 당기순이익 / 자본총계 * 100
            if '당기순이익' in accounts and '자본총계' in accounts:
                if accounts['자본총계'] != 0:
                    ratios['ROE'] = (accounts['당기순이익'] / accounts['자본총계']) * 100
            
            # ROA = 당기순이익 / 자산총계 * 100  
            if '당기순이익' in accounts and '자산총계' in accounts:
                if accounts['자산총계'] != 0:
                    ratios['ROA'] = (accounts['당기순이익'] / accounts['자산총계']) * 100
            
            # 부채비율 = 부채총계 / 자본총계 * 100
            if '부채총계' in accounts and '자본총계' in accounts:
                if accounts['자본총계'] != 0:
                    ratios['부채비율'] = (accounts['부채총계'] / accounts['자본총계']) * 100
            
            # 유동비율 = 유동자산 / 유동부채 * 100
            if '유동자산' in accounts and '유동부채' in accounts:
                if accounts['유동부채'] != 0:
                    ratios['유동비율'] = (accounts['유동자산'] / accounts['유동부채']) * 100
            
            # 매출총이익률 = (매출액 - 매출원가) / 매출액 * 100
            if '매출액' in accounts and '매출원가' in accounts:
                if accounts['매출액'] != 0:
                    gross_profit = accounts['매출액'] - accounts.get('매출원가', 0)
                    ratios['매출총이익률'] = (gross_profit / accounts['매출액']) * 100
            
            # 영업이익률 = 영업이익 / 매출액 * 100
            if '영업이익' in accounts and '매출액' in accounts:
                if accounts['매출액'] != 0:
                    ratios['영업이익률'] = (accounts['영업이익'] / accounts['매출액']) * 100
        
        except Exception as e:
            print(f"⚠️ 재무비율 계산 오류: {e}")
        
        return ratios, accounts
    
    def screen_stocks(self, min_roe=15, max_debt_ratio=50, min_current_ratio=150):
        """🔍 종목 스크리닝 (워런 버핏 스타일)"""
        print(f"🔍 종목 스크리닝 중... (ROE≥{min_roe}%, 부채비율≤{max_debt_ratio}%, 유동비율≥{min_current_ratio}%)")
        
        # 수집된 모든 기업에 대해 재무비율 계산
        companies = self.query_dart_db("""
            SELECT DISTINCT stock_code, corp_name
            FROM company_info
            WHERE stock_code IS NOT NULL AND stock_code != ''
        """)
        
        screening_results = []
        
        for _, company in companies.iterrows():
            stock_code = company['stock_code']
            corp_name = company['corp_name']
            
            # 최신연도 재무비율 계산
            ratios, accounts = self.calculate_financial_ratios(stock_code, '2023')
            
            if ratios:
                # 스크리닝 조건 확인
                roe = ratios.get('ROE', 0)
                debt_ratio = ratios.get('부채비율', 999)
                current_ratio = ratios.get('유동비율', 0)
                
                if (roe >= min_roe and 
                    debt_ratio <= max_debt_ratio and 
                    current_ratio >= min_current_ratio):
                    
                    screening_results.append({
                        'stock_code': stock_code,
                        'corp_name': corp_name,
                        'ROE': round(roe, 2),
                        '부채비율': round(debt_ratio, 2),
                        '유동비율': round(current_ratio, 2),
                        '영업이익률': round(ratios.get('영업이익률', 0), 2)
                    })
        
        return pd.DataFrame(screening_results)
    
    def create_financial_report(self, stock_code):
        """📊 종목별 재무분석 리포트 생성"""
        company_detail = self.get_company_detail(stock_code)
        
        if company_detail.empty:
            print(f"❌ {stock_code} 기업 정보를 찾을 수 없습니다.")
            return
        
        company_info = company_detail.iloc[0]
        corp_name = company_info['corp_name']
        
        print("=" * 60)
        print(f"📊 {corp_name} ({stock_code}) 재무분석 리포트")
        print("=" * 60)
        
        # 기업 기본정보
        print(f"🏢 기업명: {corp_name}")
        print(f"👨‍💼 대표이사: {company_info['ceo_nm']}")
        print(f"🏭 업종: {company_info['ind_tp']}")
        print(f"📅 설립일: {company_info['est_dt']}")
        print(f"🌐 홈페이지: {company_info['hm_url']}")
        
        # 최근 3년간 재무비율
        print(f"\n💰 최근 3년간 재무비율:")
        print("-" * 40)
        
        years = ['2023', '2022', '2021']
        ratio_summary = []
        
        for year in years:
            ratios, accounts = self.calculate_financial_ratios(stock_code, year)
            if ratios:
                ratio_summary.append({
                    '연도': year,
                    'ROE(%)': round(ratios.get('ROE', 0), 2),
                    'ROA(%)': round(ratios.get('ROA', 0), 2),
                    '부채비율(%)': round(ratios.get('부채비율', 0), 2),
                    '유동비율(%)': round(ratios.get('유동비율', 0), 2),
                    '영업이익률(%)': round(ratios.get('영업이익률', 0), 2)
                })
        
        if ratio_summary:
            ratio_df = pd.DataFrame(ratio_summary)
            print(ratio_df.to_string(index=False))
            
            # 워런 버핏 기준 평가
            print(f"\n🎯 워런 버핏 기준 평가:")
            print("-" * 30)
            
            latest_ratios = ratio_summary[0] if ratio_summary else {}
            roe = latest_ratios.get('ROE(%)', 0)
            debt_ratio = latest_ratios.get('부채비율(%)', 999)
            
            if roe >= 15:
                print(f"✅ ROE {roe}% (기준: 15% 이상)")
            else:
                print(f"❌ ROE {roe}% (기준: 15% 이상)")
            
            if debt_ratio <= 50:
                print(f"✅ 부채비율 {debt_ratio}% (기준: 50% 이하)")
            else:
                print(f"❌ 부채비율 {debt_ratio}% (기준: 50% 이하)")
        
        print("=" * 60)
    
    def visualize_industry_comparison(self):
        """📈 업종별 재무비율 비교 시각화"""
        # 업종별 평균 ROE 계산
        query = """
            SELECT ci.ind_tp, 
                   AVG(CASE WHEN fs.account_nm = '당기순이익' THEN 
                       CAST(REPLACE(fs.thstrm_amount, ',', '') AS REAL) END) as avg_net_income,
                   AVG(CASE WHEN fs.account_nm = '자본총계' THEN 
                       CAST(REPLACE(fs.thstrm_amount, ',', '') AS REAL) END) as avg_equity
            FROM company_info ci
            JOIN financial_statements fs ON ci.corp_code = fs.corp_code
            WHERE ci.ind_tp IS NOT NULL AND ci.ind_tp != ''
            AND fs.bsns_year = '2023'
            AND fs.account_nm IN ('당기순이익', '자본총계')
            GROUP BY ci.ind_tp
            HAVING COUNT(DISTINCT ci.corp_code) >= 3
        """
        
        industry_data = self.query_dart_db(query)
        
        if not industry_data.empty:
            # ROE 계산
            industry_data['ROE'] = (industry_data['avg_net_income'] / industry_data['avg_equity']) * 100
            industry_data = industry_data.dropna().sort_values('ROE', ascending=False)
            
            # 시각화
            plt.figure(figsize=(12, 8))
            plt.barh(industry_data['ind_tp'], industry_data['ROE'])
            plt.xlabel('ROE (%)')
            plt.title('업종별 평균 ROE 비교 (2023년)')
            plt.tight_layout()
            plt.show()


def main():
    """메인 실행 함수"""
    
    print("🚀 Finance Data Vibe - DART 데이터 분석기")
    print("=" * 60)
    
    try:
        # 분석기 초기화
        analyzer = DARTDataAnalyzer()
        
        while True:
            print("\n📊 원하는 기능을 선택하세요:")
            print("1. 데이터 수집 현황 확인")
            print("2. 기업 리스트 조회")
            print("3. 특정 기업 상세 정보")
            print("4. 재무분석 리포트")
            print("5. 종목 스크리닝 (워런 버핏 스타일)")
            print("6. 업종별 비교 차트")
            print("0. 종료")
            
            choice = input("\n선택하세요 (0-6): ").strip()
            
            if choice == '0':
                print("👋 분석을 종료합니다.")
                break
            
            elif choice == '1':
                analyzer.get_data_summary()
            
            elif choice == '2':
                companies = analyzer.get_company_list()
                if not companies.empty:
                    print("\n📋 수집된 기업 리스트 (상위 20개):")
                    print(companies.to_string(index=False))
                else:
                    print("❌ 수집된 기업 데이터가 없습니다.")
            
            elif choice == '3':
                stock_code = input("종목코드를 입력하세요 (예: 005930): ").strip()
                company_detail = analyzer.get_company_detail(stock_code)
                if not company_detail.empty:
                    print(f"\n🏢 {company_detail.iloc[0]['corp_name']} 상세정보:")
                    for col in company_detail.columns:
                        print(f"   {col}: {company_detail.iloc[0][col]}")
                else:
                    print(f"❌ {stock_code} 기업 정보를 찾을 수 없습니다.")
            
            elif choice == '4':
                stock_code = input("종목코드를 입력하세요 (예: 005930): ").strip()
                analyzer.create_financial_report(stock_code)
            
            elif choice == '5':
                print("🔍 워런 버핏 스타일 종목 스크리닝")
                screened = analyzer.screen_stocks()
                if not screened.empty:
                    print(f"\n✅ 조건을 만족하는 {len(screened)}개 종목:")
                    print(screened.to_string(index=False))
                else:
                    print("❌ 조건을 만족하는 종목이 없습니다.")
            
            elif choice == '6':
                print("📈 업종별 ROE 비교 차트 생성 중...")
                analyzer.visualize_industry_comparison()
            
            else:
                print("❌ 올바른 번호를 선택해주세요.")
    
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


if __name__ == "__main__":
    main()