"""
주식 데이터 확인 및 전체 종목 뉴스 수집 설정
"""

import sqlite3
import pandas as pd
from pathlib import Path

def check_databases():
    """데이터베이스 현황 확인"""
    
    project_root = Path.cwd()
    
    print("🔍 데이터베이스 현황 확인")
    print("="*50)
    
    # 1. finance_data.db 확인
    finance_db = project_root / "finance_data.db"
    if finance_db.exists():
        print(f"✅ finance_data.db 발견 ({finance_db.stat().st_size / 1024:.1f} KB)")
        
        with sqlite3.connect(finance_db) as conn:
            stock_count = pd.read_sql_query(
                "SELECT COUNT(*) as count FROM stock_info", conn
            ).iloc[0]['count']
            
            print(f"   📊 종목 수: {stock_count:,}개")
            
            # 테이블 스키마 확인
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(stock_info)")
            columns = [row[1] for row in cursor.fetchall()]
            print(f"   📋 컬럼: {', '.join(columns)}")
            
            # 샘플 종목 조회
            if 'code' in columns:
                sample_stocks = pd.read_sql_query(
                    "SELECT code, name FROM stock_info LIMIT 5", conn
                )
            elif 'symbol' in columns:
                sample_stocks = pd.read_sql_query(
                    "SELECT symbol as code, name FROM stock_info LIMIT 5", conn
                )
            else:
                sample_stocks = pd.read_sql_query(
                    "SELECT * FROM stock_info LIMIT 5", conn
                )
                
            print("   📋 샘플 종목:")
            for _, stock in sample_stocks.iterrows():
                if 'code' in stock:
                    print(f"      • {stock['name']}({stock['code']})")
                elif 'symbol' in stock:
                    print(f"      • {stock['name']}({stock['symbol']})")
                else:
                    print(f"      • {stock.to_dict()}")
    else:
        print("❌ finance_data.db 없음")
    
    # 2. data/stock_data.db 확인 (대량 데이터)
    stock_db = project_root / "data" / "stock_data.db"
    if stock_db.exists():
        print(f"\n✅ data/stock_data.db 발견 ({stock_db.stat().st_size / (1024*1024):.1f} MB)")
        
        with sqlite3.connect(stock_db) as conn:
            stock_count = pd.read_sql_query(
                "SELECT COUNT(*) as count FROM stock_info", conn
            ).iloc[0]['count']
            
            print(f"   📊 종목 수: {stock_count:,}개")
            
            # 테이블 확인
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"   📋 테이블: {', '.join(tables)}")
            
            # 스키마 확인
            cursor.execute("PRAGMA table_info(stock_info)")
            columns = [row[1] for row in cursor.fetchall()]
            print(f"   📋 컬럼: {', '.join(columns)}")
            
            # 샘플 데이터 확인
            sample_data = pd.read_sql_query("SELECT * FROM stock_info LIMIT 3", conn)
            print(f"   📋 샘플 데이터:")
            for _, row in sample_data.iterrows():
                print(f"      • {row.to_dict()}")
    else:
        print("❌ data/stock_data.db 없음")
    
    return finance_db.exists(), stock_db.exists()

