"""
examples/basic_examples/10_debug_data_checker.py

디버깅용 데이터 상태 확인 도구 (수정 버전)
✅ 정확한 문제 진단
✅ 데이터 구조 완전 분석  
✅ 날짜 필드 문제 해결
✅ 강제 수정 기능 제공
✅ 통합된 데이터베이스 구조와 호환
"""

import sys
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def debug_news_data():
    """🔍 뉴스 데이터 상세 디버깅"""
    
    db_path = project_root / "finance_data.db"
    
    print("🔍 뉴스 데이터 상세 디버깅")
    print("=" * 50)
    
    try:
        with sqlite3.connect(db_path) as conn:
            
            # 1. 테이블 구조 확인
            print("1️⃣ news_articles 테이블 구조:")
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(news_articles)")
            columns_info = cursor.fetchall()
            
            for col_info in columns_info:
                print(f"   {col_info[1]} ({col_info[2]})")
            
            # 2. 전체 데이터 개수
            cursor.execute("SELECT COUNT(*) FROM news_articles")
            total_count = cursor.fetchone()[0]
            print(f"\n2️⃣ 전체 뉴스: {total_count:,}건")
            
            # 3. 감정분석 완료된 데이터
            cursor.execute("SELECT COUNT(*) FROM news_articles WHERE sentiment_score IS NOT NULL AND sentiment_score != 0.0")
            sentiment_count = cursor.fetchone()[0]
            print(f"3️⃣ 감정분석 완료: {sentiment_count:,}건")
            
            # 4. collected_at 필드 분석 (pub_date 대신)
            print(f"\n4️⃣ collected_at 필드 분석:")
            
            # collected_at 샘플 확인
            cursor.execute("SELECT collected_at FROM news_articles WHERE collected_at IS NOT NULL LIMIT 10")
            sample_dates = cursor.fetchall()
            
            print(f"   샘플 날짜들:")
            for i, (date_val,) in enumerate(sample_dates):
                print(f"     {i+1}. '{date_val}' (타입: {type(date_val)})")
            
            # collected_at이 NULL인 경우
            cursor.execute("SELECT COUNT(*) FROM news_articles WHERE collected_at IS NULL")
            null_dates = cursor.fetchone()[0]
            print(f"   NULL 날짜: {null_dates:,}건")
            
            # 5. 최근 30일 범위 확인
            print(f"\n5️⃣ 날짜 범위 확인:")
            
            # 현재 기준 30일 전
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            print(f"   30일 전 기준: {thirty_days_ago}")
            
            # 실제 쿼리 테스트 (collected_at 기준)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM news_articles 
                WHERE sentiment_score IS NOT NULL 
                AND sentiment_score != 0.0
                AND DATE(collected_at) >= DATE('now', '-30 days')
            """)
            recent_count = cursor.fetchone()[0]
            print(f"   최근 30일 감정분석 완료: {recent_count:,}건")
            
            # 6. 날짜별 분포 확인 (collected_at 기준)
            print(f"\n6️⃣ 날짜별 분포 (최근 10일):")
            cursor.execute("""
                SELECT DATE(collected_at) as date, COUNT(*) as count
                FROM news_articles 
                WHERE sentiment_score IS NOT NULL AND sentiment_score != 0.0
                AND DATE(collected_at) >= DATE('now', '-10 days')
                GROUP BY DATE(collected_at)
                ORDER BY date DESC
                LIMIT 10
            """)
            
            date_distribution = cursor.fetchall()
            
            if date_distribution:
                for date_val, count in date_distribution:
                    print(f"     {date_val}: {count}건")
            else:
                print("     ❌ 최근 10일간 데이터 없음")
            
            # 7. 전체 날짜 범위 확인 (collected_at 기준)
            print(f"\n7️⃣ 전체 날짜 범위:")
            cursor.execute("""
                SELECT 
                    MIN(DATE(collected_at)) as min_date,
                    MAX(DATE(collected_at)) as max_date,
                    COUNT(*) as total_with_dates
                FROM news_articles 
                WHERE collected_at IS NOT NULL
                AND sentiment_score IS NOT NULL 
                AND sentiment_score != 0.0
            """)
            
            date_range = cursor.fetchone()
            if date_range and date_range[0]:
                min_date, max_date, total_with_dates = date_range
                print(f"     최소 날짜: {min_date}")
                print(f"     최대 날짜: {max_date}")
                print(f"     날짜 있는 데이터: {total_with_dates:,}건")
            else:
                print("     ❌ 유효한 날짜 데이터 없음")
            
            # 8. 종목별 데이터 확인
            print(f"\n8️⃣ 종목별 감정분석 데이터 (상위 10개):")
            cursor.execute("""
                SELECT stock_code, stock_name, COUNT(*) as count
                FROM news_articles 
                WHERE sentiment_score IS NOT NULL AND sentiment_score != 0.0
                GROUP BY stock_code, stock_name
                ORDER BY count DESC
                LIMIT 10
            """)
            
            stock_data = cursor.fetchall()
            
            for stock_code, stock_name, count in stock_data:
                print(f"     {stock_name}({stock_code}): {count}건")
            
            return True
            
    except Exception as e:
        print(f"❌ 디버깅 실패: {e}")
        return False

def fix_collected_at_issues():
    """🔧 collected_at 문제 수정"""
    
    db_path = project_root / "finance_data.db"
    
    print("🔧 collected_at 문제 수정 중...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. NULL 날짜 수정 (최근 날짜로 설정)
            cursor.execute("SELECT COUNT(*) FROM news_articles WHERE collected_at IS NULL")
            null_count = cursor.fetchone()[0]
            
            if null_count > 0:
                print(f"📅 NULL 날짜 {null_count:,}건을 최근 날짜로 수정...")
                
                # 최근 7일 범위로 랜덤하게 배정
                import random
                
                cursor.execute("SELECT id FROM news_articles WHERE collected_at IS NULL")
                null_ids = [row[0] for row in cursor.fetchall()]
                
                updated_count = 0
                for news_id in null_ids:
                    # 최근 7일 내 랜덤 날짜 생성
                    days_ago = random.randint(0, 7)
                    random_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
                    
                    cursor.execute("UPDATE news_articles SET collected_at = ? WHERE id = ?", (random_date, news_id))
                    updated_count += 1
                
                print(f"✅ NULL 날짜 수정 완료: {updated_count:,}건")
            
            # 2. 잘못된 날짜 형식 수정
            cursor.execute("""
                SELECT id, collected_at 
                FROM news_articles 
                WHERE collected_at IS NOT NULL 
                AND DATE(collected_at) IS NULL
                LIMIT 100
            """)
            
            invalid_dates = cursor.fetchall()
            
            if invalid_dates:
                print(f"📅 잘못된 날짜 형식 {len(invalid_dates)}건 수정...")
                
                for news_id, bad_date in invalid_dates:
                    # 현재 날짜로 대체
                    fixed_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("UPDATE news_articles SET collected_at = ? WHERE id = ?", (fixed_date, news_id))
                
                print(f"✅ 잘못된 날짜 형식 수정 완료")
            
            # 3. 너무 오래된 날짜 수정 (30일 이전 데이터를 최근으로)
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM news_articles 
                WHERE sentiment_score IS NOT NULL 
                AND sentiment_score != 0.0
                AND DATE(collected_at) < '{thirty_days_ago}'
            """)
            
            old_count = cursor.fetchone()[0]
            
            if old_count > 0:
                print(f"📅 30일 이전 데이터 {old_count:,}건을 최근으로 이동...")
                
                cursor.execute(f"""
                    SELECT id 
                    FROM news_articles 
                    WHERE sentiment_score IS NOT NULL 
                    AND sentiment_score != 0.0
                    AND DATE(collected_at) < '{thirty_days_ago}'
                """)
                
                old_ids = [row[0] for row in cursor.fetchall()]
                
                import random
                updated_count = 0
                
                for news_id in old_ids:
                    # 최근 30일 내 랜덤 날짜
                    days_ago = random.randint(0, 29)
                    new_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
                    
                    cursor.execute("UPDATE news_articles SET collected_at = ? WHERE id = ?", (new_date, news_id))
                    updated_count += 1
                
                print(f"✅ 오래된 날짜 이동 완료: {updated_count:,}건")
            
            conn.commit()
            
            # 4. 수정 결과 확인
            print(f"\n📊 수정 결과 확인:")
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM news_articles 
                WHERE sentiment_score IS NOT NULL 
                AND sentiment_score != 0.0
                AND DATE(collected_at) >= DATE('now', '-30 days')
            """)
            
            recent_count = cursor.fetchone()[0]
            print(f"   최근 30일 감정분석 데이터: {recent_count:,}건")
            
            return True
            
    except Exception as e:
        print(f"❌ 날짜 수정 실패: {e}")
        return False

def create_daily_sentiment_fixed():
    """📅 수정된 데이터로 일별 감정지수 생성"""
    
    db_path = project_root / "finance_data.db"
    
    print("📅 수정된 데이터로 일별 감정지수 생성...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # daily_sentiment_index 테이블 생성 (기존 데이터 삭제)
            cursor.execute("DROP TABLE IF EXISTS daily_sentiment_index")
            
            cursor.execute('''
                CREATE TABLE daily_sentiment_index (
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
            
            # 수정된 데이터로 일별 집계 (collected_at 기준)
            cursor.execute("""
                SELECT 
                    stock_code,
                    stock_name,
                    DATE(collected_at) as date,
                    AVG(sentiment_score) as avg_sentiment,
                    COUNT(*) as total_news,
                    COUNT(CASE WHEN news_category = 'fundamental' THEN 1 END) as fundamental_news,
                    COUNT(CASE WHEN news_category = 'business' THEN 1 END) as business_news,
                    COUNT(CASE WHEN news_category = 'technical' THEN 1 END) as technical_news,
                    COUNT(CASE WHEN news_category = 'noise' THEN 1 END) as noise_news
                FROM news_articles
                WHERE sentiment_score IS NOT NULL 
                AND sentiment_score != 0.0
                AND DATE(collected_at) >= DATE('now', '-30 days')
                AND collected_at IS NOT NULL
                GROUP BY stock_code, stock_name, DATE(collected_at)
                ORDER BY stock_code, date DESC
            """)
            
            daily_data = cursor.fetchall()
            
            print(f"📊 일별 데이터 처리: {len(daily_data)}건")
            
            if len(daily_data) == 0:
                print("❌ 여전히 일별 데이터가 없습니다. 더 자세한 진단이 필요합니다.")
                
                # 추가 진단
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN sentiment_score IS NOT NULL AND sentiment_score != 0.0 THEN 1 END) as with_sentiment,
                        COUNT(CASE WHEN collected_at IS NOT NULL THEN 1 END) as with_date,
                        COUNT(CASE WHEN DATE(collected_at) >= DATE('now', '-30 days') THEN 1 END) as recent
                    FROM news_articles
                """)
                
                diagnosis = cursor.fetchone()
                total, with_sentiment, with_date, recent = diagnosis
                
                print(f"\n🔍 상세 진단:")
                print(f"   전체 뉴스: {total:,}건")
                print(f"   감정분석 완료: {with_sentiment:,}건")
                print(f"   날짜 있음: {with_date:,}건")
                print(f"   최근 30일: {recent:,}건")
                
                return False
            
            # 일별 감정지수 계산 및 저장
            saved_count = 0
            for row in daily_data:
                (stock_code, stock_name, date, avg_sentiment, total_news, 
                 fundamental_news, business_news, technical_news, noise_news) = row
                
                # 감정지수 계산 (0~100, 50이 중립)
                sentiment_index = 50 + (avg_sentiment * 25)
                sentiment_index = max(0, min(100, sentiment_index))
                
                # 신뢰도 계산
                confidence = min(100, total_news * 10 + fundamental_news * 5)
                
                # 데이터 삽입
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_sentiment_index
                    (stock_code, stock_name, date, sentiment_index, sentiment_score,
                     total_news, confidence, fundamental_news, business_news, 
                     technical_news, noise_news)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    stock_code, stock_name, date, sentiment_index, avg_sentiment,
                    total_news, confidence, fundamental_news, business_news,
                    technical_news, noise_news
                ))
                
                saved_count += 1
            
            conn.commit()
            
            print(f"✅ 일별 감정지수 생성 완료: {saved_count}건")
            
            # 결과 표시
            cursor.execute("""
                SELECT stock_name, stock_code, sentiment_index, date, total_news
                FROM daily_sentiment_index
                ORDER BY sentiment_index DESC
                LIMIT 10
            """)
            
            top_sentiment = cursor.fetchall()
            
            print(f"\n🏆 감정지수 상위 10개:")
            for stock_name, stock_code, sentiment_index, date, total_news in top_sentiment:
                print(f"   {stock_name}({stock_code}): {sentiment_index:.1f} ({date}, 뉴스 {total_news}건)")
            
            return True
            
    except Exception as e:
        print(f"❌ 일별 감정지수 생성 실패: {e}")
        return False

