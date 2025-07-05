"""
프로젝트 기본 설정

이 파일은 프로젝트 전체에서 사용하는 기본 설정들을 관리합니다.
"""

import os
from pathlib import Path

# 프로젝트 루트 디렉토리
ROOT_DIR = Path(__file__).parent.parent

# 데이터 디렉토리
DATA_DIR = ROOT_DIR / 'data'
RAW_DATA_DIR = DATA_DIR / 'raw'
PROCESSED_DATA_DIR = DATA_DIR / 'processed'

# API 설정 (환경변수에서 읽기)
DART_API_KEY = os.getenv('DART_API_KEY', '')

# 기본 분석 대상 종목들
DEFAULT_STOCKS = [
    '005930',  # 삼성전자
    '000660',  # SK하이닉스
    '035420',  # NAVER
    '005380',  # 현대차
    '006400',  # 삼성SDI
    '051910',  # LG화학
    '035720',  # 카카오
    '207940',  # 삼성바이오로직스
]

# 기술적 분석 기본 설정
TECHNICAL_INDICATORS = {
    'SMA_PERIODS': [5, 20, 60, 120],
    'EMA_PERIODS': [12, 26],
    'RSI_PERIOD': 14,
    'MACD_FAST': 12,
    'MACD_SLOW': 26,
    'MACD_SIGNAL': 9,
    'BOLLINGER_PERIOD': 20,
    'BOLLINGER_STD': 2,
    'STOCHASTIC_K': 14,
    'STOCHASTIC_D': 3,
}

# 기본적 분석 기준값 (워런 버핏 스타일)
FUNDAMENTAL_CRITERIA = {
    'MIN_ROE': 15,  # 최소 ROE 15%
    'MAX_DEBT_RATIO': 50,  # 부채비율 50% 이하
    'MIN_CURRENT_RATIO': 150,  # 유동비율 150% 이상
    'MIN_INTEREST_COVERAGE': 5,  # 이자보상배율 5배 이상
}

# 차트 설정
CHART_SETTINGS = {
    'FIGSIZE': (12, 8),
    'DPI': 100,
    'STYLE': 'seaborn',
    'COLORS': {
        'CANDLE_UP': '#FF6B6B',
        'CANDLE_DOWN': '#4ECDC4', 
        'SMA': '#FF9F43',
        'EMA': '#3742FA',
        'RSI_OVERSOLD': '#2ED573',
        'RSI_OVERBOUGHT': '#FF3838'
    }
}
