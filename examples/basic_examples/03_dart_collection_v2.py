"""
📋 DART 공시정보 수집 시스템 (업데이트 버전)

이 모듈은 DART(전자공시시스템)에서 기업의 공시 정보를 수집합니다.
주식 DB와 연동하여 모든 종목의 DART 데이터를 자동 수집할 수 있습니다.

주요 개선사항:
1. 주식 DB 자동 연동
2. 배치 처리로 안전한 대량 수집  
3. 중복 수집 방지
4. 실시간 진행률 표시

🎯 목표: 완전한 기본적 분석 데이터베이스 구축
"""

import sys
from pathlib import Path
import requests
import json
import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta
from tqdm import tqdm
import zipfile
import xml.etree.ElementTree as ET

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

try:
    from config.settings import DATA_DIR, PROCESSED_DATA_DIR
    import os
    from dotenv import load_dotenv
    load_dotenv()  # .env 파일에서 환경변수 로드
except ImportError as e:
    print(f"❌ 패키지 설치 필요: {e}")
    print("pip install python-dotenv 실행하세요!")
    exit(1)


class DARTCollector:
    """
    DART 공시정보 수집기 (업데이트 버전)
    
    주요 기능:
    1. 기업 기본정보 수집
    2. 공시 검색 및 수집  
    3. 재무제표 데이터 추출
    4. 주식 DB 연동 자동 수집
    """
    
    def __init__(self, api_key=None):
        """DART 수집기 초기화"""
        self.api_key = api_key or os.getenv('DART_API_KEY')
        
        if not self.api_key:
            print("❌ DART API KEY가 필요합니다!")
            print("🔗 https://opendart.fss.or.kr/ 에서 API KEY를 발급받으세요.")
            raise ValueError("DART API KEY 필요")
        
        self.base_url = "https://opendart.fss.or.kr/api"
        self.data_dir = Path(DATA_DIR)
        
        # DART 전용 디렉토리
        self.dart_dir = self.data_dir / 'dart'
        self.dart_dir.mkdir(exist_ok=True)
        
        # DB 경로
        self.db_path = self.data_dir / 'dart_data.db'
        self.stock_db_path = self.data_dir / 'stock_data.db'
        
        self.init_database()
        
        # 통계
        self.api_stats = {
            'total_requests': 0,
            'success_requests': 0,
            'failed_requests': 0
        }
        
        print(f"✅ DART 수집기 초기화 완료 (API KEY: {self.api_key[:10]}...)")
    
    def init_database(self):
        """🗄️ DART 데이터용 SQLite 데이터베이스 초기화"""
        print("🗄️ DART 데이터베이스 초기화 중...")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 기업 기본정보 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS company_info (
                    corp_code TEXT PRIMARY KEY,
                    corp_name TEXT NOT NULL,
                    corp_name_eng TEXT,
                    stock_name TEXT,
                    stock_code TEXT,
                    ceo_nm TEXT,
                    corp_cls TEXT,
                    jurir_no TEXT,
                    bizr_no TEXT,
                    adres TEXT,
                    hm_url TEXT,
                    ir_url TEXT,
                    phn_no TEXT,
                    fax_no TEXT,
                    ind_tp TEXT,
                    est_dt TEXT,
                    acc_mt TEXT,
                    created_date TEXT,
                    updated_date TEXT
                )
            ''')
            
            # 공시정보 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disclosure_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    corp_code TEXT NOT NULL,
                    corp_name TEXT,
                    stock_code TEXT,
                    corp_cls TEXT,
                    report_nm TEXT,
                    rcept_no TEXT UNIQUE,
                    flr_nm TEXT,
                    rcept_dt TEXT,
                    rm TEXT,
                    created_date TEXT,
                    FOREIGN KEY (corp_code) REFERENCES company_info (corp_code)
                )
            ''')
            
            # 재무제표 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS financial_statements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rcept_no TEXT NOT NULL,
                    corp_code TEXT NOT NULL,
                    bsns_year TEXT,
                    reprt_code TEXT,
                    sj_div TEXT,
                    sj_nm TEXT,
                    account_nm TEXT,
                    fs_div TEXT,
                    fs_nm TEXT,
                    thstrm_nm TEXT,
                    thstrm_amount TEXT,
                    thstrm_add_amount TEXT,
                    frmtrm_nm TEXT,
                    frmtrm_amount TEXT,
                    frmtrm_q_nm TEXT,
                    frmtrm_q_amount TEXT,
                    frmtrm_add_amount TEXT,
                    bfefrmtrm_nm TEXT,
                    bfefrmtrm_amount TEXT,
                    ord INTEGER,
                    currency TEXT,
                    created_date TEXT,
                    FOREIGN KEY (corp_code) REFERENCES company_info (corp_code)
                )
            ''')
            
            # 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_disclosure_corp_code ON disclosure_info(corp_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_financial_corp_code ON financial_statements(corp_code)')
            
            conn.commit()
        
        print("✅ DART 데이터베이스 초기화 완료")
    
    def api_request(self, endpoint, params, max_retries=3):
        """📡 DART API 요청"""
        params['crtfc_key'] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(max_retries):
            try:
                self.api_stats['total_requests'] += 1
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                if data.get('status') == '000':  # 정상
                    self.api_stats['success_requests'] += 1
                    return data
                elif data.get('status') == '013':  # 조회된 데이터가 없음
                    return {'status': '013', 'message': '조회된 데이터가 없습니다', 'list': []}
                else:
                    self.api_stats['failed_requests'] += 1
                    return None
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.api_stats['failed_requests'] += 1
                    return None
        
        return None
    
    def get_corp_code_list(self):
        """🏢 전체 기업 고유번호 리스트 다운로드"""
        print("🏢 기업 고유번호 리스트 다운로드 중...")
        
        url = "https://opendart.fss.or.kr/api/corpCode.xml"
        params = {'crtfc_key': self.api_key}
        
        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            
            # ZIP 파일 저장 및 압축 해제
            zip_path = self.dart_dir / 'corp_code.zip'
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.dart_dir)
            
            # XML 파일 파싱
            xml_path = self.dart_dir / 'CORPCODE.xml'
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            companies = []
            for company in root.findall('list'):
                corp_code = company.find('corp_code').text if company.find('corp_code') is not None else ''
                corp_name = company.find('corp_name').text if company.find('corp_name') is not None else ''
                stock_code = company.find('stock_code').text if company.find('stock_code') is not None else ''
                
                if stock_code and len(stock_code) == 6:
                    companies.append({
                        'corp_code': corp_code,
                        'corp_name': corp_name,
                        'stock_code': stock_code
                    })
            
            df = pd.DataFrame(companies)
            print(f"✅ 총 {len(df)}개 상장회사 정보 수집 완료")
            
            # 파일 정리
            zip_path.unlink()
            xml_path.unlink()
            
            return df
            
        except Exception as e:
            print(f"❌ 기업 리스트 다운로드 실패: {e}")
            return pd.DataFrame()
    
    def get_stock_codes_from_db(self):
        """📊 주식 DB에서 모든 종목코드 가져오기"""
        if not self.stock_db_path.exists():
            print("❌ 주식 데이터베이스가 없습니다!")
            print("먼저 주식 데이터 수집을 완료해주세요.")
            return []
        
        try:
            with sqlite3.connect(self.stock_db_path) as conn:
                query = """
                    SELECT DISTINCT symbol as stock_code
                    FROM stock_info
                    WHERE symbol IS NOT NULL 
                    AND LENGTH(symbol) = 6
                    ORDER BY symbol
                """
                result = pd.read_sql_query(query, conn)
                
                print(f"📊 주식 DB에서 {len(result)}개 종목 발견")
                return result['stock_code'].tolist()
                
        except Exception as e:
            print(f"❌ 주식 DB 조회 실패: {e}")
            return []
    
    def get_company_info(self, corp_code):
        """🏢 기업 개황정보 조회"""
        endpoint = "company.json"
        params = {'corp_code': corp_code}
        return self.api_request(endpoint, params)
    
    def search_disclosure(self, corp_code=None, bgn_de=None, end_de=None):
        """📋 공시정보 검색"""
        endpoint = "list.json"
        params = {'page_no': 1, 'page_count': 100}
        
        if corp_code:
            params['corp_code'] = corp_code
        if bgn_de:
            params['bgn_de'] = bgn_de
        if end_de:
            params['end_de'] = end_de
        
        data = self.api_request(endpoint, params)
        if data and data.get('status') == '000':
            return data.get('list', [])
        return []
    
    def get_financial_statement(self, corp_code, bsns_year):
        """📊 재무제표 조회"""
        data = self.api_request("fnlttSinglAcntAll.json", {
            'corp_code': corp_code,
            'bsns_year': bsns_year,
            'reprt_code': '11011',  # 사업보고서
            'fs_div': 'CFS'  # 연결재무제표
        })
        
        return {'financial_data': data.get('list', []) if data else []}
    
    def save_company_info_to_db(self, company_data):
        """기업 정보를 DB에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO company_info 
                    (corp_code, corp_name, corp_name_eng, stock_name, stock_code, ceo_nm, 
                     corp_cls, jurir_no, bizr_no, adres, hm_url, ir_url, phn_no, fax_no, 
                     ind_tp, est_dt, acc_mt, created_date, updated_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    company_data.get('corp_code', ''),
                    company_data.get('corp_name', ''),
                    company_data.get('corp_name_eng', ''),
                    company_data.get('stock_name', ''),
                    company_data.get('stock_code', ''),
                    company_data.get('ceo_nm', ''),
                    company_data.get('corp_cls', ''),
                    company_data.get('jurir_no', ''),
                    company_data.get('bizr_no', ''),
                    company_data.get('adres', ''),
                    company_data.get('hm_url', ''),
                    company_data.get('ir_url', ''),
                    company_data.get('phn_no', ''),
                    company_data.get('fax_no', ''),
                    company_data.get('ind_tp', ''),
                    company_data.get('est_dt', ''),
                    company_data.get('acc_mt', ''),
                    current_time,
                    current_time
                ))
                
                conn.commit()
                return True
        except Exception as e:
            return False
    
    def save_disclosure_to_db(self, disclosure_list):
        """공시정보를 DB에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                for disclosure in disclosure_list:
                    cursor.execute('''
                        INSERT OR IGNORE INTO disclosure_info 
                        (corp_code, corp_name, stock_code, corp_cls, report_nm, rcept_no, 
                         flr_nm, rcept_dt, rm, created_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        disclosure.get('corp_code', ''),
                        disclosure.get('corp_name', ''),
                        disclosure.get('stock_code', ''),
                        disclosure.get('corp_cls', ''),
                        disclosure.get('report_nm', ''),
                        disclosure.get('rcept_no', ''),
                        disclosure.get('flr_nm', ''),
                        disclosure.get('rcept_dt', ''),
                        disclosure.get('rm', ''),
                        current_time
                    ))
                
                conn.commit()
                return True
        except Exception as e:
            return False
    
    def save_financial_data_to_db(self, corp_code, rcept_no, financial_data):
        """재무제표 데이터를 DB에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                for item in financial_data.get('financial_data', []):
                    cursor.execute('''
                        INSERT OR IGNORE INTO financial_statements 
                        (rcept_no, corp_code, bsns_year, reprt_code, sj_div, sj_nm, account_nm, 
                         fs_div, fs_nm, thstrm_nm, thstrm_amount, thstrm_add_amount, 
                         frmtrm_nm, frmtrm_amount, frmtrm_q_nm, frmtrm_q_amount, 
                         frmtrm_add_amount, bfefrmtrm_nm, bfefrmtrm_amount, ord, currency, created_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        rcept_no,
                        corp_code,
                        item.get('bsns_year', ''),
                        item.get('reprt_code', ''),
                        item.get('sj_div', ''),
                        item.get('sj_nm', ''),
                        item.get('account_nm', ''),
                        item.get('fs_div', ''),
                        item.get('fs_nm', ''),
                        item.get('thstrm_nm', ''),
                        item.get('thstrm_amount', ''),
                        item.get('thstrm_add_amount', ''),
                        item.get('frmtrm_nm', ''),
                        item.get('frmtrm_amount', ''),
                        item.get('frmtrm_q_nm', ''),
                        item.get('frmtrm_q_amount', ''),
                        item.get('frmtrm_add_amount', ''),
                        item.get('bfefrmtrm_nm', ''),
                        item.get('bfefrmtrm_amount', ''),
                        item.get('ord', ''),
                        item.get('currency', ''),
                        current_time
                    ))
                
                conn.commit()
                return True
        except Exception as e:
            return False
    
    def collect_all_stock_dart_data(self, collect_financial=True, years=['2023', '2022', '2021'], batch_size=50):
        """🚀 주식 DB의 모든 종목에 대해 DART 데이터 수집"""
        print("🚀 주식 DB 연동 DART 데이터 전체 수집 시작!")
        print("=" * 60)
        
        # 1. 주식 DB에서 모든 종목코드 가져오기
        all_stock_codes = self.get_stock_codes_from_db()
        if not all_stock_codes:
            return
        
        # 2. 이미 수집된 종목 확인
        existing_stocks = self.query_db("""
            SELECT DISTINCT stock_code 
            FROM company_info 
            WHERE stock_code IS NOT NULL AND stock_code != ''
        """)
        
        existing_set = set(existing_stocks['stock_code'].tolist()) if not existing_stocks.empty else set()
        new_stock_codes = [code for code in all_stock_codes if code not in existing_set]
        
        print(f"📊 전체 종목: {len(all_stock_codes):,}개")
        print(f"✅ 이미 수집됨: {len(existing_set):,}개") 
        print(f"🆕 새로 수집할 종목: {len(new_stock_codes):,}개")
        
        if not new_stock_codes:
            print("🎉 모든 종목의 DART 데이터가 이미 수집되어 있습니다!")
            return
        
        # 3. 수집 확인
        estimated_time = len(new_stock_codes) * 0.5 / 60
        print(f"⏱️  예상 소요시간: 약 {estimated_time:.1f}분")
        
        confirm = input(f"\n{len(new_stock_codes):,}개 종목의 DART 데이터를 수집하시겠습니까? (y/N): ").strip().lower()
        if confirm != 'y':
            print("👋 수집을 취소했습니다.")
            return
        
        # 4. 기업 고유번호 매핑
        print("🏢 기업 고유번호 매핑 중...")
        corp_code_df = self.get_corp_code_list()
        corp_mapping = {}
        for _, row in corp_code_df.iterrows():
            corp_mapping[row['stock_code']] = {
                'corp_code': row['corp_code'],
                'corp_name': row['corp_name']
            }
        
        # 5. 배치 처리
        success_count = 0
        fail_count = 0
        
        for i in range(0, len(new_stock_codes), batch_size):
            batch_codes = new_stock_codes[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(new_stock_codes) - 1) // batch_size + 1
            
            print(f"\n🔄 배치 {batch_num}/{total_batches} 처리 중... ({len(batch_codes)}개 종목)")
            
            progress_bar = tqdm(batch_codes, desc="📋 DART 수집", unit="종목", leave=False)
            
            for stock_code in progress_bar:
                if stock_code not in corp_mapping:
                    fail_count += 1
                    continue
                
                corp_info = corp_mapping[stock_code]
                corp_code = corp_info['corp_code']
                corp_name = corp_info['corp_name']
                
                progress_bar.set_postfix({'Current': f"{stock_code}({corp_name[:8]})"})
                
                try:
                    # 기업 개황정보 수집
                    company_data = self.get_company_info(corp_code)
                    if company_data and company_data.get('status') == '000':
                        self.save_company_info_to_db(company_data)
                    
                    # 공시정보 수집
                    end_date = datetime.now().strftime('%Y%m%d')
                    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
                    
                    disclosures = self.search_disclosure(corp_code=corp_code, bgn_de=start_date, end_de=end_date)
                    if disclosures:
                        self.save_disclosure_to_db(disclosures)
                    
                    # 재무제표 수집
                    if collect_financial:
                        for year in years:
                            financial_data = self.get_financial_statement(corp_code, year)
                            if financial_data:
                                rcept_no = disclosures[0].get('rcept_no', '') if disclosures else ''
                                self.save_financial_data_to_db(corp_code, rcept_no, financial_data)
                    
                    success_count += 1
                    time.sleep(0.1)  # API 제한 고려
                    
                except Exception as e:
                    fail_count += 1
            
            # 배치 간 휴식
            if i + batch_size < len(new_stock_codes):
                print("⏸️  잠시 휴식 중... (30초)")
                time.sleep(30)
        
        # 6. 최종 결과
        print("\n" + "=" * 60)
        print("📋 DART 데이터 전체 수집 완료!")
        print("=" * 60)
        print(f"📊 처리된 종목: {len(new_stock_codes):,}개")
        print(f"✅ 성공: {success_count:,}개 ({success_count/len(new_stock_codes)*100:.1f}%)")
        print(f"❌ 실패: {fail_count:,}개")
        print(f"🗄️ 데이터 저장: {self.db_path}")
        print("=" * 60)
    
    def collect_company_data(self, stock_codes, collect_financial=True, years=['2023', '2022', '2021']):
        """📦 선택된 종목들의 DART 데이터 수집"""
        print("🚀 DART 데이터 수집 시작!")
        print(f"📊 총 {len(stock_codes)}개 종목 처리 예정")
        
        # 기업 고유번호 매핑
        corp_code_df = self.get_corp_code_list()
        stock_to_corp = {}
        for _, row in corp_code_df.iterrows():
            stock_to_corp[row['stock_code']] = {
                'corp_code': row['corp_code'],
                'corp_name': row['corp_name']
            }
        
        success_count = 0
        fail_count = 0
        
        progress_bar = tqdm(stock_codes, desc="📋 DART 데이터 수집", unit="종목")
        
        for stock_code in progress_bar:
            if stock_code not in stock_to_corp:
                fail_count += 1
                continue
            
            corp_info = stock_to_corp[stock_code]
            corp_code = corp_info['corp_code']
            corp_name = corp_info['corp_name']
            
            progress_bar.set_postfix({'Current': f"{stock_code}({corp_name[:8]})"})
            
            try:
                # 기업 개황정보 수집
                company_data = self.get_company_info(corp_code)
                if company_data and company_data.get('status') == '000':
                    self.save_company_info_to_db(company_data)
                
                # 공시정보 수집
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
                
                disclosures = self.search_disclosure(corp_code=corp_code, bgn_de=start_date, end_de=end_date)
                if disclosures:
                    self.save_disclosure_to_db(disclosures)
                
                # 재무제표 수집
                if collect_financial:
                    for year in years:
                        financial_data = self.get_financial_statement(corp_code, year)
                        if financial_data:
                            rcept_no = disclosures[0].get('rcept_no', '') if disclosures else ''
                            self.save_financial_data_to_db(corp_code, rcept_no, financial_data)
                
                success_count += 1
                time.sleep(0.1)
                
            except Exception as e:
                fail_count += 1
        
        # 결과 출력
        print("\n" + "=" * 60)
        print("📋 DART 데이터 수집 완료!")
        print("=" * 60)
        print(f"📊 전체 종목: {len(stock_codes)}개")
        print(f"✅ 성공: {success_count}개")
        print(f"❌ 실패: {fail_count}개")
        print(f"📡 API 통계: 총 {self.api_stats['total_requests']}건 요청")
        print(f"🗄️ 데이터 저장: {self.db_path}")
        print("=" * 60)
    
    def query_db(self, query, params=None):
        """DB 쿼리 실행"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if params:
                    return pd.read_sql_query(query, conn, params=params)
                else:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"❌ 쿼리 실행 실패: {e}")
            return pd.DataFrame()


