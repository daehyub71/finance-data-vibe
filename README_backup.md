# 🚀 Finance Data Vibe

> 학습 중심의 금융 데이터 분석 및 투자 도구 개발 프로젝트

## 📖 프로젝트 소개

이 프로젝트는 다음과 같은 목적으로 개발되었습니다:

1. **금융 데이터 분석 시스템 구축**
2. **워런 버핏 스타일 가치투자 도구 개발** 
3. **코드 분석 및 학습을 통한 개발 실력 향상** ⭐
4. **GitHub 포트폴리오 구축**

## 🎯 주요 기능

- **📊 실시간 주식 데이터 수집** (한국/미국 시장)
- **📈 30+ 기술적 분석 지표** 구현 및 시각화
- **💰 워런 버핏 스타일 기본적 분석** 
- **📰 뉴스 감정 분석** 기반 투자 신호
- **📱 인터랙티브 웹 대시보드**

## 🏗️ 프로젝트 구조

```
finance-data-vibe/
├── docs/                   # 📚 학습 문서
├── examples/               # 🧪 학습용 예제들  
├── tutorials/              # 📖 단계별 튜토리얼
├── src/                    # 💻 메인 소스코드
├── experiments/            # 🔬 실험 및 탐색
└── tests/                  # 🧪 테스트 코드
```

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (Windows)
venv\Scripts\activate

# 가상환경 활성화 (Mac/Linux)  
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. 첫 번째 실행
```bash
# 기본 데이터 수집 테스트
python examples/basic_examples/01_data_loading.py

# 메인 애플리케이션 실행
python src/main.py
```

### 3. 웹 대시보드 실행
```bash
streamlit run src/app.py
```

## 📚 학습 가이드

### 초급자용
1. `examples/basic_examples/` - 기초 개념 학습
2. `tutorials/` - 단계별 가이드 따라하기
3. `docs/concepts/` - 이론 학습

### 중급자용  
1. `src/analysis/` - 실제 분석 로직 분석
2. `experiments/` - 자유로운 실험
3. 백테스팅 시스템 구축

### 고급자용
1. 머신러닝 모델 통합
2. 실시간 트레이딩 시스템
3. 포트폴리오 최적화

## 🛠️ 기술 스택

- **언어**: Python 3.9+
- **데이터**: FinanceDataReader, yfinance
- **분석**: pandas, numpy, scipy
- **시각화**: matplotlib, plotly, seaborn  
- **웹앱**: Streamlit
- **개발도구**: VS Code, Black, Pylint

## 📈 주요 분석 지표

### 기술적 분석
- 추세: SMA, EMA, MACD, ADX
- 모멘텀: RSI, Stochastic, Williams %R
- 변동성: Bollinger Bands, ATR
- 거래량: OBV, VWAP

### 기본적 분석  
- 수익성: ROE, ROA, 영업이익률
- 성장성: 매출/이익 성장률
- 안정성: 부채비율, 유동비율
- 밸류에이션: PER, PBR, PEG

## 📝 학습 노트

개인 학습 진도와 이해한 내용은 `LEARNING_NOTES.md`에서 관리하세요.

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 📞 문의

프로젝트 관련 문의나 학습 관련 질문은 GitHub Issues를 통해 남겨주세요!

---

⭐ 이 프로젝트가 도움이 되었다면 Star를 눌러주세요!
