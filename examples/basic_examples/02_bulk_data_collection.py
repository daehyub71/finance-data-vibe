"""
📊 전 종목 시세 데이터 수집 시스템

이 모듈은 한국 주식 시장의 모든 종목 데이터를 체계적으로 수집하고 저장합니다.

학습 내용:
1. 종목 코드 리스트 확보 방법
2. 대량 데이터 수집 최적화
3. 에러 처리 및 재시도 로직
4. 진행상황 모니터링
5. 데이터 저장 및 관리 체계

🎯 목표: 분석을 위한 완전한 데이터베이스 구축
"""

import sys
from pathlib import Path
import time
from datetime import datetime, timedelta
import pandas as pd
from tqdm import tqdm
import json
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


class StockDataCollector:
    """
    주식 데이터 대량 수집기 (CSV + DB 동시 저장)
    
    이 클래스는 효율적이고 안전한 대량 데이터 수집을 위해 설계되었습니다.
    CSV와 SQLite DB에 동시 저장하여 각각의 장점을 활용합니다.
    
    📊 CSV 장점: 호환성, 가독성, 백업 용이
    🗄️  DB 장점: 빠른 쿼리, 인덱싱, 대용량 처리
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
            'success_count': 0,
            'fail_count': 0,
            'failed_stocks': [],
            'start_time': None,
            'end_time': None,
            'csv_saved': 0,
            'db_saved': 0
        }
    
    def init_database(self):
        """
        🗄️ SQLite 데이터베이스 초기화
        
        테이블 구조:
        1. stock_info: 종목 기본 정보
        2. stock_prices: 일별 가격 데이터
        3. collection_log: 수집 이력
        """
        print("🗄️ 데이터베이스 초기화 중...")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 종목 정보 테이블
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
            
            # 주가 데이터 테이블
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
            
            # 수집 이력 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS collection_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    collection_date TEXT,
                    status TEXT,
                    error_message TEXT,
                    records_count INTEGER
                )
            ''')
            
            # 인덱스 생성 (쿼리 성능 향상)
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol ON stock_prices(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_prices_date ON stock_prices(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol_date ON stock_prices(symbol, date)')
            
            conn.commit()
        
        print("✅ 데이터베이스 초기화 완료")
    
    def save_stock_info_to_db(self, symbol, name, market=None, sector=None, industry=None, market_cap=None):
        """종목 기본 정보를 DB에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_info 
                    (symbol, name, market, sector, industry, market_cap, created_date, updated_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (symbol, name, market, sector, industry, market_cap, current_time, current_time))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"  ⚠️ 종목 정보 DB 저장 실패: {e}")
            return False
    
    def save_price_data_to_db(self, symbol, price_data):
        """주가 데이터를 DB에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                current_time = datetime.now().isoformat()
                
                # 데이터 준비
                records = []
                for date, row in price_data.iterrows():
                    # 전일 대비 변화율 계산
                    change_pct = None
                    if len(records) > 0:
                        prev_close = records[-1][6]  # 이전 종가
                        if prev_close > 0:
                            change_pct = ((row['Close'] - prev_close) / prev_close) * 100
                    
                    records.append((
                        symbol,
                        date.strftime('%Y-%m-%d'),
                        float(row['Open']) if pd.notna(row['Open']) else None,
                        float(row['High']) if pd.notna(row['High']) else None,
                        float(row['Low']) if pd.notna(row['Low']) else None,
                        float(row['Close']) if pd.notna(row['Close']) else None,
                        int(row['Volume']) if pd.notna(row['Volume']) else None,
                        change_pct,
                        current_time
                    ))
                
                # 배치 삽입 (기존 데이터는 무시)
                cursor = conn.cursor()
                cursor.executemany('''
                    INSERT OR IGNORE INTO stock_prices 
                    (symbol, date, open, high, low, close, volume, change_pct, created_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', records)
                
                # 수집 이력 저장
                cursor.execute('''
                    INSERT INTO collection_log (symbol, collection_date, status, records_count)
                    VALUES (?, ?, ?, ?)
                ''', (symbol, current_time, 'SUCCESS', len(records)))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"  ⚠️ 주가 데이터 DB 저장 실패: {e}")
            
            # 실패 로그 저장
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO collection_log (symbol, collection_date, status, error_message)
                        VALUES (?, ?, ?, ?)
                    ''', (symbol, datetime.now().isoformat(), 'FAILED', str(e)))
                    conn.commit()
            except:
                pass
            
            return False
    
    def get_stock_list_from_api(self, market='ALL'):
        """
        📋 API에서 전체 종목 리스트 가져오기
        
        Args:
            market (str): 'KOSPI', 'KOSDAQ', 'ALL'
            
        Returns:
            pd.DataFrame: 종목 코드와 기본 정보
        """
        print("📋 종목 리스트 수집 중...")
        
        stock_list = []
        
        if market in ['KOSPI', 'ALL']:
            print("  📈 코스피 종목 수집...")
            kospi = fdr.StockListing('KOSPI')
            kospi['Market'] = 'KOSPI'
            stock_list.append(kospi)
        
        if market in ['KOSDAQ', 'ALL']:
            print("  📊 코스닥 종목 수집...")
            kosdaq = fdr.StockListing('KOSDAQ')
            kosdaq['Market'] = 'KOSDAQ'
            stock_list.append(kosdaq)
        
        # 데이터 합치기
        all_stocks = pd.concat(stock_list, ignore_index=True)
        
        # 컬럼명 확인 및 표준화
        print(f"📋 컬럼명 확인: {list(all_stocks.columns)}")
        
        # 컬럼명 표준화 (FinanceDataReader 버전에 따라 달라질 수 있음)
        column_mapping = {}
        for col in all_stocks.columns:
            if col.lower() in ['code', 'symbol']:
                column_mapping[col] = 'Symbol'
            elif col.lower() in ['name', '종목명']:
                column_mapping[col] = 'Name'
            elif col.lower() in ['sector', '섹터']:
                column_mapping[col] = 'Sector'
            elif col.lower() in ['industry', '업종']:
                column_mapping[col] = 'Industry'
            elif col.lower() in ['marcap', 'market_cap', '시가총액']:
                column_mapping[col] = 'Marcap'
        
        # 컬럼명 변경
        all_stocks = all_stocks.rename(columns=column_mapping)
        
        # 필수 컬럼이 없으면 인덱스를 Symbol로 사용
        if 'Symbol' not in all_stocks.columns:
            all_stocks = all_stocks.reset_index()
            all_stocks = all_stocks.rename(columns={'index': 'Symbol'})
        
        print(f"✅ 총 {len(all_stocks)}개 종목 발견")
        print(f"   📈 코스피: {len(all_stocks[all_stocks['Market']=='KOSPI'])}개")
        print(f"   📊 코스닥: {len(all_stocks[all_stocks['Market']=='KOSDAQ'])}개")
        print(f"📋 표준화된 컬럼: {list(all_stocks.columns)}")
        
        return all_stocks
    
    def filter_stocks(self, stock_list, min_market_cap=None, sectors=None):
        """
        🔍 종목 필터링
        
        Args:
            stock_list (pd.DataFrame): 전체 종목 리스트
            min_market_cap (int): 최소 시가총액 (억원)
            sectors (list): 포함할 섹터 리스트
            
        Returns:
            pd.DataFrame: 필터링된 종목 리스트
        """
        filtered = stock_list.copy()
        
        print("🔍 종목 필터링 중...")
        
        # 시가총액 필터링
        if min_market_cap:
            original_count = len(filtered)
            # 시가총액이 있는 종목만 (NaN 제외)
            filtered = filtered.dropna(subset=['Marcap'])
            # 최소 시가총액 이상
            filtered = filtered[filtered['Marcap'] >= min_market_cap * 100000000]
            print(f"  💰 시가총액 {min_market_cap}억원 이상: {original_count} → {len(filtered)}개")
        
        # 섹터 필터링
        if sectors:
            original_count = len(filtered)
            filtered = filtered[filtered['Sector'].isin(sectors)]
            print(f"  🏢 선택 섹터만: {original_count} → {len(filtered)}개")
        
        # 기본 필터링 (상장폐지, 관리종목 등 제외)
        original_count = len(filtered)
        filtered = filtered[~filtered['Name'].str.contains('스팩|리츠', na=False)]
        print(f"  🚫 스팩/리츠 제외: {original_count} → {len(filtered)}개")
        
        print(f"✅ 최종 선별된 종목: {len(filtered)}개")
        return filtered
    
    def collect_single_stock(self, symbol, name, market=None, sector=None, industry=None, market_cap=None, start_date='2023-01-01', retry_count=3):
        """
        📊 개별 종목 데이터 수집 (CSV + DB 동시 저장)
        
        Args:
            symbol (str): 종목 코드
            name (str): 종목명
            market (str): 시장 (KOSPI/KOSDAQ)
            sector (str): 섹터
            industry (str): 업종
            market_cap (float): 시가총액
            start_date (str): 시작일
            retry_count (int): 재시도 횟수
            
        Returns:
            bool: 성공 여부
        """
        today = datetime.now().strftime('%Y-%m-%d')
        csv_success = False
        db_success = False
        
        for attempt in range(retry_count):
            try:
                # 데이터 수집
                data = fdr.DataReader(symbol, start_date, today)
                
                if len(data) == 0:
                    raise ValueError("빈 데이터")
                
                # 추가 정보 컬럼 (CSV용)
                data['Symbol'] = symbol
                data['Name'] = name
                
                # 1. CSV 파일로 저장
                if self.save_csv:
                    try:
                        filename = f"{symbol}_{name.replace('/', '_').replace('*', '_')}.csv"
                        filepath = self.raw_data_dir / filename
                        data.to_csv(filepath, encoding='utf-8-sig')
                        csv_success = True
                        self.stats['csv_saved'] += 1
                    except Exception as e:
                        print(f"    ⚠️ CSV 저장 실패: {e}")
                
                # 2. DB에 저장
                if self.save_db:
                    # 종목 정보 저장
                    info_success = self.save_stock_info_to_db(
                        symbol, name, market, sector, industry, market_cap
                    )
                    
                    # 주가 데이터 저장
                    price_success = self.save_price_data_to_db(symbol, data)
                    
                    if info_success and price_success:
                        db_success = True
                        self.stats['db_saved'] += 1
                
                # 하나라도 성공하면 성공으로 간주
                return csv_success or db_success
                
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(1)  # 1초 대기 후 재시도
                    continue
                else:
                    print(f"    ❌ {symbol} ({name}) 실패: {str(e)}")
                    self.stats['failed_stocks'].append({
                        'symbol': symbol,
                        'name': name,
                        'error': str(e)
                    })
                    return False
        
        return False
    
    def collect_all_stocks(self, stock_list, delay=0.1, save_progress=True):
        """
        🚀 전체 종목 데이터 수집 (CSV + DB)
        
        Args:
            stock_list (pd.DataFrame): 수집할 종목 리스트
            delay (float): 요청 간 지연시간 (초)
            save_progress (bool): 진행상황 저장 여부
        """
        self.stats['total_stocks'] = len(stock_list)
        self.stats['start_time'] = datetime.now()
        
        print("🚀 대량 데이터 수집 시작!")
        print(f"📊 총 {len(stock_list)}개 종목 수집 예정")
        
        storage_info = []
        if self.save_csv:
            storage_info.append("📄 CSV 파일")
        if self.save_db:
            storage_info.append("🗄️ SQLite DB")
        print(f"💾 저장 방식: {' + '.join(storage_info)}")
        print("=" * 60)
        
        # 진행률 표시바
        progress_bar = tqdm(
            stock_list.iterrows(), 
            total=len(stock_list),
            desc="📈 데이터 수집",
            unit="종목"
        )
        
        for idx, row in progress_bar:
            # 안전한 컬럼 접근
            symbol = row.get('Symbol', row.name if hasattr(row, 'name') else str(idx))
            name = row.get('Name', f'종목_{symbol}')
            market = row.get('Market', None)
            sector = row.get('Sector', None)
            industry = row.get('Industry', None)
            market_cap = row.get('Marcap', None)
            
            # 진행률 표시바 업데이트
            progress_bar.set_postfix({
                'Current': f"{symbol}({name[:8]})",
                'Success': self.stats['success_count'],
                'CSV': self.stats['csv_saved'],
                'DB': self.stats['db_saved']
            })
            
            # 데이터 수집
            success = self.collect_single_stock(
                symbol, name, market, sector, industry, market_cap
            )
            
            if success:
                self.stats['success_count'] += 1
            else:
                self.stats['fail_count'] += 1
            
            # API 요청 제한을 위한 지연
            time.sleep(delay)
            
            # 중간 저장 (매 100개마다)
            if save_progress and (idx + 1) % 100 == 0:
                self.save_collection_stats()
        
        self.stats['end_time'] = datetime.now()
        self.save_collection_stats()
        self.print_collection_summary()
    
    def save_collection_stats(self):
        """📊 수집 통계 저장"""
        stats_file = self.processed_data_dir / 'collection_stats.json'
        
        # datetime 객체를 문자열로 변환
        stats_to_save = self.stats.copy()
        if stats_to_save['start_time']:
            stats_to_save['start_time'] = stats_to_save['start_time'].isoformat()
        if stats_to_save['end_time']:
            stats_to_save['end_time'] = stats_to_save['end_time'].isoformat()
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats_to_save, f, ensure_ascii=False, indent=2)
    
    def print_collection_summary(self):
        """📋 수집 결과 요약 출력"""
        print("\n" + "=" * 60)
        print("📋 데이터 수집 완료!")
        print("=" * 60)
        
        elapsed_time = self.stats['end_time'] - self.stats['start_time']
        
        print(f"⏱️  소요 시간: {elapsed_time}")
        print(f"📊 전체 종목: {self.stats['total_stocks']:,}개")
        print(f"✅ 성공: {self.stats['success_count']:,}개 ({self.stats['success_count']/self.stats['total_stocks']*100:.1f}%)")
        print(f"❌ 실패: {self.stats['fail_count']:,}개")
        
        if self.save_csv:
            print(f"📄 CSV 저장: {self.stats['csv_saved']:,}개")
        if self.save_db:
            print(f"🗄️ DB 저장: {self.stats['db_saved']:,}개")
        
        if self.stats['failed_stocks']:
            print(f"\n❌ 실패한 종목들:")
            for fail in self.stats['failed_stocks'][:10]:  # 처음 10개만 표시
                print(f"   {fail['symbol']} ({fail['name']}): {fail['error']}")
            if len(self.stats['failed_stocks']) > 10:
                print(f"   ... 외 {len(self.stats['failed_stocks'])-10}개")
        
        if self.save_csv:
            print(f"\n📁 CSV 저장 위치: {self.raw_data_dir}")
        if self.save_db:
            print(f"🗄️ DB 저장 위치: {self.db_path}")
            print(f"   DB 크기: {self.get_db_size():.1f} MB")
        
        print("=" * 60)
    
    def get_db_size(self):
        """DB 파일 크기 확인 (MB)"""
        try:
            size_bytes = os.path.getsize(self.db_path)
            return size_bytes / (1024 * 1024)
        except:
            return 0
    
    def query_db(self, query, params=None):
        """
        🔍 DB 쿼리 실행 (학습용)
        
        Args:
            query (str): SQL 쿼리
            params (tuple): 쿼리 매개변수
            
        Returns:
            pd.DataFrame: 쿼리 결과
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if params:
                    return pd.read_sql_query(query, conn, params=params)
                else:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"❌ 쿼리 실행 실패: {e}")
            return pd.DataFrame()
    
    def get_stock_data(self, symbol, start_date=None, end_date=None):
        """
        📈 특정 종목 데이터 조회
        
        Args:
            symbol (str): 종목 코드
            start_date (str): 시작일 (YYYY-MM-DD)
            end_date (str): 종료일 (YYYY-MM-DD)
            
        Returns:
            pd.DataFrame: 주가 데이터
        """
        query = """
            SELECT date, open, high, low, close, volume, change_pct
            FROM stock_prices 
            WHERE symbol = ?
        """
        params = [symbol]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date"
        
        return self.query_db(query, tuple(params))
    
    def get_saved_stock_list(self):
        """📋 DB에 저장된 종목 리스트 조회"""
        query = """
            SELECT symbol, name, market, sector, industry, market_cap
            FROM stock_info
            ORDER BY market_cap DESC
        """
        return self.query_db(query)
    
    def get_collection_stats(self):
        """📊 수집 통계 조회"""
        query = """
            SELECT 
                status,
                COUNT(*) as count,
                AVG(records_count) as avg_records
            FROM collection_log
            GROUP BY status
        """
        return self.query_db(query)


