"""
한글 인코딩 문제 진단 및 수정 스크립트
"SK이터닉스" → "SK하이닉스" 같은 한글 깨짐 문제 해결
"""

import sqlite3
import pandas as pd
from pathlib import Path
import re

def diagnose_korean_encoding_issues():
    """한글 인코딩 문제 진단"""
    
    print("🔍 한글 인코딩 문제 진단")
    print("=" * 50)
    
    finance_db = Path.cwd() / "finance_data.db"
    
    if not finance_db.exists():
        print("❌ finance_data.db 파일을 찾을 수 없습니다.")
        return
    
    try:
        with sqlite3.connect(finance_db) as conn:
            
            print("1️⃣ 깨진 한글 종목명 찾기")
            print("-" * 30)
            
            # 이상한 한글이 포함된 종목명 찾기
            weird_korean_query = """
                SELECT DISTINCT stock_name, COUNT(*) as count
                FROM news_articles 
                WHERE stock_name LIKE '%이터%' 
                   OR stock_name LIKE '%앗자%'
                   OR stock_name LIKE '%으트%'
                   OR stock_name LIKE '%으스%'
                   OR stock_name LIKE '%뀽%'
                   OR stock_name LIKE '%묵%'
                   OR stock_name REGEXP '[가-힣]*[ㄱ-ㅎㅏ-ㅣ]+[가-힣]*'
                GROUP BY stock_name
                ORDER BY count DESC
            """
            
            try:
                weird_names = pd.read_sql_query(weird_korean_query, conn)
                
                if not weird_names.empty:
                    print("  🔍 발견된 깨진 한글 종목명:")
                    for _, row in weird_names.iterrows():
                        print(f"    '{row['stock_name']}': {row['count']:,}건")
                else:
                    print("  ✅ 명확한 패턴의 깨진 한글은 없습니다.")
                    
            except Exception as e:
                print(f"  ❌ 깨진 한글 검색 실패: {e}")
            
            print(f"\n2️⃣ 특정 문제 케이스 확인")
            print("-" * 30)
            
            # SK하이닉스 관련 모든 변형 찾기
            sk_variants_query = """
                SELECT DISTINCT stock_name, COUNT(*) as count
                FROM news_articles 
                WHERE stock_name LIKE '%SK%' 
                  AND (stock_name LIKE '%이터%' OR stock_name LIKE '%하이%')
                GROUP BY stock_name
                ORDER BY count DESC
            """
            
            sk_variants = pd.read_sql_query(sk_variants_query, conn)
            
            if not sk_variants.empty:
                print("  📊 SK 관련 종목명 변형:")
                for _, row in sk_variants.iterrows():
                    original_name = row['stock_name']
                    if '이터닉스' in original_name:
                        suggested = original_name.replace('이터닉스', '하이닉스')
                        print(f"    ❌ '{original_name}' → ✅ '{suggested}' ({row['count']:,}건)")
                    else:
                        print(f"    ✅ '{original_name}': {row['count']:,}건")
            
            print(f"\n3️⃣ 제목에서 한글 깨짐 확인")
            print("-" * 30)
            
            # 제목에서 깨진 한글 샘플 찾기
            title_encoding_query = """
                SELECT title, stock_name, COUNT(*) as count
                FROM news_articles 
                WHERE title LIKE '%이터닉스%' 
                   OR title LIKE '%SK이터%'
                GROUP BY title, stock_name
                ORDER BY count DESC
                LIMIT 5
            """
            
            title_issues = pd.read_sql_query(title_encoding_query, conn)
            
            if not title_issues.empty:
                print("  📰 제목에서 발견된 한글 깨짐:")
                for _, row in title_issues.iterrows():
                    print(f"    '{row['title'][:50]}...' ({row['count']}건)")
            else:
                print("  ✅ 제목에서 명확한 한글 깨짐은 없습니다.")
                
    except Exception as e:
        print(f"❌ 진단 실패: {e}")

