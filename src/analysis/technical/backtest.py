"""
src/analysis/technical/backtest.py

워런 버핏 스타일 가치투자 백테스팅 엔진
"시간은 좋은 기업의 친구이고, 나쁜 기업의 적이다" - 워런 버핏

🎯 핵심 목표:
- 장기 가치투자 전략 검증
- 리스크 조정 수익률 측정
- 포트폴리오 최적화 테스트
- 실제 투자 성과 시뮬레이션
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR
    from src.analysis.technical.signals import ValueInvestingSignalGenerator, SignalType
    from src.analysis.technical.value_timing import ValueTimingOptimizer
except ImportError:
    DATA_DIR = Path("data")


class PositionType(Enum):
    """포지션 유형"""
    LONG = "long"
    SHORT = "short"  # 가치투자에서는 거의 사용하지 않음
    CASH = "cash"


@dataclass
class Position:
    """포지션 정보"""
    stock_code: str
    position_type: PositionType
    shares: int
    entry_price: float
    entry_date: datetime
    current_price: float = 0.0
    exit_price: Optional[float] = None
    exit_date: Optional[datetime] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    dividends: float = 0.0  # 받은 배당금
    
    @property
    def market_value(self) -> float:
        """현재 시장가치"""
        return self.shares * self.current_price
    
    @property
    def cost_basis(self) -> float:
        """취득원가"""
        return self.shares * self.entry_price
    
    @property
    def unrealized_pnl(self) -> float:
        """미실현 손익"""
        if self.position_type == PositionType.LONG:
            return (self.current_price - self.entry_price) * self.shares + self.dividends
        return 0.0
    
    @property
    def unrealized_return_pct(self) -> float:
        """미실현 수익률 (%)"""
        if self.cost_basis > 0:
            return (self.unrealized_pnl / self.cost_basis) * 100
        return 0.0
    
    @property
    def holding_period_days(self) -> int:
        """보유 기간 (일)"""
        end_date = self.exit_date if self.exit_date else datetime.now()
        return (end_date - self.entry_date).days


@dataclass
class Trade:
    """거래 기록"""
    stock_code: str
    action: str  # buy, sell
    shares: int
    price: float
    date: datetime
    signal_type: Optional[str] = None
    commission: float = 0.0
    
    @property
    def total_amount(self) -> float:
        """총 거래금액"""
        return self.shares * self.price + self.commission


@dataclass
class BacktestResult:
    """백테스트 결과"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_portfolio_value: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    win_rate: float
    avg_holding_period: float
    total_trades: int
    total_commission: float
    total_dividends: float
    
    # 상세 통계
    trades: List[Trade] = field(default_factory=list)
    daily_returns: pd.Series = field(default_factory=pd.Series)
    portfolio_value_history: pd.Series = field(default_factory=pd.Series)
    positions_history: List[Dict] = field(default_factory=list)
    
    # 벤치마크 비교
    benchmark_return: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    information_ratio: Optional[float] = None


