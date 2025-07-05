"""
Finance Data Vibe - 메인 실행 파일

이 파일은 프로젝트의 메인 진입점입니다.
기본적인 데이터 수집과 분석을 실행합니다.
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.settings import DEFAULT_STOCKS


def main():
    """메인 실행 함수"""
    print("🚀 Finance Data Vibe 시작!")
    print("=" * 50)
    
    print("📋 기본 설정 확인:")
    print(f"분석 대상 종목: {len(DEFAULT_STOCKS)}개")
    for stock in DEFAULT_STOCKS:
        print(f"  - {stock}")
    
    print("\n✅ 프로젝트 설정 완료!")
    print("\n📚 학습을 시작하려면:")
    print("  python examples/basic_examples/01_data_loading.py")
    print("\n🌐 웹 대시보드를 실행하려면:")
    print("  streamlit run src/app.py")


if __name__ == "__main__":
    main()
