"""
SPEC-ENHANCED-STATS-001: 고급 통계 대시보드 API

엔드포인트:
- GET /api/v1/enhanced-statistics/{task_id}
  고급 통계 제공: 시계열 데이터, 화자 참여도 패턴, 키워드 빈도 추이, 회의 효율성 지표
- GET /api/v1/enhanced-statistics/overview
  전체 프로젝트 통계 개요
"""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import (
    get_db_session,
    get_redis_client,
    get_request_context,
    require_task_access,
)
from backend.schemas.enhanced_statistics import (
    EnhancedStatisticsResponse,
    OverviewResponse,
)
from backend.services.enhanced_statistics import EnhancedStatisticsService

router = APIRouter(prefix="/enhanced-statistics", tags=["enhanced_statistics"])


def get_enhanced_statistics_service() -> EnhancedStatisticsService:
    """EnhancedStatisticsService 인스턴스 제공 (FastAPI Depends)"""
    return EnhancedStatisticsService()


@router.get("/{task_id}", response_model=EnhancedStatisticsResponse)
async def get_enhanced_statistics(
    task_id: str,
    request: Request = Depends(get_request_context),
    time_range: str = Query(
        default="7d", pattern="^(1d|7d|30d|90d)$", description="시간 범위 (1d, 7d, 30d, 90d)"
    ),
    top_n_keywords: int = Query(default=10, ge=1, le=50, description="상위 키워드 수"),
    include_speaker_analysis: bool = Query(default=True, description="화자별 분석 포함"),
    include_efficiency_metrics: bool = Query(default=True, description="효율성 지표 포함"),
    db: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: EnhancedStatisticsService = Depends(get_enhanced_statistics_service),
) -> EnhancedStatisticsResponse:
    """
    고급 통계 정보 제공

    Args:
        task_id: 분석할 회의록 task ID
        time_range: 분석 시간 범위
        top_n_keywords: 상위 키워드 수
        include_speaker_analysis: 화자별 분석 포함 여부
        include_efficiency_metrics: 효율성 지표 포함 여부
        db: 데이터베이스 세션
        redis_client: Redis 클라이언트
    """
    await require_task_access(request, db, task_id)
    return await svc.get_enhanced_statistics(
        task_id=task_id,
        time_range=time_range,
        top_n_keywords=top_n_keywords,
        include_speaker_analysis=include_speaker_analysis,
        include_efficiency_metrics=include_efficiency_metrics,
        db=db,
        redis_client=redis_client,
    )


@router.get("/overview", response_model=OverviewResponse)
async def get_project_overview(
    period: str = Query(default="30d", pattern="^(7d|30d|90d|180d)$", description="기간 범위"),
    top_meetings: int = Query(default=5, ge=1, le=20, description="상위 회의 수"),
    db: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: EnhancedStatisticsService = Depends(get_enhanced_statistics_service),
) -> OverviewResponse:
    """
    프로젝트 전체 통계 개요

    Args:
        period: 통계 기간
        top_meetings: 상위 회의 수
        db: 데이터베이스 세션
        redis_client: Redis 클라이언트
    """
    return await svc.get_project_overview(
        period=period,
        top_meetings=top_meetings,
        db=db,
        redis_client=redis_client,
    )
