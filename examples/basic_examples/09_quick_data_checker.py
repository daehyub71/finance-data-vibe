"""
examples/basic_examples/09_quick_data_checker.py

빠른 데이터 확인 및 샘플 생성 도구 (수정 버전)
✅ 현재 데이터베이스 상태 완전 분석
✅ 뉴스 데이터 존재 여부 확인
✅ 샘플 감정 분석 데이터 생성 (테스트용)
✅ 실제 데이터로 워런 버핏 시스템 즉시 테스트
✅ 통합된 데이터베이스 구조와 호환
"""

import sys
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import random

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def check_database_status():
    """📊 데이터베이스 상태 완전 분석"""
    
    db_path = project_root / "finance_data.db"
    
    print("🔍 Finance Data Vibe 데이터베이스 상태 분석")
    print("=" * 60)
    
    if not db_path.exists():
        print("❌ finance_data.db 파일이 없습니다!")
        print("\n🚀 해결 방법:")
        print("1. python examples/basic_examples/06_full_news_collector.py")
        print("2. 메뉴에서 '1. 테스트 모드' 선택")
        return False
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 테이블 목록 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            print(f"📋 발견된 테이블: {len(tables)}개")
            for table in tables:
                print(f"   - {table}")
            
            # 2. 각 테이블 데이터 개수 확인
            print(f"\n📊 테이블별 데이터 현황:")
            
            table_status = {}
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    table_status[table] = count
                    print(f"   📄 {table}: {count:,}건")
                except Exception as e:
                    print(f"   ❌ {table}: 조회 실패 ({e})")
                    table_status[table] = 0
            
            # 3. news_articles 테이블 상세 분석
            if 'news_articles' in tables and table_status['news_articles'] > 0:
                print(f"\n📰 뉴스 데이터 상세 분석:")
                
                # 뉴스 테이블 컬럼 확인
                cursor.execute("PRAGMA table_info(news_articles)")
                columns = [row[1] for row in cursor.fetchall()]
                print(f"   컬럼: {', '.join(columns)}")
                
                # 감정 분석 완료 여부 확인
                sentiment_columns = ['sentiment_score', 'sentiment_label', 'news_category', 'long_term_relevance']
                missing_sentiment_cols = [col for col in sentiment_columns if col not in columns]
                
                if missing_sentiment_cols:
                    print(f"   ❌ 누락된 감정분석 컬럼: {missing_sentiment_cols}")
                    print(f"   🔧 해결방법: python examples/basic_examples/08_db_migration_sentiment.py")
                    return False
                else:
                    print(f"   ✅ 감정분석 컬럼 모두 존재")
                
                # 감정 분석 완료된 뉴스 개수
                cursor.execute("SELECT COUNT(*) FROM news_articles WHERE sentiment_score IS NOT NULL AND sentiment_score != 0.0")
                analyzed_count = cursor.fetchone()[0]
                
                print(f"   📈 감정분석 완료: {analyzed_count:,}건")
                print(f"   ⏳ 감정분석 대기: {table_status['news_articles'] - analyzed_count:,}건")
                
                if analyzed_count == 0:
                    print(f"   🎯 상태: 감정분석 실행 필요")
                    return 'need_sentiment_analysis'
                else:
                    print(f"   ✅ 상태: 감정분석 데이터 존재")
                    return 'has_sentiment_data'
            
            # 4. stock_info 테이블 확인
            if 'stock_info' in tables:
                cursor.execute("SELECT COUNT(*) FROM stock_info")
                stock_count = cursor.fetchone()[0]
                print(f"\n📈 주식 정보: {stock_count:,}개 종목")
                
                if stock_count > 0:
                    cursor.execute("SELECT code, name FROM stock_info LIMIT 5")
                    sample_stocks = cursor.fetchall()
                    print(f"   샘플: {', '.join([f'{code}({name})' for code, name in sample_stocks])}")
            
            return True
            
    except Exception as e:
        print(f"❌ 데이터베이스 분석 실패: {e}")
        return False