def migrate_stock_data():
    """대량 주식 데이터를 finance_data.db로 복사"""
    
    project_root = Path.cwd()
    source_db = project_root / "data" / "stock_data.db"
    target_db = project_root / "finance_data.db"
    
    if not source_db.exists():
        print("❌ 소스 데이터베이스가 없습니다.")
        return False
    
    print("🔄 주식 데이터 마이그레이션 시작...")
    
    try:
        # 먼저 소스 스키마 확인
        with sqlite3.connect(source_db) as source_conn:
            cursor = source_conn.cursor()
            cursor.execute("PRAGMA table_info(stock_info)")
            columns = [row[1] for row in cursor.fetchall()]
            print(f"📋 소스 컬럼: {', '.join(columns)}")
            
            # 컬럼명에 따라 쿼리 조정
            if 'symbol' in columns and 'name' in columns:
                # symbol 컬럼 사용
                query = """
                    SELECT symbol as code, name, 
                           COALESCE(market, '') as market, 
                           COALESCE(sector, '') as sector
                    FROM stock_info 
                    ORDER BY symbol
                """
            elif 'code' in columns and 'name' in columns:
                # code 컬럼 사용
                query = """
                    SELECT code, name,
                           COALESCE(market, '') as market, 
                           COALESCE(sector, '') as sector
                    FROM stock_info 
                    ORDER BY code
                """
            else:
                # 기본 컬럼만 사용
                available_cols = ', '.join(columns[:4])  # 처음 4개 컬럼만
                query = f"SELECT {available_cols} FROM stock_info ORDER BY 1"
            
            print(f"📊 실행 쿼리: {query}")
            stock_data = pd.read_sql_query(query, source_conn)
        
        print(f"📊 소스에서 {len(stock_data):,}개 종목 로드")
        print(f"📋 로드된 컬럼: {', '.join(stock_data.columns)}")
        
        # 컬럼명 표준화 (code, name, market, sector)
        if 'symbol' in stock_data.columns and 'code' not in stock_data.columns:
            stock_data = stock_data.rename(columns={'symbol': 'code'})
        
        # 필수 컬럼이 없으면 기본값 추가
        required_columns = ['code', 'name', 'market', 'sector']
        for col in required_columns:
            if col not in stock_data.columns:
                stock_data[col] = '' if col in ['market', 'sector'] else f'unknown_{col}'
        
        # 필요한 컬럼만 선택
        stock_data = stock_data[required_columns]
        
        # 중복 제거 및 정리
        stock_data = stock_data.drop_duplicates(subset=['code'])
        stock_data = stock_data.dropna(subset=['code', 'name'])
        
        print(f"📊 정리 후: {len(stock_data):,}개 종목")
        
        # 타겟에 데이터 삽입
        with sqlite3.connect(target_db) as target_conn:
            # 기존 데이터 백업 후 삭제
            cursor = target_conn.cursor()
            cursor.execute("DELETE FROM stock_info")
            
            # 새 데이터 삽입
            stock_data.to_sql('stock_info', target_conn, if_exists='append', index=False)
            
            # 확인
            new_count = pd.read_sql_query(
                "SELECT COUNT(*) as count FROM stock_info", target_conn
            ).iloc[0]['count']
            
            print(f"✅ {new_count:,}개 종목 마이그레이션 완료!")
            
            # 샘플 확인
            sample = pd.read_sql_query(
                "SELECT code, name, market FROM stock_info LIMIT 5", target_conn
            )
            print("📋 마이그레이션된 샘플:")
            for _, row in sample.iterrows():
                print(f"   • {row['name']}({row['code']}) - {row['market']}")
            
        return True
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 실행 함수"""
    
    print("Finance Data Vibe - 주식 데이터 확인")
    print("="*50)
    
    # 현재 상황 확인
    has_finance_db, has_stock_db = check_databases()
    
    if has_stock_db and has_finance_db:
        print("\n🎯 다음 단계 옵션:")
        print("1. 대량 주식 데이터를 finance_data.db로 복사")
        print("2. 현재 상태 유지 (20개 종목)")
        print("3. 종료")
        
        choice = input("\n선택 (1-3): ").strip()
        
        if choice == '1':
            if migrate_stock_data():
                print("\n🚀 이제 전체 모드에서 전체 종목 뉴스 수집이 가능합니다!")
                print("뉴스 수집기를 다시 실행하세요:")
                print("python examples/basic_examples/06_full_news_collector.py")
            
        elif choice == '2':
            print("현재 상태를 유지합니다. (20개 종목)")
            
        elif choice == '3':
            print("프로그램을 종료합니다.")
            
    elif has_stock_db:
        print("\n💡 대량 주식 데이터가 있습니다!")
        print("finance_data.db로 복사하시겠습니까? (y/N): ", end="")
        
        choice = input().strip().lower()
        if choice == 'y':
            migrate_stock_data()
            
    else:
        print("\n❌ 대량 주식 데이터가 없습니다.")
        print("먼저 다음 스크립트를 실행하세요:")
        print("python examples/basic_examples/02_bulk_data_collection.py")

if __name__ == "__main__":
    main()