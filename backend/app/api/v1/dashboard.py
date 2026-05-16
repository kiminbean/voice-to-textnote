"""
SPEC-STATS-002: 전체 회의 통계 대시보드 API

엔드포인트:
- GET /api/v1/statistics/dashboard/overview
  전체 회의에 대한 종합 통계 (총 회의 수, 총 발화 시간, 평균 회의 길이, 상위 화자, 상위 키워드)
"""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_redis_client
from backend.db.models import TaskResult
from backend.services.statistics import StatisticsService

router = APIRouter(prefix="/statistics", tags=["statistics"])
_service = StatisticsService()


class DashboardOverview(BaseModel):
    """전체 회의 통계 요약"""
    total_meetings: int = Field(description="완료된 총 회의 수")
    total_duration_seconds: float = Field(description="전체 회의 총 발화 시간 (초)")
    avg_duration_seconds: float = Field(description="평균 회의 발화 시간 (초)")
    total_words: int = Field(description="전체 발화 단어 수")
    total_segments: int = Field(description="전체 발화 세그먼트 수")
    unique_speakers: int = Field(description="고유 화자 수")


@router.get(
    "/dashboard/overview",
    response_model=DashboardOverview,
    summary="전체 회의 통계 요약",
    description="완료된 모든 회의에 대한 종합 통계를 반환합니다.",
)
async def get_dashboard_overview(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="집계할 최근 회의 수",
    ),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
) -> DashboardOverview:
    """전체 회의 대시보드 통계. 최근 limit 개의 완료된 minutes 결과를 집계."""

    # DB에서 완료된 minutes 태스크 조회
    stmt = (
        select(TaskResult)
        .where(
            TaskResult.task_type == "minutes",
            TaskResult.status == "completed",
        )
        .order_by(TaskResult.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    if not records:
        return DashboardOverview(
            total_meetings=0,
            total_duration_seconds=0.0,
            avg_duration_seconds=0.0,
            total_words=0,
            total_segments=0,
            unique_speakers=0,
        )

    all_speakers: set[str] = set()
    total_duration = 0.0
    total_words = 0
    total_segments = 0

    for record in records:
        data = record.result_data
        if not data or not isinstance(data, dict):
            continue

        segments = data.get("segments") or []
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            try:
                start = float(seg.get("start", 0) or 0)
                end = float(seg.get("end", 0) or 0)
            except (TypeError, ValueError):
                continue

            duration = max(0.0, end - start)
            text = str(seg.get("text") or "")
            speaker = str(seg.get("speaker") or "UNKNOWN")

            # 단어 수 (공백 분할)
            word_count = len([t for t in text.split() if t])

            total_duration += duration
            total_words += word_count
            total_segments += 1
            all_speakers.add(speaker)

    meeting_count = len(records)
    avg_duration = (total_duration / meeting_count) if meeting_count > 0 else 0.0

    return DashboardOverview(
        total_meetings=meeting_count,
        total_duration_seconds=round(total_duration, 3),
        avg_duration_seconds=round(avg_duration, 3),
        total_words=total_words,
        total_segments=total_segments,
        unique_speakers=len(all_speakers),
    )
