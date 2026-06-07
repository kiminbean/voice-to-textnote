"""
SPEC-SENTIMENT-001: 회의 감성 분석 API

엔드포인트:
- GET /sentiment/meeting/{meeting_id} - 특정 회의의 감성 분석
- GET /sentiment/trends - 시간별 감성 추이 분석
- GET /sentiment/speaker/{speaker_id} - 화자별 감성 분석
- GET /sentiment/dashboard/summary - 감성 대시보드 요약
- POST /sentiment - 감정 분석 작업 요청 (202 Accepted)
- GET /sentiment/{task_id}/status - 작업 상태 조회
- GET /sentiment/{task_id} - 전체 결과 조회
- DELETE /sentiment/{task_id} - 작업 삭제
"""

import json
import statistics
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.errors import not_found
from backend.db.models import TaskResult
from backend.schemas.sentiment import (
    SentimentCreateRequest,
    SentimentResponse,
    SentimentStatusResponse,
)
from backend.schemas.transcription import TaskStatus
from backend.services.sentiment_service import SentimentService
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


class SentimentLabel(StrEnum):
    """감성 레이블"""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class SentimentScore(BaseModel):
    """감성 점수"""

    positive: float = Field(description="긍정적 감성 비율 (0.0 ~ 1.0)")
    neutral: float = Field(description="중립적 감성 비율 (0.0 ~ 1.0)")
    negative: float = Field(description="부정적 감성 비율 (0.0 ~ 1.0)")
    dominant: SentimentLabel = Field(description="주요 감성")
    overall_score: float = Field(
        description="종합 감성 점수 (-1.0 ~ 1.0, 1=매우 긍정, -1=매우 부정)"
    )


class SentimentAnalysis(BaseModel):
    """회의 감성 분석 결과"""

    meeting_id: str = Field(description="회의 ID")
    segments_analyzed: int = Field(description="분석된 세그먼트 수")
    sentiment_scores: SentimentScore = Field(description="감성 점수")
    key_phrases: dict[str, float] = Field(description="주요 키워드별 감성 점수")
    trend_direction: Literal["improving", "declining", "stable"] = Field(description="추이 방향")


class SpeakerSentiment(BaseModel):
    """화자별 감성 분석"""

    speaker_id: str = Field(description="화자 ID")
    speaker_name: str = Field(description="화자 이름")
    sentiment_score: float = Field(description="평균 감성 점수 (-1.0 ~ 1.0)")
    segments_count: int = Field(description="발화 세그먼트 수")
    positive_ratio: float = Field(description="긍정적 발화 비율")
    negative_ratio: float = Field(description="부정적 발화 비율")


def get_sentiment_service() -> SentimentService:
    """SentimentService 인스턴스 제공 (FastAPI Depends)"""
    return SentimentService()


@router.get(
    "/meeting/{meeting_id}",
    response_model=SentimentAnalysis,
    summary="특정 회의 감성 분석",
    description="지정된 회의록의 감성을 분석합니다.",
)
async def analyze_meeting_sentiment(
    meeting_id: str,
    db: AsyncSession = Depends(get_db_session),
    svc: SentimentService = Depends(get_sentiment_service),
) -> SentimentAnalysis:
    """특정 회의록의 감성을 분석합니다."""
    # 회의록 데이터 조회
    stmt = select(TaskResult).where(
        TaskResult.task_id == meeting_id,
        TaskResult.task_type == "minutes",
        TaskResult.status == "completed",
    )
    result = await db.execute(stmt)
    record = result.scalars().first()

    if not record or not record.result_data:
        raise ValueError(f"회의록 데이터를 찾을 수 없습니다: {meeting_id}")

    data = record.result_data
    segments = data.get("segments", [])

    # 감성 분석 서비스 호출
    analysis = await svc.analyze_meeting_sentiment(segments)

    logger.info(
        "회의 감성 분석 완료",
        meeting_id=meeting_id,
        segments_count=len(segments),
        overall_score=analysis.overall_score,
    )

    return SentimentAnalysis(
        meeting_id=meeting_id,
        segments_analyzed=len(segments),
        sentiment_scores=analysis,
        key_phrases=await svc.extract_key_phrases_with_sentiment(segments),
        trend_direction=svc.calculate_trend_direction(segments),
    )


