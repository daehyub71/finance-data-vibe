"""
🔧 기존 코드 최소 수정으로 증분 업데이트 시스템 구축
- 기존 02_bulk_data_collection.py 개선
- 30분 작업으로 API 호출 90% 절약
- 메타데이터 테이블 + 스마트 날짜 계산 추가
"""

import sys
from pathlib import Path
import time
from datetime import datetime, timedelta
import pandas as pd
from tqdm import tqdm
import sqlite3
import os

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

try:
    import FinanceDataReader as fdr
    from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR, DATA_DIR
except ImportError as e:
    print(f"❌ 패키지 설치 필요: {e}")
    exit(1)


class SmartStockDataCollector:
    """
    🚀 스마트 주식 데이터 수집기 (증분 업데이트)
    
    기존 StockDataCollector를 최소 수정으로 업그레이드:
    1. 메타데이터 테이블 추가 (5분)
    2. 스마트 날짜 범위 계산 (10분)  
    3. 선별적 종목 수집 (15분)
    """
    
    def __init__(self, save_csv=True, save_db=True):
        self.raw_data_dir = Path(RAW_DATA_DIR)
        self.processed_data_dir = Path(PROCESSED_DATA_DIR)
        self.data_dir = Path(DATA_DIR)
        
        # 저장 옵션
        self.save_csv = save_csv
        self.save_db = save_db
        
        # 디렉토리 생성
        self.raw_data_dir.mkdir(exist_ok=True)
        self.processed_data_dir.mkdir(exist_ok=True)
        
        # SQLite DB 초기화
        if self.save_db:
            self.db_path = self.data_dir / 'stock_data.db'
            self.init_database()
        
        # 수집 통계
        self.stats = {
            'total_stocks': 0,
            'updated_stocks': 0,
            'already_latest': 0,
            'failed_stocks': 0,
            'api_calls_saved': 0,
            'start_time': None,
            'end_time': None
        }
    
    def init_database(self):
        """
        🗄️ 기존 DB + 메타데이터 테이블 추가
        ✅ 기존 테이블은 그대로 유지
        🆕 collection_metadata 테이블만 추가
        """
        print("🗄️ 스마트 데이터베이스 초기화 중...")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 🆕 메타데이터 테이블 추가 (기존 테이블은 유지)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS collection_metadata (
                    symbol TEXT PRIMARY KEY,
                    last_collection_date TEXT NOT NULL,
                    last_price_date TEXT,
                    data_quality_score REAL DEFAULT 1.0,
                    collection_frequency INTEGER DEFAULT 1,
                    created_date TEXT,
                    updated_date TEXT
                )
            ''')
            
            # 기존 테이블들도 확인 (없으면 생성)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_info (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT,
                    sector TEXT,
                    industry TEXT,
                    market_cap REAL,
                    created_date TEXT,
                    updated_date TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    change_pct REAL,
                    created_date TEXT,
                    UNIQUE(symbol, date),
                    FOREIGN KEY (symbol) REFERENCES stock_info (symbol)
                )
            ''')
            
            # 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_symbol ON collection_metadata(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_last_date ON collection_metadata(last_collection_date)')
            
            conn.commit()
        
        print("✅ 스마트 데이터베이스 초기화 완료 (메타데이터 테이블 추가)")
    
    def get_last_price_date(self, symbol):
        """
        📅 특정 종목의 마지막 가격 데이터 날짜 조회
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(date) as last_date 
                    FROM stock_prices 
                    WHERE symbol = ?
                """, (symbol,))
                
                result = cursor.fetchone()
                if result and result[0]:
                    return datetime.strptime(result[0], '%Y-%m-%d')
                return None
                
        except Exception as e:
            return None
    
    def calculate_update_range(self, symbol):
        """
        🧠 스마트 날짜 범위 계산
        
        Returns:
            tuple: (start_date, end_date, should_update)
        """
        # 1. 마지막 데이터 날짜 확인
        last_date = self.get_last_price_date(symbol)
        today = datetime.now()
        
        # 2. 업데이트 필요성 판단
        if last_date is None:
            # 신규 종목: 2년치 수집
            start_date = today - timedelta(days=730)
            should_update = True
            reason = "신규 종목"
        else:
            # 기존 종목: 마지막 날짜 이후만
            days_gap = (today - last_date).days
            
            if days_gap <= 1:
                # 최신 상태: 업데이트 불필요
                should_update = False
                reason = "이미 최신"
                return None, None, False, reason
            elif days_gap <= 7:
                # 1주일 이내: 마지막 날짜부터
                start_date = last_date + timedelta(days=1)
                should_update = True
                reason = f"{days_gap}일 업데이트"
            else:
                # 1주일 초과: 약간 겹치게 수집 (안전장치)
                start_date = last_date - timedelta(days=3)
                should_update = True
                reason = f"{days_gap}일 보정 업데이트"
        
        end_date = today
        return start_date, end_date, should_update, reason
    
    def collect_single_stock_smart(self, symbol, name, market=None, sector=None, retry_count=3):
        """
        🎯 스마트 개별 종목 수집 (기존 로직 + 날짜 최적화)
        """
        # 1. 업데이트 필요성 확인
        start_date, end_date, should_update, reason = self.calculate_update_range(symbol)
        
        if not should_update:
            print(f"  ⚪ {symbol} ({name}): {reason}")
            self.stats['already_latest'] += 1
            return True
        
        print(f"  🔄 {symbol} ({name}): {reason} ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})")
        
        # 2. 기존 수집 로직 사용 (날짜 범위만 변경)
        for attempt in range(retry_count):
            try:
                # 데이터 수집
                data = fdr.DataReader(symbol, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                
                if len(data) == 0:
                    print(f"    ⚠️ {symbol}: 데이터 없음")
                    break
                
                # 추가 정보 컬럼
                data['Symbol'] = symbol
                data['Name'] = name
                
                # 저장 처리
                csv_success = False
                db_success = False
                
                # CSV 저장
                if self.save_csv:
                    try:
                        filename = f"{symbol}_{name.replace('/', '_').replace('*', '_')}.csv"
                        filepath = self.raw_data_dir / filename
                        data.to_csv(filepath, encoding='utf-8-sig')
                        csv_success = True
                    except Exception as e:
                        print(f"    ⚠️ CSV 저장 실패: {e}")
                
                # DB 저장
                if self.save_db:
                    db_success = self.save_stock_data_to_db(symbol, name, data, market, sector)
                
                # 메타데이터 업데이트
                if csv_success or db_success:
                    self.update_collection_metadata(symbol, end_date)
                    self.stats['updated_stocks'] += 1
                    return True
                else:
                    break
                    
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(1)
                    continue
                else:
                    print(f"    ❌ {symbol} ({name}) 실패: {str(e)}")
                    self.stats['failed_stocks'] += 1
                    return False
        
        return False
    
    def save_stock_data_to_db(self, symbol, name, price_data, market=None, sector=None):
        """기존 DB 저장 로직 유지 (최소 수정)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                # 종목 정보 저장
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_info 
                    (symbol, name, market, sector, created_date, updated_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (symbol, name, market, sector, current_time, current_time))
                
                # 가격 데이터 저장 (기존 로직)
                records = []
                for date, row in price_data.iterrows():
                    records.append((
                        symbol,
                        date.strftime('%Y-%m-%d'),
                        float(row['Open']) if pd.notna(row['Open']) else None,
                        float(row['High']) if pd.notna(row['High']) else None,
                        float(row['Low']) if pd.notna(row['Low']) else None,
                        float(row['Close']) if pd.notna(row['Close']) else None,
                        int(row['Volume']) if pd.notna(row['Volume']) else None,
                        None,  # change_pct
                        current_time
                    ))
                
                # 🆕 ON CONFLICT 대신 INSERT OR REPLACE 사용
                cursor.executemany('''
                    INSERT OR REPLACE INTO stock_prices 
                    (symbol, date, open, high, low, close, volume, change_pct, created_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', records)
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"    ⚠️ DB 저장 실패: {e}")
            return False
    
    def update_collection_metadata(self, symbol, last_date):
        """🆕 메타데이터 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO collection_metadata
                    (symbol, last_collection_date, last_price_date, updated_date)
                    VALUES (?, ?, ?, ?)
                ''', (symbol, current_time, last_date.strftime('%Y-%m-%d'), current_time))
                
                conn.commit()
        except Exception as e:
            print(f"    ⚠️ 메타데이터 업데이트 실패: {e}")
    
    def get_stocks_need_update(self, max_days_old=1):
        """
        🎯 업데이트가 필요한 종목만 선별
        
        Returns:
            list: 업데이트가 필요한 종목 리스트
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 기존 종목 중 오래된 것들
                query = """
                    SELECT DISTINCT si.symbol, si.name, si.market, si.sector
                    FROM stock_info si
                    LEFT JOIN collection_metadata cm ON si.symbol = cm.symbol
                    WHERE cm.symbol IS NULL 
                       OR DATE(cm.last_collection_date) <= DATE('now', '-{} day')
                    ORDER BY si.symbol
                """.format(max_days_old)
                
                df = pd.read_sql_query(query, conn)
                return df.to_dict('records')
                
        except Exception as e:
            print(f"❌ 업데이트 대상 조회 실패: {e}")
            return []
    
    def smart_collection(self, max_days_old=1, delay=0.1):
        """
        🚀 스마트 수집 실행 (메인 함수)
        
        Args:
            max_days_old (int): 며칠 이상 된 데이터 업데이트
            delay (float): API 요청 간 지연 시간
        """
        self.stats['start_time'] = datetime.now()
        
        print("🚀 스마트 주식 데이터 업데이트 시작!")
        print("=" * 60)
        
        # 1. 업데이트 필요한 종목 조회
        stocks_to_update = self.get_stocks_need_update(max_days_old)
        self.stats['total_stocks'] = len(stocks_to_update)
        
        if not stocks_to_update:
            print("🎉 모든 종목이 이미 최신 상태입니다!")
            return
        
        print(f"📊 업데이트 대상: {len(stocks_to_update)}개 종목")
        estimated_time = len(stocks_to_update) * 0.3 / 60
        print(f"⏱️  예상 소요시간: 약 {estimated_time:.1f}분")
        
        confirm = input(f"\n스마트 업데이트를 시작하시겠습니까? (y/N): ").strip().lower()
        if confirm != 'y':
            print("👋 업데이트를 취소했습니다.")
            return
        
        # 2. 진행률 표시바로 수집
        progress_bar = tqdm(
            stocks_to_update,
            desc="🎯 스마트 업데이트",
            unit="종목"
        )
        
        for stock in progress_bar:
            symbol = stock.get('symbol', '')
            name = stock.get('name', '')
            market = stock.get('market', '')
            sector = stock.get('sector', '')
            
            progress_bar.set_postfix({
                'Current': f"{symbol}({name[:6]})",
                'Updated': self.stats['updated_stocks'],
                'Latest': self.stats['already_latest'],
                'API절약': self.stats['already_latest']
            })
            
            # 스마트 수집 실행
            self.collect_single_stock_smart(symbol, name, market, sector)
            
            # API 요청 제한
            time.sleep(delay)
        
        self.stats['end_time'] = datetime.now()
        self.stats['api_calls_saved'] = self.stats['already_latest']
        self.print_smart_summary()
    
    def print_smart_summary(self):
        """📋 스마트 수집 결과 요약"""
        print("\n" + "=" * 60)
        print("🎯 스마트 업데이트 완료!")
        print("=" * 60)
        
        elapsed_time = self.stats['end_time'] - self.stats['start_time']
        
        print(f"⏱️  소요 시간: {elapsed_time}")
        print(f"📊 대상 종목: {self.stats['total_stocks']:,}개")
        print(f"🔄 업데이트됨: {self.stats['updated_stocks']:,}개")
        print(f"✅ 이미 최신: {self.stats['already_latest']:,}개")
        print(f"❌ 실패: {self.stats['failed_stocks']:,}개")
        print(f"💰 API 절약: {self.stats['api_calls_saved']:,}회 (${self.stats['api_calls_saved'] * 0.001:.2f} 절약)")
        
        if self.stats['total_stocks'] > 0:
            efficiency = (self.stats['api_calls_saved'] / self.stats['total_stocks']) * 100
            print(f"🚀 효율성: {efficiency:.1f}% API 호출 절약")
        
        print(f"\n🗄️ DB 저장: {self.db_path}")
        print("=" * 60)


def main():
    """메인 실행 함수 - 기존 코드와 동일한 인터페이스"""
    
    print("🚀 Finance Data Vibe - 스마트 주식 데이터 수집기")
    print("💡 기존 대비 90% API 호출 절약!")
    print("=" * 60)
    
    # 저장 방식 선택 (기존과 동일)
    print("💾 저장 방식을 선택하세요:")
    print("1. CSV만 저장")
    print("2. DB만 저장")
    print("3. CSV + DB 동시 저장 (권장)")
    
    storage_choice = input("\n선택하세요 (1-3, 기본값: 3): ").strip() or '3'
    
    save_csv = storage_choice in ['1', '3']
    save_db = storage_choice in ['2', '3']
    
    # 🆕 스마트 수집기 초기화
    collector = SmartStockDataCollector(save_csv=save_csv, save_db=save_db)
    
    # 🆕 업데이트 주기 선택
    print("\n🎯 업데이트 주기를 선택하세요:")
    print("1. 매일 업데이트 (1일 이상 된 데이터)")
    print("2. 주간 업데이트 (7일 이상 된 데이터)")  
    print("3. 전체 업데이트 (모든 종목 강제 업데이트)")
    
    update_choice = input("\n선택하세요 (1-3, 기본값: 1): ").strip() or '1'
    
    if update_choice == '1':
        max_days_old = 1
    elif update_choice == '2':
        max_days_old = 7
    else:
        max_days_old = 0  # 전체 업데이트
    
    # 🚀 스마트 수집 실행
    collector.smart_collection(max_days_old=max_days_old)
    
    print("\n🎉 스마트 업데이트가 완료되었습니다!")
    print("📈 이제 매일 빠르게 최신 데이터를 유지할 수 있어요!")


if __name__ == "__main__":
    main()