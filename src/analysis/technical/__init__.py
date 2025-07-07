"""
기술적 분석 모듈
src/analysis/technical/__init__.py

워런 버핏 스타일 가치투자를 위한 기술적 분석 도구들을 제공합니다.

주요 클래스:
- ValueInvestingTechnicalAnalyzer: 가치투자 최적화 기술적 분석기

사용법:
    from src.analysis.technical import ValueInvestingTechnicalAnalyzer
    
    analyzer = ValueInvestingTechnicalAnalyzer()
    result = analyzer.analyze_stock_timing('005930')
"""

from .technical_analysis import ValueInvestingTechnicalAnalyzer

__all__ = ['ValueInvestingTechnicalAnalyzer']

__version__ = '1.0.0'
__author__ = 'Finance Data Vibe Team'