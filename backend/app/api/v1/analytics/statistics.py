"""
SPEC-STATS-001: 회의 통계 대시보드 API

엔드포인트:
- GET /api/v1/statistics/{task_id}
  해당 minutes 작업의 화자 발화 시간/비율, 세그먼트 수, 단어 수, 키워드 빈도를 반환한다.
  읽기 전용이며 저장소 구조를 변경하지 않는다.
"""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_redis_client
from backend.schemas.statistics import StatisticsResponse
from backend.services.statistics import StatisticsService

router = APIRouter(prefix="/statistics", tags=["statistics"])


def get_statistics_service() -> StatisticsService:
    """StatisticsService 인스턴스 제공 (FastAPI Depends)"""
    return StatisticsService()


@router.get("/{task_id}", response_model=StatisticsResponse)
async def get_statistics(
    task_id: str,
    top_n: int | None = Query(
        default=None,
        ge=1,
        le=200,
        description="상위 키워드 수 (기본값: STATISTICS_KEYWORD_TOP_N)",
    ),
    min_length: int | None = Query(
        default=None,
        ge=1,
        le=10,
        description="키워드 최소 글자 수 (기본값: STATISTICS_KEYWORD_MIN_LENGTH)",
    ),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
    svc: StatisticsService = Depends(get_statistics_service),
) -> StatisticsResponse:
    """회의 통계 조회. minutes 결과가 있어야 동작한다."""
    return await svc.compute(
        redis_client=redis_client,
        db=db,
        task_id=task_id,
        keyword_top_n=top_n,
        keyword_min_length=min_length,
    )
