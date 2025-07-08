"""
뉴스 데이터베이스 스키마 수정 스크립트
quality_issues 컬럼 문제 해결

실행 방법:
python fix_news_db_schema.py
"""

import sqlite3
from pathlib import Path

def fix_news_database():
    """뉴스 데이터베이스 스키마 수정"""
    
    # 데이터베이스 경로들 확인
    possible_paths = [
        Path("finance_data.db"),
        Path("data/news_data.db"),
        Path("data/finance_data.db")
    ]
    
    db_path = None
    for path in possible_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        print("❌ 뉴스 데이터베이스를 찾을 수 없습니다.")
        return
    
    print(f"🔧 데이터베이스 수정 중: {db_path}")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 현재 테이블 구조 확인
            cursor.execute("PRAGMA table_info(news_articles)")
            columns = cursor.fetchall()
            
            print("📋 현재 테이블 구조:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
            
            # 2. quality_issues 컬럼이 있는지 확인
            column_names = [col[1] for col in columns]
            
            if 'quality_issues' not in column_names:
                print("\n✅ quality_issues 컬럼 추가 중...")
                
                # 컬럼 추가
                cursor.execute("""
                    ALTER TABLE news_articles 
                    ADD COLUMN quality_issues TEXT DEFAULT NULL
                """)
                
                print("✅ quality_issues 컬럼 추가 완료!")
            else:
                print("✅ quality_issues 컬럼이 이미 존재합니다.")
            
            # 3. 다른 필요한 컬럼들도 확인 및 추가
            required_columns = {
                'sentiment_score': 'REAL DEFAULT 0.0',
                'sentiment_label': 'TEXT DEFAULT NULL',
                'keywords': 'TEXT DEFAULT NULL',
                'view_count': 'INTEGER DEFAULT 0',
                'comment_count': 'INTEGER DEFAULT 0'
            }
            
            for col_name, col_def in required_columns.items():
                if col_name not in column_names:
                    print(f"✅ {col_name} 컬럼 추가 중...")
                    cursor.execute(f"ALTER TABLE news_articles ADD COLUMN {col_name} {col_def}")
            
            conn.commit()
            
            # 4. 최종 테이블 구조 확인
            cursor.execute("PRAGMA table_info(news_articles)")
            final_columns = cursor.fetchall()
            
            print(f"\n📋 수정된 테이블 구조:")
            for col in final_columns:
                print(f"  {col[1]} ({col[2]})")
            
            print("\n🎉 데이터베이스 스키마 수정 완료!")
            
    except Exception as e:
        print(f"❌ 스키마 수정 실패: {e}")


def create_proper_news_table():
    """올바른 뉴스 테이블 생성 (백업용)"""
    
    db_path = Path("finance_data.db")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 기존 테이블 백업
            print("💾 기존 테이블 백업 중...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_articles_backup AS 
                SELECT * FROM news_articles
            """)
            
            # 새 테이블 생성
            print("🆕 새 테이블 생성 중...")
            cursor.execute("DROP TABLE IF EXISTS news_articles")
            
            cursor.execute('''
                CREATE TABLE news_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    link TEXT NOT NULL UNIQUE,
                    description TEXT,
                    content TEXT,
                    pub_date TEXT,
                    source TEXT,
                    sentiment_score REAL DEFAULT 0.0,
                    sentiment_label TEXT,
                    keywords TEXT,
                    view_count INTEGER DEFAULT 0,
                    comment_count INTEGER DEFAULT 0,
                    quality_issues TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_stock_code ON news_articles(stock_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_pub_date ON news_articles(pub_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_collected_at ON news_articles(collected_at)')
            
            # 백업 데이터 복구 (공통 컬럼만)
            print("📥 백업 데이터 복구 중...")
            cursor.execute("""
                INSERT INTO news_articles (
                    stock_code, stock_name, title, link, description, 
                    content, pub_date, source, collected_at
                )
                SELECT 
                    stock_code, stock_name, title, link, description,
                    content, pub_date, source, 
                    COALESCE(collected_at, datetime('now'))
                FROM news_articles_backup
            """)
            
            conn.commit()
            print("✅ 새 테이블 생성 및 데이터 복구 완료!")
            
    except Exception as e:
        print(f"❌ 테이블 재생성 실패: {e}")


if __name__ == "__main__":
    print("🔧 뉴스 데이터베이스 스키마 수정 도구")
    print("=" * 50)
    
    print("\n수정 방법을 선택하세요:")
    print("1. 컬럼만 추가 (빠른 수정) - 추천")
    print("2. 테이블 재생성 (완전 수정)")
    
    choice = input("\n선택 (1-2): ").strip()
    
    if choice == '1':
        fix_news_database()
    elif choice == '2':
        confirm = input("⚠️ 기존 데이터가 손실될 수 있습니다. 계속하시겠습니까? (y/N): ").strip().lower()
        if confirm == 'y':
            create_proper_news_table()
        else:
            print("❌ 취소되었습니다.")
    else:
        print("❌ 잘못된 선택입니다.")