"""
화자 분리 API 엔드포인트
REQ-DIA-019~022: REST API 화자 분리 요청/조회/삭제
"""

import json
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.config import settings
from backend.app.dependencies import get_redis_client
from backend.schemas.diarization import (
    DiarizationCreateRequest,
    DiarizationResponse,
    DiarizationStatusResponse,
)
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/diarizations", tags=["diarizations"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        429: {"description": "동시 처리 한도 초과"},
        503: {"description": "메모리 임계값 초과"},
    },
)
async def create_diarization(
    request: DiarizationCreateRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    """
    화자 분리 작업 생성
    POST /api/v1/diarizations
    """
    # --- 동시 처리 제한 확인 (REQ-DIA-014: 최대 2개) ---
    active_count = await redis_client.scard("active_dia_jobs") or 0
    if active_count >= settings.max_concurrent_diarizations:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"동시 화자 분리 작업 한도({settings.max_concurrent_diarizations}개)를 "
                "초과했습니다. 잠시 후 재시도하세요."
            ),
        )

    # --- 작업 ID 생성 및 초기 상태 저장 ---
    task_id = str(uuid.uuid4())
    stt_task_id_str = str(request.stt_task_id)
    now = datetime.now(UTC)

    initial_status = {
        "task_id": task_id,
        "stt_task_id": stt_task_id_str,
        "status": TaskStatus.pending.value,
        "progress": 0.0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    status_key = f"task:dia:status:{task_id}"
    await redis_client.setex(
        status_key, settings.diarization_result_ttl, json.dumps(initial_status)
    )

    # --- Celery 작업 등록 ---
    from backend.workers.tasks.diarization_task import diarization_celery_task

    diarization_celery_task.delay(
        task_id=task_id,
        stt_task_id=stt_task_id_str,
        num_speakers=request.num_speakers,
        min_speakers=request.min_speakers,
        max_speakers=request.max_speakers,
    )

    logger.info(
        "화자 분리 작업 등록",
        task_id=task_id,
        stt_task_id=stt_task_id_str,
    )

    return {
        "task_id": task_id,
        "stt_task_id": stt_task_id_str,
        "status": TaskStatus.pending.value,
        "status_url": f"/api/v1/diarizations/{task_id}/status",
        "result_url": f"/api/v1/diarizations/{task_id}",
        "created_at": now.isoformat(),
    }


@router.get(
    "/{task_id}/status",
    response_model=DiarizationStatusResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_diarization_status(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> DiarizationStatusResponse:
    """
    화자 분리 작업 상태 폴링
    GET /api/v1/diarizations/{task_id}/status
    """
    status_key = f"task:dia:status:{task_id}"
    raw = await redis_client.get(status_key)

    if raw is None:
        raise HTTPException(status_code=404, detail="화자 분리 작업을 찾을 수 없습니다.")

    data = json.loads(raw)

    now = datetime.now(UTC)
    created_at_str = data.get("created_at")
    updated_at_str = data.get("updated_at")

    return DiarizationStatusResponse(
        task_id=task_id,  # type: ignore[arg-type]
        stt_task_id=data.get("stt_task_id", task_id),  # type: ignore[arg-type]
        status=TaskStatus(data["status"]),
        progress=data.get("progress", 0.0),
        message=data.get("message"),
        error_message=data.get("error_message"),
        created_at=datetime.fromisoformat(created_at_str) if created_at_str else now,
        updated_at=datetime.fromisoformat(updated_at_str) if updated_at_str else now,
    )


@router.get(
    "/{task_id}",
    response_model=DiarizationResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_diarization_result(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> DiarizationResponse:
    """
    화자 분리 결과 조회
    GET /api/v1/diarizations/{task_id}
    """
    result_key = f"task:dia:result:{task_id}"
    raw = await redis_client.get(result_key)

    if raw is None:
        # Redis 캐시 미스 → 상태 확인
        status_key = f"task:dia:status:{task_id}"
        status_raw = await redis_client.get(status_key)
        if status_raw is None:
            raise HTTPException(status_code=404, detail="화자 분리 작업을 찾을 수 없습니다.")

        status_data = json.loads(status_raw)
        task_status = TaskStatus(status_data["status"])
        ca_str = status_data.get("created_at")
        created_at = datetime.fromisoformat(ca_str) if ca_str else datetime.now(UTC)
        stt_task_id = status_data.get("stt_task_id", task_id)

        return DiarizationResponse(
            task_id=task_id,  # type: ignore[arg-type]
            stt_task_id=stt_task_id,  # type: ignore[arg-type]
            status=task_status,
            segments=[],
            speakers=[],
            created_at=created_at,
            error_message=status_data.get("error_message"),
        )

    data = json.loads(raw)

    from backend.schemas.diarization import DiarizedSegmentResult, SpeakerInfo

    segments = [DiarizedSegmentResult(**seg) for seg in data.get("segments", [])]
    speakers = [SpeakerInfo(**sp) for sp in data.get("speakers", [])]

    return DiarizationResponse(
        task_id=data["task_id"],  # type: ignore[arg-type]
        stt_task_id=data.get("stt_task_id", task_id),  # type: ignore[arg-type]
        status=TaskStatus(data["status"]),
        segments=segments,
        speakers=speakers,
        num_speakers=data.get("num_speakers"),
        created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(UTC),
        completed_at=(
            datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
        ),
        error_message=data.get("error_message") or data.get("error"),
    )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_diarization(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> None:
    """
    화자 분리 작업 및 결과 삭제
    DELETE /api/v1/diarizations/{task_id}
    """
    # Redis 캐시 삭제
    await redis_client.delete(
        f"task:dia:status:{task_id}",
        f"task:dia:result:{task_id}",
    )

    logger.info("화자 분리 작업 삭제", task_id=task_id)
