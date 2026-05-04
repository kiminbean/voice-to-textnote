"""
감정 분석 API 엔드포인트
SPEC-SENTIMENT-001:
- POST /api/v1/sentiment → 감정 분석 작업 요청 (202 Accepted)
- GET /api/v1/sentiment/{task_id}/status → 상태 조회
- GET /api/v1/sentiment/{task_id} → 전체 결과 조회
- GET /api/v1/sentiment/meeting/{meeting_id} → 회의 ID로 감정 분석 결과 조회
- DELETE /api/v1/sentiment/{task_id} → 삭제
"""

import json
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.dependencies import get_redis_client
from backend.schemas.sentiment import (
    SentimentCreateRequest,
    SentimentResponse,
    SentimentStatusResponse,
)
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses={429: {"description": "동시 처리 한도 초과"}},
)
async def create_sentiment(
    request: SentimentCreateRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    """감정 분석 작업 요청 — POST /api/v1/sentiment"""
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
    """감정 분석 상태 조회 — GET /api/v1/sentiment/{task_id}/status"""
    status_key = f"task:sentiment:status:{task_id}"
    raw = await redis_client.get(status_key)

    if raw is None:
        raise HTTPException(status_code=404, detail="감정 분석 작업을 찾을 수 없습니다.")

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
    """감정 분석 결과 전체 조회 — GET /api/v1/sentiment/{task_id}"""
    result_key = f"task:sentiment:result:{task_id}"
    raw = await redis_client.get(result_key)

    if raw is None:
        status_key = f"task:sentiment:status:{task_id}"
        status_raw = await redis_client.get(status_key)
        if status_raw is None:
            raise HTTPException(status_code=404, detail="감정 분석 작업을 찾을 수 없습니다.")
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
    """감정 분석 작업 및 결과 삭제 — DELETE /api/v1/sentiment/{task_id}"""
    await redis_client.delete(
        f"task:sentiment:status:{task_id}",
        f"task:sentiment:result:{task_id}",
    )
    logger.info("감정 분석 작업 삭제", task_id=task_id)
