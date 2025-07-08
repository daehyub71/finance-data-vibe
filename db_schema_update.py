"""
데이터베이스 스키마 업데이트 스크립트
기존 news_articles 테이블에 새로운 컬럼들을 안전하게 추가합니다.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import shutil

def update_database_schema():
    """기존 데이터베이스의 스키마를 업데이트합니다."""
    
    # 프로젝트 루트 경로 설정
    project_root = Path(__file__).parent.parent.parent
    db_path = project_root / "finance_data.db"
    
    print(f"📊 데이터베이스 스키마 업데이트 시작: {db_path}")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 기존 테이블 구조 확인
            cursor.execute("PRAGMA table_info(news_articles)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            print(f"✅ 기존 컬럼들: {existing_columns}")
            
            # 2. 필요한 새 컬럼들 정의
            new_columns = [
                ('quality_score', 'REAL DEFAULT 0.0'),
                ('is_duplicate', 'INTEGER DEFAULT 0'),
                ('content_length', 'INTEGER DEFAULT 0'),
                ('keyword_relevance', 'REAL DEFAULT 0.0'),
                ('source_reliability', 'REAL DEFAULT 0.0')
            ]
            
            # 3. 누락된 컬럼들 추가
            added_columns = []
            for col_name, col_definition in new_columns:
                if col_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE news_articles ADD COLUMN {col_name} {col_definition}")
                        added_columns.append(col_name)
                        print(f"  ✅ 컬럼 추가: {col_name}")
                    except sqlite3.Error as e:
                        print(f"  ❌ 컬럼 추가 실패 ({col_name}): {e}")
                else:
                    print(f"  ⏭️  이미 존재: {col_name}")
            
            # 4. 인덱스 생성 (안전하게)
            indexes = [
                ('idx_news_quality_score', 'quality_score'),
                ('idx_news_content_length', 'content_length'),
                ('idx_news_source_reliability', 'source_reliability')
            ]
            
            for index_name, column_name in indexes:
                try:
                    cursor.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON news_articles({column_name})')
                    print(f"  ✅ 인덱스 생성: {index_name}")
                except sqlite3.Error as e:
                    print(f"  ❌ 인덱스 생성 실패 ({index_name}): {e}")
            
            conn.commit()
            
            # 5. 업데이트된 테이블 구조 확인
            cursor.execute("PRAGMA table_info(news_articles)")
            updated_columns = [row[1] for row in cursor.fetchall()]
            
            print(f"\n🎉 스키마 업데이트 완료!")
            print(f"  📊 추가된 컬럼: {added_columns}")
            print(f"  📋 전체 컬럼 수: {len(updated_columns)}개")
            print(f"  📝 최종 컬럼들: {updated_columns}")
            
            return True
            
    except Exception as e:
        print(f"❌ 데이터베이스 업데이트 실패: {e}")
        return False

def backup_database():
    """데이터베이스 백업 생성"""
    project_root = Path(__file__).parent.parent.parent
    db_path = project_root / "finance_data.db"
    backup_path = project_root / f"finance_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    
    try:
        if db_path.exists():
            shutil.copy2(db_path, backup_path)
            print(f"✅ 백업 생성: {backup_path}")
            return True
        else:
            print(f"⚠️ 원본 DB 파일이 없습니다: {db_path}")
            return False
    except Exception as e:
        print(f"❌ 백업 실패: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Finance Data Vibe - 데이터베이스 스키마 업데이트")
    print("=" * 60)
    
    # 백업 생성 여부 확인
    create_backup = input("백업을 생성하시겠습니까? (Y/n): ").strip().lower()
    if create_backup != 'n':
        backup_database()
    
    # 스키마 업데이트 실행
    confirm = input("\n데이터베이스 스키마를 업데이트하시겠습니까? (y/N): ").strip().lower()
    if confirm == 'y':
        success = update_database_schema()
        if success:
            print("\n🎉 업데이트 완료! 이제 뉴스 수집기를 다시 실행할 수 있습니다.")
        else:
            print("\n❌ 업데이트 실패. 백업에서 복원을 고려해주세요.")
    else:
        print("👋 업데이트를 취소했습니다.")