"""
뉴스 데이터 디버깅 및 문제 해결 스크립트
삼성전자 뉴스가 안 보이는 문제를 해결합니다.
"""

import sqlite3
import pandas as pd
from pathlib import Path

def find_all_databases():
    """모든 데이터베이스 파일 찾기"""
    project_root = Path.cwd()
    db_files = list(project_root.rglob('*.db'))
    
    print("🔍 발견된 데이터베이스 파일들:")
    for i, db_file in enumerate(db_files, 1):
        size_mb = db_file.stat().st_size / (1024 * 1024)
        print(f"  {i}. {db_file.name} ({size_mb:.1f} MB) - {db_file.relative_to(project_root)}")
    
    return db_files

def analyze_database_structure(db_path):
    """데이터베이스 구조 분석"""
    print(f"\n📊 {db_path.name} 데이터베이스 분석:")
    
    try:
        with sqlite3.connect(db_path) as conn:
            # 테이블 목록 조회
            tables_df = pd.read_sql_query("""
                SELECT name, type 
                FROM sqlite_master 
                WHERE type='table'
                ORDER BY name
            """, conn)
            
            if tables_df.empty:
                print("  ❌ 테이블이 없습니다.")
                return
            
            print(f"  📋 테이블 목록 ({len(tables_df)}개):")
            for _, row in tables_df.iterrows():
                print(f"    - {row['name']}")
            
            # 뉴스 관련 테이블 찾기
            news_tables = [name for name in tables_df['name'] if 'news' in name.lower()]
            
            if news_tables:
                print(f"\n  📰 뉴스 테이블: {news_tables}")
                
                for table in news_tables:
                    analyze_news_table(conn, table)
            else:
                print("  ❌ 뉴스 테이블을 찾을 수 없습니다.")
                
    except Exception as e:
        print(f"  ❌ 데이터베이스 접근 실패: {e}")

def analyze_news_table(conn, table_name):
    """뉴스 테이블 상세 분석"""
    print(f"\n    📊 {table_name} 테이블 분석:")
    
    try:
        # 테이블 구조 확인
        columns_df = pd.read_sql_query(f"PRAGMA table_info({table_name})", conn)
        print(f"      컬럼들: {', '.join(columns_df['name'].tolist())}")
        
        # 총 레코드 수
        count_df = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table_name}", conn)
        total_count = count_df.iloc[0]['count']
        print(f"      총 뉴스 수: {total_count:,}건")
        
        # stock_code 관련 분석
        if 'stock_code' in columns_df['name'].values:
            print(f"      📈 종목코드 분석:")
            
            # 종목코드별 뉴스 수
            stock_count_df = pd.read_sql_query(f"""
                SELECT stock_code, COUNT(*) as news_count
                FROM {table_name}
                WHERE stock_code IS NOT NULL AND stock_code != ''
                GROUP BY stock_code
                ORDER BY news_count DESC
                LIMIT 10
            """, conn)
            
            if not stock_count_df.empty:
                print(f"        상위 10개 종목 뉴스 수:")
                for _, row in stock_count_df.iterrows():
                    print(f"          {row['stock_code']}: {row['news_count']:,}건")
                
                # 삼성전자 관련 확인
                samsung_codes = ['005930', '삼성전자', 'Samsung', 'SAMSUNG']
                samsung_news = []
                
                for code in samsung_codes:
                    samsung_df = pd.read_sql_query(f"""
                        SELECT COUNT(*) as count
                        FROM {table_name}
                        WHERE stock_code LIKE '%{code}%' 
                           OR stock_name LIKE '%{code}%'
                           OR title LIKE '%{code}%'
                    """, conn)
                    
                    count = samsung_df.iloc[0]['count']
                    if count > 0:
                        samsung_news.append(f"{code}: {count}건")
                
                if samsung_news:
                    print(f"        🎯 삼성전자 관련 뉴스:")
                    for news in samsung_news:
                        print(f"          {news}")
                else:
                    print(f"        ❌ 삼성전자 관련 뉴스를 찾을 수 없습니다!")
                
                # 실제 삼성전자 뉴스 샘플 조회
                sample_df = pd.read_sql_query(f"""
                    SELECT stock_code, stock_name, title
                    FROM {table_name}
                    WHERE (stock_code LIKE '%005930%' 
                           OR stock_name LIKE '%삼성전자%' 
                           OR title LIKE '%삼성전자%')
                    LIMIT 5
                """, conn)
                
                if not sample_df.empty:
                    print(f"        📄 삼성전자 뉴스 샘플:")
                    for _, row in sample_df.iterrows():
                        print(f"          [{row.get('stock_code', 'N/A')}] {row.get('title', 'N/A')[:50]}...")
            else:
                print(f"        ❌ 종목코드가 있는 뉴스가 없습니다.")
        else:
            print(f"        ❌ stock_code 컬럼이 없습니다.")
            
        # 최근 뉴스 확인
        if 'pub_date' in columns_df['name'].values or 'collected_at' in columns_df['name'].values:
            date_column = 'pub_date' if 'pub_date' in columns_df['name'].values else 'collected_at'
            
            recent_df = pd.read_sql_query(f"""
                SELECT {date_column}, COUNT(*) as count
                FROM {table_name}
                WHERE {date_column} IS NOT NULL
                GROUP BY DATE({date_column})
                ORDER BY {date_column} DESC
                LIMIT 7
            """, conn)
            
            if not recent_df.empty:
                print(f"        📅 최근 7일간 뉴스:")
                for _, row in recent_df.iterrows():
                    print(f"          {row[date_column]}: {row['count']}건")
                    
    except Exception as e:
        print(f"      ❌ 테이블 분석 실패: {e}")

