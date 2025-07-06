"""
examples/basic_examples/08_db_migration_sentiment.py

통합 감정분석 데이터베이스 마이그레이션 도구
✅ 기존 뉴스 데이터 보존
✅ 감정분석 컬럼 추가  
✅ 감정분석 및 투자신호 테이블 생성
✅ 자동 백업 및 검증
✅ 펀더멘털 플래그 설정
"""

import sys
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
import shutil

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    """데이터베이스 마이그레이션 도구"""
    
    def __init__(self):
        self.db_path = project_root / "finance_data.db"
        logger.info(f"📊 데이터베이스: {self.db_path}")
    
    def backup_database(self):
        """데이터베이스 백업"""
        
        backup_path = project_root / f"finance_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        try:
            if self.db_path.exists():
                shutil.copy2(self.db_path, backup_path)
                logger.info(f"✅ 데이터베이스 백업 완료: {backup_path}")
                return True, backup_path
            else:
                logger.error("❌ 원본 데이터베이스가 없습니다!")
                return False, None
        except Exception as e:
            logger.error(f"❌ 백업 실패: {e}")
            return False, None
    
    def check_existing_structure(self):
        """기존 데이터베이스 구조 확인"""
        
        if not self.db_path.exists():
            logger.error("❌ finance_data.db 파일이 없습니다!")
            logger.info("먼저 뉴스 수집을 실행하세요: python examples/basic_examples/06_full_news_collector.py")
            return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 테이블 목록 확인
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                logger.info(f"📋 기존 테이블: {', '.join(tables)}")
                
                # news_articles 테이블 구조 확인
                if 'news_articles' in tables:
                    cursor.execute("PRAGMA table_info(news_articles)")
                    columns = [row[1] for row in cursor.fetchall()]
                    logger.info(f"📰 news_articles 컬럼: {', '.join(columns)}")
                    
                    # 데이터 개수 확인
                    cursor.execute("SELECT COUNT(*) FROM news_articles")
                    count = cursor.fetchone()[0]
                    logger.info(f"📊 기존 뉴스 데이터: {count:,}건")
                    
                    return True
                else:
                    logger.error("❌ news_articles 테이블이 없습니다!")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 데이터베이스 확인 실패: {e}")
            return False
    
    def migrate_news_articles_table(self):
        """news_articles 테이블에 감정분석 컬럼 추가 (통합 버전)"""
        
        logger.info("🔧 news_articles 테이블 마이그레이션 중...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 기존 컬럼 확인
                cursor.execute("PRAGMA table_info(news_articles)")
                existing_columns = [row[1] for row in cursor.fetchall()]
                
                logger.info(f"📊 기존 컬럼: {', '.join(existing_columns)}")
                
                # 필요한 컬럼들 추가 (두 버전 통합)
                columns_to_add = [
                    ('sentiment_score', 'REAL DEFAULT 0.0'),
                    ('sentiment_label', 'TEXT DEFAULT "neutral"'),
                    ('news_category', 'TEXT DEFAULT "general"'), 
                    ('long_term_relevance', 'INTEGER DEFAULT 50'),
                    ('is_fundamental', 'INTEGER DEFAULT 0')
                ]
                
                added_columns = []
                for col_name, col_definition in columns_to_add:
                    if col_name not in existing_columns:
                        try:
                            cursor.execute(f"ALTER TABLE news_articles ADD COLUMN {col_name} {col_definition}")
                            added_columns.append(col_name)
                            logger.info(f"✅ 컬럼 추가: {col_name}")
                        except sqlite3.Error as e:
                            if "duplicate column name" not in str(e):
                                logger.error(f"❌ 컬럼 추가 실패 {col_name}: {e}")
                    else:
                        logger.info(f"⏭️  컬럼 이미 존재: {col_name}")
                
                # 인덱스 생성 (성능 최적화)
                indexes = [
                    ("idx_news_sentiment_score", "sentiment_score"),
                    ("idx_news_sentiment_label", "sentiment_label"),
                    ("idx_news_category", "news_category"),
                    ("idx_news_stock_date", "stock_code, pub_date"),
                    ("idx_news_relevance", "long_term_relevance"),
                    ("idx_news_fundamental", "is_fundamental")
                ]
                
                for index_name, index_columns in indexes:
                    try:
                        cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON news_articles({index_columns})")
                        logger.info(f"✅ 인덱스 생성: {index_name}")
                    except sqlite3.Error as e:
                        logger.warning(f"⚠️ 인덱스 생성 실패 ({index_name}): {e}")
                
                conn.commit()
                logger.info("✅ news_articles 테이블 마이그레이션 완료")
                
                if added_columns:
                    logger.info(f"📝 추가된 컬럼: {', '.join(added_columns)}")
                
        except Exception as e:
            logger.error(f"❌ news_articles 마이그레이션 실패: {e}")
            raise
    
    def create_sentiment_analysis_table(self):
        """일별 감정분석 테이블 생성 (통합 버전)"""
        
        logger.info("📈 sentiment_analysis 테이블 생성 중...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 원래 파일의 daily_sentiment_index와 새 파일의 sentiment_analysis 통합
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sentiment_analysis (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stock_code TEXT NOT NULL,
                        stock_name TEXT NOT NULL,
                        date TEXT NOT NULL,
                        sentiment_index REAL NOT NULL DEFAULT 50.0,
                        sentiment_score REAL NOT NULL DEFAULT 0.0,
                        positive_count INTEGER DEFAULT 0,
                        negative_count INTEGER DEFAULT 0,
                        neutral_count INTEGER DEFAULT 0,
                        total_count INTEGER DEFAULT 0,
                        fundamental_ratio REAL DEFAULT 0.0,
                        confidence REAL DEFAULT 0.0,
                        fundamental_news INTEGER DEFAULT 0,
                        business_news INTEGER DEFAULT 0,
                        technical_news INTEGER DEFAULT 0,
                        noise_news INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(stock_code, date)
                    )
                ''')
                
                # daily_sentiment_index 테이블도 생성 (호환성)
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
                
                # 인덱스 생성
                indexes = [
                    ("idx_sentiment_stock_date", "sentiment_analysis", "stock_code, date"),
                    ("idx_sentiment_index", "sentiment_analysis", "sentiment_index"),
                    ("idx_sentiment_confidence", "sentiment_analysis", "confidence"),
                    ("idx_daily_stock_code", "daily_sentiment_index", "stock_code"),
                    ("idx_daily_date", "daily_sentiment_index", "date"),
                    ("idx_daily_sentiment_index", "daily_sentiment_index", "sentiment_index"),
                    ("idx_daily_stock_date", "daily_sentiment_index", "stock_code, date")
                ]
                
                for index_name, table_name, index_columns in indexes:
                    try:
                        cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({index_columns})")
                        logger.info(f"✅ 인덱스 생성: {index_name}")
                    except sqlite3.Error as e:
                        logger.warning(f"⚠️ 인덱스 생성 실패 ({index_name}): {e}")
                
                conn.commit()
                logger.info("✅ 감정분석 테이블 생성 완료")
                
        except Exception as e:
            logger.error(f"❌ 감정분석 테이블 생성 실패: {e}")
            raise
    
    def create_investment_signals_table(self):
        """투자신호 테이블 생성"""
        
        logger.info("🚀 investment_signals 테이블 생성 중...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS investment_signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stock_code TEXT NOT NULL,
                        stock_name TEXT NOT NULL,
                        signal_type TEXT NOT NULL,
                        signal_strength REAL NOT NULL,
                        confidence REAL NOT NULL,
                        fundamental_sentiment REAL DEFAULT 0.0,
                        technical_score REAL DEFAULT 0.0,
                        news_score REAL DEFAULT 0.0,
                        fundamental_news INTEGER DEFAULT 0,
                        total_news INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP DEFAULT NULL
                    )
                ''')
                
                # 인덱스 생성
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_stock ON investment_signals(stock_code)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_strength ON investment_signals(signal_strength)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_created ON investment_signals(created_at)')
                
                conn.commit()
                logger.info("✅ investment_signals 테이블 생성 완료")
                
        except Exception as e:
            logger.error(f"❌ investment_signals 테이블 생성 실패: {e}")
    
    def populate_is_fundamental_flag(self):
        """기존 뉴스에 is_fundamental 플래그 설정"""
        
        logger.info("🏷️  is_fundamental 플래그 설정 중...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 펀더멘털 관련 키워드
                fundamental_keywords = [
                    '실적', '매출', '영업이익', '순이익', '재무제표', 'roe', '부채비율',
                    '배당', '감사보고서', '공시', '사업보고서', '분기실적', '연간실적',
                    '신사업', '사업확장', '인수합병', '전략적제휴', '자금조달', '투자유치'
                ]
                
                # 기존 뉴스 조회
                cursor.execute("SELECT id, title, description, content FROM news_articles WHERE is_fundamental = 0 OR is_fundamental IS NULL")
                news_items = cursor.fetchall()
                
                updated_count = 0
                
                for news_id, title, description, content in news_items:
                    full_text = f"{title} {description} {content}".lower()
                    
                    # 펀더멘털 키워드 체크
                    is_fundamental = 0
                    for keyword in fundamental_keywords:
                        if keyword in full_text:
                            is_fundamental = 1
                            break
                    
                    # 업데이트
                    cursor.execute("UPDATE news_articles SET is_fundamental = ? WHERE id = ?", (is_fundamental, news_id))
                    if is_fundamental:
                        updated_count += 1
                
                conn.commit()
                logger.info(f"✅ is_fundamental 플래그 설정 완료: {updated_count:,}개 펀더멘털 뉴스 식별")
                
        except Exception as e:
            logger.error(f"❌ is_fundamental 플래그 설정 실패: {e}")
    
    def run_full_migration(self):
        """전체 마이그레이션 실행 (통합 버전)"""
        
        logger.info("🚀 통합 데이터베이스 마이그레이션 시작")
        logger.info("=" * 70)
        
        try:
            # 1. 기존 구조 확인
            if not self.check_existing_structure():
                return False
            
            # 2. 백업 생성
            logger.info("💾 데이터베이스 백업 중...")
            backup_success, backup_path = self.backup_database()
            if backup_success:
                logger.info(f"✅ 백업 완료: {backup_path}")
            else:
                logger.warning("⚠️ 백업 실패, 계속 진행...")
            
            # 3. news_articles 테이블 마이그레이션
            self.migrate_news_articles_table()
            
            # 4. sentiment_analysis 테이블 생성
            self.create_sentiment_analysis_table()
            
            # 5. investment_signals 테이블 생성
            self.create_investment_signals_table()
            
            # 6. is_fundamental 플래그 설정
            self.populate_is_fundamental_flag()
            
            # 7. 마이그레이션 완료 확인
            self.verify_migration()
            
            # 8. 최종 상태 리포트
            self.generate_final_report()
            
            logger.info("=" * 70)
            logger.info("🎉 통합 데이터베이스 마이그레이션 완료!")
            logger.info("\n📝 다음 단계:")
            logger.info("1. python examples/basic_examples/07_buffett_sentiment_analyzer.py")
            logger.info("2. 메뉴에서 '1. 뉴스 감정 분석 실행' 선택")
            logger.info("3. 감정 분석 완료 후 '4. 워런 버핏 투자 신호 생성' 실행")
            logger.info("4. streamlit run sentiment_dashboard.py")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 마이그레이션 실패: {e}")
            return False
    
    def generate_final_report(self):
        """최종 마이그레이션 리포트 생성"""
        
        logger.info("📊 최종 마이그레이션 리포트 생성 중...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 전체 통계
                cursor.execute("SELECT COUNT(*) FROM news_articles")
                total_news = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM news_articles WHERE sentiment_score IS NOT NULL AND sentiment_score != 0.0")
                analyzed_news = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM news_articles WHERE is_fundamental = 1")
                fundamental_news = cursor.fetchone()[0]
                
                # 테이블 존재 확인
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                logger.info("\n" + "="*60)
                logger.info("📈 최종 마이그레이션 리포트")
                logger.info("="*60)
                logger.info(f"📊 전체 뉴스: {total_news:,}건")
                logger.info(f"🔍 감정 분석 완료: {analyzed_news:,}건")
                logger.info(f"⏳ 감정 분석 대기: {total_news - analyzed_news:,}건")
                logger.info(f"📈 펀더멘털 뉴스: {fundamental_news:,}건")
                logger.info(f"📋 생성된 테이블: {len(tables)}개")
                
                required_tables = ['news_articles', 'sentiment_analysis', 'daily_sentiment_index', 'investment_signals']
                missing_tables = [table for table in required_tables if table not in tables]
                
                if missing_tables:
                    logger.warning(f"⚠️ 누락된 테이블: {', '.join(missing_tables)}")
                else:
                    logger.info("✅ 모든 필수 테이블 생성 완료")
                
        except Exception as e:
            logger.error(f"❌ 리포트 생성 실패: {e}")
    
    def check_database_status(self):
        """데이터베이스 상태 확인 (통합 버전)"""
        
        if not self.db_path.exists():
            logger.error("❌ 데이터베이스 파일이 없습니다!")
            logger.info("먼저 뉴스 수집을 실행하세요: python examples/basic_examples/06_full_news_collector.py")
            return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 테이블 목록 확인
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                logger.info(f"📊 데이터베이스 상태:")
                logger.info(f"   테이블 수: {len(tables)}개")
                logger.info(f"   테이블 목록: {', '.join(tables)}")
                
                # news_articles 테이블 구조 확인
                if 'news_articles' in tables:
                    cursor.execute("PRAGMA table_info(news_articles)")
                    columns = [row[1] for row in cursor.fetchall()]
                    
                    logger.info(f"\n📋 news_articles 테이블:")
                    logger.info(f"   컬럼 수: {len(columns)}개")
                    
                    # 감정 분석 컬럼 확인
                    required_columns = ['sentiment_score', 'sentiment_label', 'news_category', 'long_term_relevance', 'is_fundamental']
                    missing_columns = [col for col in required_columns if col not in columns]
                    
                    if missing_columns:
                        logger.warning(f"❌ 누락된 감정 분석 컬럼: {', '.join(missing_columns)}")
                        return False
                    else:
                        logger.info("✅ 모든 감정 분석 컬럼 존재")
                    
                    # 데이터 개수 확인
                    cursor.execute("SELECT COUNT(*) FROM news_articles")
                    total_count = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM news_articles WHERE sentiment_score IS NOT NULL AND sentiment_score != 0.0")
                    analyzed_count = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM news_articles WHERE is_fundamental = 1")
                    fundamental_count = cursor.fetchone()[0]
                    
                    logger.info(f"\n📈 뉴스 데이터:")
                    logger.info(f"   전체 뉴스: {total_count:,}건")
                    logger.info(f"   감정 분석 완료: {analyzed_count:,}건")
                    logger.info(f"   펀더멘털 뉴스: {fundamental_count:,}건")
                
                # 다른 테이블들 확인
                other_tables = ['sentiment_analysis', 'daily_sentiment_index', 'investment_signals']
                for table in other_tables:
                    if table in tables:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        logger.info(f"📊 {table}: {count:,}건")
                    else:
                        logger.warning(f"❌ {table} 테이블 없음")
                
                return True
                
        except sqlite3.Error as e:
            logger.error(f"❌ 데이터베이스 확인 실패: {e}")
            return False
    
    def verify_migration(self):
        """마이그레이션 검증"""
        
        logger.info("🔍 마이그레이션 검증 중...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 테이블 존재 확인
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                required_tables = ['news_articles', 'sentiment_analysis', 'investment_signals']
                missing_tables = [table for table in required_tables if table not in tables]
                
                if missing_tables:
                    logger.error(f"❌ 누락된 테이블: {missing_tables}")
                    return False
                
                # news_articles 컬럼 확인
                cursor.execute("PRAGMA table_info(news_articles)")
                columns = [row[1] for row in cursor.fetchall()]
                
                required_columns = ['sentiment_score', 'sentiment_label', 'news_category', 'long_term_relevance', 'is_fundamental']
                missing_columns = [col for col in required_columns if col not in columns]
                
                if missing_columns:
                    logger.error(f"❌ news_articles 누락 컬럼: {missing_columns}")
                    return False
                
                # 데이터 확인
                cursor.execute("SELECT COUNT(*) FROM news_articles")
                news_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM news_articles WHERE is_fundamental = 1")
                fundamental_count = cursor.fetchone()[0]
                
                logger.info(f"✅ 검증 완료:")
                logger.info(f"   📰 총 뉴스: {news_count:,}건")
                logger.info(f"   📊 펀더멘털 뉴스: {fundamental_count:,}건")
                logger.info(f"   📋 모든 테이블 존재: {', '.join(required_tables)}")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ 마이그레이션 검증 실패: {e}")
            return False

def main():
    """메인 실행 함수 (통합 버전)"""
    
    print("\n" + "="*70)
    print("🛠️  Finance Data Vibe - 통합 감정분석 데이터베이스 마이그레이션 도구")
    print("="*70)
    print("📊 기존 뉴스 데이터 보존하면서 감정분석 기능 추가")
    print("✅ 자동 백업 및 검증")
    print("✅ 모든 필요한 테이블 및 인덱스 생성")
    print()
    
    migrator = DatabaseMigrator()
    
    while True:
        print("\n📋 통합 마이그레이션 메뉴:")
        print("1. 전체 마이그레이션 실행 (권장) 🚀")
        print("2. 데이터베이스 상태 확인")
        print("3. 데이터베이스 백업만")
        print("4. 개별 컴포넌트 마이그레이션")
        print("5. 마이그레이션 검증")
        print("0. 종료")
        
        choice = input("\n선택 (0-5): ").strip()
        
        if choice == '0':
            print("👋 마이그레이션 도구를 종료합니다.")
            break
        
        elif choice == '1':
            # 전체 마이그레이션 (권장)
            print("\n🚀 전체 마이그레이션을 시작합니다...")
            print("⚠️ 이 작업은 다음을 수행합니다:")
            print("   • 자동 백업 생성")
            print("   • news_articles 테이블에 감정분석 컬럼 추가")
            print("   • sentiment_analysis, investment_signals 테이블 생성")
            print("   • 펀더멘털 뉴스 플래그 설정")
            print("   • 모든 인덱스 생성")
            
            confirm = input("\n계속하시겠습니까? (y/N): ").strip().lower()
            
            if confirm == 'y':
                success = migrator.run_full_migration()
                if success:
                    print("\n🎉 전체 마이그레이션 성공!")
                    print("\n📝 다음 단계:")
                    print("1. python examples/basic_examples/07_buffett_sentiment_analyzer.py")
                    print("2. 메뉴에서 '1. 뉴스 감정 분석 실행' 선택")
                    print("3. 감정 분석 완료 후 '4. 워런 버핏 투자 신호 생성' 실행")
                    print("4. streamlit run sentiment_dashboard.py")
                else:
                    print("\n❌ 마이그레이션 실패. 로그를 확인하세요.")
            else:
                print("👋 마이그레이션을 취소했습니다.")
        
        elif choice == '2':
            # 데이터베이스 상태 확인
            print("\n🔍 데이터베이스 상태 확인 중...")
            if migrator.check_database_status():
                print("✅ 데이터베이스 상태 양호")
            else:
                print("❌ 마이그레이션이 필요합니다")
        
        elif choice == '3':
            # 백업만
            print("\n💾 데이터베이스 백업 중...")
            success, backup_path = migrator.backup_database()
            if success:
                print(f"✅ 백업 완료: {backup_path}")
            else:
                print("❌ 백업 실패")
        
        elif choice == '4':
            # 개별 컴포넌트 마이그레이션
            print("\n🔧 개별 컴포넌트 마이그레이션:")
            print("1. news_articles 테이블 마이그레이션")
            print("2. sentiment_analysis 테이블 생성")
            print("3. investment_signals 테이블 생성")
            print("4. is_fundamental 플래그 설정")
            
            sub_choice = input("선택 (1-4): ").strip()
            
            try:
                if sub_choice == '1':
                    migrator.migrate_news_articles_table()
                elif sub_choice == '2':
                    migrator.create_sentiment_analysis_table()
                elif sub_choice == '3':
                    migrator.create_investment_signals_table()
                elif sub_choice == '4':
                    migrator.populate_is_fundamental_flag()
                else:
                    print("❌ 올바른 번호를 선택해주세요.")
                    continue
                
                print("✅ 개별 마이그레이션 완료")
                
            except Exception as e:
                print(f"❌ 개별 마이그레이션 실패: {e}")
        
        elif choice == '5':
            # 마이그레이션 검증
            print("\n🔍 마이그레이션 검증 중...")
            if migrator.verify_migration():
                print("✅ 마이그레이션 검증 성공")
            else:
                print("❌ 마이그레이션 검증 실패")
        
        else:
            print("❌ 올바른 번호를 선택해주세요.")

# 기존 파일과의 호환성을 위한 함수들
def migrate_database():
    """기존 파일 호환성 - migrate_database 함수"""
    migrator = DatabaseMigrator()
    return migrator.run_full_migration()

def check_database_status():
    """기존 파일 호환성 - check_database_status 함수"""
    migrator = DatabaseMigrator()
    return migrator.check_database_status()

def backup_database():
    """기존 파일 호환성 - backup_database 함수"""
    migrator = DatabaseMigrator()
    return migrator.backup_database()

if __name__ == "__main__":
    main()