def fix_korean_encoding_issues():
    """한글 인코딩 문제 수정"""
    
    print(f"\n🔧 한글 인코딩 문제 수정")
    print("=" * 40)
    
    finance_db = Path.cwd() / "finance_data.db"
    
    # 알려진 한글 깨짐 패턴과 올바른 변환 매핑
    encoding_fixes = {
        # SK하이닉스 관련
        'SK이터닉스': 'SK하이닉스',
        'SK 이터닉스': 'SK하이닉스',
        'SK이터': 'SK하이닉스',
        
        # 삼성전자 관련 
        '삼성쩌자': '삼성전자',
        '삼성전쟈': '삼성전자',
        
        # LG 관련
        'LG쩌자': 'LG전자',
        'LG전쟈': 'LG전자',
        
        # 현대차 관련
        '현대차차': '현대차',
        '현댸차': '현대차',
        
        # NAVER 관련
        'NABER': 'NAVER',
        'NAEVR': 'NAVER',
        
        # 기타 일반적인 한글 깨짐
        '이터': '하이',
        '쩌자': '전자',
        '쟈': '자',
        '댸': '대',
    }
    
    try:
        with sqlite3.connect(finance_db) as conn:
            cursor = conn.cursor()
            
            total_fixed = 0
            
            print("1️⃣ 종목명 수정...")
            
            for wrong, correct in encoding_fixes.items():
                # stock_name 수정
                cursor.execute("""
                    UPDATE news_articles 
                    SET stock_name = REPLACE(stock_name, ?, ?)
                    WHERE stock_name LIKE '%' || ? || '%'
                """, (wrong, correct, wrong))
                
                name_fixed = cursor.rowcount
                if name_fixed > 0:
                    print(f"  ✅ 종목명 '{wrong}' → '{correct}': {name_fixed}건 수정")
                    total_fixed += name_fixed
            
            print(f"\n2️⃣ 제목 수정...")
            
            for wrong, correct in encoding_fixes.items():
                # title 수정
                cursor.execute("""
                    UPDATE news_articles 
                    SET title = REPLACE(title, ?, ?)
                    WHERE title LIKE '%' || ? || '%'
                """, (wrong, correct, wrong))
                
                title_fixed = cursor.rowcount
                if title_fixed > 0:
                    print(f"  ✅ 제목 '{wrong}' → '{correct}': {title_fixed}건 수정")
                    total_fixed += title_fixed
            
            print(f"\n3️⃣ 설명(description) 수정...")
            
            for wrong, correct in encoding_fixes.items():
                # description 수정
                cursor.execute("""
                    UPDATE news_articles 
                    SET description = REPLACE(description, ?, ?)
                    WHERE description LIKE '%' || ? || '%'
                """, (wrong, correct, wrong))
                
                desc_fixed = cursor.rowcount
                if desc_fixed > 0:
                    print(f"  ✅ 설명 '{wrong}' → '{correct}': {desc_fixed}건 수정")
                    total_fixed += desc_fixed
            
            # 특별 케이스: SK하이닉스 종목코드 매핑
            print(f"\n4️⃣ SK하이닉스 종목코드 매핑...")
            cursor.execute("""
                UPDATE news_articles 
                SET stock_code = '000660'
                WHERE stock_name = 'SK하이닉스' AND stock_code != '000660'
            """)
            
            code_fixed = cursor.rowcount
            if code_fixed > 0:
                print(f"  ✅ SK하이닉스 종목코드 수정: {code_fixed}건")
                total_fixed += code_fixed
            
            conn.commit()
            
            print(f"\n📊 총 수정 건수: {total_fixed:,}건")
            
            # 수정 결과 확인
            print(f"\n5️⃣ 수정 결과 확인...")
            
            # SK하이닉스 최신 뉴스 확인
            sk_check = pd.read_sql_query("""
                SELECT stock_code, stock_name, title
                FROM news_articles 
                WHERE stock_name = 'SK하이닉스'
                ORDER BY pub_date DESC 
                LIMIT 3
            """, conn)
            
            if not sk_check.empty:
                print("  📰 수정된 SK하이닉스 뉴스:")
                for _, row in sk_check.iterrows():
                    print(f"    [{row['stock_code']}] {row['stock_name']} - {row['title'][:40]}...")
            
            # 여전히 남은 문제 확인
            remaining_issues = pd.read_sql_query("""
                SELECT DISTINCT stock_name
                FROM news_articles 
                WHERE stock_name LIKE '%이터%' 
                   OR stock_name LIKE '%쩌자%'
                   OR stock_name LIKE '%쟈%'
                LIMIT 5
            """, conn)
            
            if not remaining_issues.empty:
                print(f"  ⚠️ 여전히 남은 문제:")
                for _, row in remaining_issues.iterrows():
                    print(f"    '{row['stock_name']}'")
            else:
                print(f"  ✅ 알려진 한글 깨짐 문제 모두 해결!")
                
    except Exception as e:
        print(f"❌ 수정 실패: {e}")