@router.get(
    "/trends",
    summary="시간별 감성 추이",
    description="지정된 기간 동안의 감성 추이를 분석합니다.",
)
async def analyze_sentiment_trends(
    days: int = Query(default=30, ge=7, le=365, description="분석 기간 (일)"),
    db: AsyncSession = Depends(get_db_session),
    svc: SentimentService = Depends(get_sentiment_service),
) -> dict[str, list[dict]]:
    """시간별 감성 추이 분석"""
    # 지정된 기간 내의 완료된 회의록 조회
    since_date = datetime.utcnow() - timedelta(days=days)

    stmt = (
        select(TaskResult)
        .where(
            TaskResult.task_type == "minutes",
            TaskResult.status == "completed",
            TaskResult.created_at >= since_date,
        )
        .order_by(TaskResult.created_at)
    )

    result = await db.execute(stmt)
    records = result.scalars().all()

    trends = await svc.analyze_historical_trends([r.result_data for r in records if r.result_data])

    logger.info(
        "감성 추이 분석 완료",
        days=days,
        meetings_count=len(records),
    )

    return {
        "trends": trends,
        "period_days": days,
        "meetings_count": len(records),
    }


@router.get(
    "/speaker/{speaker_id}",
    response_model=SpeakerSentiment,
    summary="화자별 감성 분석",
    description="특정 화자의 감성 패턴을 분석합니다.",
)
async def analyze_speaker_sentiment(
    speaker_id: str,
    meeting_id: str | None = Query(
        default=None, description="특정 회의 내에서의 화자 분석 (지정하지 않으면 전체)"
    ),
    db: AsyncSession = Depends(get_db_session),
    svc: SentimentService = Depends(get_sentiment_service),
) -> SpeakerSentiment:
    """특정 화자의 감성을 분석합니다."""
    # 범위 설정: 전체 또는 특정 회의
    meeting_ids = [meeting_id] if meeting_id else None

    segments = await svc.get_speaker_segments(speaker_id, meeting_ids)

    if not segments:
        raise ValueError(f"화자 발화 데이터를 찾을 수 없습니다: {speaker_id}")

    analysis = await svc.analyze_speaker_sentiment(segments)

    logger.info(
        "화자 감성 분석 완료",
        speaker_id=speaker_id,
        segments_count=len(segments),
        sentiment_score=analysis.overall_score,
    )

    return SpeakerSentiment(
        speaker_id=speaker_id,
        speaker_name=analysis.speaker_name,
        sentiment_score=analysis.overall_score,
        segments_count=len(segments),
        positive_ratio=analysis.positive_ratio,
        negative_ratio=analysis.negative_ratio,
    )