def create_sample_sentiment_data():
    """🧪 샘플 감정분석 데이터 생성 (테스트용)"""
    
    db_path = project_root / "finance_data.db"
    
    print("🧪 샘플 감정분석 데이터 생성 중...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 뉴스 데이터 존재 확인
            cursor.execute("SELECT COUNT(*) FROM news_articles")
            total_news = cursor.fetchone()[0]
            
            if total_news == 0:
                print("❌ 뉴스 데이터가 없습니다!")
                print("🚀 먼저 뉴스 수집을 실행하세요:")
                print("   python examples/basic_examples/06_full_news_collector.py")
                return False
            
            # 2. 감정분석 안된 뉴스들 샘플링
            cursor.execute("""
                SELECT id, stock_code, stock_name, title, content, description 
                FROM news_articles 
                WHERE (sentiment_score IS NULL OR sentiment_score = 0.0)
                ORDER BY RANDOM() 
                LIMIT 100
            """)
            
            sample_news = cursor.fetchall()
            
            if not sample_news:
                print("✅ 모든 뉴스가 이미 감정분석 완료되었습니다!")
                return True
            
            print(f"📊 샘플 감정분석 생성: {len(sample_news)}건")
            
            # 3. 워런 버핏 스타일 샘플 감정분석 생성
            buffett_categories = ['fundamental', 'business', 'financial', 'management', 'market', 'technical', 'noise']
            sentiment_labels = ['bullish', 'positive', 'neutral', 'negative', 'bearish']
            
            updated_count = 0
            
            for news in sample_news:
                news_id, stock_code, stock_name, title, content, description = news
                
                # 제목 기반 간단한 카테고리 분류
                title_lower = (title or "").lower()
                content_lower = (content or "").lower()
                
                if any(word in title_lower for word in ['실적', '매출', '이익', 'roe', '재무']):
                    category = 'fundamental'
                    base_sentiment = random.uniform(0.1, 0.7)  # 펀더멘털은 대체로 긍정적
                elif any(word in title_lower for word in ['신사업', '사업확장', '투자', '개발']):
                    category = 'business'
                    base_sentiment = random.uniform(0.0, 0.6)
                elif any(word in title_lower for word in ['자금', '차입', '대출', '신용등급']):
                    category = 'financial'
                    base_sentiment = random.uniform(-0.2, 0.4)
                elif any(word in title_lower for word in ['차트', '기술적', '목표주가', '추천']):
                    category = 'technical'
                    base_sentiment = random.uniform(-0.3, 0.3)
                else:
                    category = random.choice(['market', 'noise'])
                    base_sentiment = random.uniform(-0.4, 0.4)
                
                # 감정 점수 생성 (-1.0 ~ 1.0)
                sentiment_score = max(-1.0, min(1.0, base_sentiment + random.uniform(-0.2, 0.2)))
                
                # 감정 라벨 결정
                if sentiment_score > 0.3:
                    sentiment_label = 'bullish'
                elif sentiment_score > 0.1:
                    sentiment_label = 'positive'
                elif sentiment_score > -0.1:
                    sentiment_label = 'neutral'
                elif sentiment_score > -0.3:
                    sentiment_label = 'negative'
                else:
                    sentiment_label = 'bearish'
                
                # 장기 투자 관련성 (0~100)
                category_relevance = {
                    'fundamental': random.randint(80, 95),
                    'business': random.randint(70, 85),
                    'financial': random.randint(75, 90),
                    'management': random.randint(60, 80),
                    'market': random.randint(30, 50),
                    'technical': random.randint(15, 35),
                    'noise': random.randint(5, 20)
                }
                
                long_term_relevance = category_relevance[category]
                
                # 데이터베이스 업데이트
                cursor.execute("""
                    UPDATE news_articles 
                    SET sentiment_score = ?, 
                        sentiment_label = ?,
                        news_category = ?,
                        long_term_relevance = ?
                    WHERE id = ?
                """, (sentiment_score, sentiment_label, category, long_term_relevance, news_id))
                
                updated_count += 1
            
            conn.commit()
            
            print(f"✅ 샘플 감정분석 생성 완료: {updated_count}건")
            
            # 4. 결과 확인
            cursor.execute("""
                SELECT sentiment_label, COUNT(*) as count
                FROM news_articles 
                WHERE sentiment_score IS NOT NULL AND sentiment_score != 0.0
                GROUP BY sentiment_label
                ORDER BY count DESC
            """)
            
            sentiment_dist = cursor.fetchall()
            
            print(f"\n📊 감정 분포:")
            for label, count in sentiment_dist:
                print(f"   {label}: {count}건")
            
            return True
            
    except Exception as e:
        print(f"❌ 샘플 데이터 생성 실패: {e}")
        return False

def create_daily_sentiment_sample():
    """📅 일별 감정지수 샘플 데이터 생성"""
    
    db_path = project_root / "finance_data.db"
    
    print("📅 일별 감정지수 샘플 데이터 생성 중...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # daily_sentiment_index 테이블 생성
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
            
            # 감정분석 완료된 뉴스 기반으로 일별 지수 계산
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
                WHERE sentiment_score IS NOT NULL AND sentiment_score != 0.0
                AND DATE(collected_at) >= DATE('now', '-30 days')
                GROUP BY stock_code, stock_name, DATE(collected_at)
                ORDER BY stock_code, date DESC
            """)
            
            daily_data = cursor.fetchall()
            
            if not daily_data:
                print("❌ 감정분석 데이터가 없어서 일별 지수를 생성할 수 없습니다.")
                return False
            
            print(f"📊 일별 데이터 처리: {len(daily_data)}건")
            
            # 일별 감정지수 계산 및 저장
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
            
            conn.commit()
            
            # 결과 확인
            cursor.execute("SELECT COUNT(*) FROM daily_sentiment_index")
            daily_count = cursor.fetchone()[0]
            
            print(f"✅ 일별 감정지수 생성 완료: {daily_count}건")
            
            # 상위 감정지수 종목 표시
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

def show_investment_signals_sample():
    """🎯 투자신호 샘플 생성 및 표시"""
    
    db_path = project_root / "finance_data.db"
    
    print("🎯 워런 버핏 투자신호 샘플 생성...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 감정분석 완료된 종목별 신호 생성 (collected_at 기준으로 수정)
            cursor.execute("""
                SELECT 
                    na.stock_code,
                    na.stock_name,
                    COUNT(*) as total_news,
                    COUNT(CASE WHEN na.news_category = 'fundamental' THEN 1 END) as fundamental_news,
                    AVG(na.sentiment_score) as avg_sentiment,
                    AVG(CASE WHEN na.news_category = 'fundamental' THEN na.sentiment_score END) as fundamental_sentiment,
                    AVG(na.long_term_relevance) as avg_relevance,
                    MAX(na.sentiment_score) as max_sentiment,
                    MIN(na.sentiment_score) as min_sentiment
                FROM news_articles na
                WHERE na.sentiment_score IS NOT NULL AND na.sentiment_score != 0.0
                AND DATE(na.collected_at) >= DATE('now', '-7 days')
                GROUP BY na.stock_code, na.stock_name
                HAVING fundamental_news >= 1
                ORDER BY fundamental_sentiment DESC NULLS LAST, avg_relevance DESC
                LIMIT 20
            """)
            
            signals_data = cursor.fetchall()
            
            if not signals_data:
                print("❌ 투자신호 생성할 데이터가 없습니다.")
                return False
            
            print(f"🚀 워런 버핏 투자신호 (상위 {len(signals_data)}개):")
            print("=" * 80)
            
            for row in signals_data:
                (stock_code, stock_name, total_news, fundamental_news, avg_sentiment,
                 fundamental_sentiment, avg_relevance, max_sentiment, min_sentiment) = row
                
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

def quick_sentiment_analysis():
    """⚡ 빠른 감정분석 실행 (소량)"""
    
    print("⚡ 빠른 감정분석 실행 중...")
    
    try:
        # 07_buffett_sentiment_analyzer.py 파일에서 직접 import
        sys.path.append(str(project_root / "examples" / "basic_examples"))

        # BuffettSentimentAnalyzer 클래스 임포트 시도
        try:
            from buffett_sentiment_analyzer import BuffettSentimentAnalyzer
        except ImportError:
            try:
                import importlib.util
                module_path = project_root / "examples" / "basic_examples" / "buffett_sentiment_analyzer.py"
                spec = importlib.util.spec_from_file_location("buffett_sentiment_analyzer", str(module_path))
                buffett_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(buffett_module)
                BuffettSentimentAnalyzer = buffett_module.BuffettSentimentAnalyzer
            except Exception:
                print("❌ BuffettSentimentAnalyzer를 찾을 수 없습니다.")
                print("🔧 다음 파일을 먼저 실행하세요:")
                print("   python examples/basic_examples/07_buffett_sentiment_analyzer.py")
                return False
        
        analyzer = BuffettSentimentAnalyzer()
        
        # 소량 감정분석 실행
        results = analyzer.analyze_news_batch(limit=50)
        
        if not results.empty:
            print(f"✅ 빠른 감정분석 완료: {len(results)}건")
            
            # 일별 감정지수 계산
            daily_results = analyzer.calculate_daily_sentiment_index(days=7)
            
            if not daily_results.empty:
                print(f"✅ 일별 감정지수 계산 완료: {len(daily_results)}건")
            
            return True
        else:
            print("❌ 감정분석할 데이터가 없습니다.")
            return False
            
    except Exception as e:
        print(f"❌ 빠른 감정분석 실패: {e}")
        print(f"🔧 수동으로 실행하세요:")
        print("   python examples/basic_examples/07_buffett_sentiment_analyzer.py")
        return False

def main():
    """메인 실행 함수"""
    
    print("🚀 Finance Data Vibe - 빠른 데이터 확인 및 샘플 생성 도구")
    print("=" * 70)
    
    while True:
        print("\n📋 빠른 분석 메뉴:")
        print("1. 📊 데이터베이스 상태 전체 분석")
        print("2. 🧪 샘플 감정분석 데이터 생성 (즉시 테스트용)")
        print("3. 📅 일별 감정지수 샘플 생성")
        print("4. 🎯 워런 버핏 투자신호 샘플 보기")
        print("5. ⚡ 빠른 감정분석 실행 (소량)")
        print("6. 🚀 전체 프로세스 (2→3→4 순서대로)")
        print("0. 종료")
        
        choice = input("\n선택 (0-6): ").strip()
        
        if choice == '0':
            print("👋 빠른 분석 도구를 종료합니다.")
            break
            
        elif choice == '1':
            # 데이터베이스 상태 분석
            status = check_database_status()
            
            if status == False:
                print("\n💡 권장 해결책:")
                print("1. 뉴스 수집: python examples/basic_examples/06_full_news_collector.py")
                print("2. DB 마이그레이션: python examples/basic_examples/08_db_migration_sentiment.py")
            elif status == 'need_sentiment_analysis':
                print("\n💡 다음 단계:")
                print("옵션 1: python examples/basic_examples/07_buffett_sentiment_analyzer.py (정식)")
                print("옵션 2: 이 도구에서 '2. 샘플 감정분석 데이터 생성' (빠른 테스트)")
            elif status == 'has_sentiment_data':
                print("\n🎉 모든 데이터 준비 완료!")
                print("💡 이제 가능한 기능:")
                print("- 일별 감정지수 계산")
                print("- 워런 버핏 투자신호 생성")
        
        elif choice == '2':
            # 샘플 감정분석 데이터 생성
            if create_sample_sentiment_data():
                print("\n🎉 샘플 데이터 생성 완료!")
                print("💡 이제 다른 기능들을 테스트할 수 있습니다.")
        
        elif choice == '3':
            # 일별 감정지수 샘플 생성
            create_daily_sentiment_sample()
        
        elif choice == '4':
            # 투자신호 샘플 보기
            show_investment_signals_sample()
        
        elif choice == '5':
            # 빠른 감정분석 실행
            quick_sentiment_analysis()
        
        elif choice == '6':
            # 전체 프로세스
            print("🚀 전체 샘플 생성 프로세스 시작...")
            
            print("\n1️⃣ 샘플 감정분석 데이터 생성...")
            if create_sample_sentiment_data():
                
                print("\n2️⃣ 일별 감정지수 계산...")
                if create_daily_sentiment_sample():
                    
                    print("\n3️⃣ 워런 버핏 투자신호 생성...")
                    if show_investment_signals_sample():
                        
                        print("\n🎉 전체 프로세스 완료!")
                        print("✅ 이제 워런 버핏 스타일 감정분석 시스템이 완전히 작동합니다!")
                        print("\n🔥 다음 단계:")
                        print("python examples/basic_examples/07_buffett_sentiment_analyzer.py")
                        print("→ 메뉴 2, 4번으로 실제 데이터 확인")
                    else:
                        print("❌ 투자신호 생성 실패")
                else:
                    print("❌ 일별 감정지수 계산 실패")
            else:
                print("❌ 샘플 데이터 생성 실패")
        
        else:
            print("❌ 올바른 번호를 선택해주세요.")

if __name__ == "__main__":
    main()