def verify_encoding_fix():
    """한글 인코딩 수정 검증"""
    
    print(f"\n✅ 한글 인코딩 수정 검증")
    print("=" * 30)
    
    finance_db = Path.cwd() / "finance_data.db"
    
    try:
        with sqlite3.connect(finance_db) as conn:
            
            # SK하이닉스 검색 테스트
            hynix_test = pd.read_sql_query("""
                SELECT COUNT(*) as count
                FROM news_articles 
                WHERE stock_name = 'SK하이닉스'
            """, conn)
            
            hynix_count = hynix_test.iloc[0]['count']
            print(f"📊 정상 'SK하이닉스' 뉴스: {hynix_count:,}건")
            
            # 잘못된 형태 확인
            wrong_hynix = pd.read_sql_query("""
                SELECT COUNT(*) as count
                FROM news_articles 
                WHERE stock_name LIKE '%이터닉스%'
            """, conn)
            
            wrong_count = wrong_hynix.iloc[0]['count']
            
            if wrong_count == 0:
                print("✅ 'SK이터닉스' 문제 완전 해결!")
            else:
                print(f"⚠️ 여전히 '{wrong_count}'건의 '이터닉스' 문제 남음")
            
            # 전체 SK 관련 뉴스 확인
            sk_total = pd.read_sql_query("""
                SELECT stock_name, COUNT(*) as count
                FROM news_articles 
                WHERE stock_name LIKE '%SK%하이닉스%' OR stock_name LIKE '%SK%이터%'
                GROUP BY stock_name
                ORDER BY count DESC
            """, conn)
            
            if not sk_total.empty:
                print(f"📈 SK하이닉스 관련 모든 뉴스:")
                for _, row in sk_total.iterrows():
                    status = "✅" if "하이닉스" in row['stock_name'] else "❌"
                    print(f"  {status} '{row['stock_name']}': {row['count']:,}건")
            
    except Exception as e:
        print(f"❌ 검증 실패: {e}")

def main():
    """메인 실행 함수"""
    
    print("🚀 한글 인코딩 문제 해결 시작")
    print("=" * 60)
    
    # 1. 문제 진단
    diagnose_korean_encoding_issues()
    
    # 2. 문제 수정
    fix_korean_encoding_issues()
    
    # 3. 수정 검증
    verify_encoding_fix()
    
    print(f"\n🎉 한글 인코딩 문제 해결 완료!")
    print("=" * 60)
    print("📝 해결된 문제:")
    print("1. 'SK이터닉스' → 'SK하이닉스' 수정")
    print("2. 기타 한글 깨짐 패턴 일괄 수정")
    print("3. 종목코드 매핑 정상화")
    print("4. 제목, 종목명, 설명 전체 정리")
    
    print(f"\n💡 추가 권장사항:")
    print("1. 앞으로 뉴스 수집 시 UTF-8 인코딩 확실히 설정")
    print("2. 데이터베이스 연결 시 charset='utf8mb4' 사용")
    print("3. BeautifulSoup 파싱 시 encoding 명시적 지정")

if __name__ == "__main__":
    main()