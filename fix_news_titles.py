"""
텍스트 정제 함수 수정 - 한글 중복 문자열 문제 해결
06_full_news_collector.py의 _clean_text 함수를 이것으로 교체하세요
"""

def _clean_text(self, text: str) -> str:
    """텍스트 정제 (한글 중복 문자열 문제 해결)"""
    
    if not text:
        return ""
    
    # 1. HTML 태그 제거 (공백으로 대체)
    import re
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # 2. HTML 엔티티 디코딩
    import html
    text = html.unescape(text)
    
    # 3. 특수 문자를 공백으로 대체
    text = re.sub(r'[&\[\]{}()\*\+\?\|\^\$\\.~`!@#%=:;",<>]', ' ', text)
    
    # 4. 숫자와 한글/영문 사이에 공백 추가
    text = re.sub(r'(\d)([가-힣])', r'\1 \2', text)
    text = re.sub(r'([가-힣])(\d)', r'\1 \2', text)
    
    # 5. 불필요한 문구 제거
    patterns_to_remove = [
        r'// flash 오류를 우회하기 위한 함수 추가.*',
        r'본 기사는.*?입니다',
        r'저작권자.*?무단.*?금지',
        r'기자\s*=.*?기자',
        r'^\s*\[.*?\]\s*',  # 시작 부분의 [태그]
        r'\s*\[.*?\]\s*$',  # 끝 부분의 [태그]
        r'무단전재.*?금지',
        r'ⓒ.*?무단.*?금지',
        r'Copyright.*?All.*?rights.*?reserved',
        r'이\s*메일.*?보내기',
        r'카카오톡.*?공유',
        r'페이스북.*?공유',
        r'트위터.*?공유'
    ]
    
    for pattern in patterns_to_remove:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # 6. 여러 공백을 하나로 통합
    text = re.sub(r'\s+', ' ', text)
    
    # 7. 중복 단어 제거 (핵심 수정 부분!)
    words = text.split()
    cleaned_words = []
    prev_word = ""
    
    for word in words:
        # 연속된 같은 단어 제거
        if word != prev_word:
            cleaned_words.append(word)
        prev_word = word
    
    text = ' '.join(cleaned_words)
    
    # 8. 중복 구문 제거 (더 정교하게)
    # 예: "SK하이닉스SK하이닉스" -> "SK하이닉스"
    text = re.sub(r'([가-힣A-Za-z0-9]+)\1+', r'\1', text)
    
    # 9. 3글자 이상 반복되는 패턴 제거
    # 예: "ABCABCABC" -> "ABC"
    def remove_repeating_patterns(text):
        # 3글자부터 10글자까지 반복 패턴 찾기
        for length in range(3, 11):
            pattern = f'(.{{{length}}})(\\1)+'
            text = re.sub(pattern, r'\1', text)
        return text
    
    text = remove_repeating_patterns(text)
    
    # 10. 최종 정리
    text = text.strip()
    
    return text

def fix_existing_news_titles():
    """기존 뉴스 제목들의 중복 문자열 수정"""
    import sqlite3
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent.parent
    db_path = project_root / "finance_data.db"
    
    if not db_path.exists():
        print("❌ 데이터베이스 파일이 없습니다.")
        return
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 중복 문자열이 있는 뉴스 조회
            cursor.execute("""
                SELECT id, title, stock_name 
                FROM news_articles 
                WHERE title LIKE '%SK하이닉스SK하이닉스%' 
                   OR title LIKE '%삼성전자삼성전자%'
                   OR title LIKE '%LG전자LG전자%'
                   OR title REGEXP '([가-힣A-Za-z0-9]{2,})\\1+'
            """)
            
            problematic_news = cursor.fetchall()
            
            print(f"🔍 중복 문자열이 있는 뉴스: {len(problematic_news)}건")
            
            fixed_count = 0
            for news_id, title, stock_name in problematic_news:
                # 중복 문자열 제거
                fixed_title = re.sub(r'([가-힣A-Za-z0-9]+)\1+', r'\1', title)
                
                # 추가 정제
                fixed_title = re.sub(r'\s+', ' ', fixed_title).strip()
                
                if fixed_title != title:
                    cursor.execute("""
                        UPDATE news_articles 
                        SET title = ? 
                        WHERE id = ?
                    """, (fixed_title, news_id))
                    
                    fixed_count += 1
                    print(f"수정: {title} -> {fixed_title}")
            
            conn.commit()
            print(f"✅ {fixed_count}건의 뉴스 제목 수정 완료")
            
    except Exception as e:
        print(f"❌ 뉴스 제목 수정 실패: {e}")

# 실행 함수
def main():
    """뉴스 제목 중복 문자열 수정 실행"""
    print("🔧 뉴스 제목 중복 문자열 수정 시작...")
    fix_existing_news_titles()
    print("🎉 수정 완료!")

if __name__ == "__main__":
    main()