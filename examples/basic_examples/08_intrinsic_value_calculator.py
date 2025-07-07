"""
💰 워런 버핏 스타일 내재가치 계산 시스템

이 모듈은 워런 버핏의 투자 철학을 바탕으로 내재가치를 계산합니다.

계산 방법:
1. 📊 DCF 모델 (Discounted Cash Flow) - 현금흐름 할인법
2. 💎 소유주 이익 기반 계산 (워런 버핏 방식)
3. 📈 성장률 기반 내재가치 (지속가능한 성장률)
4. 🛡️ 50% 안전마진 적용 매수가 계산

🎯 목표: 데이터 기반으로 정확한 내재가치 계산 및 매수 타이밍 제공
"""

import sys
from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
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


class IntrinsicValueCalculator:
    """
    💰 워런 버핏 스타일 내재가치 계산기
    
    DCF 모델과 소유주 이익을 기반으로 진정한 기업 가치를 계산합니다.
    """
    
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.dart_db_path = self.data_dir / 'dart_data.db'
        self.stock_db_path = self.data_dir / 'stock_data.db'
        
        if not self.dart_db_path.exists():
            print(f"❌ DART 데이터베이스가 없습니다: {self.dart_db_path}")
            exit(1)
        
        # 워런 버핏 스타일 계산 상수
        self.calculation_constants = {
            'risk_free_rate': 0.035,      # 무위험 수익률 3.5% (한국 국채 10년)
            'market_risk_premium': 0.06,  # 시장 위험 프리미엄 6%
            'terminal_growth_rate': 0.025, # 장기 성장률 2.5%
            'safety_margin': 0.5,         # 안전마진 50%
            'buffett_required_return': 0.15, # 워런 버핏 요구수익률 15%
            'conservative_growth_cap': 0.15,  # 보수적 성장률 상한 15%
            'min_years_data': 3,           # 최소 필요 데이터 년수
            'projection_years': 10         # 현금흐름 예측 년수
        }
        
        print("💰 내재가치 계산 시스템 초기화 완료")
    
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
    
    def get_historical_financials(self, stock_code, years=['2023', '2022', '2021']):
        """📊 다년간 재무데이터 수집"""
        financial_history = {}
        
        for year in years:
            query = """
                SELECT fs.account_nm, fs.thstrm_amount, fs.bsns_year
                FROM financial_statements fs
                JOIN company_info ci ON fs.corp_code = ci.corp_code
                WHERE ci.stock_code = ? AND fs.bsns_year = ?
                ORDER BY fs.ord
            """
            
            data = self.query_dart_db(query, (stock_code, year))
            
            if not data.empty:
                accounts = {}
                for _, row in data.iterrows():
                    try:
                        amount = float(str(row['thstrm_amount']).replace(',', ''))
                        accounts[row['account_nm']] = amount
                    except:
                        continue
                
                financial_history[year] = accounts
        
        return financial_history
    
    def calculate_owner_earnings(self, financial_data):
        """💎 소유주 이익 계산 (워런 버핏의 핵심 개념)"""
        """
        소유주 이익 = 당기순이익 + 감가상각비 + 기타 비현금비용 - 자본적지출 - 운전자본 변화
        
        단순화된 버전: 당기순이익 + 감가상각비 - (매출 증가에 필요한 재투자)
        """
        
        try:
            net_income = financial_data.get('당기순이익', 0)
            
            # 감가상각비 추정 (매출의 2-3% 가정)
            revenue = financial_data.get('매출액', 0)
            estimated_depreciation = revenue * 0.025
            
            # 재투자 필요액 추정 (매출 증가의 5% 가정)
            estimated_reinvestment = revenue * 0.05
            
            # 소유주 이익 계산
            owner_earnings = net_income + estimated_depreciation - estimated_reinvestment
            
            return max(owner_earnings, net_income * 0.8)  # 최소 순이익의 80%
            
        except Exception as e:
            print(f"⚠️ 소유주 이익 계산 오류: {e}")
            return financial_data.get('당기순이익', 0)
    
    def calculate_sustainable_growth_rate(self, financial_history):
        """📈 지속가능한 성장률 계산"""
        try:
            years = sorted(financial_history.keys(), reverse=True)
            
            if len(years) < 2:
                return 0.05  # 기본값 5%
            
            # ROE 기반 성장률 계산
            roe_growth_rates = []
            revenue_growth_rates = []
            earnings_growth_rates = []
            
            for i in range(len(years) - 1):
                current_year = years[i]
                previous_year = years[i + 1]
                
                current_data = financial_history[current_year]
                previous_data = financial_history[previous_year]
                
                # 매출 성장률
                current_revenue = current_data.get('매출액', 0)
                previous_revenue = previous_data.get('매출액', 0)
                
                if previous_revenue > 0:
                    revenue_growth = (current_revenue / previous_revenue) - 1
                    revenue_growth_rates.append(revenue_growth)
                
                # 순이익 성장률
                current_earnings = current_data.get('당기순이익', 0)
                previous_earnings = previous_data.get('당기순이익', 0)
                
                if previous_earnings > 0 and current_earnings > 0:
                    earnings_growth = (current_earnings / previous_earnings) - 1
                    earnings_growth_rates.append(earnings_growth)
                
                # ROE 계산
                current_equity = current_data.get('자본총계', 0)
                if current_equity > 0 and current_earnings > 0:
                    roe = current_earnings / current_equity
                    # ROE 기반 성장률 (보수적으로 배당성향 40% 가정)
                    roe_growth_rates.append(roe * 0.6)
            
            # 보수적 성장률 계산 (여러 방법의 최솟값)
            growth_estimates = []
            
            if revenue_growth_rates:
                avg_revenue_growth = np.mean(revenue_growth_rates)
                growth_estimates.append(min(avg_revenue_growth, self.calculation_constants['conservative_growth_cap']))
            
            if earnings_growth_rates:
                avg_earnings_growth = np.mean(earnings_growth_rates)
                growth_estimates.append(min(avg_earnings_growth, self.calculation_constants['conservative_growth_cap']))
            
            if roe_growth_rates:
                avg_roe_growth = np.mean(roe_growth_rates)
                growth_estimates.append(min(avg_roe_growth, self.calculation_constants['conservative_growth_cap']))
            
            if growth_estimates:
                # 보수적 접근: 최솟값 사용
                sustainable_growth = min(growth_estimates)
                # 음수 성장률은 0으로 처리
                return max(sustainable_growth, 0)
            else:
                return 0.05  # 기본값 5%
                
        except Exception as e:
            print(f"⚠️ 성장률 계산 오류: {e}")
            return 0.05
    
    def calculate_discount_rate(self, stock_code):
        """📊 할인율 계산 (CAPM 모델 + 워런 버핏 요구수익률)"""
        try:
            # 베타 계산을 위한 주가 데이터 조회
            price_query = """
                SELECT date, close
                FROM stock_prices 
                WHERE symbol = ?
                AND date >= date('now', '-2 years')
                ORDER BY date
            """
            
            price_data = self.query_stock_db(price_query, (stock_code,))
            
            if len(price_data) > 50:
                # 간단한 베타 추정 (시장 대비 변동성)
                returns = price_data['close'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252)  # 연환산
                
                # 베타 추정 (시장 평균 변동성 20% 가정)
                market_volatility = 0.20
                estimated_beta = min(volatility / market_volatility, 1.5)  # 베타 상한 1.5
            else:
                estimated_beta = 1.0  # 기본값
            
            # CAPM 할인율
            risk_free_rate = self.calculation_constants['risk_free_rate']
            market_risk_premium = self.calculation_constants['market_risk_premium']
            capm_rate = risk_free_rate + estimated_beta * market_risk_premium
            
            # 워런 버핏 요구수익률과 비교하여 높은 값 사용 (보수적 접근)
            buffett_rate = self.calculation_constants['buffett_required_return']
            
            discount_rate = max(capm_rate, buffett_rate)
            
            return min(discount_rate, 0.20)  # 할인율 상한 20%
            
        except Exception as e:
            print(f"⚠️ 할인율 계산 오류: {e}")
            return self.calculation_constants['buffett_required_return']
    
    def calculate_dcf_value(self, stock_code):
        """💰 DCF 내재가치 계산 (워런 버핏 스타일)"""
        try:
            # 1. 재무데이터 수집
            financial_history = self.get_historical_financials(stock_code)
            
            if len(financial_history) < 2:
                return None
            
            latest_year = max(financial_history.keys())
            latest_financials = financial_history[latest_year]
            
            # 2. 기본 재무지표 계산
            current_owner_earnings = self.calculate_owner_earnings(latest_financials)
            growth_rate = self.calculate_sustainable_growth_rate(financial_history)
            discount_rate = self.calculate_discount_rate(stock_code)
            
            if current_owner_earnings <= 0:
                return None
            
            # 3. 현금흐름 예측 (10년간)
            projected_cash_flows = []
            projection_years = self.calculation_constants['projection_years']
            
            for year in range(1, projection_years + 1):
                # 성장률을 점진적으로 감소 (워런 버핏의 보수적 접근)
                if year <= 5:
                    annual_growth = growth_rate
                else:
                    # 6년차부터 점진적으로 장기성장률로 수렴
                    terminal_growth = self.calculation_constants['terminal_growth_rate']
                    decay_factor = (projection_years - year) / 5
                    annual_growth = terminal_growth + (growth_rate - terminal_growth) * decay_factor
                
                future_cash_flow = current_owner_earnings * ((1 + annual_growth) ** year)
                present_value = future_cash_flow / ((1 + discount_rate) ** year)
                projected_cash_flows.append(present_value)
            
            # 4. 터미널 밸류 계산
            terminal_cash_flow = current_owner_earnings * ((1 + growth_rate) ** projection_years)
            terminal_growth = self.calculation_constants['terminal_growth_rate']
            
            # 고든 성장 모델
            terminal_value = terminal_cash_flow * (1 + terminal_growth) / (discount_rate - terminal_growth)
            terminal_pv = terminal_value / ((1 + discount_rate) ** projection_years)
            
            # 5. 총 기업가치 계산
            total_pv_cash_flows = sum(projected_cash_flows)
            enterprise_value = total_pv_cash_flows + terminal_pv
            
            # 6. 주주가치 계산 (순현금 반영)
            total_debt = latest_financials.get('부채총계', 0)
            cash_and_equivalents = latest_financials.get('현금및현금성자산', 0) * 1.5  # 보수적 추정
            
            equity_value = enterprise_value - total_debt + cash_and_equivalents
            
            # 7. 주식 수 추정 (시가총액 기반)
            current_price = self.get_current_stock_price(stock_code)
            if current_price is None:
                return None
            
            # 대략적인 주식 수 추정 (자본총계 / 장부가치 기준)
            book_value_per_share = latest_financials.get('자본총계', 0) / 1000000  # 백만주 가정
            estimated_shares = max(latest_financials.get('자본총계', 0) / (current_price * 1000000), 1000000)
            
            # 8. 주당 내재가치
            intrinsic_value_per_share = equity_value / estimated_shares
            
            return {
                'intrinsic_value': intrinsic_value_per_share,
                'current_price': current_price,
                'discount_rate': discount_rate,
                'growth_rate': growth_rate,
                'owner_earnings': current_owner_earnings,
                'enterprise_value': enterprise_value,
                'equity_value': equity_value,
                'terminal_value_ratio': terminal_pv / enterprise_value,
                'cash_flows_pv': total_pv_cash_flows,
                'terminal_pv': terminal_pv
            }
            
        except Exception as e:
            print(f"❌ DCF 계산 오류: {e}")
            return None
    
    def get_current_stock_price(self, stock_code):
        """📈 현재 주가 조회"""
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
            print(f"⚠️ 주가 조회 오류: {e}")
            return None
    
    def calculate_multiple_valuations(self, stock_code):
        """🎯 다중 밸류에이션 방법론 (종합 내재가치)"""
        try:
            # 1. DCF 내재가치
            dcf_result = self.calculate_dcf_value(stock_code)
            
            # 2. 재무데이터 조회
            financial_history = self.get_historical_financials(stock_code)
            latest_year = max(financial_history.keys())
            latest_financials = financial_history[latest_year]
            
            # 3. PER 기반 내재가치
            per_value = self.calculate_per_based_value(stock_code, latest_financials)
            
            # 4. PBR 기반 내재가치
            pbr_value = self.calculate_pbr_based_value(stock_code, latest_financials)
            
            # 5. ROE 기반 내재가치 (워런 버핏 선호)
            roe_value = self.calculate_roe_based_value(stock_code, latest_financials)
            
            # 6. 종합 내재가치 계산 (가중평균)
            valuations = []
            weights = []
            
            if dcf_result and dcf_result['intrinsic_value'] > 0:
                valuations.append(dcf_result['intrinsic_value'])
                weights.append(0.4)  # DCF 40% 비중
            
            if per_value > 0:
                valuations.append(per_value)
                weights.append(0.25)  # PER 25% 비중
            
            if pbr_value > 0:
                valuations.append(pbr_value)
                weights.append(0.15)  # PBR 15% 비중
            
            if roe_value > 0:
                valuations.append(roe_value)
                weights.append(0.2)   # ROE 20% 비중
            
            if not valuations:
                return None
            
            # 가중평균 내재가치
            total_weight = sum(weights)
            if total_weight > 0:
                weights = [w/total_weight for w in weights]  # 정규화
                weighted_intrinsic_value = sum(v*w for v, w in zip(valuations, weights))
            else:
                weighted_intrinsic_value = np.mean(valuations)
            
            # 현재 주가
            current_price = self.get_current_stock_price(stock_code)
            
            if current_price is None:
                return None
            
            # 안전마진 적용 매수가
            safety_margin = self.calculation_constants['safety_margin']
            target_buy_price = weighted_intrinsic_value * (1 - safety_margin)
            
            return {
                'intrinsic_value': weighted_intrinsic_value,
                'current_price': current_price,
                'target_buy_price': target_buy_price,
                'safety_margin': safety_margin * 100,
                'upside_potential': ((weighted_intrinsic_value / current_price) - 1) * 100 if current_price > 0 else 0,
                'valuation_methods': {
                    'dcf_value': dcf_result['intrinsic_value'] if dcf_result else None,
                    'per_value': per_value,
                    'pbr_value': pbr_value,
                    'roe_value': roe_value
                },
                'dcf_details': dcf_result
            }
            
        except Exception as e:
            print(f"❌ 종합 밸류에이션 계산 오류: {e}")
            return None
    
    def calculate_per_based_value(self, stock_code, financial_data):
        """📊 PER 기반 내재가치"""
        try:
            net_income = financial_data.get('당기순이익', 0)
            
            if net_income <= 0:
                return 0
            
            # 업종별 적정 PER (한국 시장 기준)
            sector_pers = {
                'IT': 15,
                '반도체': 12,
                '자동차': 8,
                '화학': 10,
                '금융': 6,
                '바이오': 20,
                '기본값': 12
            }
            
            # 기업정보에서 업종 조회
            company_query = """
                SELECT ind_tp FROM company_info WHERE stock_code = ?
            """
            industry_result = self.query_dart_db(company_query, (stock_code,))
            
            if not industry_result.empty:
                industry = industry_result.iloc[0]['ind_tp']
                # 업종 매칭
                fair_per = sector_pers.get('기본값', 12)
                for sector, per in sector_pers.items():
                    if sector in str(industry):
                        fair_per = per
                        break
            else:
                fair_per = sector_pers['기본값']
            
            # 보수적 PER 적용 (적정 PER의 80%)
            conservative_per = fair_per * 0.8
            
            # 주당순이익 추정
            estimated_shares = 1000000  # 백만주 가정
            eps = net_income / estimated_shares
            
            return eps * conservative_per
            
        except Exception as e:
            return 0
    
    def calculate_pbr_based_value(self, stock_code, financial_data):
        """📈 PBR 기반 내재가치"""
        try:
            equity = financial_data.get('자본총계', 0)
            
            if equity <= 0:
                return 0
            
            # ROE 기반 적정 PBR 계산
            net_income = financial_data.get('당기순이익', 0)
            if equity > 0:
                roe = net_income / equity
                
                # ROE 기반 적정 PBR (간단한 모델)
                if roe >= 0.15:  # ROE 15% 이상
                    fair_pbr = 1.5
                elif roe >= 0.10:  # ROE 10% 이상
                    fair_pbr = 1.2
                else:
                    fair_pbr = 1.0
            else:
                fair_pbr = 1.0
            
            # 보수적 PBR 적용
            conservative_pbr = fair_pbr * 0.9
            
            # 주당 장부가치
            estimated_shares = 1000000  # 백만주 가정
            book_value_per_share = equity / estimated_shares
            
            return book_value_per_share * conservative_pbr
            
        except Exception as e:
            return 0
    
    def calculate_roe_based_value(self, stock_code, financial_data):
        """🏆 ROE 기반 내재가치 (워런 버핏 선호 방법)"""
        try:
            net_income = financial_data.get('당기순이익', 0)
            equity = financial_data.get('자본총계', 0)
            
            if net_income <= 0 or equity <= 0:
                return 0
            
            roe = net_income / equity
            
            # ROE 기반 내재가치 계산
            # 가정: 고ROE 기업은 더 높은 밸류에이션 받을 자격
            required_return = self.calculation_constants['buffett_required_return']
            
            if roe > required_return:
                # ROE가 요구수익률보다 높으면 프리미엄 부여
                premium_multiplier = min(roe / required_return, 2.0)  # 최대 2배
            else:
                premium_multiplier = 0.8  # 할인 적용
            
            # 주당 장부가치에 프리미엄/할인 적용
            estimated_shares = 1000000
            book_value_per_share = equity / estimated_shares
            
            return book_value_per_share * premium_multiplier
            
        except Exception as e:
            return 0
    
    def create_valuation_report(self, stock_code):
        """📋 종목별 완전한 내재가치 분석 리포트"""
        
        # 기업 정보 조회
        company_query = """
            SELECT corp_name, ceo_nm, ind_tp
            FROM company_info
            WHERE stock_code = ?
        """
        company_info = self.query_dart_db(company_query, (stock_code,))
        
        if company_info.empty:
            print(f"❌ {stock_code} 기업 정보를 찾을 수 없습니다.")
            return
        
        corp_name = company_info.iloc[0]['corp_name']
        
        print("=" * 100)
        print(f"💰 {corp_name} ({stock_code}) 내재가치 분석 리포트")
        print("=" * 100)
        
        # 종합 밸류에이션 계산
        valuation_result = self.calculate_multiple_valuations(stock_code)
        
        if not valuation_result:
            print("❌ 내재가치 계산에 필요한 데이터가 부족합니다.")
            return
        
        # 1. 핵심 결과 요약
        intrinsic_value = valuation_result['intrinsic_value']
        current_price = valuation_result['current_price']
        target_buy_price = valuation_result['target_buy_price']
        upside_potential = valuation_result['upside_potential']
        
        print(f"📊 내재가치 종합 분석:")
        print(f"   💎 계산된 내재가치: {intrinsic_value:,.0f}원")
        print(f"   📈 현재 주가: {current_price:,.0f}원")
        print(f"   🎯 목표 매수가: {target_buy_price:,.0f}원 (50% 안전마진 적용)")
        print(f"   🚀 상승 여력: {upside_potential:+.1f}%")
        print()
        
        # 2. 투자 판단
        if current_price <= target_buy_price:
            investment_decision = "🚀 강력 매수 추천 - 50% 안전마진 이하"
            action_color = "🟢"
        elif current_price <= intrinsic_value * 0.8:
            investment_decision = "✅ 매수 추천 - 20% 할인 가격"
            action_color = "🟡"
        elif current_price <= intrinsic_value:
            investment_decision = "⚠️ 신중한 매수 - 적정가 이하"
            action_color = "🟠"
        else:
            investment_decision = "❌ 매수 부적합 - 과대평가 상태"
            action_color = "🔴"
        
        print(f"🎯 투자 판단: {action_color} {investment_decision}")
        print()
        
        # 3. 다양한 방법론별 내재가치
        methods = valuation_result['valuation_methods']
        print(f"🔍 방법론별 내재가치 분석:")
        
        if methods['dcf_value']:
            print(f"   📊 DCF 모델: {methods['dcf_value']:,.0f}원 (40% 비중)")
        if methods['per_value'] > 0:
            print(f"   📈 PER 기반: {methods['per_value']:,.0f}원 (25% 비중)")
        if methods['pbr_value'] > 0:
            print(f"   📋 PBR 기반: {methods['pbr_value']:,.0f}원 (15% 비중)")
        if methods['roe_value'] > 0:
            print(f"   🏆 ROE 기반: {methods['roe_value']:,.0f}원 (20% 비중)")
        print()
        
        # 4. DCF 상세 분석
        dcf_details = valuation_result['dcf_details']
        if dcf_details:
            print(f"📊 DCF 모델 상세 분석:")
            print(f"   💰 소유주 이익: {dcf_details['owner_earnings']:,.0f}")
            print(f"   📈 성장률: {dcf_details['growth_rate']*100:.1f}%")
            print(f"   📉 할인율: {dcf_details['discount_rate']*100:.1f}%")
            print(f"   🏢 기업가치: {dcf_details['enterprise_value']:,.0f}")
            print(f"   👥 주주가치: {dcf_details['equity_value']:,.0f}")
            print(f"   🔮 터미널밸류 비중: {dcf_details['terminal_value_ratio']*100:.1f}%")
            print()
        
        # 5. 매수 전략 제안
        print(f"🎯 워런 버핏 스타일 매수 전략:")
        
        if current_price <= target_buy_price:
            print(f"   🚀 즉시 매수 고려 - 안전마진 확보됨")
            print(f"   💰 추천 매수 비중: 포트폴리오의 3-5%")
            print(f"   📅 보유 기간: 장기 (10년+)")
        elif current_price <= intrinsic_value * 0.9:
            print(f"   ✅ 분할 매수 전략 권장")
            print(f"   📉 목표가 접근 시 추가 매수: {target_buy_price:,.0f}원")
            print(f"   💰 초기 매수 비중: 포트폴리오의 1-2%")
        else:
            print(f"   ⏳ 워치리스트 등록 및 대기")
            print(f"   📉 매수 고려가: {intrinsic_value*0.8:,.0f}원 이하")
            print(f"   📉 적극 매수가: {target_buy_price:,.0f}원 이하")
        print()
        
        # 6. 리스크 요인
        print(f"⚠️ 주요 리스크 요인:")
        terminal_ratio = dcf_details['terminal_value_ratio'] if dcf_details else 0.5
        
        if terminal_ratio > 0.7:
            print(f"   🔮 터미널 밸류 의존도 높음 ({terminal_ratio*100:.1f}%)")
        
        if dcf_details and dcf_details['growth_rate'] > 0.1:
            print(f"   📈 높은 성장률 가정 ({dcf_details['growth_rate']*100:.1f}%)")
        
        print(f"   📊 내재가치 계산의 불확실성")
        print(f"   🌍 거시경제 환경 변화")
        print(f"   🏢 기업 경영환경 변화")
        
        print("=" * 100)
    
    def find_undervalued_stocks(self, min_discount=0.2, limit=30):
        """💎 저평가 종목 자동 발굴"""
        print(f"💎 저평가 종목 발굴 중... (최소 {min_discount*100:.0f}% 할인)")
        
        # 모든 기업 조회
        companies = self.query_dart_db("""
            SELECT DISTINCT stock_code, corp_name
            FROM company_info
            WHERE stock_code IS NOT NULL AND stock_code != ''
            ORDER BY stock_code
        """)
        
        undervalued_stocks = []
        
        for idx, row in companies.iterrows():
            stock_code = row['stock_code']
            corp_name = row['corp_name']
            
            # 진행률 표시
            if (idx + 1) % 30 == 0:
                print(f"⏳ 진행률: {idx + 1}/{len(companies)} ({(idx + 1)/len(companies)*100:.1f}%)")
            
            try:
                valuation_result = self.calculate_multiple_valuations(stock_code)
                
                if valuation_result:
                    intrinsic_value = valuation_result['intrinsic_value']
                    current_price = valuation_result['current_price']
                    
                    if current_price > 0:
                        discount = 1 - (current_price / intrinsic_value)
                        
                        if discount >= min_discount:
                            undervalued_stocks.append({
                                '순위': len(undervalued_stocks) + 1,
                                '종목코드': stock_code,
                                '기업명': corp_name,
                                '내재가치': int(intrinsic_value),
                                '현재가': int(current_price),
                                '할인율': f"{discount*100:.1f}%",
                                '상승여력': f"{valuation_result['upside_potential']:.1f}%",
                                '목표매수가': int(valuation_result['target_buy_price'])
                            })
                            
                            # 큰 할인 발견 시 알림
                            if discount >= 0.5:
                                print(f"🚨 대형 할인 발견! {corp_name}({stock_code}): {discount*100:.1f}% 할인")
                
            except Exception as e:
                continue
        
        # 할인율 순 정렬
        if undervalued_stocks:
            df = pd.DataFrame(undervalued_stocks)
            df['할인율_숫자'] = df['할인율'].str.replace('%', '').astype(float)
            df = df.sort_values('할인율_숫자', ascending=False).head(limit)
            df = df.drop('할인율_숫자', axis=1)
            df['순위'] = range(1, len(df) + 1)
            
            return df
        else:
            return pd.DataFrame()
    
    def visualize_valuation_analysis(self, stock_code):
        """📊 내재가치 분석 시각화"""
        valuation_result = self.calculate_multiple_valuations(stock_code)
        
        if not valuation_result:
            print("❌ 시각화할 데이터가 없습니다.")
            return
        
        # 기업명 조회
        company_query = """SELECT corp_name FROM company_info WHERE stock_code = ?"""
        company_info = self.query_dart_db(company_query, (stock_code,))
        corp_name = company_info.iloc[0]['corp_name'] if not company_info.empty else stock_code
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'💰 {corp_name}({stock_code}) 내재가치 분석', fontsize=16, fontweight='bold')
        
        # 1. 내재가치 vs 현재가 비교
        intrinsic_value = valuation_result['intrinsic_value']
        current_price = valuation_result['current_price']
        target_buy_price = valuation_result['target_buy_price']
        
        values = [intrinsic_value, current_price, target_buy_price]
        labels = ['내재가치', '현재가', '목표매수가\n(50%할인)']
        colors = ['#4ECDC4', '#FF6B6B', '#45B7D1']
        
        bars = ax1.bar(labels, values, color=colors, alpha=0.7)
        ax1.set_ylabel('주가 (원)')
        ax1.set_title('내재가치 vs 현재가 비교')
        ax1.grid(axis='y', alpha=0.3)
        
        # 막대 위에 값 표시
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                    f'{value:,.0f}원', ha='center', va='bottom', fontweight='bold')
        
        # 2. 방법론별 내재가치
        methods = valuation_result['valuation_methods']
        method_values = []
        method_labels = []
        
        if methods['dcf_value'] and methods['dcf_value'] > 0:
            method_values.append(methods['dcf_value'])
            method_labels.append('DCF\n(40%)')
        if methods['per_value'] > 0:
            method_values.append(methods['per_value'])
            method_labels.append('PER\n(25%)')
        if methods['pbr_value'] > 0:
            method_values.append(methods['pbr_value'])
            method_labels.append('PBR\n(15%)')
        if methods['roe_value'] > 0:
            method_values.append(methods['roe_value'])
            method_labels.append('ROE\n(20%)')
        
        if method_values:
            ax2.bar(method_labels, method_values, color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A'], alpha=0.7)
            ax2.axhline(y=current_price, color='red', linestyle='--', label=f'현재가: {current_price:,.0f}원')
            ax2.set_ylabel('내재가치 (원)')
            ax2.set_title('방법론별 내재가치')
            ax2.legend()
            ax2.grid(axis='y', alpha=0.3)
        
        # 3. DCF 현금흐름 분석
        dcf_details = valuation_result['dcf_details']
        if dcf_details:
            cash_flows_pv = dcf_details['cash_flows_pv']
            terminal_pv = dcf_details['terminal_pv']
            
            values = [cash_flows_pv, terminal_pv]
            labels = ['10년 현금흐름\n현재가치', '터미널 밸류\n현재가치']
            colors = ['#96CEB4', '#FECA57']
            
            ax3.pie(values, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
            ax3.set_title('DCF 구성 요소')
        
        # 4. 투자 안전성 분석
        safety_metrics = ['할인율', '안전마진', '상승여력']
        safety_values = [
            dcf_details['discount_rate']*100 if dcf_details else 15,
            valuation_result['safety_margin'],
            abs(valuation_result['upside_potential'])
        ]
        
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
        bars = ax4.barh(safety_metrics, safety_values, color=colors, alpha=0.7)
        ax4.set_xlabel('비율 (%)')
        ax4.set_title('투자 안전성 지표')
        ax4.grid(axis='x', alpha=0.3)
        
        # 값 표시
        for bar, value in zip(bars, safety_values):
            width = bar.get_width()
            ax4.text(width + width*0.01, bar.get_y() + bar.get_height()/2.,
                    f'{value:.1f}%', ha='left', va='center', fontweight='bold')
        
        plt.tight_layout()
        plt.show()


def main():
    """메인 실행 함수"""
    
    print("💰 워런 버핏 스타일 내재가치 계산 시스템")
    print("=" * 80)
    print("🎯 DCF 모델과 다중 밸류에이션으로 정확한 내재가치를 계산합니다")
    print("🛡️ 50% 안전마진을 적용한 보수적 투자 전략을 제공합니다")
    print("=" * 80)
    
    try:
        calculator = IntrinsicValueCalculator()
        
        while True:
            print("\n💰 원하는 기능을 선택하세요:")
            print("1. 특정 종목 내재가치 분석")
            print("2. 저평가 종목 자동 발굴")
            print("3. 내재가치 분석 시각화")
            print("4. 포트폴리오 종목들 일괄 분석")
            print("5. 목표 매수가 계산기")
            print("0. 종료")
            
            choice = input("\n선택하세요 (0-5): ").strip()
            
            if choice == '0':
                print("👋 내재가치 계산 시스템을 종료합니다.")
                break
            
            elif choice == '1':
                stock_code = input("\n분석할 종목코드를 입력하세요 (예: 005930): ").strip()
                if stock_code:
                    calculator.create_valuation_report(stock_code)
                else:
                    print("❌ 올바른 종목코드를 입력해주세요.")
            
            elif choice == '2':
                print("\n💎 저평가 종목 발굴 옵션:")
                try:
                    min_discount = float(input("최소 할인율 (기본 20%): ").strip() or "20") / 100
                    limit = int(input("최대 결과 개수 (기본 20): ").strip() or "20")
                    
                    undervalued_df = calculator.find_undervalued_stocks(min_discount, limit)
                    
                    if not undervalued_df.empty:
                        print(f"\n💎 발견된 저평가 종목: {len(undervalued_df)}개")
                        print("=" * 100)
                        print(undervalued_df.to_string(index=False))
                        print("=" * 100)
                        
                        print(f"\n📊 저평가 종목 요약:")
                        print(f"   평균 할인율: {undervalued_df['할인율'].str.replace('%', '').astype(float).mean():.1f}%")
                        print(f"   최대 할인율: {undervalued_df['할인율'].iloc[0]}")
                        print(f"   평균 상승여력: {undervalued_df['상승여력'].str.replace('%', '').astype(float).mean():.1f}%")
                    else:
                        print("❌ 조건을 만족하는 저평가 종목을 찾지 못했습니다.")
                        print("💡 할인율 기준을 낮춰서 다시 시도해보세요.")
                        
                except ValueError:
                    print("❌ 올바른 숫자를 입력해주세요.")
            
            elif choice == '3':
                stock_code = input("\n시각화할 종목코드를 입력하세요 (예: 005930): ").strip()
                if stock_code:
                    calculator.visualize_valuation_analysis(stock_code)
                else:
                    print("❌ 올바른 종목코드를 입력해주세요.")
            
            elif choice == '4':
                print("\n📋 포트폴리오 일괄 분석:")
                stock_codes_input = input("종목코드들을 쉼표로 구분해서 입력하세요 (예: 005930,000660,035420): ").strip()
                
                if stock_codes_input:
                    stock_codes = [code.strip() for code in stock_codes_input.split(',')]
                    
                    portfolio_results = []
                    for stock_code in stock_codes:
                        try:
                            valuation = calculator.calculate_multiple_valuations(stock_code)
                            if valuation:
                                company_query = """SELECT corp_name FROM company_info WHERE stock_code = ?"""
                                company_info = calculator.query_dart_db(company_query, (stock_code,))
                                corp_name = company_info.iloc[0]['corp_name'] if not company_info.empty else stock_code
                                
                                portfolio_results.append({
                                    '종목코드': stock_code,
                                    '기업명': corp_name,
                                    '내재가치': int(valuation['intrinsic_value']),
                                    '현재가': int(valuation['current_price']),
                                    '목표매수가': int(valuation['target_buy_price']),
                                    '상승여력': f"{valuation['upside_potential']:.1f}%"
                                })
                        except:
                            continue
                    
                    if portfolio_results:
                        portfolio_df = pd.DataFrame(portfolio_results)
                        print("\n📊 포트폴리오 내재가치 분석:")
                        print("=" * 90)
                        print(portfolio_df.to_string(index=False))
                        print("=" * 90)
                    else:
                        print("❌ 분석 가능한 종목이 없습니다.")
                else:
                    print("❌ 종목코드를 입력해주세요.")
            
            elif choice == '5':
                print("\n🎯 목표 매수가 계산기:")
                stock_code = input("종목코드 입력 (예: 005930): ").strip()
                
                if stock_code:
                    try:
                        safety_margin = float(input("원하는 안전마진 % (기본 50%): ").strip() or "50") / 100
                        
                        valuation = calculator.calculate_multiple_valuations(stock_code)
                        if valuation:
                            intrinsic_value = valuation['intrinsic_value']
                            current_price = valuation['current_price']
                            custom_target = intrinsic_value * (1 - safety_margin)
                            
                            print(f"\n🎯 목표 매수가 계산 결과:")
                            print(f"   💎 내재가치: {intrinsic_value:,.0f}원")
                            print(f"   📈 현재가: {current_price:,.0f}원")
                            print(f"   🎯 목표 매수가: {custom_target:,.0f}원 ({safety_margin*100:.0f}% 안전마진)")
                            
                            if current_price <= custom_target:
                                print(f"   🚀 현재 매수 적기! ({((custom_target/current_price-1)*100):+.1f}% 여유)")
                            else:
                                print(f"   ⏳ 매수 대기 ({((current_price/custom_target-1)*100):+.1f}% 고평가)")
                        else:
                            print("❌ 내재가치 계산에 실패했습니다.")
                    except ValueError:
                        print("❌ 올바른 숫자를 입력해주세요.")
                else:
                    print("❌ 종목코드를 입력해주세요.")
            
            else:
                print("❌ 올바른 번호를 선택해주세요.")
    
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("💡 필요한 데이터가 충분히 수집되었는지 확인해주세요.")


if __name__ == "__main__":
    main()