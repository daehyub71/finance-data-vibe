"""
📋 DART 공시정보 수집 시스템

이 모듈은 DART(전자공시시스템)에서 기업의 공시 정보를 수집합니다.

학습 내용:
1. DART API 사용법
2. 공시 유형별 데이터 수집
3. 재무제표 데이터 파싱
4. 기업 기본정보 수집
5. 데이터 정제 및 저장

🎯 목표: 가치투자를 위한 기본적 분석 데이터 확보

DART API 신청 방법:
1. https://opendart.fss.or.kr/ 접속
2. 개발자 등록 → API KEY 발급
3. 환경변수 DART_API_KEY에 설정
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
    DART 공시정보 수집기
    
    이 클래스는 DART API를 활용하여 기업의 공시정보를 체계적으로 수집합니다.
    
    주요 기능:
    1. 기업 기본정보 수집
    2. 공시 검색 및 수집  
    3. 재무제표 데이터 추출
    4. 사업보고서 주요 정보 파싱
    """
    
    def __init__(self, api_key=None):
        """
        DART 수집기 초기화
        
        Args:
            api_key (str): DART API KEY (없으면 환경변수에서 읽기)
        """
        self.api_key = api_key or os.getenv('DART_API_KEY')
        
        if not self.api_key:
            print("❌ DART API KEY가 필요합니다!")
            print("🔗 https://opendart.fss.or.kr/ 에서 API KEY를 발급받으세요.")
            print("📝 발급 후 .env 파일에 DART_API_KEY=your_key_here 추가하거나")
            print("   환경변수로 설정하세요.")
            raise ValueError("DART API KEY 필요")
        
        self.base_url = "https://opendart.fss.or.kr/api"
        self.data_dir = Path(DATA_DIR)
        self.processed_dir = Path(PROCESSED_DATA_DIR)
        
        # 디렉토리 생성
        self.dart_dir = self.data_dir / 'dart'
        self.dart_dir.mkdir(exist_ok=True)
        
        # SQLite DB 경로
        self.db_path = self.data_dir / 'dart_data.db'
        self.init_database()
        
        # API 요청 통계
        self.api_stats = {
            'total_requests': 0,
            'success_requests': 0,
            'failed_requests': 0
        }
        
        print(f"✅ DART 수집기 초기화 완료 (API KEY: {self.api_key[:10]}...)")
    
    def init_database(self):
        """
        🗄️ DART 데이터용 SQLite 데이터베이스 초기화
        """
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
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_disclosure_rcept_dt ON disclosure_info(rcept_dt)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_financial_corp_code ON financial_statements(corp_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_financial_bsns_year ON financial_statements(bsns_year)')
            
            conn.commit()
        
        print("✅ DART 데이터베이스 초기화 완료")
    
    def api_request(self, endpoint, params, max_retries=3):
        """
        📡 DART API 요청 (재시도 로직 포함)
        
        Args:
            endpoint (str): API 엔드포인트
            params (dict): 요청 파라미터
            max_retries (int): 최대 재시도 횟수
            
        Returns:
            dict: API 응답 데이터
        """
        params['crtfc_key'] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(max_retries):
            try:
                self.api_stats['total_requests'] += 1
                
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                # DART API 응답 상태 확인
                if data.get('status') == '000':  # 정상
                    self.api_stats['success_requests'] += 1
                    return data
                elif data.get('status') == '013':  # 조회된 데이터가 없음
                    return {'status': '013', 'message': '조회된 데이터가 없습니다', 'list': []}
                else:
                    print(f"⚠️ API 오류: {data.get('message', 'Unknown error')}")
                    self.api_stats['failed_requests'] += 1
                    return None
                    
            except requests.exceptions.RequestException as e:
                print(f"🔄 API 요청 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 지수 백오프
                else:
                    self.api_stats['failed_requests'] += 1
                    return None
        
        return None
    
    def get_corp_code_list(self):
        """
        🏢 전체 기업 고유번호 리스트 다운로드 및 파싱
        
        Returns:
            pd.DataFrame: 기업 정보 리스트
        """
        print("🏢 기업 고유번호 리스트 다운로드 중...")
        
        # 기업고유번호 다운로드
        url = "https://opendart.fss.or.kr/api/corpCode.xml"
        params = {'crtfc_key': self.api_key}
        
        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            
            # ZIP 파일 저장
            zip_path = self.dart_dir / 'corp_code.zip'
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            # ZIP 파일 압축 해제
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.dart_dir)
            
            # XML 파일 파싱
            xml_path = self.dart_dir / 'CORPCODE.xml'
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # 기업 정보 추출
            companies = []
            for company in root.findall('list'):
                corp_code = company.find('corp_code').text if company.find('corp_code') is not None else ''
                corp_name = company.find('corp_name').text if company.find('corp_name') is not None else ''
                stock_code = company.find('stock_code').text if company.find('stock_code') is not None else ''
                modify_date = company.find('modify_date').text if company.find('modify_date') is not None else ''
                
                # 상장회사만 필터링 (stock_code가 있는 경우)
                if stock_code and len(stock_code) == 6:
                    companies.append({
                        'corp_code': corp_code,
                        'corp_name': corp_name,
                        'stock_code': stock_code,
                        'modify_date': modify_date
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
    
    def get_company_info(self, corp_code):
        """
        🏢 기업 개황정보 조회
        
        Args:
            corp_code (str): 기업 고유번호
            
        Returns:
            dict: 기업 개황정보
        """
        endpoint = "company.json"
        params = {'corp_code': corp_code}
        
        data = self.api_request(endpoint, params)
        if data and data.get('status') == '000':
            return data
        return None
    
    def search_disclosure(self, corp_code=None, bgn_de=None, end_de=None, pblntf_ty=None, page_no=1, page_count=100):
        """
        📋 공시정보 검색
        
        Args:
            corp_code (str): 기업 고유번호
            bgn_de (str): 검색 시작일 (YYYYMMDD)
            end_de (str): 검색 종료일 (YYYYMMDD)
            pblntf_ty (str): 공시유형 ('A': 정기공시, 'B': 주요사항보고, 'C': 발행공시, 'D': 지분공시)
            page_no (int): 페이지 번호
            page_count (int): 페이지당 건수 (1~100)
            
        Returns:
            list: 공시정보 리스트
        """
        endpoint = "list.json"
        params = {
            'page_no': page_no,
            'page_count': page_count
        }
        
        if corp_code:
            params['corp_code'] = corp_code
        if bgn_de:
            params['bgn_de'] = bgn_de
        if end_de:
            params['end_de'] = end_de
        if pblntf_ty:
            params['pblntf_ty'] = pblntf_ty
        
        data = self.api_request(endpoint, params)
        if data and data.get('status') == '000':
            return data.get('list', [])
        return []
    
    def get_financial_statement(self, corp_code, bsns_year, reprt_code='11011'):
        """
        📊 재무제표 조회
        
        Args:
            corp_code (str): 기업 고유번호
            bsns_year (str): 사업연도 (YYYY)
            reprt_code (str): 보고서 코드
                             '11011': 사업보고서
                             '11012': 반기보고서  
                             '11013': 1분기보고서
                             '11014': 3분기보고서
                             
        Returns:
            dict: 재무제표 데이터
        """
        # 재무상태표 조회
        bs_data = self.api_request("fnlttSinglAcntAll.json", {
            'corp_code': corp_code,
            'bsns_year': bsns_year,
            'reprt_code': reprt_code,
            'fs_div': 'CFS'  # 연결재무제표
        })
        
        # 손익계산서 조회  
        is_data = self.api_request("fnlttSinglAcntAll.json", {
            'corp_code': corp_code,
            'bsns_year': bsns_year,
            'reprt_code': reprt_code,
            'fs_div': 'CFS'
        })
        
        return {
            'balance_sheet': bs_data.get('list', []) if bs_data else [],
            'income_statement': is_data.get('list', []) if is_data else []
        }
    
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
            print(f"  ⚠️ 기업정보 DB 저장 실패: {e}")
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
            print(f"  ⚠️ 공시정보 DB 저장 실패: {e}")
            return False
    
    def save_financial_data_to_db(self, corp_code, rcept_no, financial_data):
        """재무제표 데이터를 DB에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                # 재무상태표와 손익계산서 모두 저장
                all_data = financial_data.get('balance_sheet', []) + financial_data.get('income_statement', [])
                
                for item in all_data:
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
            print(f"  ⚠️ 재무데이터 DB 저장 실패: {e}")
            return False
    
    def collect_company_data(self, stock_codes, collect_financial=True, years=['2023', '2022', '2021']):
        """
        🚀 종목별 DART 데이터 일괄 수집
        
        Args:
            stock_codes (list): 수집할 종목코드 리스트
            collect_financial (bool): 재무제표 수집 여부
            years (list): 수집할 연도 리스트
        """
        print("🚀 DART 데이터 일괄 수집 시작!")
        print(f"📊 총 {len(stock_codes)}개 종목 처리 예정")
        
        # 1. 기업 고유번호 매핑 테이블 생성
        print("🏢 기업 고유번호 매핑 중...")
        corp_code_df = self.get_corp_code_list()
        if corp_code_df.empty:
            print("❌ 기업 고유번호 리스트 수집 실패")
            return
        
        # 종목코드로 기업 고유번호 매핑
        stock_to_corp = {}
        for _, row in corp_code_df.iterrows():
            stock_to_corp[row['stock_code']] = {
                'corp_code': row['corp_code'],
                'corp_name': row['corp_name']
            }
        
        # 2. 종목별 데이터 수집
        success_count = 0
        fail_count = 0
        
        progress_bar = tqdm(stock_codes, desc="📋 DART 데이터 수집", unit="종목")
        
        for stock_code in progress_bar:
            if stock_code not in stock_to_corp:
                print(f"⚠️ {stock_code}: 기업 고유번호 없음")
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
                
                # 최근 공시정보 수집 (최근 1년)
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
                
                disclosures = self.search_disclosure(
                    corp_code=corp_code,
                    bgn_de=start_date,
                    end_de=end_date,
                    pblntf_ty='A'  # 정기공시만
                )
                
                if disclosures:
                    self.save_disclosure_to_db(disclosures)
                
                # 재무제표 수집
                if collect_financial:
                    for year in years:
                        financial_data = self.get_financial_statement(corp_code, year)
                        if financial_data:
                            # 최근 사업보고서의 접수번호 찾기
                            recent_disclosures = [d for d in disclosures if year in d.get('rcept_dt', '')]
                            rcept_no = recent_disclosures[0].get('rcept_no', '') if recent_disclosures else ''
                            
                            self.save_financial_data_to_db(corp_code, rcept_no, financial_data)
                
                success_count += 1
                
                # API 요청 제한 고려 (초당 10건)
                time.sleep(0.1)
                
            except Exception as e:
                print(f"❌ {stock_code} ({corp_name}) 수집 실패: {e}")
                fail_count += 1
        
        # 수집 결과 요약
        print("\n" + "=" * 60)
        print("📋 DART 데이터 수집 완료!")
        print("=" * 60)
        print(f"📊 전체 종목: {len(stock_codes)}개")
        print(f"✅ 성공: {success_count}개")
        print(f"❌ 실패: {fail_count}개")
        print(f"📡 API 통계: 총 {self.api_stats['total_requests']}건 요청")
        print(f"🗄️ 데이터 저장: {self.db_path}")
        print("=" * 60)
    
    def get_stock_codes_from_db(self):
        """
        📊 주식 DB에서 모든 종목코드 가져오기
        
        Returns:
            list: 주식 DB에 저장된 모든 종목코드
        """
        stock_db_path = self.data_dir / 'stock_data.db'
        
        if not stock_db_path.exists():
            print("❌ 주식 데이터베이스가 없습니다!")
            print("먼저 주식 데이터 수집을 완료해주세요.")
            return []
        
        try:
            with sqlite3.connect(stock_db_path) as conn:
                query = """
                    SELECT DISTINCT symbol as stock_code, name as corp_name
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
    
    def collect_all_stock_dart_data(self, collect_financial=True, years=['2023', '2022', '2021'], batch_size=50):
        """
        🚀 주식 DB의 모든 종목에 대해 DART 데이터 수집
        
        Args:
            collect_financial (bool): 재무제표 수집 여부
            years (list): 수집할 연도 리스트
            batch_size (int): 배치 처리 단위 (API 제한 고려)
        """
        print("🚀 주식 DB 연동 DART 데이터 전체 수집 시작!")
        print("=" * 60)
        
        # 1. 주식 DB에서 모든 종목코드 가져오기
        all_stock_codes = self.get_stock_codes_from_db()
        
        if not all_stock_codes:
            print("❌ 수집할 종목이 없습니다.")
            return
        
        # 2. 이미 수집된 종목 확인
        existing_stocks = self.query_db("""
            SELECT DISTINCT stock_code 
            FROM company_info 
            WHERE stock_code IS NOT NULL AND stock_code != ''
        """)
        
        existing_set = set(existing_stocks['stock_code'].tolist()) if not existing_stocks.empty else set()
        
        # 3. 수집이 필요한 종목만 필터링
        new_stock_codes = [code for code in all_stock_codes if code not in existing_set]
        
        print(f"📊 전체 종목: {len(all_stock_codes):,}개")
        print(f"✅ 이미 수집됨: {len(existing_set):,}개") 
        print(f"🆕 새로 수집할 종목: {len(new_stock_codes):,}개")
        
        if not new_stock_codes:
            print("🎉 모든 종목의 DART 데이터가 이미 수집되어 있습니다!")
            return
        
        # 4. 예상 소요시간 계산
        estimated_time = len(new_stock_codes) * 0.5 / 60  # 분 단위
        print(f"⏱️  예상 소요시간: 약 {estimated_time:.1f}분")
        
        confirm = input(f"\n{len(new_stock_codes):,}개 종목의 DART 데이터를 수집하시겠습니까? (y/N): ").strip().lower()
        
        if confirm != 'y':
            print("👋 수집을 취소했습니다.")
            return
        
        # 5. 배치 단위로 수집 실행
        success_count = 0
        fail_count = 0
        
        # 배치 단위로 나누어 처리
        for i in range(0, len(new_stock_codes), batch_size):
            batch_codes = new_stock_codes[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(new_stock_codes) - 1) // batch_size + 1
            
            print(f"\n🔄 배치 {batch_num}/{total_batches} 처리 중... ({len(batch_codes)}개 종목)")
            
            batch_success, batch_fail = self.collect_company_data_batch(
                batch_codes, collect_financial, years
            )
            
            success_count += batch_success
            fail_count += batch_fail
            
            # 배치 간 휴식 (API 제한 고려)
            if i + batch_size < len(new_stock_codes):
                print("⏸️  잠시 휴식 중... (30초)")
                time.sleep(30)
        
        # 6. 최종 결과 리포트
        print("\n" + "=" * 60)
        print("📋 DART 데이터 전체 수집 완료!")
        print("=" * 60)
        print(f"📊 처리된 종목: {len(new_stock_codes):,}개")
        print(f"✅ 성공: {success_count:,}개 ({success_count/len(new_stock_codes)*100:.1f}%)")
        print(f"❌ 실패: {fail_count:,}개")
        print(f"📡 총 API 요청: {self.api_stats['total_requests']:,}건")
        print(f"🗄️ 데이터 저장: {self.db_path}")
        
        # 7. 수집 후 통계
        self.print_collection_statistics()
        print("=" * 60)
    
    def collect_company_data_batch(self, stock_codes, collect_financial=True, years=['2023', '2022', '2021']):
        """
        📦 배치 단위로 DART 데이터 수집
        
        Args:
            stock_codes (list): 배치 처리할 종목코드 리스트
            collect_financial (bool): 재무제표 수집 여부
            years (list): 수집할 연도 리스트
            
        Returns:
            tuple: (성공 개수, 실패 개수)
        """
        # 1. 기업 고유번호 매핑 테이블 생성 (캐시된 데이터 활용)
        if not hasattr(self, '_corp_code_mapping'):
            print("🏢 기업 고유번호 매핑 생성 중...")
            corp_code_df = self.get_corp_code_list()
            self._corp_code_mapping = {}
            
            for _, row in corp_code_df.iterrows():
                self._corp_code_mapping[row['stock_code']] = {
                    'corp_code': row['corp_code'],
                    'corp_name': row['corp_name']
                }
        
        # 2. 배치 내 종목별 데이터 수집
        success_count = 0
        fail_count = 0
        
        progress_bar = tqdm(stock_codes, desc="📋 DART 수집", unit="종목", leave=False)
        
        for stock_code in progress_bar:
            if stock_code not in self._corp_code_mapping:
                fail_count += 1
                continue
            
            corp_info = self._corp_code_mapping[stock_code]
            corp_code = corp_info['corp_code']
            corp_name = corp_info['corp_name']
            
            progress_bar.set_postfix({'Current': f"{stock_code}({corp_name[:8]})"})
            
            try:
                # 기업 개황정보 수집
                company_data = self.get_company_info(corp_code)
                if company_data and company_data.get('status') == '000':
                    self.save_company_info_to_db(company_data)
                
                # 최근 공시정보 수집
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
                
                disclosures = self.search_disclosure(
                    corp_code=corp_code,
                    bgn_de=start_date,
                    end_de=end_date,
                    pblntf_ty='A'  # 정기공시만
                )
                
                if disclosures:
                    self.save_disclosure_to_db(disclosures)
                
                # 재무제표 수집
                if collect_financial:
                    for year in years:
                        financial_data = self.get_financial_statement(corp_code, year)
                        if financial_data:
                            recent_disclosures = [d for d in disclosures if year in d.get('rcept_dt', '')]
                            rcept_no = recent_disclosures[0].get('rcept_no', '') if recent_disclosures else ''
                            
                            self.save_financial_data_to_db(corp_code, rcept_no, financial_data)
                
                success_count += 1
                
                # API 요청 제한 고려 (초당 10건)
                time.sleep(0.1)
                
            except Exception as e:
                print(f"\n❌ {stock_code} ({corp_name}) 수집 실패: {e}")
                fail_count += 1
        
        return success_count, fail_count
    
    def print_collection_statistics(self):
        """📊 수집 통계 출력"""
        print("\n📊 수집 통계:")
        
        # 기업 정보 통계
        company_stats = self.query_db("""
            SELECT 
                COUNT(*) as total_companies,
                COUNT(CASE WHEN stock_code IS NOT NULL AND stock_code != '' THEN 1 END) as listed_companies
            FROM company_info
        """)
        
        if not company_stats.empty:
            print(f"   🏢 전체 기업: {company_stats.iloc[0]['total_companies']:,}개")
            print(f"   📈 상장기업: {company_stats.iloc[0]['listed_companies']:,}개")
        
        # 재무데이터 통계
        financial_stats = self.query_db("""
            SELECT 
                bsns_year,
                COUNT(DISTINCT corp_code) as companies_count,
                COUNT(*) as records_count
            FROM financial_statements
            GROUP BY bsns_year
            ORDER BY bsns_year DESC
        """)
        
        if not financial_stats.empty:
            print(f"   💰 재무데이터:")
            for _, row in financial_stats.iterrows():
                print(f"      {row['bsns_year']}년: {row['companies_count']:,}개 기업, {row['records_count']:,}건")
    
    def query_db(self, query, params=None):
        """DB 쿼리 실행 (DART DB)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if params:
                    return pd.read_sql_query(query, conn, params=params)
                else:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"❌ 쿼리 실행 실패: {e}")
            return pd.DataFrame()
    
    def get_company_list(self):
        """수집된 기업 리스트 조회"""
        query = """
            SELECT stock_code, corp_name, ceo_nm, ind_tp, est_dt
            FROM company_info
            WHERE stock_code IS NOT NULL AND stock_code != ''
            ORDER BY corp_name
        """
        return self.query_db(query)
    
    def get_financial_summary(self, stock_code, year):
        """특정 종목의 재무요약 조회"""
        query = """
            SELECT ci.corp_name, fs.account_nm, fs.thstrm_amount
            FROM financial_statements fs
            JOIN company_info ci ON fs.corp_code = ci.corp_code
            WHERE ci.stock_code = ? AND fs.bsns_year = ?
            AND fs.account_nm IN ('자산총계', '부채총계', '자본총계', '매출액', '당기순이익')
            ORDER BY fs.ord
        """
        return self.query_db(query, (stock_code, year))


def main():
    """메인 실행 함수"""
    
    print("🚀 Finance Data Vibe - DART 공시정보 수집기")
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
        print("3. 직접 입력")
        
        choice = input("\n선택하세요 (1-3, 기본값: 1): ").strip() or '1'
        
        if choice == '1':
            # 기본 종목들
            stock_codes = ['005930', '000660', '035420', '005380', '006400', 
                          '051910', '035720', '207940', '068270', '028260']
        elif choice == '2':
            # 코스피 50 (예시)
            stock_codes = ['005930', '000660', '035420', '005380', '006400', 
                          '051910', '035720', '207940', '068270', '028260',
                          '066570', '323410', '003670', '096770', '034730']  # 일부만 예시
        else:
            # 직접 입력
            input_codes = input("종목코드를 쉼표로 구분해서 입력하세요 (예: 005930,000660): ")
            stock_codes = [code.strip() for code in input_codes.split(',') if code.strip()]
        
        if not stock_codes:
            print("❌ 유효한 종목코드가 없습니다.")
            return
        
        # 수집 옵션 선택
        print(f"\n📋 수집 설정:")
        print(f"   종목 수: {len(stock_codes)}개")
        print(f"   예상 소요시간: 약 {len(stock_codes) * 0.5:.1f}분")
        
        collect_financial = input("\n재무제표도 수집하시겠습니까? (Y/n): ").strip().lower() != 'n'
        
        confirm = input("\n수집을 시작하시겠습니까? (y/N): ").strip().lower()
        
        if confirm == 'y':
            # 데이터 수집 실행
            collector.collect_company_data(
                stock_codes=stock_codes,
                collect_financial=collect_financial,
                years=['2023', '2022', '2021']
            )
            
            # 수집 결과 시연
            print("\n" + "="*40)
            print("🔍 수집 결과 시연")
            print("="*40)
            
            # 수집된 기업 리스트
            companies = collector.get_company_list()
            if not companies.empty:
                print("\n📋 수집된 기업들:")
                print(companies.head(10))
            
            # 삼성전자 재무요약 (있다면)
            if '005930' in stock_codes:
                financial = collector.get_financial_summary('005930', '2023')
                if not financial.empty:
                    print("\n📊 삼성전자 2023년 재무요약:")
                    print(financial)
            
            print("\n🎉 DART 데이터 수집이 완료되었습니다!")
            print("이제 기본적 분석을 위한 데이터가 준비되었어요!")
            
        else:
            print("👋 수집을 취소했습니다.")
    
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("API KEY가 올바른지 확인해주세요.")


if __name__ == "__main__":
    main()