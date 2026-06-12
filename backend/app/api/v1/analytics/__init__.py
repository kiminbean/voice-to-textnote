"""
Analytics domain package
하위 호환성을 위해 analytics 모듈의 주요 심볼을 노출합니다.
"""

# analytics 모듈의 심볼들을 패키지 레벨로 노출
from backend.app.api.v1.analytics.advanced_search import router as advanced_search_router
from backend.app.api.v1.analytics.dashboard import router as dashboard_router
from backend.app.api.v1.analytics.enhanced_statistics import router as enhanced_statistics_router
from backend.app.api.v1.analytics.export import router as export_router
from backend.app.api.v1.analytics.keyword_search import router as keyword_search_router
from backend.app.api.v1.analytics.search import router as search_router
from backend.app.api.v1.analytics.sentiment import router as sentiment_router
from backend.app.api.v1.analytics.statistics import router as statistics_router
from backend.app.api.v1.analytics.vocabulary import router as vocabulary_router

__all__ = [
    "advanced_search_router",
    "dashboard_router",
    "enhanced_statistics_router",
    "search_router",
    "sentiment_router",
    "statistics_router",
    "vocabulary_router",
]
