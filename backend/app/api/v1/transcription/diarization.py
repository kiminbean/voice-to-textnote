"""
화자 분리 API 엔드포인트
REQ-DIA-019~022: REST API 화자 분리 요청/조회/삭제
"""

import inspect
import json
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.dependencies import (
    get_db_session,
    get_redis_client,
    get_request_context,
    require_task_access,
)
from backend.app.errors import not_found, too_many_requests
from backend.app.result_fallback import get_result_with_fallback
from backend.schemas.diarization import (
    DiarizationCreateRequest,
    DiarizationResponse,
    DiarizationStatusResponse,
)
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/diarizations", tags=["diarizations"])


async def _scard(redis_client: aioredis.Redis, key: str) -> int:
    value = redis_client.scard(key)
    return int(await value if inspect.isawaitable(value) else value)


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
    http_request = Depends(get_request_context),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    """
    화자 분리 작업 생성
    POST /api/v1/diarizations
    """
    # --- 동시 처리 제한 확인 (REQ-DIA-014: 최대 2개) ---
    active_count = await _scard(redis_client, "active_dia_jobs")
    if active_count >= settings.max_concurrent_diarizations:
        too_many_requests(
            f"동시 화자 분리 작업 한도({settings.max_concurrent_diarizations}개)를 "
            "초과했습니다. 잠시 후 재시도하세요."
        )

    # --- 작업 ID 생성 및 초기 상태 저장 ---
    task_id = str(uuid.uuid4())
    stt_task_id_str = str(request.stt_task_id)
    now = datetime.now(UTC)
    has_request = isinstance(http_request, Request)
    user_id = getattr(http_request.state, "user_id", None) if has_request else None
    is_guest = bool(getattr(http_request.state, "is_guest", False)) if has_request else False
    guest_session_id = getattr(http_request.state, "guest_session_id", None) if has_request else None

    initial_status = {
        "task_id": task_id,
        "stt_task_id": stt_task_id_str,
        "status": TaskStatus.pending.value,
        "progress": 0.0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "user_id": str(user_id) if user_id else None,
        "is_guest": is_guest,
        "guest_session_id": guest_session_id,
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
        user_id=user_id,
        is_guest=is_guest,
        guest_session_id=guest_session_id,
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
    http_request = Depends(get_request_context),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db_session: AsyncSession = Depends(get_db_session),
) -> DiarizationStatusResponse:
    """
    화자 분리 작업 상태 폴링
    GET /api/v1/diarizations/{task_id}/status
    """
    status_key = f"task:dia:status:{task_id}"
    raw = await redis_client.get(status_key)

    if raw is None:
        not_found("화자 분리 작업을 찾을 수 없습니다.")

    data = json.loads(raw)
    await require_task_access(http_request, db_session, task_id, data)

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
    http_request = Depends(get_request_context),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db_session: AsyncSession = Depends(get_db_session),
) -> DiarizationResponse:
    """
    화자 분리 결과 조회
    GET /api/v1/diarizations/{task_id}
    """
    result_key = f"task:dia:result:{task_id}"

    # Redis 캐시 우선, 미스 시 DB 폴백 (REQ-PERSIST-009)
    raw_data = await get_result_with_fallback(
        redis_client=redis_client,
        task_id=task_id,
        redis_key=result_key,
        db_session=db_session,
    )

    if raw_data is None:
        # Redis + DB 모두 미스 → 상태 키 확인
        status_key = f"task:dia:status:{task_id}"
        status_raw = await redis_client.get(status_key)
        if status_raw is None:
            not_found("화자 분리 작업을 찾을 수 없습니다.")

        status_data = json.loads(status_raw)
        await require_task_access(http_request, db_session, task_id, status_data)
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

    from backend.schemas.diarization import DiarizedSegmentResult, SpeakerInfo

    await require_task_access(http_request, db_session, task_id, raw_data)
    segments = [DiarizedSegmentResult(**seg) for seg in raw_data.get("segments", [])]
    speakers = [SpeakerInfo(**sp) for sp in raw_data.get("speakers", [])]

    return DiarizationResponse(
        task_id=raw_data["task_id"],  # type: ignore[arg-type]
        stt_task_id=raw_data.get("stt_task_id", task_id),  # type: ignore[arg-type]
        status=TaskStatus(raw_data["status"]),
        segments=segments,
        speakers=speakers,
        num_speakers=raw_data.get("num_speakers"),
        created_at=datetime.fromisoformat(raw_data["created_at"])
        if raw_data.get("created_at")
        else datetime.now(UTC),
        completed_at=(
            datetime.fromisoformat(raw_data["completed_at"])
            if raw_data.get("completed_at")
            else None
        ),
        error_message=raw_data.get("error_message") or raw_data.get("error"),
    )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_diarization(
    task_id: str,
    http_request = Depends(get_request_context),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db_session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    화자 분리 작업 및 결과 삭제
    DELETE /api/v1/diarizations/{task_id}
    """
    status_raw = await redis_client.get(f"task:dia:status:{task_id}")
    result_raw = await redis_client.get(f"task:dia:result:{task_id}")
    payload = json.loads(result_raw or status_raw) if (result_raw or status_raw) else None
    await require_task_access(http_request, db_session, task_id, payload)

    # Redis 캐시 삭제
    await redis_client.delete(
        f"task:dia:status:{task_id}",
        f"task:dia:result:{task_id}",
    )

    logger.info("화자 분리 작업 삭제", task_id=task_id)
