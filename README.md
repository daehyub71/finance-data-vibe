@"
# 📈 Finance Data Vibe Dashboard

워런 버핏 스타일 가치투자를 위한 완전한 데이터 분석 시스템

## 🚀 실시간 대시보드
**🌐 웹 접속**: [finance-data-vibe.streamlit.app](https://finance-data-vibe.streamlit.app)  
**📱 모바일**: 동일 URL에서 반응형 지원

## 📊 주요 기능
- **2,759개 종목** 실시간 데이터 분석
- **DART 공시정보** 자동 수집 및 분석
- **뉴스 감정분석** 기반 투자 신호
- **워런 버핏 스타일** 가치투자 스크리닝
- **인터랙티브 차트** 및 시각화

## 🛠️ 기술 스택
- **Frontend**: Streamlit, Plotly
- **Backend**: Python, SQLite
- **Data**: FinanceDataReader, DART API, 네이버 뉴스 API
- **Deploy**: Streamlit Community Cloud

## 📂 프로젝트 구조
- `streamlit_app.py`: 메인 대시보드 애플리케이션
- `src/`: 핵심 분석 모듈들
- `examples/`: 학습용 예제 코드들
- `data/`: 수집된 데이터 (샘플)

## 🏃‍♂️ 로컬 실행
\`\`\`bash
pip install -r requirements.txt
streamlit run streamlit_app.py
\`\`\`

## 📈 성과
- ✅ 전종목 데이터 수집 완료
- ✅ 실시간 웹 대시보드 구축
- ✅ 모바일 반응형 지원
- ✅ 자동 배포 파이프라인

---
**개발자**: Your Name | **GitHub**: [finance-data-vibe](https://github.com/yourusername/finance-data-vibe)
"@ | Out-File -FilePath README.md -Encoding utf8