"""
회의록 API 엔드포인트
REQ-MIN-006: POST /api/v1/minutes → 202 Accepted
REQ-MIN-011: GET /api/v1/minutes/{task_id}/status → 상태 조회
REQ-MIN-012: GET /api/v1/minutes/{task_id} → 전체 결과 조회
REQ-MIN-013: Redis 결과 캐싱 24h TTL
REQ-MIN-014: DELETE /api/v1/minutes/{task_id} → 204 No Content
REQ-MIN-015: 존재하지 않는 task_id → 404
"""

import json
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status

from backend.app.config import settings
from backend.app.dependencies import get_redis_client
from backend.app.errors import not_found, too_many_requests
from backend.schemas.minutes import (
    MinutesCreateRequest,
    MinutesPatchRequest,
    MinutesResponse,
    MinutesSegment,
    MinutesStatusResponse,
    SpeakerStats,
)
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/minutes", tags=["minutes"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        429: {"description": "동시 처리 한도 초과"},
    },
)
async def create_minutes(
    request: MinutesCreateRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    """
    회의록 생성 작업 요청
    POST /api/v1/minutes
    """
    # --- 동시 처리 제한 확인 (REQ-MIN-008: 최대 3개) ---
    active_count = await redis_client.scard("active_min_jobs") or 0
    if active_count >= settings.max_concurrent_minutes:
        too_many_requests(
            f"동시 회의록 생성 작업 한도({settings.max_concurrent_minutes}개)를 "
            "초과했습니다. 잠시 후 재시도하세요."
        )

    # --- 작업 ID 생성 및 초기 상태 저장 ---
    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    initial_status = {
        "task_id": task_id,
        "diarization_task_id": request.diarization_task_id,
        "status": TaskStatus.pending.value,
        "progress": 0.0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    status_key = f"task:min:status:{task_id}"
    await redis_client.setex(status_key, settings.minutes_result_ttl, json.dumps(initial_status))

    # --- Celery 작업 등록 (REQ-MIN-006) ---
    from backend.workers.tasks.minutes_task import minutes_celery_task

    minutes_celery_task.delay(
        task_id=task_id,
        diarization_task_id=request.diarization_task_id,
        output_format=request.output_format,
        speaker_names=request.speaker_names,
        stt_task_id=request.stt_task_id,
    )

    logger.info(
        "회의록 생성 작업 등록",
        task_id=task_id,
        diarization_task_id=request.diarization_task_id,
        stt_task_id=request.stt_task_id,
    )

    return {
        "task_id": task_id,
        "diarization_task_id": request.diarization_task_id,
        "status": TaskStatus.pending.value,
        "status_url": f"/api/v1/minutes/{task_id}/status",
        "result_url": f"/api/v1/minutes/{task_id}",
        "created_at": now.isoformat(),
    }


@router.get(
    "/{task_id}/status",
    response_model=MinutesStatusResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_minutes_status(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> MinutesStatusResponse:
    """
    회의록 작업 상태 조회
    GET /api/v1/minutes/{task_id}/status
    """
    status_key = f"task:min:status:{task_id}"
    raw = await redis_client.get(status_key)

    if raw is None:
        not_found("회의록 작업을 찾을 수 없습니다.")

    data = json.loads(raw)

    return MinutesStatusResponse(
        task_id=task_id,
        status=TaskStatus(data["status"]),
        progress=data.get("progress", 0.0),
        message=data.get("message"),
        error_message=data.get("error_message"),
    )


@router.get(
    "/{task_id}",
    response_model=MinutesResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_minutes_result(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> MinutesResponse:
    """
    회의록 결과 전체 조회
    GET /api/v1/minutes/{task_id}
    """
    result_key = f"task:min:result:{task_id}"
    raw = await redis_client.get(result_key)

    if raw is None:
        # Redis 캐시 미스 → 상태 확인
        status_key = f"task:min:status:{task_id}"
        status_raw = await redis_client.get(status_key)

        if status_raw is None:
            not_found("회의록 작업을 찾을 수 없습니다.")

        status_data = json.loads(status_raw)
        task_status = TaskStatus(status_data["status"])

        # 아직 처리 중 → 빈 결과 반환
        return MinutesResponse(
            task_id=task_id,
            status=task_status,
            diarization_task_id=status_data.get("diarization_task_id", ""),
            segments=[],
            speakers=[],
            total_duration=0.0,
            total_speakers=0,
            error_message=status_data.get("error_message"),
        )

    data = json.loads(raw)

    # MinutesSegment, SpeakerStats 객체 변환
    segments = [MinutesSegment(**seg) for seg in data.get("segments", [])]
    speakers = [SpeakerStats(**sp) for sp in data.get("speakers", [])]

    return MinutesResponse(
        task_id=data["task_id"],
        status=TaskStatus(data["status"]),
        diarization_task_id=data["diarization_task_id"],
        segments=segments,
        speakers=speakers,
        total_duration=data.get("total_duration", 0.0),
        total_speakers=data.get("total_speakers", 0),
        markdown=data.get("markdown"),
        error_message=data.get("error_message") or data.get("error"),
    )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_minutes(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> None:
    """
    회의록 작업 및 결과 삭제
    DELETE /api/v1/minutes/{task_id}
    """
    # Redis 캐시 삭제 (상태 + 결과)
    await redis_client.delete(
        f"task:min:status:{task_id}",
        f"task:min:result:{task_id}",
    )

    logger.info("회의록 작업 삭제", task_id=task_id)


@router.patch(
    "/{task_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "작업 없음"}},
)
async def patch_minutes(
    task_id: str,
    request: MinutesPatchRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    """
    협업 편집 결과 부분 업데이트 (SPEC-COLLAB-001, REQ-COLLAB-020)
    PATCH /api/v1/minutes/{task_id}
    """
    result_key = f"task:min:result:{task_id}"
    raw = await redis_client.get(result_key)

    if raw is None:
        not_found("회의록 작업을 찾을 수 없습니다.")

    data = json.loads(raw)
    updated_fields = []

    for field, value in request.fields.items():
        if field in ("segments", "speakers", "total_duration", "total_speakers"):
            continue
        data[field] = value
        updated_fields.append(field)

    await redis_client.setex(
        result_key,
        settings.minutes_result_ttl,
        json.dumps(data, ensure_ascii=False),
    )

    logger.info(
        "회의록 부분 업데이트",
        task_id=task_id,
        fields=updated_fields,
    )

    return {"task_id": task_id, "updated_fields": updated_fields}
