"""
화자별 회의 통계 API

엔드포인트:
- GET   /api/v1/speakers/{speaker_id}/meetings        해당 화자의 회의 목록
- GET   /api/v1/speakers/{speaker_id}/statistics       화자별 통계
- GET   /api/v1/speakers/{speaker_id}/activity-timeline 활동 시간대 분석
- GET   /api/v1/speakers/{speaker_id}/participation     참여도 분석
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.auth_models import User
from backend.db.models import TaskResult
from backend.db.speaker_models import SpeakerProfile
from backend.schemas.speaker_statistics import (
    SpeakerActivityTimelineResponse,
    SpeakerMeetingsResponse,
    SpeakerParticipationResponse,
    SpeakerStatisticsResponse,
)
from backend.services.speaker_statistics_service import SpeakerStatisticsService

router = APIRouter(prefix="/speakers", tags=["speaker-statistics"])


def get_speaker_statistics_service() -> SpeakerStatisticsService:
    """SpeakerStatisticsService 인스턴스 제공 (FastAPI Depends)"""
    return SpeakerStatisticsService()


@router.get("/{speaker_id}/meetings", response_model=SpeakerMeetingsResponse)
async def get_speaker_meetings(
    speaker_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: Optional[datetime] = Query(None, description="시작 날짜"),
    date_to: Optional[datetime] = Query(None, description="종료 날짜"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerStatisticsService = Depends(get_speaker_statistics_service),
) -> SpeakerMeetingsResponse:
    """화자가 참여한 회의 목록."""
    offset = (page - 1) * page_size
    meetings, total = await svc.get_speaker_meetings(
        session=db,
        speaker_id=speaker_id,
        user_id=user.id,
        date_from=date_from,
        date_to=date_to,
        limit=page_size,
        offset=offset,
    )
    return SpeakerMeetingsResponse(
        items=meetings,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{speaker_id}/statistics", response_model=SpeakerStatisticsResponse)
async def get_speaker_statistics(
    speaker_id: uuid.UUID,
    date_from: Optional[datetime] = Query(None, description="통계 시작 날짜"),
    date_to: Optional[datetime] = Query(None, description="통계 종료 날짜"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerStatisticsService = Depends(get_speaker_statistics_service),
) -> SpeakerStatisticsResponse:
    """화자별 회의 통계."""
    stats = await svc.get_speaker_statistics(
        session=db,
        speaker_id=speaker_id,
        user_id=user.id,
        date_from=date_from,
        date_to=date_to,
    )
    return stats


@router.get("/{speaker_id}/activity-timeline", response_model=SpeakerActivityTimelineResponse)
async def get_speaker_activity_timeline(
    speaker_id: uuid.UUID,
    date_from: Optional[datetime] = Query(None, description="분석 시작 날짜"),
    date_to: Optional[datetime] = Query(None, description="분석 종료 날짜"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerStatisticsService = Depends(get_speaker_statistics_service),
) -> SpeakerActivityTimelineResponse:
    """화자별 활동 시간대 분석."""
    timeline = await svc.get_activity_timeline(
        session=db,
        speaker_id=speaker_id,
        user_id=user.id,
        date_from=date_from,
        date_to=date_to,
    )
    return timeline


@router.get("/{speaker_id}/participation", response_model=SpeakerParticipationResponse)
async def get_speaker_participation(
    speaker_id: uuid.UUID,
    date_from: Optional[datetime] = Query(None, description="분석 시작 날짜"),
    date_to: Optional[datetime] = Query(None, description="분석 종료 날짜"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerStatisticsService = Depends(get_speaker_statistics_service),
) -> SpeakerParticipationResponse:
    """화자별 참여도 분석."""
    participation = await svc.get_participation_analysis(
        session=db,
        speaker_id=speaker_id,
        user_id=user.id,
        date_from=date_from,
        date_to=date_to,
    )
    return participation