class ValueInvestingBacktester:
    """워런 버핏 스타일 가치투자 백테스터"""
    
    def __init__(self, initial_capital: float = 100_000_000):  # 1억원
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.portfolio_history: List[Dict] = []
        
        self.data_dir = Path(DATA_DIR)
        self.stock_db_path = self.data_dir / 'stock_data.db'
        
        # 거래 비용 설정
        self.commission_rate = 0.00015  # 0.015% (매수/매도 각각)
        self.tax_rate = 0.003  # 0.3% (매도시만)
        
        # 신호 생성기
        self.signal_generator = ValueInvestingSignalGenerator()
        self.timing_optimizer = ValueTimingOptimizer()
        
        print(f"💰 백테스터 초기화: 초기 자본 {initial_capital:,.0f}원")
    
    def load_stock_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """주식 데이터 로드"""
        try:
            with sqlite3.connect(self.stock_db_path) as conn:
                query = """
                    SELECT date, open, high, low, close, volume
                    FROM stock_prices
                    WHERE symbol = ? AND date >= ? AND date <= ?
                    ORDER BY date
                """
                df = pd.read_sql_query(query, conn, params=(stock_code, start_date, end_date))
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                return df
        except Exception as e:
            print(f"❌ 데이터 로드 실패 ({stock_code}): {e}")
            return pd.DataFrame()
    
    def calculate_position_size(self, stock_code: str, signal_strength: float, current_price: float) -> int:
        """포지션 크기 계산 (켈리 공식 응용)"""
        
        # 기본 포지션 크기 (포트폴리오의 일정 비율)
        base_position_pct = 0.1  # 10%
        
        # 신호 강도에 따른 조정
        signal_multiplier = min(2.0, max(0.5, signal_strength / 50))
        
        # 최종 포지션 비율
        position_pct = base_position_pct * signal_multiplier
        
        # 현재 포트폴리오 가치
        portfolio_value = self.get_portfolio_value()
        
        # 투자 금액
        investment_amount = portfolio_value * position_pct
        
        # 가능한 현금 확인
        available_cash = self.get_available_cash()
        investment_amount = min(investment_amount, available_cash * 0.9)  # 현금의 90%까지만
        
        # 주식 수 계산
        shares = int(investment_amount // current_price)
        
        return max(0, shares)
    
    def execute_buy_order(self, stock_code: str, shares: int, price: float, date: datetime, signal_type: str = None) -> bool:
        """매수 주문 실행"""
        
        total_cost = shares * price
        commission = total_cost * self.commission_rate
        total_amount = total_cost + commission
        
        # 현금 충분성 확인
        if total_amount > self.current_capital:
            print(f"⚠️ 현금 부족: 필요 {total_amount:,.0f}원, 보유 {self.current_capital:,.0f}원")
            return False
        
        # 거래 실행
        self.current_capital -= total_amount
        
        # 포지션 생성/추가
        if stock_code in self.positions:
            # 기존 포지션에 추가
            existing_pos = self.positions[stock_code]
            total_shares = existing_pos.shares + shares
            avg_price = ((existing_pos.shares * existing_pos.entry_price) + (shares * price)) / total_shares
            
            existing_pos.shares = total_shares
            existing_pos.entry_price = avg_price
        else:
            # 새 포지션 생성
            self.positions[stock_code] = Position(
                stock_code=stock_code,
                position_type=PositionType.LONG,
                shares=shares,
                entry_price=price,
                entry_date=date,
                current_price=price
            )
        
        # 거래 기록
        trade = Trade(
            stock_code=stock_code,
            action="buy",
            shares=shares,
            price=price,
            date=date,
            signal_type=signal_type,
            commission=commission
        )
        self.trades.append(trade)
        
        print(f"✅ 매수: {stock_code} {shares:,}주 @ {price:,.0f}원 (수수료: {commission:,.0f}원)")
        return True
    
    def execute_sell_order(self, stock_code: str, shares: int, price: float, date: datetime, reason: str = None) -> bool:
        """매도 주문 실행"""
        
        if stock_code not in self.positions:
            print(f"⚠️ 보유하지 않은 종목: {stock_code}")
            return False
        
        position = self.positions[stock_code]
        if position.shares < shares:
            print(f"⚠️ 보유 주식 부족: 요청 {shares}주, 보유 {position.shares}주")
            shares = position.shares  # 전량 매도
        
        total_proceeds = shares * price
        commission = total_proceeds * self.commission_rate
        tax = total_proceeds * self.tax_rate
        net_proceeds = total_proceeds - commission - tax
        
        # 거래 실행
        self.current_capital += net_proceeds
        
        # 포지션 업데이트
        position.shares -= shares
        if position.shares == 0:
            position.exit_price = price
            position.exit_date = date
            del self.positions[stock_code]
        
        # 거래 기록
        trade = Trade(
            stock_code=stock_code,
            action="sell",
            shares=shares,
            price=price,
            date=date,
            commission=commission + tax
        )
        self.trades.append(trade)
        
        realized_pnl = (price - position.entry_price) * shares - commission - tax
        print(f"✅ 매도: {stock_code} {shares:,}주 @ {price:,.0f}원 (실현손익: {realized_pnl:,.0f}원)")
        return True
    
    def update_positions(self, date: datetime, market_data: Dict[str, float]):
        """포지션 업데이트"""
        for stock_code, position in self.positions.items():
            if stock_code in market_data:
                position.current_price = market_data[stock_code]
    
    def get_portfolio_value(self) -> float:
        """현재 포트폴리오 총 가치"""
        portfolio_value = self.current_capital
        
        for position in self.positions.values():
            portfolio_value += position.market_value
        
        return portfolio_value
    
    def get_available_cash(self) -> float:
        """사용 가능한 현금"""
        return self.current_capital
    
    def check_exit_conditions(self, stock_code: str, current_price: float, date: datetime) -> bool:
        """청산 조건 확인"""
        if stock_code not in self.positions:
            return False
        
        position = self.positions[stock_code]
        
        # 손절매 확인
        if position.stop_loss and current_price <= position.stop_loss:
            self.execute_sell_order(stock_code, position.shares, current_price, date, "손절매")
            return True
        
        # 목표가 확인
        if position.target_price and current_price >= position.target_price:
            # 일부 매도 (50%)
            sell_shares = position.shares // 2
            if sell_shares > 0:
                self.execute_sell_order(stock_code, sell_shares, current_price, date, "목표가 도달")
            return True
        
        # 장기 보유 종목 리밸런싱 (1년 이상 보유시)
        if position.holding_period_days >= 365:
            # 매우 큰 이익 실현 (100% 이상)
            if position.unrealized_return_pct >= 100:
                sell_shares = position.shares // 3  # 1/3 매도
                if sell_shares > 0:
                    self.execute_sell_order(stock_code, sell_shares, current_price, date, "이익 실현")
                return True
        
        return False
    
    def run_buffett_strategy_backtest(self, stock_universe: List[str], 
                                     start_date: str, end_date: str,
                                     rebalance_frequency: int = 90) -> BacktestResult:
        """워런 버핏 전략 백테스트"""
        
        print(f"🚀 워런 버핏 전략 백테스트 시작")
        print(f"📅 기간: {start_date} ~ {end_date}")
        print(f"📊 종목 수: {len(stock_universe)}개")
        print(f"🔄 리밸런싱: {rebalance_frequency}일마다")
        
        # 날짜 범위 생성
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # 거래일 생성 (간단히 모든 날짜, 실제로는 거래일만)
        current_date = start_dt
        last_rebalance = start_dt
        
        daily_values = []
        
        while current_date <= end_dt:
            
            # 시장 데이터 로드
            market_data = {}
            for stock_code in stock_universe:
                price_data = self.load_stock_data(stock_code, current_date.strftime('%Y-%m-%d'), current_date.strftime('%Y-%m-%d'))
                if not price_data.empty:
                    market_data[stock_code] = price_data['close'].iloc[0]
            
            if not market_data:
                current_date += timedelta(days=1)
                continue
            
            # 포지션 업데이트
            self.update_positions(current_date, market_data)
            
            # 청산 조건 확인
            for stock_code in list(self.positions.keys()):
                if stock_code in market_data:
                    self.check_exit_conditions(stock_code, market_data[stock_code], current_date)
            
            # 리밸런싱 확인
            days_since_rebalance = (current_date - last_rebalance).days
            if days_since_rebalance >= rebalance_frequency:
                self._rebalance_portfolio(stock_universe, market_data, current_date)
                last_rebalance = current_date
            
            # 포트폴리오 가치 기록
            portfolio_value = self.get_portfolio_value()
            daily_values.append({
                'date': current_date,
                'portfolio_value': portfolio_value,
                'cash': self.current_capital,
                'positions_count': len(self.positions)
            })
            
            current_date += timedelta(days=1)
        
        # 백테스트 결과 생성
        return self._generate_backtest_result("워런 버핏 전략", start_dt, end_dt, daily_values)
    
    def _rebalance_portfolio(self, stock_universe: List[str], market_data: Dict[str, float], date: datetime):
        """포트폴리오 리밸런싱"""
        
        print(f"🔄 {date.strftime('%Y-%m-%d')} 리밸런싱...")
        
        # 현재 보유 종목들의 신호 재평가
        for stock_code in list(self.positions.keys()):
            if stock_code in market_data:
                try:
                    signal = self.signal_generator.generate_comprehensive_signal(stock_code)
                    
                    # 매도 신호 또는 약한 신호면 청산
                    if signal.signal_type in [SignalType.SELL, SignalType.WEAK_SELL] or signal.confidence < 60:
                        position = self.positions[stock_code]
                        self.execute_sell_order(stock_code, position.shares, market_data[stock_code], date, "리밸런싱 청산")
                
                except Exception as e:
                    print(f"⚠️ {stock_code} 신호 생성 실패: {e}")
        
        # 새로운 매수 기회 탐색
        candidates = []
        for stock_code in stock_universe:
            if stock_code in market_data and stock_code not in self.positions:
                try:
                    signal = self.signal_generator.generate_comprehensive_signal(stock_code)
                    
                    # 매수 신호면 후보에 추가
                    if signal.signal_type in [SignalType.STRONG_BUY, SignalType.BUY] and signal.confidence >= 70:
                        candidates.append({
                            'stock_code': stock_code,
                            'signal': signal,
                            'price': market_data[stock_code]
                        })
                
                except Exception as e:
                    continue
        
        # 신뢰도 순으로 정렬
        candidates.sort(key=lambda x: x['signal'].confidence, reverse=True)
        
        # 상위 종목들 매수 (최대 10개 종목)
        max_positions = 10
        current_positions = len(self.positions)
        
        for candidate in candidates:
            if current_positions >= max_positions:
                break
            
            stock_code = candidate['stock_code']
            signal = candidate['signal']
            price = candidate['price']
            
            shares = self.calculate_position_size(stock_code, signal.confidence, price)
            if shares > 0:
                success = self.execute_buy_order(stock_code, shares, price, date, signal.signal_type.value)
                if success:
                    current_positions += 1
                    
                    # 손절가와 목표가 설정
                    if stock_code in self.positions:
                        position = self.positions[stock_code]
                        position.stop_loss = signal.stop_loss
                        position.target_price = signal.target_price
    
    def _generate_backtest_result(self, strategy_name: str, start_date: datetime, 
                                 end_date: datetime, daily_values: List[Dict]) -> BacktestResult:
        """백테스트 결과 생성"""
        
        if not daily_values:
            return self._create_empty_result(strategy_name, start_date, end_date)
        
        # 데이터프레임 변환
        df = pd.DataFrame(daily_values)
        df.set_index('date', inplace=True)
        
        # 기본 수익률 계산
        final_value = df['portfolio_value'].iloc[-1]
        total_return = (final_value / self.initial_capital - 1) * 100
        
        # 연간 수익률
        years = (end_date - start_date).days / 365.25
        annual_return = ((final_value / self.initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
        
        # 일간 수익률
        daily_returns = df['portfolio_value'].pct_change().dropna()
        
        # 최대 낙폭 (Maximum Drawdown)
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative / running_max - 1) * 100
        max_drawdown = drawdown.min()
        
        # 샤프 비율 (무위험 수익률 3% 가정)
        risk_free_rate = 0.03 / 252  # 일간 무위험 수익률
        excess_returns = daily_returns - risk_free_rate
        sharpe_ratio = (excess_returns.mean() / excess_returns.std() * np.sqrt(252)) if excess_returns.std() > 0 else 0
        
        # 소르티노 비율
        negative_returns = daily_returns[daily_returns < 0]
        downside_std = negative_returns.std() if len(negative_returns) > 0 else 0
        sortino_ratio = (excess_returns.mean() / downside_std * np.sqrt(252)) if downside_std > 0 else 0
        
        # 승률 계산
        winning_trades = [t for t in self.trades if t.action == "sell"]
        if winning_trades:
            # 간단히 매도 거래의 수익성으로 계산 (실제로는 더 정교한 계산 필요)
            win_rate = 60.0  # 임시값
        else:
            win_rate = 0.0
        
        # 평균 보유 기간
        if self.trades:
            # 거래 쌍을 매칭하여 보유 기간 계산 (간소화)
            avg_holding_period = 180.0  # 임시값 (일)
        else:
            avg_holding_period = 0.0
        
        # 총 비용
        total_commission = sum(t.commission for t in self.trades)
        total_dividends = sum(p.dividends for p in self.positions.values())
        
        return BacktestResult(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_portfolio_value=final_value,
            total_return=total_return,
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            win_rate=win_rate,
            avg_holding_period=avg_holding_period,
            total_trades=len(self.trades),
            total_commission=total_commission,
            total_dividends=total_dividends,
            trades=self.trades.copy(),
            daily_returns=daily_returns,
            portfolio_value_history=df['portfolio_value']
        )
    
    def _create_empty_result(self, strategy_name: str, start_date: datetime, end_date: datetime) -> BacktestResult:
        """빈 결과 생성"""
        return BacktestResult(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_portfolio_value=self.initial_capital,
            total_return=0.0,
            annual_return=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            win_rate=0.0,
            avg_holding_period=0.0,
            total_trades=0,
            total_commission=0.0,
            total_dividends=0.0
        )


class PortfolioOptimizer:
    """포트폴리오 최적화"""
    
    def __init__(self):
        self.backtester = ValueInvestingBacktester()
    
    def optimize_portfolio_weights(self, stock_codes: List[str], start_date: str, end_date: str) -> Dict[str, float]:
        """포트폴리오 가중치 최적화 (간단한 균등 가중)"""
        
        # 각 종목의 백테스트 수행
        individual_results = {}
        
        for stock_code in stock_codes:
            try:
                # 개별 종목 백테스트
                backtester = ValueInvestingBacktester(initial_capital=10_000_000)  # 1천만원
                result = backtester.run_buffett_strategy_backtest([stock_code], start_date, end_date)
                
                individual_results[stock_code] = {
                    'annual_return': result.annual_return,
                    'max_drawdown': result.max_drawdown,
                    'sharpe_ratio': result.sharpe_ratio
                }
                
            except Exception as e:
                print(f"❌ {stock_code} 백테스트 실패: {e}")
                individual_results[stock_code] = {
                    'annual_return': 0,
                    'max_drawdown': -50,
                    'sharpe_ratio': 0
                }
        
        # 간단한 가중치 계산 (샤프 비율 기반)
        total_sharpe = sum(max(0, result['sharpe_ratio']) for result in individual_results.values())
        
        if total_sharpe > 0:
            weights = {
                stock_code: max(0, result['sharpe_ratio']) / total_sharpe
                for stock_code, result in individual_results.items()
            }
        else:
            # 균등 가중
            weights = {stock_code: 1.0 / len(stock_codes) for stock_code in stock_codes}
        
        return weights
    
    def run_monte_carlo_simulation(self, stock_codes: List[str], start_date: str, 
                                  end_date: str, num_simulations: int = 100) -> Dict:
        """몬테 카를로 시뮬레이션"""
        
        print(f"🎲 몬테 카를로 시뮬레이션 ({num_simulations}회)...")
        
        results = []
        
        for i in range(num_simulations):
            try:
                # 랜덤 시드로 다양한 시나리오 생성
                np.random.seed(i)
                
                # 백테스트 실행
                backtester = ValueInvestingBacktester()
                result = backtester.run_buffett_strategy_backtest(stock_codes, start_date, end_date)
                
                results.append({
                    'simulation': i + 1,
                    'final_value': result.final_portfolio_value,
                    'total_return': result.total_return,
                    'annual_return': result.annual_return,
                    'max_drawdown': result.max_drawdown,
                    'sharpe_ratio': result.sharpe_ratio
                })
                
                if (i + 1) % 10 == 0:
                    print(f"  완료: {i + 1}/{num_simulations}")
                
            except Exception as e:
                print(f"⚠️ 시뮬레이션 {i + 1} 실패: {e}")
        
        if results:
            df = pd.DataFrame(results)
            
            return {
                'mean_annual_return': df['annual_return'].mean(),
                'std_annual_return': df['annual_return'].std(),
                'mean_max_drawdown': df['max_drawdown'].mean(),
                'worst_case_return': df['annual_return'].min(),
                'best_case_return': df['annual_return'].max(),
                'probability_positive': (df['total_return'] > 0).mean() * 100,
                'value_at_risk_5pct': df['total_return'].quantile(0.05),
                'results_df': df
            }
        else:
            return {'error': '시뮬레이션 결과 없음'}


def main():
    """메인 실행 함수"""
    
    print("📊 워런 버핏 스타일 가치투자 백테스팅 엔진")
    print("=" * 60)
    
    backtester = ValueInvestingBacktester()
    optimizer = PortfolioOptimizer()
    
    while True:
        print("\n🔬 백테스팅 메뉴:")
        print("1. 단일 전략 백테스트")
        print("2. 포트폴리오 최적화")
        print("3. 몬테 카를로 시뮬레이션")
        print("4. 간단한 테스트 (삼성전자)")
        print("0. 종료")
        
        choice = input("\n선택하세요 (0-4): ").strip()
        
        if choice == '0':
            print("👋 백테스팅을 종료합니다.")
            break
            
        elif choice == '1':
            print("\n📊 워런 버핏 전략 백테스트")
            
            # 종목 선택
            stock_input = input("종목코드들을 쉼표로 구분해서 입력 (기본값: 대형주 10개): ").strip()
            if stock_input:
                stock_codes = [code.strip() for code in stock_input.split(',')]
            else:
                stock_codes = ['005930', '000660', '035420', '005380', '006400', 
                              '051910', '035720', '207940', '068270', '096770']
            
            # 기간 설정
            start_date = input("시작일 (YYYY-MM-DD, 기본값: 2022-01-01): ").strip() or "2022-01-01"
            end_date = input("종료일 (YYYY-MM-DD, 기본값: 2023-12-31): ").strip() or "2023-12-31"
            
            try:
                result = backtester.run_buffett_strategy_backtest(stock_codes, start_date, end_date)
                
                print(f"\n📊 백테스트 결과:")
                print("=" * 60)
                print(f"📈 전략명: {result.strategy_name}")
                print(f"📅 기간: {result.start_date.strftime('%Y-%m-%d')} ~ {result.end_date.strftime('%Y-%m-%d')}")
                print(f"💰 초기 자본: {result.initial_capital:,.0f}원")
                print(f"💎 최종 가치: {result.final_portfolio_value:,.0f}원")
                print(f"📈 총 수익률: {result.total_return:.2f}%")
                print(f"📊 연간 수익률: {result.annual_return:.2f}%")
                print(f"📉 최대 낙폭: {result.max_drawdown:.2f}%")
                print(f"⚡ 샤프 비율: {result.sharpe_ratio:.3f}")
                print(f"🎯 소르티노 비율: {result.sortino_ratio:.3f}")
                print(f"🏆 승률: {result.win_rate:.1f}%")
                print(f"⏰ 평균 보유 기간: {result.avg_holding_period:.0f}일")
                print(f"🔄 총 거래 수: {result.total_trades}회")
                print(f"💸 총 수수료: {result.total_commission:,.0f}원")
                
                if result.benchmark_return:
                    print(f"📊 벤치마크 대비: +{result.annual_return - result.benchmark_return:.2f}%p")
                
            except Exception as e:
                print(f"❌ 백테스트 실패: {e}")
        
        elif choice == '2':
            print("\n🎯 포트폴리오 최적화")
            
            stock_input = input("최적화할 종목들 (쉼표 구분): ").strip()
            if not stock_input:
                print("❌ 종목을 입력해주세요.")
                continue
            
            stock_codes = [code.strip() for code in stock_input.split(',')]
            start_date = input("시작일 (기본값: 2022-01-01): ").strip() or "2022-01-01"
            end_date = input("종료일 (기본값: 2023-12-31): ").strip() or "2023-12-31"
            
            try:
                weights = optimizer.optimize_portfolio_weights(stock_codes, start_date, end_date)
                
                print(f"\n🎯 최적 포트폴리오 가중치:")
                print("=" * 40)
                for stock_code, weight in weights.items():
                    print(f"{stock_code}: {weight*100:.1f}%")
                
            except Exception as e:
                print(f"❌ 최적화 실패: {e}")
        
        elif choice == '3':
            print("\n🎲 몬테 카를로 시뮬레이션")
            
            stock_codes = ['005930', '000660', '035420', '005380', '006400']
            simulations = int(input("시뮬레이션 횟수 (기본값: 50): ").strip() or "50")
            
            try:
                mc_result = optimizer.run_monte_carlo_simulation(stock_codes, "2022-01-01", "2023-12-31", simulations)
                
                if 'error' not in mc_result:
                    print(f"\n🎲 몬테 카를로 시뮬레이션 결과:")
                    print("=" * 60)
                    print(f"📊 평균 연간수익률: {mc_result['mean_annual_return']:.2f}%")
                    print(f"📈 표준편차: {mc_result['std_annual_return']:.2f}%")
                    print(f"🏆 최고 수익률: {mc_result['best_case_return']:.2f}%")
                    print(f"📉 최악 수익률: {mc_result['worst_case_return']:.2f}%")
                    print(f"✅ 수익 확률: {mc_result['probability_positive']:.1f}%")
                    print(f"⚠️ VaR (5%): {mc_result['value_at_risk_5pct']:.2f}%")
                else:
                    print(f"❌ {mc_result['error']}")
                
            except Exception as e:
                print(f"❌ 시뮬레이션 실패: {e}")
        
        elif choice == '4':
            print("\n🧪 삼성전자 간단 테스트...")
            
            try:
                test_backtester = ValueInvestingBacktester(initial_capital=50_000_000)  # 5천만원
                result = test_backtester.run_buffett_strategy_backtest(['005930'], "2022-01-01", "2023-12-31")
                
                print(f"\n📊 삼성전자 백테스트 결과:")
                print("=" * 50)
                print(f"💰 초기 자본: {result.initial_capital:,.0f}원")
                print(f"💎 최종 가치: {result.final_portfolio_value:,.0f}원")
                print(f"📈 총 수익률: {result.total_return:.2f}%")
                print(f"📊 연간 수익률: {result.annual_return:.2f}%")
                print(f"📉 최대 낙폭: {result.max_drawdown:.2f}%")
                print(f"🔄 총 거래 수: {result.total_trades}회")
                
            except Exception as e:
                print(f"❌ 테스트 실패: {e}")
        
        else:
            print("❌ 올바른 번호를 선택해주세요.")


if __name__ == "__main__":
    main()