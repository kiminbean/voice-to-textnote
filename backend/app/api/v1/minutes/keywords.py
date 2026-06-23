"""
SPEC-KEYWORD-001: 자동 키워드 추출/추천 API

엔드포인트:
- POST /api/v1/keywords/extract
- GET  /api/v1/keywords/{task_id}
- POST /api/v1/keywords/{task_id}/recommend
"""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import (
    get_db_session,
    get_redis_client,
    get_request_context,
    require_task_access,
)
from backend.schemas.keyword import (
    KeywordExtractRequest,
    KeywordRecommendRequest,
    KeywordResponse,
)
from backend.services.keyword_service import KeywordService

router = APIRouter(prefix="/keywords", tags=["keywords"])


def get_keyword_service() -> KeywordService:
    """KeywordService 인스턴스 제공 (FastAPI Depends)"""
    return KeywordService()


@router.post(
    "/extract",
    response_model=KeywordResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_keywords(
    payload: KeywordExtractRequest,
    svc: KeywordService = Depends(get_keyword_service),
) -> KeywordResponse:
    """임의 텍스트에서 TF-IDF + TextRank 하이브리드 키워드를 추출한다."""
    return svc.extract_from_text(
        payload.text,
        language=payload.language,
        max_keywords=payload.max_keywords,
        min_score=payload.min_score,
        source="text",
    )


@router.get(
    "/{task_id}",
    response_model=KeywordResponse,
    responses={404: {"description": "회의 데이터 없음"}},
)
async def get_meeting_keywords(
    task_id: str,
    request: Request = Depends(get_request_context),
    max_keywords: int | None = Query(
        default=None,
        ge=1,
        le=100,
        description="반환할 최대 키워드 수 (기본값: KEYWORD_MAX_KEYWORDS)",
    ),
    min_score: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="최소 중요도 점수 (기본값: KEYWORD_MIN_SCORE)",
    ),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
    svc: KeywordService = Depends(get_keyword_service),
) -> KeywordResponse:
    """기존 회의 task_id의 저장된 회의록/전사 결과에서 키워드를 추출한다."""
    await require_task_access(request, db, task_id)
    return await svc.extract_for_task(
        redis_client=redis_client,
        db=db,
        task_id=task_id,
        max_keywords=max_keywords,
        min_score=min_score,
    )


@router.post(
    "/{task_id}/recommend",
    response_model=KeywordResponse,
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "회의 데이터 없음"}},
)
async def recommend_meeting_keywords(
    task_id: str,
    request: Request = Depends(get_request_context),
    payload: KeywordRecommendRequest | None = None,
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
    svc: KeywordService = Depends(get_keyword_service),
) -> KeywordResponse:
    """현재 회의와 최근 회의 히스토리를 함께 반영해 추천 키워드를 반환한다."""
    await require_task_access(request, db, task_id)
    options = payload or KeywordRecommendRequest()
    return await svc.recommend_for_task(
        redis_client=redis_client,
        db=db,
        task_id=task_id,
        max_keywords=options.max_keywords,
        min_score=options.min_score,
        history_limit=options.history_limit,
    )
