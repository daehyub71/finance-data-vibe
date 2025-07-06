"""
examples/basic_examples/08_db_migration_sentiment.py

감정 분석용 데이터베이스 마이그레이션 스크립트
✅ news_articles 테이블에 감정 분석 컬럼 추가
✅ 기존 데이터 보존하면서 안전하게 업데이트
✅ 인덱스 생성으로 쿼리 성능 최적화
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def migrate_database():
    """감정 분석용 데이터베이스 마이그레이션"""
    
    db_path = project_root / "finance_data.db"
    
    print("🔄 감정 분석용 데이터베이스 마이그레이션 시작")
    print(f"📁 DB 경로: {db_path}")
    
    if not db_path.exists():
        print("❌ 데이터베이스 파일이 없습니다!")
        print("먼저 뉴스 수집을 실행해주세요: python examples/basic_examples/06_full_news_collector.py")
        return False
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 기존 테이블 구조 확인
            cursor.execute("PRAGMA table_info(news_articles)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            print(f"📊 기존 컬럼: {existing_columns}")
            
            # 2. 필요한 컬럼들 정의
            new_columns = {
                'sentiment_score': 'REAL DEFAULT 0.0',
                'sentiment_label': 'TEXT DEFAULT "neutral"',
                'news_category': 'TEXT DEFAULT "general"',
                'long_term_relevance': 'INTEGER DEFAULT 50'
            }
            
            # 3. 누락된 컬럼 추가
            added_columns = []
            for col_name, col_definition in new_columns.items():
                if col_name not in existing_columns:
                    try:
                        alter_sql = f"ALTER TABLE news_articles ADD COLUMN {col_name} {col_definition}"
                        cursor.execute(alter_sql)
                        added_columns.append(col_name)
                        print(f"✅ 컬럼 추가: {col_name}")
                    except sqlite3.Error as e:
                        print(f"❌ 컬럼 추가 실패 ({col_name}): {e}")
                else:
                    print(f"⏭️  컬럼 이미 존재: {col_name}")
            
            # 4. 인덱스 생성 (성능 최적화)
            indexes = [
                ("idx_news_sentiment_score", "sentiment_score"),
                ("idx_news_sentiment_label", "sentiment_label"),
                ("idx_news_category", "news_category"),
                ("idx_news_stock_date", "stock_code, pub_date"),
                ("idx_news_relevance", "long_term_relevance")
            ]
            
            for index_name, index_columns in indexes:
                try:
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON news_articles({index_columns})")
                    print(f"✅ 인덱스 생성: {index_name}")
                except sqlite3.Error as e:
                    print(f"⚠️ 인덱스 생성 실패 ({index_name}): {e}")
            
            # 5. daily_sentiment_index 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_sentiment_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    sentiment_index REAL NOT NULL DEFAULT 50.0,
                    sentiment_score REAL NOT NULL DEFAULT 0.0,
                    total_news INTEGER NOT NULL DEFAULT 0,
                    confidence INTEGER NOT NULL DEFAULT 0,
                    fundamental_news INTEGER DEFAULT 0,
                    business_news INTEGER DEFAULT 0,
                    technical_news INTEGER DEFAULT 0,
                    noise_news INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(stock_code, date)
                )
            ''')
            print("✅ daily_sentiment_index 테이블 생성")
            
            # 6. daily_sentiment_index 인덱스 생성
            daily_indexes = [
                ("idx_daily_stock_code", "stock_code"),
                ("idx_daily_date", "date"),
                ("idx_daily_sentiment_index", "sentiment_index"),
                ("idx_daily_stock_date", "stock_code, date")
            ]
            
            for index_name, index_columns in daily_indexes:
                try:
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON daily_sentiment_index({index_columns})")
                    print(f"✅ 일별 감정 인덱스 생성: {index_name}")
                except sqlite3.Error as e:
                    print(f"⚠️ 일별 감정 인덱스 생성 실패 ({index_name}): {e}")
            
            # 7. 변경사항 저장
            conn.commit()
            
            # 8. 마이그레이션 결과 확인
            cursor.execute("SELECT COUNT(*) FROM news_articles")
            total_news = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM news_articles WHERE sentiment_score IS NOT NULL AND sentiment_score != 0.0")
            analyzed_news = cursor.fetchone()[0]
            
            print("\n" + "="*60)
            print("🎉 데이터베이스 마이그레이션 완료!")
            print("="*60)
            print(f"📊 전체 뉴스: {total_news:,}건")
            print(f"🔍 감정 분석 완료: {analyzed_news:,}건")
            print(f"⏳ 감정 분석 대기: {total_news - analyzed_news:,}건")
            
            if added_columns:
                print(f"✅ 추가된 컬럼: {', '.join(added_columns)}")
            else:
                print("ℹ️  모든 컬럼이 이미 존재합니다")
            
            print("\n🚀 이제 감정 분석을 실행할 수 있습니다:")
            print("   python examples/basic_examples/07_buffett_sentiment_analyzer.py")
            print("="*60)
            
            return True
            
    except sqlite3.Error as e:
        print(f"❌ 데이터베이스 마이그레이션 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        return False

def check_database_status():
    """데이터베이스 상태 확인"""
    
    db_path = project_root / "finance_data.db"
    
    if not db_path.exists():
        print("❌ 데이터베이스 파일이 없습니다!")
        return False
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 테이블 목록 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            print(f"📊 데이터베이스 상태 확인:")
            print(f"   테이블 수: {len(tables)}개")
            print(f"   테이블 목록: {', '.join(tables)}")
            
            # news_articles 테이블 구조 확인
            if 'news_articles' in tables:
                cursor.execute("PRAGMA table_info(news_articles)")
                columns = [row[1] for row in cursor.fetchall()]
                
                print(f"\n📋 news_articles 테이블:")
                print(f"   컬럼 수: {len(columns)}개")
                print(f"   컬럼 목록: {', '.join(columns)}")
                
                # 감정 분석 컬럼 확인
                required_columns = ['sentiment_score', 'sentiment_label', 'news_category', 'long_term_relevance']
                missing_columns = [col for col in required_columns if col not in columns]
                
                if missing_columns:
                    print(f"❌ 누락된 감정 분석 컬럼: {', '.join(missing_columns)}")
                    return False
                else:
                    print("✅ 모든 감정 분석 컬럼 존재")
                
                # 데이터 개수 확인
                cursor.execute("SELECT COUNT(*) FROM news_articles")
                total_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM news_articles WHERE sentiment_score IS NOT NULL AND sentiment_score != 0.0")
                analyzed_count = cursor.fetchone()[0]
                
                print(f"\n📈 뉴스 데이터:")
                print(f"   전체 뉴스: {total_count:,}건")
                print(f"   감정 분석 완료: {analyzed_count:,}건")
                print(f"   감정 분석 대기: {total_count - analyzed_count:,}건")
                
            # daily_sentiment_index 테이블 확인
            if 'daily_sentiment_index' in tables:
                cursor.execute("SELECT COUNT(*) FROM daily_sentiment_index")
                daily_count = cursor.fetchone()[0]
                print(f"\n📅 일별 감정 지수: {daily_count:,}건")
            else:
                print("\n❌ daily_sentiment_index 테이블 없음")
                return False
            
            return True
            
    except sqlite3.Error as e:
        print(f"❌ 데이터베이스 확인 실패: {e}")
        return False

def backup_database():
    """데이터베이스 백업"""
    
    db_path = project_root / "finance_data.db"
    backup_path = project_root / f"finance_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    
    try:
        if db_path.exists():
            import shutil
            shutil.copy2(db_path, backup_path)
            print(f"✅ 데이터베이스 백업 완료: {backup_path}")
            return True
        else:
            print("❌ 원본 데이터베이스가 없습니다!")
            return False
    except Exception as e:
        print(f"❌ 백업 실패: {e}")
        return False

def main():
    """메인 실행 함수"""
    
    print("🛠️  Finance Data Vibe - 감정 분석 데이터베이스 마이그레이션 도구")
    print("="*70)
    
    while True:
        print("\n📋 마이그레이션 메뉴:")
        print("1. 데이터베이스 상태 확인")
        print("2. 데이터베이스 백업")
        print("3. 마이그레이션 실행 (감정 분석 컬럼 추가)")
        print("4. 전체 프로세스 (백업 + 마이그레이션)")
        print("0. 종료")
        
        choice = input("\n선택 (0-4): ").strip()
        
        if choice == '0':
            print("👋 마이그레이션 도구를 종료합니다.")
            break
            
        elif choice == '1':
            # 데이터베이스 상태 확인
            print("\n🔍 데이터베이스 상태 확인 중...")
            if check_database_status():
                print("✅ 데이터베이스 상태 양호")
            else:
                print("❌ 마이그레이션이 필요합니다")
        
        elif choice == '2':
            # 데이터베이스 백업
            print("\n💾 데이터베이스 백업 중...")
            backup_database()
        
        elif choice == '3':
            # 마이그레이션 실행
            print("\n🔄 마이그레이션 실행 중...")
            if migrate_database():
                print("🎉 마이그레이션 성공!")
            else:
                print("❌ 마이그레이션 실패!")
        
        elif choice == '4':
            # 전체 프로세스
            print("\n🚀 전체 마이그레이션 프로세스 시작...")
            
            # 1. 백업
            print("\n1️⃣ 데이터베이스 백업...")
            if not backup_database():
                print("❌ 백업 실패로 중단합니다.")
                continue
            
            # 2. 마이그레이션
            print("\n2️⃣ 마이그레이션 실행...")
            if migrate_database():
                print("\n🎉 전체 프로세스 성공 완료!")
                print("\n📝 다음 단계:")
                print("1. python examples/basic_examples/07_buffett_sentiment_analyzer.py")
                print("2. 메뉴에서 '1. 뉴스 감정 분석 실행' 선택")
                print("3. 감정 분석 완료 후 '4. 워런 버핏 투자 신호 생성' 실행")
            else:
                print("❌ 마이그레이션 실패!")
        
        else:
            print("❌ 올바른 번호를 선택해주세요.")

if __name__ == "__main__":
    main()