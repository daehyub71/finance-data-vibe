"""
📚 학습 예제 1: 데이터 로딩 기초

이 예제에서 배울 내용:
1. FinanceDataReader 사용법
2. 주식 데이터의 구조 이해  
3. 데이터 전처리 기본기
4. 판다스 DataFrame 활용법

🎯 학습 목표: 주식 데이터 로딩과 기본 구조 완전 이해
"""

import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from datetime import datetime

# Windows 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'  # 맑은 고딕
plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지

# 또는 다른 한글 폰트들
# plt.rcParams['font.family'] = 'NanumGothic'
# plt.rcParams['font.family'] = 'Batang'
# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

try:
    import FinanceDataReader as fdr
    import pandas as pd
    import matplotlib.pyplot as plt
    from config.settings import DEFAULT_STOCKS
except ImportError as e:
    print(f"❌ 패키지 설치 필요: {e}")
    print("터미널에서 'pip install -r requirements.txt' 실행하세요!")
    exit(1)


def learn_data_loading():
    """
    🎯 학습 목표: 주식 데이터 로딩과 기본 구조 이해
    """
    
    print("=" * 60)
    print("📊 Finance Data Vibe - 첫 번째 학습 시작!")
    print("=" * 60)
    
    # 1. 한국 주식 데이터 로딩
    print("\n1️⃣ 삼성전자 데이터 로딩 중...")
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        samsung = fdr.DataReader('005930', '2023-01-01', today)
        #samsung = fdr.DataReader('005930', '2023-01-01', '2024-01-01')
        print(f"✅ 데이터 로딩 완료! 총 {len(samsung)}개 행")
        print(f"📅 기간: {samsung.index[0].date()} ~ {samsung.index[-1].date()}")
    except Exception as e:
        print(f"❌ 데이터 로딩 실패: {e}")
        return
    
    # 2. 데이터 구조 탐색  
    print("\n2️⃣ 데이터 구조 분석")
    print("컬럼들:", samsung.columns.tolist())
    print("\n데이터 타입:")
    print(samsung.dtypes)
    
    print("\n처음 5개 행:")
    print(samsung.head())
    
    # 3. 기본 통계 정보
    print("\n3️⃣ 기본 통계 정보")
    print(samsung.describe())
    
    # 4. 간단한 분석
    print("\n4️⃣ 간단한 분석")
    print(f"최고가: {samsung['High'].max():,}원")
    print(f"최저가: {samsung['Low'].min():,}원") 
    print(f"평균 거래량: {samsung['Volume'].mean():,.0f}주")
    
    # 5. 기본 차트 (선택사항)
    try:
        print("\n5️⃣ 기본 차트 생성 중...")
        plt.figure(figsize=(12, 6))
        plt.plot(samsung.index, samsung['Close'], label='삼성전자 종가', linewidth=1)
        # 동적 제목 생성 (시작일과 종료일 반영)
        start_date = samsung.index[0].strftime('%Y.%m')
        end_date = samsung.index[-1].strftime('%Y.%m')
        plt.title(f'삼성전자 주가 차트 ({start_date} ~ {end_date})', fontsize=16)
        plt.xlabel('날짜')
        plt.ylabel('주가 (원)')
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
        print("✅ 차트 생성 완료!")
    except Exception as e:
        print(f"⚠️ 차트 생성 실패 (선택사항): {e}")
    
    # 6. 학습 정리
    print("\n" + "=" * 60)
    print("🎓 학습 내용 정리:")
    print("✅ OHLCV 데이터 구조: Open, High, Low, Close, Volume")
    print("✅ 인덱스는 날짜(DatetimeIndex)로 구성")
    print("✅ 결측값 확인과 데이터 품질 검증 중요")
    print("✅ matplotlib으로 기본 차트 생성 가능")
    print("=" * 60)
    
    print("\n🚀 다음 단계: examples/basic_examples/02_simple_charts.py")


if __name__ == "__main__":
    learn_data_loading()
