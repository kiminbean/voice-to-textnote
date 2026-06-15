"""
SPEC-EFFICIENCY-001: 회의 효율성 평가 API

엔드포인트:
- GET /api/v1/analytics/efficiency/{task_id}
  회의 효율성을 다양한 지표로 분석하고 개선 제안을 반환합니다.
  발화 시간 분포, 화자 참여도, 결정 속도, 액션 아이템 생성 등을 분석합니다.
"""


import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_redis_client
from backend.schemas.efficiency import (
    EfficiencyScoreResponse,
)
from backend.services.efficiency_service import EfficiencyService

router = APIRouter(prefix="/efficiency", tags=["efficiency"])


def get_efficiency_service() -> EfficiencyService:
    """EfficiencyService 인스턴스 제공 (FastAPI Depends)"""
    return EfficiencyService()


@router.get("/{task_id}", response_model=EfficiencyScoreResponse)
async def get_meeting_efficiency(
    task_id: str,
    include_recommendations: bool = Query(
        default=True,
        description="개선 제안 포함 여부"
    ),
    min_speakers: int = Query(
        default=2,
        ge=1,
        le=20,
        description="최소 화자 수 (기본값: 2)"
    ),
    analysis_depth: str = Query(
        default="standard",
        pattern="^(basic|standard|detailed)$",
        description="분석 깊이: basic, standard, detailed"
    ),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
    svc: EfficiencyService = Depends(get_efficiency_service),
) -> EfficiencyScoreResponse:
    """
    회의 효율성 평가

    다양한 지표를 통해 회의 효율성을 분석하고 개선 제안을 제공합니다.

    - task_id: 분석할 회의 ID
    - include_recommendations: 개선 제안 포함 여부
    - min_speakers: 최소 화자 수 (1-20)
    - analysis_depth: 분석 깊이 (basic/standard/detailed)
    """

    return await svc.analyze_meeting_efficiency(
        redis_client=redis_client,
        db=db,
        task_id=task_id,
        include_recommendations=include_recommendations,
        min_speakers=min_speakers,
        analysis_depth=analysis_depth
    )