def fix_stock_code_mapping():
    """종목코드 매핑 문제 수정"""
    print(f"\n🔧 종목코드 매핑 문제 수정 시도...")
    
    # finance_data.db에서 삼성전자 뉴스 확인
    finance_db = Path.cwd() / "finance_data.db"
    
    if finance_db.exists():
        try:
            with sqlite3.connect(finance_db) as conn:
                # 뉴스 테이블에서 삼성전자 관련 뉴스 조회
                samsung_check = pd.read_sql_query("""
                    SELECT DISTINCT stock_code, stock_name, COUNT(*) as count
                    FROM news_articles
                    WHERE title LIKE '%삼성전자%' 
                       OR stock_name LIKE '%삼성전자%'
                    GROUP BY stock_code, stock_name
                """, conn)
                
                if not samsung_check.empty:
                    print("  📊 삼성전자 관련 뉴스 발견:")
                    for _, row in samsung_check.iterrows():
                        print(f"    종목코드: {row['stock_code']}, 종목명: {row['stock_name']}, 뉴스수: {row['count']}건")
                    
                    # 종목코드가 '005930'이 아닌 경우 수정
                    cursor = conn.cursor()
                    
                    # 삼성전자 뉴스의 종목코드를 '005930'으로 통일
                    cursor.execute("""
                        UPDATE news_articles 
                        SET stock_code = '005930', stock_name = '삼성전자'
                        WHERE (title LIKE '%삼성전자%' OR stock_name LIKE '%삼성전자%')
                          AND stock_code != '005930'
                    """)
                    
                    updated_rows = cursor.rowcount
                    if updated_rows > 0:
                        print(f"  ✅ {updated_rows}건의 삼성전자 뉴스 종목코드 수정 완료")
                        conn.commit()
                    else:
                        print("  ✅ 종목코드가 이미 올바르게 설정되어 있습니다.")
                    
                    # 수정 후 확인
                    final_check = pd.read_sql_query("""
                        SELECT COUNT(*) as count
                        FROM news_articles
                        WHERE stock_code = '005930'
                    """, conn)
                    
                    samsung_count = final_check.iloc[0]['count']
                    print(f"  📊 최종 삼성전자(005930) 뉴스 수: {samsung_count:,}건")
                    
                else:
                    print("  ❌ 삼성전자 관련 뉴스가 전혀 없습니다.")
                    
        except Exception as e:
            print(f"  ❌ 종목코드 매핑 수정 실패: {e}")
    else:
        print("  ❌ finance_data.db 파일을 찾을 수 없습니다.")

def verify_news_query_function():
    """뉴스 조회 함수 검증"""
    print(f"\n🔍 뉴스 조회 함수 검증...")
    
    finance_db = Path.cwd() / "finance_data.db"
    
    if finance_db.exists():
        try:
            with sqlite3.connect(finance_db) as conn:
                # 실제 뉴스 조회 테스트
                test_query = """
                    SELECT stock_code, stock_name, title, pub_date
                    FROM news_articles
                    WHERE stock_code = '005930'
                    ORDER BY pub_date DESC
                    LIMIT 5
                """
                
                result_df = pd.read_sql_query(test_query, conn)
                
                if not result_df.empty:
                    print("  ✅ 삼성전자(005930) 뉴스 조회 성공:")
                    for _, row in result_df.iterrows():
                        print(f"    [{row['stock_code']}] {row['title'][:60]}...")
                else:
                    print("  ❌ 삼성전자(005930) 뉴스 조회 실패")
                    
                    # 대안 검색
                    alt_query = """
                        SELECT stock_code, stock_name, title, pub_date
                        FROM news_articles
                        WHERE stock_name LIKE '%삼성전자%' OR title LIKE '%삼성전자%'
                        LIMIT 5
                    """
                    
                    alt_result = pd.read_sql_query(alt_query, conn)
                    
                    if not alt_result.empty:
                        print("  🔍 대안 검색으로 삼성전자 뉴스 발견:")
                        for _, row in alt_result.iterrows():
                            print(f"    [{row['stock_code']}] {row['stock_name']} - {row['title'][:50]}...")
                    else:
                        print("  ❌ 어떤 방법으로도 삼성전자 뉴스를 찾을 수 없습니다.")
                        
        except Exception as e:
            print(f"  ❌ 뉴스 조회 검증 실패: {e}")

def main():
    """메인 실행 함수"""
    print("🚀 뉴스 데이터 디버깅 시작")
    print("=" * 70)
    
    # 1. 모든 데이터베이스 파일 찾기
    db_files = find_all_databases()
    
    # 2. 각 데이터베이스 구조 분석
    for db_file in db_files:
        analyze_database_structure(db_file)
    
    # 3. 종목코드 매핑 문제 수정
    fix_stock_code_mapping()
    
    # 4. 뉴스 조회 함수 검증
    verify_news_query_function()
    
    print(f"\n🎉 디버깅 완료!")
    print("=" * 70)
    print("📝 해결 방법:")
    print("1. 종목코드 매핑이 수정되었다면 뉴스 검색 시스템을 다시 테스트해보세요.")
    print("2. 여전히 문제가 있다면 뉴스 수집 스크립트를 다시 실행해보세요.")
    print("3. 데이터베이스 파일 경로가 다르다면 설정을 확인해보세요.")

if __name__ == "__main__":
    main()