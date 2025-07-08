"""
뉴스 데이터베이스 완전 수정 스크립트
모든 컬럼 오류 해결 (quality_issues, is_verified 등)

실행 방법:
python complete_news_db_fix.py
"""

import sqlite3
from pathlib import Path
import logging

def find_news_database():
    """뉴스 데이터베이스 경로 찾기"""
    possible_paths = [
        Path("finance_data.db"),
        Path("data/finance_data.db"),
        Path("data/news_data.db"),
        Path("news_data.db")
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    # 없으면 기본 경로에 생성
    return Path("finance_data.db")

def check_table_structure(db_path):
    """현재 테이블 구조 확인"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 테이블 존재 여부 확인
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='news_articles'
            """)
            
            if not cursor.fetchone():
                print("❌ news_articles 테이블이 존재하지 않습니다.")
                return None
            
            # 테이블 구조 확인
            cursor.execute("PRAGMA table_info(news_articles)")
            columns = cursor.fetchall()
            
            print("📋 현재 news_articles 테이블 구조:")
            column_names = []
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
                column_names.append(col[1])
            
            return column_names
            
    except Exception as e:
        print(f"❌ 테이블 구조 확인 실패: {e}")
        return None

def add_missing_columns(db_path, existing_columns):
    """누락된 컬럼들 추가"""
    
    # 필요한 모든 컬럼 정의
    required_columns = {
        'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
        'stock_code': 'TEXT NOT NULL',
        'stock_name': 'TEXT NOT NULL', 
        'title': 'TEXT NOT NULL',
        'link': 'TEXT NOT NULL UNIQUE',
        'description': 'TEXT',
        'content': 'TEXT',
        'pub_date': 'TEXT',
        'source': 'TEXT',
        'sentiment_score': 'REAL DEFAULT 0.0',
        'sentiment_label': 'TEXT',
        'keywords': 'TEXT',
        'view_count': 'INTEGER DEFAULT 0',
        'comment_count': 'INTEGER DEFAULT 0',
        'quality_issues': 'TEXT',
        'is_verified': 'BOOLEAN DEFAULT 0',
        'collected_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
    }
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("\n🔧 누락된 컬럼 추가 중...")
            
            for col_name, col_def in required_columns.items():
                if col_name not in existing_columns:
                    # PRIMARY KEY나 UNIQUE 제약이 있는 컬럼은 추가할 수 없으므로 스키프
                    if 'PRIMARY KEY' in col_def or 'UNIQUE' in col_def:
                        continue
                    
                    try:
                        # DEFAULT 값이 있는 컬럼 정의에서 DEFAULT 부분만 추출
                        if 'DEFAULT' in col_def:
                            col_type = col_def.split('DEFAULT')[0].strip()
                            default_value = col_def.split('DEFAULT')[1].strip()
                            add_query = f"ALTER TABLE news_articles ADD COLUMN {col_name} {col_type} DEFAULT {default_value}"
                        else:
                            add_query = f"ALTER TABLE news_articles ADD COLUMN {col_name} {col_def}"
                        
                        cursor.execute(add_query)
                        print(f"  ✅ {col_name} 컬럼 추가 완료")
                        
                    except Exception as e:
                        print(f"  ⚠️ {col_name} 컬럼 추가 실패: {e}")
            
            conn.commit()
            print("✅ 컬럼 추가 완료!")
            
    except Exception as e:
        print(f"❌ 컬럼 추가 실패: {e}")

def recreate_news_table(db_path):
    """뉴스 테이블 완전 재생성"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 기존 데이터 백업
            print("💾 기존 데이터 백업 중...")
            try:
                cursor.execute("""
                    CREATE TABLE news_articles_backup AS 
                    SELECT * FROM news_articles
                """)
                
                # 백업된 데이터 개수 확인
                cursor.execute("SELECT COUNT(*) FROM news_articles_backup")
                backup_count = cursor.fetchone()[0]
                print(f"  📊 백업된 뉴스: {backup_count:,}건")
                
            except Exception as e:
                print(f"  ⚠️ 백업 실패 (기존 데이터 없음): {e}")
                backup_count = 0
            
            # 2. 기존 테이블 삭제
            print("🗑️ 기존 테이블 삭제 중...")
            cursor.execute("DROP TABLE IF EXISTS news_articles")
            
            # 3. 새 테이블 생성
            print("🆕 새 테이블 생성 중...")
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
                    is_verified BOOLEAN DEFAULT 0,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 4. 인덱스 생성
            print("📊 인덱스 생성 중...")
            cursor.execute('CREATE INDEX idx_news_stock_code ON news_articles(stock_code)')
            cursor.execute('CREATE INDEX idx_news_pub_date ON news_articles(pub_date)')
            cursor.execute('CREATE INDEX idx_news_collected_at ON news_articles(collected_at)')
            cursor.execute('CREATE INDEX idx_news_link ON news_articles(link)')
            
            # 5. 백업 데이터 복구
            if backup_count > 0:
                print("📥 백업 데이터 복구 중...")
                
                # 공통 컬럼만 복구
                cursor.execute("""
                    INSERT INTO news_articles (
                        stock_code, stock_name, title, link, description, 
                        content, pub_date, source, 
                        sentiment_score, sentiment_label, keywords,
                        view_count, comment_count, collected_at
                    )
                    SELECT 
                        COALESCE(stock_code, ''),
                        COALESCE(stock_name, ''),
                        COALESCE(title, ''),
                        COALESCE(link, ''),
                        COALESCE(description, ''),
                        COALESCE(content, ''),
                        COALESCE(pub_date, ''),
                        COALESCE(source, ''),
                        COALESCE(sentiment_score, 0.0),
                        sentiment_label,
                        keywords,
                        COALESCE(view_count, 0),
                        COALESCE(comment_count, 0),
                        COALESCE(collected_at, datetime('now'))
                    FROM news_articles_backup
                """)
                
                # 복구된 데이터 개수 확인
                cursor.execute("SELECT COUNT(*) FROM news_articles")
                restored_count = cursor.fetchone()[0]
                print(f"  📊 복구된 뉴스: {restored_count:,}건")
                
                # 백업 테이블 삭제
                cursor.execute("DROP TABLE news_articles_backup")
            
            conn.commit()
            print("✅ 테이블 재생성 완료!")
            
    except Exception as e:
        print(f"❌ 테이블 재생성 실패: {e}")

def fix_news_collector_code():
    """뉴스 수집 코드 수정 가이드 출력"""
    print("\n📝 뉴스 수집 코드 수정 가이드:")
    print("=" * 50)
    
    fix_guide = """