def main():
    """메인 실행 함수"""
    
    print("🚀 Finance Data Vibe - DART 공시정보 수집기 (업데이트 버전)")
    print("=" * 60)
    
    # API KEY 확인
    api_key = os.getenv('DART_API_KEY')
    if not api_key:
        print("❌ DART API KEY가 설정되지 않았습니다!")
        print()
        print("📝 설정 방법:")
        print("1. https://opendart.fss.or.kr/ 에서 개발자 등록")
        print("2. API KEY 발급")
        print("3. 프로젝트 폴더에 .env 파일 생성")
        print("4. .env 파일에 다음 내용 추가:")
        print("   DART_API_KEY=여기에_발급받은_키_입력")
        print()
        
        manual_key = input("또는 여기에 API KEY를 직접 입력하세요: ").strip()
        if manual_key:
            api_key = manual_key
        else:
            print("👋 API KEY 설정 후 다시 실행해주세요.")
            return
    
    try:
        # DART 수집기 초기화
        collector = DARTCollector(api_key)
        
        # 수집할 종목 선택
        print("\n📊 수집할 종목을 선택하세요:")
        print("1. 기본 종목들 (삼성전자, SK하이닉스 등 10개)")
        print("2. 코스피 50 종목")
        print("3. 주식 DB의 모든 종목 (자동 연동) ⭐ 추천")
        print("4. 직접 입력")
        
        choice = input("\n선택하세요 (1-4, 기본값: 3): ").strip() or '3'
        
        if choice == '1':
            # 기본 종목들
            stock_codes = ['005930', '000660', '035420', '005380', '006400', 
                          '051910', '035720', '207940', '068270', '028260']
            
            collect_financial = input("\n재무제표도 수집하시겠습니까? (Y/n): ").strip().lower() != 'n'
            confirm = input(f"\n{len(stock_codes)}개 종목의 DART 데이터를 수집하시겠습니까? (y/N): ").strip().lower()
            
            if confirm == 'y':
                collector.collect_company_data(stock_codes, collect_financial, ['2023', '2022', '2021'])
            else:
                print("👋 수집을 취소했습니다.")
                
        elif choice == '2':
            # 코스피 50
            stock_codes = ['005930', '000660', '035420', '005380', '006400', 
                          '051910', '035720', '207940', '068270', '028260',
                          '066570', '323410', '003670', '096770', '034730']
            
            collect_financial = input("\n재무제표도 수집하시겠습니까? (Y/n): ").strip().lower() != 'n'
            confirm = input(f"\n{len(stock_codes)}개 종목의 DART 데이터를 수집하시겠습니까? (y/N): ").strip().lower()
            
            if confirm == 'y':
                collector.collect_company_data(stock_codes, collect_financial, ['2023', '2022', '2021'])
            else:
                print("👋 수집을 취소했습니다.")
                
        elif choice == '3':
            # 🌟 주식 DB 연동 전체 수집
            print("\n🌟 주식 DB와 연동하여 모든 종목의 DART 데이터를 수집합니다.")
            
            collect_financial = input("재무제표도 수집하시겠습니까? (Y/n): ").strip().lower() != 'n'
            
            # 전체 수집 실행
            collector.collect_all_stock_dart_data(
                collect_financial=collect_financial,
                years=['2023', '2022', '2021']
            )
            
        elif choice == '4':
            # 직접 입력
            input_codes = input("종목코드를 쉼표로 구분해서 입력하세요 (예: 005930,000660): ")
            stock_codes = [code.strip() for code in input_codes.split(',') if code.strip()]
            
            if not stock_codes:
                print("❌ 유효한 종목코드가 없습니다.")
                return
            
            collect_financial = input("\n재무제표도 수집하시겠습니까? (Y/n): ").strip().lower() != 'n'
            confirm = input(f"\n{len(stock_codes)}개 종목의 DART 데이터를 수집하시겠습니까? (y/N): ").strip().lower()
            
            if confirm == 'y':
                collector.collect_company_data(stock_codes, collect_financial, ['2023', '2022', '2021'])
            else:
                print("👋 수집을 취소했습니다.")
        
        else:
            print("❌ 올바른 선택이 아닙니다.")
            return
        
        print("\n🎉 모든 작업이 완료되었습니다!")
        print("🔍 데이터 확인: python examples/basic_examples/04_dart_data_viewer.py")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("API KEY가 올바른지 확인해주세요.")


if __name__ == "__main__":
    main()