def main():
    """메인 실행 함수"""
    
    print("🚀 Finance Data Vibe - 전종목 데이터 수집기 (CSV + DB)")
    print("=" * 60)
    
    # 저장 방식 선택
    print("💾 저장 방식을 선택하세요:")
    print("1. CSV만 저장 (호환성 최고)")
    print("2. DB만 저장 (쿼리 성능 최고)")
    print("3. CSV + DB 동시 저장 (권장)")
    
    storage_choice = input("\n선택하세요 (1-3, 기본값: 3): ").strip() or '3'
    
    save_csv = storage_choice in ['1', '3']
    save_db = storage_choice in ['2', '3']
    
    # 수집기 초기화
    collector = StockDataCollector(save_csv=save_csv, save_db=save_db)
    
    # 1. 전체 종목 리스트 가져오기
    all_stocks = collector.get_stock_list_from_api('ALL')
    
    # 2. 종목 필터링 (선택사항)
    print("\n🔍 종목 필터링 옵션:")
    print("1. 전체 종목 (시간 오래 걸림)")
    print("2. 시가총액 1000억 이상")
    print("3. 시가총액 5000억 이상") 
    print("4. 코스피 200 + 코스닥 150")
    
    choice = input("\n선택하세요 (1-4, 기본값: 2): ").strip() or '2'
    
    if choice == '1':
        filtered_stocks = all_stocks
    elif choice == '2':
        filtered_stocks = collector.filter_stocks(all_stocks, min_market_cap=1000)
    elif choice == '3':
        filtered_stocks = collector.filter_stocks(all_stocks, min_market_cap=5000)
    elif choice == '4':
        # 시가총액 상위 350개 정도
        filtered_stocks = all_stocks.nlargest(350, 'Marcap')
    else:
        filtered_stocks = collector.filter_stocks(all_stocks, min_market_cap=1000)
    
    # 3. 수집 시작 확인
    estimated_time = len(filtered_stocks) * 0.2 / 60  # 대략적인 예상 시간 (분)
    print(f"\n📊 {len(filtered_stocks)}개 종목 수집 예정")
    print(f"⏱️  예상 소요 시간: 약 {estimated_time:.1f}분")
    
    storage_info = []
    if save_csv:
        storage_info.append("📄 CSV")
    if save_db:
        storage_info.append("🗄️ DB")
    print(f"💾 저장 방식: {' + '.join(storage_info)}")
    
    confirm = input("\n수집을 시작하시겠습니까? (y/N): ").strip().lower()
    
    if confirm == 'y':
        # 4. 데이터 수집 실행
        collector.collect_all_stocks(filtered_stocks, delay=0.2)
        
        print("\n🎉 모든 작업이 완료되었습니다!")
        
        # 5. DB 기능 시연 (DB 저장한 경우)
        if save_db:
            print("\n" + "="*40)
            print("🔍 DB 기능 시연")
            print("="*40)
            
            # 수집 통계
            stats = collector.get_collection_stats()
            if not stats.empty:
                print("📊 수집 통계:")
                print(stats)
            
            # 종목 리스트 (상위 5개)
            stock_list = collector.get_saved_stock_list().head()
            if not stock_list.empty:
                print("\n📋 수집된 종목 (상위 5개):")
                print(stock_list[['symbol', 'name', 'market', 'market_cap']])
            
            # 삼성전자 최근 데이터
            samsung_data = collector.get_stock_data('005930').tail()
            if not samsung_data.empty:
                print("\n📈 삼성전자 최근 데이터:")
                print(samsung_data)
        
        print("\n🚀 이제 다양한 종목 분석을 시작할 수 있어요!")
        
    else:
        print("👋 수집을 취소했습니다.")
# 마지막 부분 삭제 (중복 코드 제거)
if __name__ == "__main__":
    main()