examples/basic_examples/06_full_news_collector.py 파일에서 
save_news_batch 함수를 다음과 같이 수정하세요:

def save_news_batch(self, news_list: List[Dict]) -> int:
    if not news_list:
        return 0
    
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.cursor()
        saved_count = 0
        
        for news in news_list:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO news_articles 
                    (stock_code, stock_name, title, link, description, 
                     content, pub_date, source, is_verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    news['stock_code'],
                    news['stock_name'], 
                    news['title'],
                    news['link'],
                    news['description'],
                    news['content'],
                    news['pub_date'],
                    news['source'],
                    1  # is_verified = True
                ))
                
                if cursor.rowcount > 0:
                    saved_count += 1
                    
            except sqlite3.Error as e:
                logger.error(f"저장 실패 - {news['title']}: {e}")
        
        conn.commit()
        return saved_count
"""
    
    print(fix_guide)

def main():
    """메인 실행 함수"""
    print("🔧 뉴스 데이터베이스 완전 수정 도구")
    print("=" * 60)
    
    # 1. 데이터베이스 찾기
    db_path = find_news_database()
    print(f"📁 데이터베이스 경로: {db_path}")
    
    if not db_path.exists():
        print("❌ 데이터베이스 파일이 없습니다.")
        print("🆕 새 데이터베이스를 생성하시겠습니까?")
        
        choice = input("새 DB 생성? (y/N): ").strip().lower()
        if choice == 'y':
            recreate_news_table(db_path)
            return
        else:
            print("❌ 작업을 취소했습니다.")
            return
    
    # 2. 현재 구조 확인
    existing_columns = check_table_structure(db_path)
    if existing_columns is None:
        print("🆕 테이블이 없으므로 새로 생성합니다.")
        recreate_news_table(db_path)
        return
    
    # 3. 수정 방법 선택
    print(f"\n🔧 수정 방법을 선택하세요:")
    print("1. 누락된 컬럼만 추가 (빠른 수정)")
    print("2. 테이블 완전 재생성 (안전한 수정)")
    print("3. 코드 수정 가이드만 보기")
    
    choice = input("\n선택 (1-3): ").strip()
    
    if choice == '1':
        add_missing_columns(db_path, existing_columns)
        
    elif choice == '2':
        confirm = input("⚠️ 테이블을 재생성합니다. 데이터는 백업 후 복구됩니다. 계속? (y/N): ").strip().lower()
        if confirm == 'y':
            recreate_news_table(db_path)
        else:
            print("❌ 취소되었습니다.")
            
    elif choice == '3':
        fix_news_collector_code()
        
    else:
        print("❌ 잘못된 선택입니다.")
    
    # 4. 최종 확인
    print("\n📋 수정 후 테이블 구조:")
    final_columns = check_table_structure(db_path)
    
    if final_columns:
        missing_required = []
        required = ['stock_code', 'stock_name', 'title', 'link', 'quality_issues', 'is_verified']
        
        for req_col in required:
            if req_col not in final_columns:
                missing_required.append(req_col)
        
        if missing_required:
            print(f"⚠️ 여전히 누락된 컬럼: {', '.join(missing_required)}")
        else:
            print("✅ 모든 필수 컬럼이 존재합니다!")
    
    print(f"\n🎉 작업 완료! 이제 뉴스 수집을 다시 실행해보세요:")
    print(f"python examples/basic_examples/06_full_news_collector.py")

if __name__ == "__main__":
    main()