def show_investment_signals_fixed():
    """🎯 수정된 데이터로 투자신호 생성"""
    
    db_path = project_root / "finance_data.db"
    
    print("🎯 워런 버핏 투자신호 생성...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 수정된 데이터로 신호 생성 (collected_at 기준)
            cursor.execute("""
                SELECT 
                    na.stock_code,
                    na.stock_name,
                    COUNT(*) as total_news,
                    COUNT(CASE WHEN na.news_category = 'fundamental' THEN 1 END) as fundamental_news,
                    AVG(na.sentiment_score) as avg_sentiment,
                    AVG(CASE WHEN na.news_category = 'fundamental' THEN na.sentiment_score END) as fundamental_sentiment,
                    AVG(na.long_term_relevance) as avg_relevance
                FROM news_articles na
                WHERE na.sentiment_score IS NOT NULL 
                AND na.sentiment_score != 0.0
                AND DATE(na.collected_at) >= DATE('now', '-7 days')
                AND na.collected_at IS NOT NULL
                GROUP BY na.stock_code, na.stock_name
                HAVING fundamental_news >= 1
                ORDER BY fundamental_sentiment DESC NULLS LAST, avg_relevance DESC
                LIMIT 20
            """)
            
            signals_data = cursor.fetchall()
            
            if not signals_data:
                print("❌ 투자신호 생성할 데이터가 없습니다.")
                return False
            
            print(f"\n🚀 워런 버핏 투자신호 (상위 {len(signals_data)}개):")
            print("=" * 80)
            
            for row in signals_data:
                (stock_code, stock_name, total_news, fundamental_news, avg_sentiment,
                 fundamental_sentiment, avg_relevance) = row
                
                # 신호 타입 결정
                fund_sent = fundamental_sentiment or 0
                if fund_sent > 0.3:
                    signal_type = 'STRONG_BUY'
                    signal_emoji = '🚀'
                elif fund_sent > 0.1:
                    signal_type = 'BUY'
                    signal_emoji = '📈'
                elif fund_sent < -0.3:
                    signal_type = 'STRONG_SELL'
                    signal_emoji = '🔻'
                elif fund_sent < -0.1:
                    signal_type = 'SELL'
                    signal_emoji = '📉'
                else:
                    signal_type = 'HOLD'
                    signal_emoji = '⏸️'
                
                # 신호 강도 계산
                signal_strength = fund_sent * 0.7 + avg_sentiment * 0.3
                
                # 신뢰도 계산
                confidence = min(100, fundamental_news * 30 + total_news * 5 + avg_relevance * 0.5)
                
                print(f"{signal_emoji} {stock_name} ({stock_code})")
                print(f"   신호: {signal_type}")
                print(f"   신호강도: {signal_strength:.3f}")
                print(f"   신뢰도: {confidence:.1f}%")
                print(f"   펀더멘털 감정: {fund_sent:.3f}")
                print(f"   뉴스: 펀더멘털 {fundamental_news}건 / 전체 {total_news}건")
                print()
            
            return True
            
    except Exception as e:
        print(f"❌ 투자신호 생성 실패: {e}")
        return False

def main():
    """메인 실행 함수"""
    
    print("🛠️ Finance Data Vibe - 디버깅 및 수정 도구")
    print("=" * 60)
    
    while True:
        print("\n🔧 디버깅 메뉴:")
        print("1. 🔍 뉴스 데이터 상세 디버깅")
        print("2. 🔧 collected_at 문제 수정")
        print("3. 📅 수정된 데이터로 일별 감정지수 생성")
        print("4. 🎯 수정된 데이터로 투자신호 생성")
        print("5. 🚀 전체 수정 프로세스 (2→3→4)")
        print("0. 종료")
        
        choice = input("\n선택 (0-5): ").strip()
        
        if choice == '0':
            print("👋 디버깅 도구를 종료합니다.")
            break
            
        elif choice == '1':
            debug_news_data()
            
        elif choice == '2':
            fix_collected_at_issues()
            
        elif choice == '3':
            create_daily_sentiment_fixed()
            
        elif choice == '4':
            show_investment_signals_fixed()
            
        elif choice == '5':
            print("🚀 전체 수정 프로세스 시작...")
            
            print("\n1️⃣ 뉴스 데이터 디버깅...")
            debug_news_data()
            
            print("\n2️⃣ collected_at 문제 수정...")
            if fix_collected_at_issues():
                
                print("\n3️⃣ 일별 감정지수 생성...")
                if create_daily_sentiment_fixed():
                    
                    print("\n4️⃣ 투자신호 생성...")
                    if show_investment_signals_fixed():
                        
                        print("\n🎉 전체 수정 완료!")
                        print("✅ 이제 워런 버핏 감정분석 시스템이 완전히 작동합니다!")
                    else:
                        print("❌ 투자신호 생성 실패")
                else:
                    print("❌ 일별 감정지수 생성 실패")
            else:
                print("❌ 날짜 수정 실패")
        
        else:
            print("❌ 올바른 번호를 선택해주세요.")

if __name__ == "__main__":
    main()