@router.get(
    "/dashboard/summary",
    summary="감성 대시보드 요약",
    description="전체 회의 감성 통계를 제공합니다.",
)
async def get_sentiment_dashboard_summary(
    days: int = Query(default=30, ge=7, le=365, description="분석 기간 (일)"),
    db: AsyncSession = Depends(get_db_session),
    svc: SentimentService = Depends(get_sentiment_service),
) -> dict:
    """감성 분석 대시보드 요약 정보"""
    # 기간 내 완료된 회의록 조회
    since_date = datetime.utcnow() - timedelta(days=days)

    stmt = select(TaskResult).where(
        TaskResult.task_type == "minutes",
        TaskResult.status == "completed",
        TaskResult.created_at >= since_date,
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    if not records:
        return {
            "total_meetings": 0,
            "average_sentiment": 0.0,
            "positive_meetings": 0,
            "negative_meetings": 0,
            "trend": "stable",
        }

    # 전체 감성 분석
    all_segments = []
    meeting_sentiments = []

    for record in records:
        if record.result_data and record.result_data.get("segments"):
            segments = record.result_data.get("segments", [])
            all_segments.extend(segments)

            meeting_analysis = await svc.analyze_meeting_sentiment(segments)
            meeting_sentiments.append(meeting_analysis.overall_score)

    # 전체 평균 계산
    average_sentiment = statistics.mean(meeting_sentiments) if meeting_sentiments else 0.0
    positive_meetings = sum(1 for s in meeting_sentiments if s > 0.1)
    negative_meetings = sum(1 for s in meeting_sentiments if s < -0.1)

    # 추이 방향 계산
    trend = svc.calculate_overall_trend(meeting_sentiments)

    return {
        "total_meetings": len(records),
        "average_sentiment": round(average_sentiment, 3),
        "positive_meetings": positive_meetings,
        "negative_meetings": negative_meetings,
        "neutral_meetings": len(meeting_sentiments) - positive_meetings - negative_meetings,
        "trend": trend,
        "period_days": days,
    }


# ---------------------------------------------------------------------------
# 감정 분석 작업 라이프사이클 (minutes/sentiment.py에서 이관)
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses={429: {"description": "동시 처리 한도 초과"}},
)
async def create_sentiment(
    request: SentimentCreateRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    initial_status = {
        "task_id": task_id,
        "minutes_task_id": request.minutes_task_id,
        "status": TaskStatus.pending.value,
        "progress": 0.0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    status_key = f"task:sentiment:status:{task_id}"
    await redis_client.setex(status_key, 86400, json.dumps(initial_status))

    from backend.workers.tasks.sentiment_task import sentiment_celery_task

    sentiment_celery_task.delay(
        task_id=task_id,
        minutes_task_id=request.minutes_task_id,
        max_tokens=request.max_tokens,
    )

    logger.info("감정 분석 작업 등록", task_id=task_id, minutes_task_id=request.minutes_task_id)

    return {
        "task_id": task_id,
        "minutes_task_id": request.minutes_task_id,
        "status": TaskStatus.pending.value,
        "status_url": f"/api/v1/sentiment/{task_id}/status",
        "result_url": f"/api/v1/sentiment/{task_id}",
        "created_at": now.isoformat(),
    }


@router.get(
    "/{task_id}/status",
    response_model=SentimentStatusResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_sentiment_status(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> SentimentStatusResponse:
    status_key = f"task:sentiment:status:{task_id}"
    raw = await redis_client.get(status_key)

    if raw is None:
        not_found("감정 분석 작업을 찾을 수 없습니다.")

    data = json.loads(raw)
    return SentimentStatusResponse(
        task_id=task_id,
        status=data["status"],
        progress=data.get("progress", 0.0),
        message=data.get("message"),
        error_message=data.get("error_message"),
    )


@router.get(
    "/{task_id}",
    response_model=SentimentResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_sentiment_result(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> SentimentResponse:
    result_key = f"task:sentiment:result:{task_id}"
    raw = await redis_client.get(result_key)

    if raw is None:
        status_key = f"task:sentiment:status:{task_id}"
        status_raw = await redis_client.get(status_key)
        if status_raw is None:
            not_found("감정 분석 작업을 찾을 수 없습니다.")
        status_data = json.loads(status_raw)
        return SentimentResponse(
            task_id=task_id,
            status=status_data["status"],
            minutes_task_id=status_data.get("minutes_task_id", ""),
        )

    data = json.loads(raw)
    return SentimentResponse(
        task_id=data["task_id"],
        status=data["status"],
        minutes_task_id=data.get("minutes_task_id", ""),
        overall_sentiment=data.get("overall_sentiment", "neutral"),
        overall_emotion=data.get("overall_emotion", "neutral"),
        segments=data.get("segments", []),
        speakers=data.get("speakers", []),
        emotional_timeline=data.get("emotional_timeline", []),
        generation_time_seconds=data.get("generation_time_seconds"),
        error_message=data.get("error_message") or data.get("error"),
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sentiment(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> None:
    await redis_client.delete(
        f"task:sentiment:status:{task_id}",
        f"task:sentiment:result:{task_id}",
    )
    logger.info("감정 분석 작업 삭제", task_id=task_id)
