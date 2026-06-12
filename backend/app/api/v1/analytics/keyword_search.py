"""
키워드 검색 및 추출 API - 확장 기능

SPEC-KEYWORD-SEARCH-001: 고급 키워드 검색 API
SPEC-KEYWORD-SEARCH-002: 자동 키워드 추천 및 통계

엔드포인트:
- GET /keywords/search - 고급 키워드 검색
- GET /keywords/suggest - 키워드 추천  
- GET /keywords/stats - 키워드 통계
"""

import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, or_

from backend.app.dependencies import get_db_session
from backend.app.errors import unprocessable
from backend.db.models import TaskResult
from backend.schemas.keyword import (
    KeywordSearchResponse,
    KeywordSuggestResponse,
    KeywordStatsResponse,
    KeywordSearchFilter,
    SortOption
)
from backend.services.keyword_service import KeywordService

router = APIRouter(tags=["keywords"])


def get_keyword_service() -> KeywordService:
    """KeywordService 인스턴스 제공 (FastAPI Depends)"""
    return KeywordService()


@router.get("/keywords/search", response_model=KeywordSearchResponse)
async def search_keywords(
    q: str = Query(..., min_length=1, description="검색할 키워드 또는 문구"),
    filter: KeywordSearchFilter = Query(default=KeywordSearchFilter()),
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    page_size: int = Query(default=20, ge=1, le=100, description="페이지당 항목 수"),
    sort: SortOption = Query(default=SortOption.relevance, description="정렬 기준"),
    db: AsyncSession = Depends(get_db_session),
    svc: KeywordService = Depends(get_keyword_service),
) -> KeywordSearchResponse:
    """
    SPEC-KEYWORD-SEARCH-001: 고급 키워드 검색
    
    - 전체 문서에서 키워드 위치 및 컨텍스트 검색
    - 다중 필터링 (날짜, 화자, 문서 유형 등)
    - 정렬 옵션 (관련도, 빈도, 최신순 등)
    - 페이지네이션 지원
    """
    # 키워드 유효성 검증
    q = q.strip()
    if not q or len(q) < 1:
        unprocessable("검색 키워드는 1글자 이상이어야 합니다.")
    
    # 자연어 처리: 여러 키워드 분리
    keywords = [kw.strip() for kw in re.split(r'[\s,，、]+', q) if kw.strip()]
    
    return await svc.search_keywords(
        session=db,
        keywords=keywords,
        filter=filter,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@router.get("/keywords/suggest", response_model=KeywordSuggestResponse)
async def suggest_keywords(
    context: str = Query(..., min_length=3, description="키워드 추천을 위한 문맥"),
    limit: int = Query(default=10, ge=1, le=50, description="추천 키워드 개수"),
    include_synonyms: bool = Query(default=True, description="동의어 포함 여부"),
    db: AsyncSession = Depends(get_db_session),
    svc: KeywordService = Depends(get_keyword_service),
) -> KeywordSuggestResponse:
    """
    SPEC-KEYWORD-SEARCH-002: 자동 키워드 추천
    
    - 문맥 기반 키워드 추천
    - 빈도 기반 추천
    - 동의어 포련 옵션
    - 실시간 검색 추적
    """
    context = context.strip()
    if len(context) < 3:
        unprocessable("문맥은 최소 3글자 이상이어야 합니다.")
    
    return await svc.suggest_keywords(
        session=db,
        context=context,
        limit=limit,
        include_synonyms=include_synonyms,
    )


@router.get("/keywords/stats", response_model=KeywordStatsResponse)
async def get_keyword_statistics(
    period: str = Query(default="30d", regex=r"^\d+[hdwm]$", description="통계 기간 (예: 7d, 2w, 1m)"),
    top_n: int = Query(default=20, ge=1, le=100, description="상위 N개 키워드"),
    include_trends: bool = Query(default=True, description="트렌드 데이터 포함"),
    db: AsyncSession = Depends(get_db_session),
    svc: KeywordService = Depends(get_keyword_service),
) -> KeywordStatsResponse:
    """
    키워드 사용 통계 API
    
    - 기간별 키워드 빈도 통계
    - 트렌드 분석
    - 인기 키워드 순위
    - 시각화를 위한 데이터 포맷
    """
    # 기간 파싱
    period_match = re.match(r'^(\d+)([hdwm])$', period)
    if not period_match:
        unprocessable("기간 형식이 올바르지 않습니다. 예: 7d, 2w, 1m")
    
    value, unit = period_match.groups()
    value = int(value)
    
    # 기간 계산
    now = datetime.utcnow()
    if unit == 'd':  # days
        start_date = now - timedelta(days=value)
    elif unit == 'h':  # hours
        start_date = now - timedelta(hours=value)
    elif unit == 'w':  # weeks
        start_date = now - timedelta(weeks=value)
    elif unit == 'm':  # months (approximate)
        start_date = now - timedelta(days=value * 30)
    
    return await svc.get_keyword_stats(
        session=db,
        start_date=start_date,
        end_date=now,
        top_n=top_n,
        include_trends=include_trends,
    )