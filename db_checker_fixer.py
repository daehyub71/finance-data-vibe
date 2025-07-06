"""
데이터베이스 파일 위치 확인 및 뉴스 제목 수정 스크립트
"""

import os
import sqlite3
import re
from pathlib import Path

def find_database_files():
    """프로젝트 내 모든 데이터베이스 파일 찾기"""
    print("🔍 데이터베이스 파일 검색 중...")
    
    project_root = Path.cwd()
    db_files = []
    
    # .db 파일 찾기
    for db_file in project_root.rglob('*.db'):
        size_mb = db_file.stat().st_size / (1024 * 1024)
        db_files.append({
            'path': str(db_file),
            'size_mb': round(size_mb, 1),
            'relative_path': str(db_file.relative_to(project_root))
        })
    
    print(f"📊 발견된 데이터베이스 파일: {len(db_files)}개")
    for db in db_files:
        print(f"  📁 {db['relative_path']} ({db['size_mb']} MB)")
    
    return db_files

def check_news_tables(db_path):
    """데이터베이스에 뉴스 테이블이 있는지 확인"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 테이블 목록 조회
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # 뉴스 관련 테이블 찾기
            news_tables = [table for table in tables if 'news' in table.lower()]
            
            if news_tables:
                print(f"\n📰 뉴스 테이블 발견: {news_tables}")
                
                for table in news_tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"  📊 {table}: {count:,}건")
                
                return True, news_tables
            else:
                print(f"  ❌ 뉴스 테이블 없음")
                return False, []
                
    except Exception as e:
        print(f"  ❌ DB 접근 실패: {e}")
        return False, []

def clean_text_advanced(text):
    """고급 텍스트 정제 함수"""
    if not text:
        return ""
    
    # 1. HTML 태그 제거
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # 2. HTML 엔티티 디코딩
    import html
    text = html.unescape(text)
    
    # 3. 중복 단어 패턴 제거 (핵심!)
    # "SK하이닉스SK하이닉스" -> "SK하이닉스"
    text = re.sub(r'([가-힣A-Za-z0-9]+)\1+', r'\1', text)
    
    # 4. 3글자 이상 반복 패턴 제거
    def remove_repeating_patterns(text):
        for length in range(3, 11):
            pattern = f'(.{{{length}}})(\\1)+'
            text = re.sub(pattern, r'\1', text)
        return text
    
    text = remove_repeating_patterns(text)
    
    # 5. 불필요한 문구 제거
    patterns_to_remove = [
        r'// flash 오류를 우회하기 위한 함수 추가.*',
        r'본 기사는.*?입니다',
        r'저작권자.*?무단.*?금지',
        r'기자\s*=.*?기자',
        r'^\s*\[.*?\]\s*',
        r'\s*\[.*?\]\s*$',
        r'무단전재.*?금지',
        r'ⓒ.*?무단.*?금지'
    ]
    
    for pattern in patterns_to_remove:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # 6. 여러 공백을 하나로
    text = re.sub(r'\s+', ' ', text)
    
    # 7. 연속된 같은 단어 제거
    words = text.split()
    cleaned_words = []
    prev_word = ""
    
    for word in words:
        if word != prev_word:
            cleaned_words.append(word)
        prev_word = word
    
    text = ' '.join(cleaned_words)
    
    return text.strip()

def fix_news_titles_in_db(db_path, table_name):
    """데이터베이스의 뉴스 제목 중복 문자열 수정"""
    print(f"\n🔧 {db_path}의 {table_name} 테이블 뉴스 제목 수정 중...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 제목 컬럼 확인
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            
            title_column = None
            for col in ['title', 'Title', 'headline', 'news_title']:
                if col in columns:
                    title_column = col
                    break
            
            if not title_column:
                print(f"  ❌ 제목 컬럼을 찾을 수 없습니다. 사용 가능한 컬럼: {columns}")
                return
            
            print(f"  📝 제목 컬럼: {title_column}")
            
            # 중복 문자열이 있는 뉴스 조회
            cursor.execute(f"""
                SELECT rowid, {title_column} 
                FROM {table_name} 
                WHERE {title_column} LIKE '%SK하이닉스SK하이닉스%' 
                   OR {title_column} LIKE '%삼성전자삼성전자%'
                   OR {title_column} LIKE '%LG전자LG전자%'
                   OR {title_column} LIKE '%LGSK%'
                   OR {title_column} LIKE '%카카오카카오%'
                   OR {title_column} LIKE '%현대차현대차%'
            """)
            
            problematic_news = cursor.fetchall()
            
            print(f"  🔍 중복 문자열이 있는 뉴스: {len(problematic_news)}건")
            
            if len(problematic_news) == 0:
                print("  ✅ 수정할 뉴스가 없습니다.")
                return
            
            fixed_count = 0
            for row_id, title in problematic_news:
                # 고급 텍스트 정제 적용
                fixed_title = clean_text_advanced(title)
                
                if fixed_title != title:
                    cursor.execute(f"""
                        UPDATE {table_name} 
                        SET {title_column} = ? 
                        WHERE rowid = ?
                    """, (fixed_title, row_id))
                    
                    fixed_count += 1
                    print(f"    수정: {title[:50]}... -> {fixed_title[:50]}...")
            
            conn.commit()
            print(f"  ✅ {fixed_count}건의 뉴스 제목 수정 완료")
            
    except Exception as e:
        print(f"  ❌ 뉴스 제목 수정 실패: {e}")

def main():
    """메인 실행 함수"""
    print("🚀 데이터베이스 파일 검색 및 뉴스 제목 수정 시작")
    print("=" * 60)
    
    # 1. 데이터베이스 파일 찾기
    db_files = find_database_files()
    
    if not db_files:
        print("❌ 데이터베이스 파일을 찾을 수 없습니다.")
        return
    
    # 2. 각 데이터베이스에서 뉴스 테이블 확인 및 수정
    total_fixed = 0
    
    for db_file in db_files:
        print(f"\n📁 {db_file['relative_path']} 검사 중...")
        
        has_news, news_tables = check_news_tables(db_file['path'])
        
        if has_news:
            for table in news_tables:
                fix_news_titles_in_db(db_file['path'], table)
                total_fixed += 1
    
    print(f"\n🎉 완료! 총 {total_fixed}개 테이블의 뉴스 제목을 수정했습니다.")

if __name__ == "__main__":
    main()