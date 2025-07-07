"""
🏆 워런 버핏 스코어카드 완전 구현

이 모듈은 워런 버핏의 투자 철학을 바탕으로 한국 주식을 100점 만점으로 평가합니다.

평가 기준 (워런 버핏 투자 철학):
📊 수익성 (30점): ROE, ROA, 영업이익률, 순이익률
📈 성장성 (25점): 매출/순이익 성장률, 성장 지속성  
🛡️ 안정성 (25점): 부채비율, 유동비율, 연속흑자년수
💰 밸류에이션 (20점): PER, PBR, 내재가치 vs 현재가

🎯 목표: 저평가 우량주 자동 발굴 및 투자 의사결정 지원
"""

import sys
from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

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


class BuffettScorecard:
    """
    🏆 워런 버핏 스코어카드 시스템
    
    워런 버핏의 투자 철학을 바탕으로 한국 주식을 종합 평가합니다.
    """
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.dart_db_path = self.data_dir / 'dart_data.db'
        self.stock_db_path = self.data_dir / 'stock_data.db'
        
        if not self.dart_db_path.exists():
            print(f"❌ DART 데이터베이스가 없습니다: {self.dart_db_path}")
            print("먼저 DART 데이터 수집을 실행해주세요.")
            exit(1)
        
        # 워런 버핏 평가 기준
        self.quality_criteria = {
            # 수익성 기준 (워런 버핏 선호)
            'excellent_roe': 20.0,      # ROE 20% 이상 (최고급)
            'good_roe': 15.0,           # ROE 15% 이상 (우수)
            'min_roe': 10.0,            # ROE 10% 이상 (최소기준)
            
            # 안정성 기준
            'max_debt_ratio': 50.0,     # 부채비율 50% 이하
            'excellent_debt_ratio': 30.0, # 부채비율 30% 이하 (우수)
            'min_current_ratio': 150.0, # 유동비율 150% 이상
            
            # 성장성 기준
            'excellent_growth': 15.0,   # 성장률 15% 이상 (고성장)
            'good_growth': 10.0,        # 성장률 10% 이상 (양호)
            'min_growth': 5.0,          # 성장률 5% 이상 (최소)
            
            # 밸류에이션 기준
            'low_per': 15.0,            # PER 15배 이하 (저평가)
            'fair_per': 20.0,           # PER 20배 이하 (적정)
            'low_pbr': 1.0,             # PBR 1.0배 이하 (저평가)
            'fair_pbr': 1.5,            # PBR 1.5배 이하 (적정)
            
            # 연속성 기준
            'min_profit_years': 5,      # 최소 5년 연속 흑자
            'excellent_profit_years': 10 # 10년 연속 흑자 (우수)
        }
        
        print("🏆 워런 버핏 스코어카드 시스템 초기화 완료")
    
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
    
    def calculate_financial_ratios(self, stock_code, year='2023'):
        """📊 재무비율 계산 (워런 버핏 핵심 지표)"""
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
        
        # 주요 계정과목 추출
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
        
        # 워런 버핏 핵심 재무비율 계산
        try:
            # 1. 수익성 지표 (워런 버핏 최우선)
            if '당기순이익' in accounts and '자본총계' in accounts and accounts['자본총계'] != 0:
                ratios['ROE'] = (accounts['당기순이익'] / accounts['자본총계']) * 100
            
            if '당기순이익' in accounts and '자산총계' in accounts and accounts['자산총계'] != 0:
                ratios['ROA'] = (accounts['당기순이익'] / accounts['자산총계']) * 100
            
            if '영업이익' in accounts and '매출액' in accounts and accounts['매출액'] != 0:
                ratios['영업이익률'] = (accounts['영업이익'] / accounts['매출액']) * 100
            
            if '당기순이익' in accounts and '매출액' in accounts and accounts['매출액'] != 0:
                ratios['순이익률'] = (accounts['당기순이익'] / accounts['매출액']) * 100
            
            # 2. 안정성 지표 (워런 버핏 중시)
            if '부채총계' in accounts and '자본총계' in accounts and accounts['자본총계'] != 0:
                ratios['부채비율'] = (accounts['부채총계'] / accounts['자본총계']) * 100
            
            if '유동자산' in accounts and '유동부채' in accounts and accounts['유동부채'] != 0:
                ratios['유동비율'] = (accounts['유동자산'] / accounts['유동부채']) * 100
            
            if '자본총계' in accounts and '자산총계' in accounts and accounts['자산총계'] != 0:
                ratios['자기자본비율'] = (accounts['자본총계'] / accounts['자산총계']) * 100
            
            # 3. 활동성 지표
            if '매출액' in accounts and '자산총계' in accounts and accounts['자산총계'] != 0:
                ratios['총자산회전율'] = accounts['매출액'] / accounts['자산총계']
            
        except Exception as e:
            print(f"⚠️ {stock_code} 재무비율 계산 오류: {e}")
        
        return ratios, accounts
    
    def calculate_growth_rates(self, stock_code, years=['2023', '2022', '2021']):
        """📈 성장률 계산 (3년간 CAGR)"""
        growth_data = {}
        yearly_data = {}
        
        # 연도별 재무데이터 수집
        for year in years:
            ratios, accounts = self.calculate_financial_ratios(stock_code, year)
            yearly_data[year] = accounts
        
        try:
            # 매출 성장률 계산 (CAGR)
            if '2023' in yearly_data and '2021' in yearly_data:
                revenue_2023 = yearly_data['2023'].get('매출액', 0)
                revenue_2021 = yearly_data['2021'].get('매출액', 0)
                
                if revenue_2021 > 0 and revenue_2023 > 0:
                    growth_data['매출성장률_CAGR'] = ((revenue_2023 / revenue_2021) ** (1/2) - 1) * 100
            
            # 순이익 성장률 계산 (CAGR)
            if '2023' in yearly_data and '2021' in yearly_data:
                profit_2023 = yearly_data['2023'].get('당기순이익', 0)
                profit_2021 = yearly_data['2021'].get('당기순이익', 0)
                
                if profit_2021 > 0 and profit_2023 > 0:
                    growth_data['순이익성장률_CAGR'] = ((profit_2023 / profit_2021) ** (1/2) - 1) * 100
            
            # 자기자본 성장률 (워런 버핏 중시)
            if '2023' in yearly_data and '2021' in yearly_data:
                equity_2023 = yearly_data['2023'].get('자본총계', 0)
                equity_2021 = yearly_data['2021'].get('자본총계', 0)
                
                if equity_2021 > 0 and equity_2023 > 0:
                    growth_data['자기자본성장률_CAGR'] = ((equity_2023 / equity_2021) ** (1/2) - 1) * 100
            
        except Exception as e:
            print(f"⚠️ {stock_code} 성장률 계산 오류: {e}")
        
        return growth_data
    
    def calculate_valuation_metrics(self, stock_code):
        """💰 밸류에이션 지표 계산"""
        try:
            # 주식 가격 데이터 조회
            price_query = """
                SELECT close, date
                FROM stock_prices 
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT 1
            """
            price_data = self.query_stock_db(price_query, (stock_code,))
            
            if price_data.empty:
                return {}
            
            current_price = float(price_data.iloc[0]['close'])
            
            # 재무데이터 조회
            ratios, accounts = self.calculate_financial_ratios(stock_code, '2023')
            
            valuation = {}
            
            # PER 계산 (워런 버핏 핵심 지표)
            if '당기순이익' in accounts and accounts['당기순이익'] > 0:
                # 대략적인 주식 수로 PER 계산 (시가총액 기반)
                market_cap_estimate = current_price * 1000000  # 임시 추정
                valuation['PER_추정'] = market_cap_estimate / accounts['당기순이익']
            
            # PBR 계산 (워런 버핏 중시)
            if '자본총계' in accounts and accounts['자본총계'] > 0:
                market_cap_estimate = current_price * 1000000  # 임시 추정
                valuation['PBR_추정'] = market_cap_estimate / accounts['자본총계']
            
            # 현재 주가 정보
            valuation['현재주가'] = current_price
            
            return valuation
            
        except Exception as e:
            print(f"⚠️ {stock_code} 밸류에이션 계산 오류: {e}")
            return {}
    
    def count_consecutive_profit_years(self, stock_code):
        """🏆 연속 흑자 년수 계산 (워런 버핏 품질 지표)"""
        try:
            # 최근 10년간 순이익 데이터 조회
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
            print(f"⚠️ {stock_code} 연속흑자 계산 오류: {e}")
            return 0
    
    def calculate_buffett_score(self, stock_code):
        """🏆 워런 버핏 스코어 계산 (100점 만점)"""
        
        # 기본 데이터 수집
        ratios, accounts = self.calculate_financial_ratios(stock_code, '2023')
        growth_data = self.calculate_growth_rates(stock_code)
        valuation = self.calculate_valuation_metrics(stock_code)
        consecutive_profits = self.count_consecutive_profit_years(stock_code)
        
        if not ratios:
            return None
        
        score_breakdown = {
            '수익성': 0,    # 30점 만점
            '성장성': 0,    # 25점 만점  
            '안정성': 0,    # 25점 만점
            '밸류에이션': 0  # 20점 만점
        }
        
        # 1. 수익성 평가 (30점 만점) - 워런 버핏 최우선
        profitability_score = 0
        
        # ROE 평가 (15점)
        roe = ratios.get('ROE', 0)
        if roe >= self.quality_criteria['excellent_roe']:  # 20% 이상
            profitability_score += 15
        elif roe >= self.quality_criteria['good_roe']:     # 15% 이상
            profitability_score += 12
        elif roe >= self.quality_criteria['min_roe']:      # 10% 이상
            profitability_score += 8
        
        # 영업이익률 평가 (8점)
        operating_margin = ratios.get('영업이익률', 0)
        if operating_margin >= 15:
            profitability_score += 8
        elif operating_margin >= 10:
            profitability_score += 6
        elif operating_margin >= 5:
            profitability_score += 3
        
        # ROA 평가 (7점)
        roa = ratios.get('ROA', 0)
        if roa >= 10:
            profitability_score += 7
        elif roa >= 7:
            profitability_score += 5
        elif roa >= 5:
            profitability_score += 3
        
        score_breakdown['수익성'] = profitability_score
        
        # 2. 성장성 평가 (25점 만점)
        growth_score = 0
        
        # 매출 성장률 (12점)
        revenue_growth = growth_data.get('매출성장률_CAGR', 0)
        if revenue_growth >= self.quality_criteria['excellent_growth']:  # 15% 이상
            growth_score += 12
        elif revenue_growth >= self.quality_criteria['good_growth']:     # 10% 이상
            growth_score += 9
        elif revenue_growth >= self.quality_criteria['min_growth']:      # 5% 이상
            growth_score += 6
        elif revenue_growth >= 0:  # 플러스 성장
            growth_score += 3
        
        # 순이익 성장률 (13점)
        profit_growth = growth_data.get('순이익성장률_CAGR', 0)
        if profit_growth >= self.quality_criteria['excellent_growth']:
            growth_score += 13
        elif profit_growth >= self.quality_criteria['good_growth']:
            growth_score += 10
        elif profit_growth >= self.quality_criteria['min_growth']:
            growth_score += 7
        elif profit_growth >= 0:
            growth_score += 3
        
        score_breakdown['성장성'] = growth_score
        
        # 3. 안정성 평가 (25점 만점) - 워런 버핏 중시
        stability_score = 0
        
        # 부채비율 평가 (10점)
        debt_ratio = ratios.get('부채비율', 999)
        if debt_ratio <= self.quality_criteria['excellent_debt_ratio']:  # 30% 이하
            stability_score += 10
        elif debt_ratio <= self.quality_criteria['max_debt_ratio']:      # 50% 이하
            stability_score += 7
        elif debt_ratio <= 100:  # 100% 이하
            stability_score += 3
        
        # 유동비율 평가 (7점)
        current_ratio = ratios.get('유동비율', 0)
        if current_ratio >= 200:
            stability_score += 7
        elif current_ratio >= self.quality_criteria['min_current_ratio']:  # 150% 이상
            stability_score += 5
        elif current_ratio >= 100:
            stability_score += 2
        
        # 연속 흑자 년수 (8점) - 워런 버핏 품질 지표
        if consecutive_profits >= self.quality_criteria['excellent_profit_years']:  # 10년 이상
            stability_score += 8
        elif consecutive_profits >= self.quality_criteria['min_profit_years']:      # 5년 이상
            stability_score += 5
        elif consecutive_profits >= 3:  # 3년 이상
            stability_score += 2
        
        score_breakdown['안정성'] = stability_score
        
        # 4. 밸류에이션 평가 (20점 만점)
        valuation_score = 0
        
        # PER 평가 (12점) - 임시 계산이므로 낮은 비중
        per_estimate = valuation.get('PER_추정', 999)
        if per_estimate <= self.quality_criteria['low_per']:     # 15배 이하
            valuation_score += 12
        elif per_estimate <= self.quality_criteria['fair_per']:  # 20배 이하
            valuation_score += 8
        elif per_estimate <= 30:  # 30배 이하
            valuation_score += 4
        
        # PBR 평가 (8점) - 임시 계산이므로 낮은 비중
        pbr_estimate = valuation.get('PBR_추정', 999)
        if pbr_estimate <= self.quality_criteria['low_pbr']:     # 1.0배 이하
            valuation_score += 8
        elif pbr_estimate <= self.quality_criteria['fair_pbr']:  # 1.5배 이하
            valuation_score += 5
        elif pbr_estimate <= 2.0:  # 2.0배 이하
            valuation_score += 2
        
        score_breakdown['밸류에이션'] = valuation_score
        
        # 총점 계산
        total_score = sum(score_breakdown.values())
        
        # 등급 부여 (워런 버핏 스타일)
        if total_score >= 85:
            grade = 'A+'  # 버핏이 사랑할 기업
        elif total_score >= 75:
            grade = 'A'   # 우수한 기업
        elif total_score >= 65:
            grade = 'B+'  # 양호한 기업
        elif total_score >= 55:
            grade = 'B'   # 보통 기업
        elif total_score >= 45:
            grade = 'C+'  # 주의 필요
        else:
            grade = 'C'   # 투자 부적합
        
        return {
            '종목코드': stock_code,
            '총점': total_score,
            '등급': grade,
            '상세점수': score_breakdown,
            '핵심지표': {
                'ROE': round(ratios.get('ROE', 0), 2),
                '부채비율': round(ratios.get('부채비율', 0), 2),
                '연속흑자': f"{consecutive_profits}년",
                '매출성장률': round(growth_data.get('매출성장률_CAGR', 0), 2),
                '현재주가': valuation.get('현재주가', 0)
            }
        }
    
    def find_buffett_gems(self, min_score=75, limit=50):
        """💎 워런 버핏이 선호할 저평가 우량주 발굴"""
        print(f"💎 워런 버핏 스타일 우량주 발굴 중... (최소 {min_score}점 이상)")
        
        # 수집된 모든 기업 조회
        companies = self.query_dart_db("""
            SELECT DISTINCT stock_code, corp_name
            FROM company_info
            WHERE stock_code IS NOT NULL AND stock_code != ''
            ORDER BY stock_code
        """)
        
        if companies.empty:
            print("❌ 분석할 기업 데이터가 없습니다.")
            return pd.DataFrame()
        
        buffett_gems = []
        
        print(f"📊 총 {len(companies)}개 기업 분석 중...")
        
        for idx, row in companies.iterrows():
            stock_code = row['stock_code']
            corp_name = row['corp_name']
            
            # 진행률 표시 (매 50개마다)
            if (idx + 1) % 50 == 0:
                print(f"⏳ 진행률: {idx + 1}/{len(companies)} ({(idx + 1)/len(companies)*100:.1f}%)")
            
            try:
                score_result = self.calculate_buffett_score(stock_code)
                
                if score_result and score_result['총점'] >= min_score:
                    result = {
                        '순위': len(buffett_gems) + 1,
                        '종목코드': stock_code,
                        '기업명': corp_name,
                        '워런버핏점수': score_result['총점'],
                        '등급': score_result['등급'],
                        'ROE': score_result['핵심지표']['ROE'],
                        '부채비율': score_result['핵심지표']['부채비율'],
                        '연속흑자': score_result['핵심지표']['연속흑자'],
                        '매출성장률': score_result['핵심지표']['매출성장률'],
                        '수익성점수': score_result['상세점수']['수익성'],
                        '성장성점수': score_result['상세점수']['성장성'],
                        '안정성점수': score_result['상세점수']['안정성'],
                        '밸류에이션점수': score_result['상세점수']['밸류에이션']
                    }
                    
                    buffett_gems.append(result)
                    
                    # 상위 기업 발견 시 실시간 알림
                    if score_result['총점'] >= 85:
                        print(f"🏆 A+ 등급 발견! {corp_name}({stock_code}): {score_result['총점']}점")
                    
            except Exception as e:
                continue
        
        # 점수순 정렬
        if buffett_gems:
            gems_df = pd.DataFrame(buffett_gems)
            gems_df = gems_df.sort_values('워런버핏점수', ascending=False).head(limit)
            
            # 순위 재정렬
            gems_df['순위'] = range(1, len(gems_df) + 1)
            
            return gems_df
        else:
            return pd.DataFrame()
    
    def create_detailed_report(self, stock_code):
        """📋 종목별 상세 워런 버핏 분석 리포트"""
        
        # 기업 정보 조회
        company_info = self.query_dart_db("""
            SELECT corp_name, ceo_nm, ind_tp, est_dt
            FROM company_info
            WHERE stock_code = ?
        """, (stock_code,))
        
        if company_info.empty:
            print(f"❌ {stock_code} 기업 정보를 찾을 수 없습니다.")
            return
        
        corp_name = company_info.iloc[0]['corp_name']
        
        print("=" * 80)
        print(f"🏆 {corp_name} ({stock_code}) 워런 버핏 스타일 분석 리포트")
        print("=" * 80)
        
        # 워런 버핏 스코어 계산
        score_result = self.calculate_buffett_score(stock_code)
        
        if not score_result:
            print("❌ 분석에 필요한 재무데이터가 부족합니다.")
            return
        
        # 1. 종합 평가
        print(f"📊 워런 버핏 종합 점수: {score_result['총점']}/100점 (등급: {score_result['등급']})")
        print()
        
        # 등급별 투자 의견
        grade = score_result['등급']
        if grade == 'A+':
            investment_opinion = "🚀 강력 매수 추천 - 워런 버핏이 선호할 최고급 기업"
        elif grade == 'A':
            investment_opinion = "✅ 매수 추천 - 우수한 품질의 투자 대상"
        elif grade == 'B+':
            investment_opinion = "⚠️ 신중한 검토 후 투자 - 양호한 수준"
        elif grade == 'B':
            investment_opinion = "🤔 추가 분석 필요 - 보통 수준"
        else:
            investment_opinion = "❌ 투자 부적합 - 워런 버핏 기준 미달"
        
        print(f"💡 투자 의견: {investment_opinion}")
        print()
        
        # 2. 영역별 상세 점수
        print("📈 영역별 상세 분석:")
        breakdown = score_result['상세점수']
        print(f"   수익성 (30점 만점): {breakdown['수익성']}점")
        print(f"   성장성 (25점 만점): {breakdown['성장성']}점")
        print(f"   안정성 (25점 만점): {breakdown['안정성']}점")
        print(f"   밸류에이션 (20점 만점): {breakdown['밸류에이션']}점")
        print()
        
        # 3. 핵심 지표 분석
        print("🔍 워런 버핏 핵심 지표:")
        indicators = score_result['핵심지표']
        
        # ROE 분석
        roe = indicators['ROE']
        if roe >= 20:
            roe_comment = "🏆 최고급 (20% 이상)"
        elif roe >= 15:
            roe_comment = "✅ 우수 (15% 이상)"
        elif roe >= 10:
            roe_comment = "⚠️ 보통 (10% 이상)"
        else:
            roe_comment = "❌ 부족 (10% 미만)"
        
        print(f"   ROE: {roe}% {roe_comment}")
        
        # 부채비율 분석
        debt_ratio = indicators['부채비율']
        if debt_ratio <= 30:
            debt_comment = "🏆 매우 안전 (30% 이하)"
        elif debt_ratio <= 50:
            debt_comment = "✅ 안전 (50% 이하)"
        elif debt_ratio <= 100:
            debt_comment = "⚠️ 주의 (100% 이하)"
        else:
            debt_comment = "❌ 위험 (100% 초과)"
        
        print(f"   부채비율: {debt_ratio}% {debt_comment}")
        
        # 기타 지표
        print(f"   연속흑자: {indicators['연속흑자']}")
        print(f"   매출성장률: {indicators['매출성장률']}%")
        print()
        
        # 4. 워런 버핏 투자 철학 관점 분석
        print("💭 워런 버핏 투자 철학 관점:")
        
        # 경제적 해자 평가
        if roe >= 15 and debt_ratio <= 50:
            moat_strength = "🏰 강력한 경제적 해자 보유"
        elif roe >= 10 and debt_ratio <= 70:
            moat_strength = "🛡️ 일정한 경쟁우위 보유"
        else:
            moat_strength = "⚡ 경쟁우위 불분명"
        
        print(f"   경제적 해자: {moat_strength}")
        
        # 관리 품질 평가
        profit_years = int(indicators['연속흑자'].replace('년', ''))
        if profit_years >= 10:
            management_quality = "🎯 뛰어난 경영진 (10년+ 연속 흑자)"
        elif profit_years >= 5:
            management_quality = "👍 양호한 경영진 (5년+ 연속 흑자)"
        else:
            management_quality = "❓ 경영 품질 검증 필요"
        
        print(f"   관리 품질: {management_quality}")
        
        # 성장 전망
        growth_rate = indicators['매출성장률']
        if growth_rate >= 10:
            growth_outlook = "🚀 고성장 기업 (10%+ 성장)"
        elif growth_rate >= 5:
            growth_outlook = "📈 안정 성장 (5%+ 성장)"
        elif growth_rate >= 0:
            growth_outlook = "🔄 저성장 기업"
        else:
            growth_outlook = "📉 성장 둔화"
        
        print(f"   성장 전망: {growth_outlook}")
        print()
        
        # 5. 투자 액션 플랜
        print("🎯 워런 버핏 스타일 투자 액션 플랜:")
        
        if score_result['총점'] >= 85:
            print("   1. 즉시 포트폴리오 검토 후 비중 확대 고려")
            print("   2. 장기 보유 전략 (10년+ 관점)")
            print("   3. 추가 하락 시 적극적 매수 기회")
        elif score_result['총점'] >= 75:
            print("   1. 추가 실사 후 투자 검토")
            print("   2. 분할 매수로 리스크 관리")
            print("   3. 중장기 보유 (5년+ 관점)")
        elif score_result['총점'] >= 65:
            print("   1. 워치리스트 등록 후 지속 모니터링")
            print("   2. 개선 신호 확인 후 투자 검토")
            print("   3. 소액 투자로 시작")
        else:
            print("   1. 현재 투자 부적합")
            print("   2. 펀더멘털 개선 시까지 대기")
            print("   3. 다른 우량주 발굴 필요")
        
        print("=" * 80)
    
    def visualize_top_stocks(self, gems_df, top_n=20):
        """📊 상위 종목 시각화"""
        if gems_df.empty:
            print("❌ 시각화할 데이터가 없습니다.")
            return
        
        top_stocks = gems_df.head(top_n)
        
        # 그래프 설정
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(f'🏆 워런 버핏 스타일 TOP {top_n} 우량주 분석', fontsize=16, fontweight='bold')
        
        # 1. 워런 버핏 점수 분포
        ax1.barh(top_stocks['기업명'], top_stocks['워런버핏점수'], color='skyblue')
        ax1.set_xlabel('워런 버핏 점수')
        ax1.set_title('종목별 워런 버핏 점수')
        ax1.grid(axis='x', alpha=0.3)
        
        # 2. ROE vs 부채비율 산점도
        scatter = ax2.scatter(top_stocks['ROE'], top_stocks['부채비율'], 
                            c=top_stocks['워런버핏점수'], cmap='viridis', s=100, alpha=0.7)
        ax2.set_xlabel('ROE (%)')
        ax2.set_ylabel('부채비율 (%)')
        ax2.set_title('ROE vs 부채비율 (색상: 워런버핏점수)')
        ax2.grid(alpha=0.3)
        plt.colorbar(scatter, ax=ax2)
        
        # 워런 버핏 선호 구간 표시
        ax2.axvline(x=15, color='red', linestyle='--', alpha=0.5, label='ROE 15% 기준선')
        ax2.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='부채비율 50% 기준선')
        ax2.legend()
        
        # 3. 영역별 평균 점수
        score_categories = ['수익성점수', '성장성점수', '안정성점수', '밸류에이션점수']
        avg_scores = [top_stocks[cat].mean() for cat in score_categories]
        max_scores = [30, 25, 25, 20]  # 각 영역별 만점
        
        categories = ['수익성\n(30점)', '성장성\n(25점)', '안정성\n(25점)', '밸류에이션\n(20점)']
        x_pos = range(len(categories))
        
        bars = ax3.bar(x_pos, avg_scores, color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A'])
        ax3.set_ylabel('평균 점수')
        ax3.set_title('영역별 평균 점수 (TOP 20 기업)')
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels(categories)
        ax3.grid(axis='y', alpha=0.3)
        
        # 만점 기준선 표시
        for i, (score, max_score) in enumerate(zip(avg_scores, max_scores)):
            ax3.axhline(y=max_score, color='red', linestyle='--', alpha=0.3)
            ax3.text(i, score + 1, f'{score:.1f}', ha='center', va='bottom', fontweight='bold')
        
        # 4. 등급 분포
        grade_counts = top_stocks['등급'].value_counts()
        colors = {'A+': '#FF6B6B', 'A': '#4ECDC4', 'B+': '#45B7D1', 'B': '#FFA07A', 'C+': '#96CEB4', 'C': '#FECA57'}
        pie_colors = [colors.get(grade, '#95A5A6') for grade in grade_counts.index]
        
        ax4.pie(grade_counts.values, labels=grade_counts.index, autopct='%1.1f%%', 
                colors=pie_colors, startangle=90)
        ax4.set_title('등급 분포')
        
        plt.tight_layout()
        plt.show()
        
        print(f"\n📊 TOP {top_n} 기업 평균 지표:")
        print(f"   평균 워런버핏 점수: {top_stocks['워런버핏점수'].mean():.1f}점")
        print(f"   평균 ROE: {top_stocks['ROE'].mean():.1f}%")
        print(f"   평균 부채비율: {top_stocks['부채비율'].mean():.1f}%")
        print(f"   평균 매출성장률: {top_stocks['매출성장률'].mean():.1f}%")


def main():
    """메인 실행 함수"""
    
    print("🏆 워런 버핏 스코어카드 시스템")
    print("=" * 60)
    print("💡 워런 버핏의 투자 철학을 바탕으로 한국 주식을 100점 만점으로 평가합니다")
    print("📊 평가 기준: 수익성(30점) + 성장성(25점) + 안정성(25점) + 밸류에이션(20점)")
    print("=" * 60)
    
    try:
        # 워런 버핏 스코어카드 초기화
        scorecard = BuffettScorecard()
        
        while True:
            print("\n🎯 원하는 기능을 선택하세요:")
            print("1. 워런 버핏 우량주 TOP 50 발굴")
            print("2. 특정 종목 상세 분석")
            print("3. 워런 버핏 A+ 등급 종목만 찾기")
            print("4. 커스텀 조건으로 스크리닝")
            print("5. 상위 종목 시각화")
            print("0. 종료")
            
            choice = input("\n선택하세요 (0-5): ").strip()
            
            if choice == '0':
                print("👋 워런 버핏 스코어카드를 종료합니다.")
                break
            
            elif choice == '1':
                print("\n💎 워런 버핏 스타일 우량주 TOP 50 발굴 중...")
                gems_df = scorecard.find_buffett_gems(min_score=70, limit=50)
                
                if not gems_df.empty:
                    print(f"\n🏆 발견된 우량주: {len(gems_df)}개")
                    print("\n" + "="*120)
                    print(gems_df[['순위', '기업명', '종목코드', '워런버핏점수', '등급', 'ROE', '부채비율', '연속흑자', '매출성장률']].to_string(index=False))
                    print("="*120)
                    
                    # 등급별 요약
                    grade_summary = gems_df['등급'].value_counts()
                    print(f"\n📊 등급별 분포:")
                    for grade, count in grade_summary.items():
                        print(f"   {grade} 등급: {count}개")
                else:
                    print("❌ 조건을 만족하는 우량주를 찾지 못했습니다.")
                    print("💡 기준을 낮춰서 다시 시도해보세요.")
            
            elif choice == '2':
                stock_code = input("\n분석할 종목코드를 입력하세요 (예: 005930): ").strip()
                if stock_code:
                    scorecard.create_detailed_report(stock_code)
                else:
                    print("❌ 올바른 종목코드를 입력해주세요.")
            
            elif choice == '3':
                print("\n🌟 워런 버핏 A+ 등급 종목 발굴 중...")
                gems_df = scorecard.find_buffett_gems(min_score=85, limit=20)
                
                if not gems_df.empty:
                    print(f"\n🏆 A+ 등급 기업: {len(gems_df)}개 발견!")
                    print("🚀 이 기업들은 워런 버핏이 가장 선호할 만한 최고급 투자 대상입니다")
                    print("\n" + "="*120)
                    print(gems_df[['순위', '기업명', '종목코드', '워런버핏점수', '등급', 'ROE', '부채비율', '연속흑자']].to_string(index=False))
                    print("="*120)
                else:
                    print("❌ A+ 등급 기업을 찾지 못했습니다.")
                    print("💡 시장에 최고급 기업이 부족하거나 기준이 매우 엄격합니다.")
            
            elif choice == '4':
                print("\n🔧 커스텀 스크리닝 조건 설정:")
                try:
                    min_score = int(input("최소 워런버핏 점수 (기본 70): ").strip() or "70")
                    limit = int(input("최대 결과 개수 (기본 30): ").strip() or "30")
                    
                    gems_df = scorecard.find_buffett_gems(min_score=min_score, limit=limit)
                    
                    if not gems_df.empty:
                        print(f"\n🎯 조건 만족 기업: {len(gems_df)}개")
                        print(gems_df[['순위', '기업명', '워런버핏점수', '등급', 'ROE', '부채비율']].to_string(index=False))
                    else:
                        print("❌ 조건을 만족하는 기업이 없습니다.")
                except ValueError:
                    print("❌ 올바른 숫자를 입력해주세요.")
            
            elif choice == '5':
                # 기존 결과가 있다면 시각화
                if 'gems_df' in locals() and not gems_df.empty:
                    print("\n📊 상위 종목 시각화 중...")
                    scorecard.visualize_top_stocks(gems_df)
                else:
                    print("❌ 먼저 종목 발굴을 실행해주세요.")
            
            else:
                print("❌ 올바른 번호를 선택해주세요.")
    
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("💡 DART 데이터가 충분히 수집되었는지 확인해주세요.")


if __name__ == "__main__":
    main()