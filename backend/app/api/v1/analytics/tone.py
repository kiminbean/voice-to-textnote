"""
SPEC-TONE-001: 발화 톤/운율 분석 API

엔드포인트:
- GET /tone/{task_id} - 톤 분석 결과 조회 (REQ-TONE-010)
- GET /tone/{task_id}/status - 작업 상태 조회
- GET /tone/meeting/{meeting_id} - 회의 기반 톤 결과 조회
- DELETE /tone/{task_id} - Redis 캐시 삭제

REQ-TONE-011: tone_model 빈 값 시 모든 엔드포인트가 503 반환
"""

import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status

from backend.app.config import settings
from backend.app.dependencies import get_redis_client
from backend.app.errors import not_found, service_unavailable
from backend.schemas.tone import (
    SpeakerTone,
    ToneResponse,
    ToneSegment,
    ToneStatusResponse,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tone", tags=["tone"])

_DISABLED_MSG = "Tone analysis is disabled (tone_model is not configured)"


def _check_tone_enabled() -> None:
    """REQ-TONE-011: tone_model 빈 값 시 503 Service Unavailable"""
    if not settings.tone_model:
        service_unavailable(_DISABLED_MSG)


@router.get(
    "/meeting/{meeting_id}",
    response_model=ToneResponse,
    responses={
        404: {"description": "결과 없음"},
        503: {"description": "tone 기능 비활성화"},
    },
)
async def get_tone_by_meeting(
    meeting_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> ToneResponse:
    """회의 ID로 톤 분석 결과 조회

    tone 결과는 dia_task_id로 저장되지만 클라이언트는 meeting_id로 조회한다.
    minutes result에서 diarization_task_id를 역추적한 뒤 tone 결과를 가져온다.
    """
    _check_tone_enabled()

    minutes_raw = await redis_client.get(f"task:min:result:{meeting_id}")
    if minutes_raw is None:
        minutes_raw = await _lookup_minutes_result_from_db(meeting_id, redis_client)
        if minutes_raw is None:
            direct_raw = await redis_client.get(f"task:tone:result:{meeting_id}")
            if direct_raw is not None:
                return _build_tone_response(json.loads(direct_raw))
            not_found(f"회의록을 찾을 수 없습니다: meeting_id={meeting_id}")

    minutes_data = json.loads(minutes_raw)
    if "segments" in minutes_data and "overall_tone" in minutes_data:
        return _build_tone_response(minutes_data)

    dia_task_id = minutes_data.get("diarization_task_id")
    if not dia_task_id:
        not_found(
            f"회의록에 diarization_task_id가 없습니다: meeting_id={meeting_id}"
        )

    result_key = f"task:tone:result:{dia_task_id}"
    raw = await redis_client.get(result_key)

    if raw is None:
        status_key = f"task:tone:status:{dia_task_id}"
        status_raw = await redis_client.get(status_key)
        if status_raw is None:
            not_found(
                f"톤 분석 결과를 찾을 수 없습니다: meeting_id={meeting_id}, "
                f"dia_task_id={dia_task_id}"
            )
        status_data = json.loads(status_raw)
        return ToneResponse(
            task_id=dia_task_id,
            status=status_data["status"],
        )

    data = json.loads(raw)
    return _build_tone_response(data)


async def _lookup_minutes_result_from_db(
    meeting_id: str,
    redis_client: aioredis.Redis,
) -> str | None:
    """Redis TTL 만료 후 DB에서 minutes 결과로 dia_task_id를 복구한다."""
    try:
        from sqlalchemy import select

        from backend.db.models import TaskResult
        from backend.db.sync_engine import get_sync_session

        with get_sync_session() as session:
            stmt = select(TaskResult).where(
                TaskResult.task_id == meeting_id,
                TaskResult.task_type == "minutes",
            )
            record = session.scalars(stmt).first()
            if record and record.result_data:
                return json.dumps(record.result_data)
        return None
    except Exception as e:
        logger.warning(
            "DB에서 minutes 결과 조회 실패, Redis 폴백 불가",
            meeting_id=meeting_id,
            error=str(e),
        )
        return None


@router.get(
    "/{task_id}/status",
    response_model=ToneStatusResponse,
    responses={
        404: {"description": "작업 없음"},
        503: {"description": "tone 기능 비활성화"},
    },
)
async def get_tone_status(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> ToneStatusResponse:
    """톤 분석 작업 상태 조회"""
    _check_tone_enabled()

    status_key = f"task:tone:status:{task_id}"
    raw = await redis_client.get(status_key)

    if raw is None:
        not_found("톤 분석 작업을 찾을 수 없습니다.")

    data = json.loads(raw)
    return ToneStatusResponse(
        task_id=task_id,
        status=data["status"],
        progress=data.get("progress"),
        message=data.get("message"),
        error_message=data.get("error_message"),
    )


@router.get(
    "/{task_id}",
    response_model=ToneResponse,
    responses={
        404: {"description": "작업 없음"},
        503: {"description": "tone 기능 비활성화"},
    },
)
async def get_tone_result(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> ToneResponse:
    """톤 분석 전체 결과 조회 (REQ-TONE-010)"""
    _check_tone_enabled()

    result_key = f"task:tone:result:{task_id}"
    raw = await redis_client.get(result_key)

    if raw is None:
        # 결과 미존재 시 상태라도 있는지 확인 (processing 중일 수 있음)
        status_key = f"task:tone:status:{task_id}"
        status_raw = await redis_client.get(status_key)
        if status_raw is None:
            not_found("톤 분석 작업을 찾을 수 없습니다.")

        status_data = json.loads(status_raw)
        return ToneResponse(
            task_id=task_id,
            status=status_data["status"],
        )

    data = json.loads(raw)
    return _build_tone_response(data)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tone(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> None:
    """톤 분석 Redis 캐시 삭제"""
    _check_tone_enabled()

    await redis_client.delete(
        f"task:tone:status:{task_id}",
        f"task:tone:result:{task_id}",
    )
    logger.info("톤 분석 작업 삭제", task_id=task_id)


def _build_tone_response(data: dict) -> ToneResponse:
    """Redis에서 가져온 dict를 ToneResponse로 변환"""
    segments = [
        ToneSegment(
            start=seg.get("start", 0.0),
            end=seg.get("end", 0.0),
            speaker=seg.get("speaker", "UNKNOWN"),
            tone=seg.get("tone", "unknown"),
            confidence=seg.get("confidence", 0.0),
            prosody_features=seg.get("prosody_features", {}),
        )
        for seg in data.get("segments", [])
    ]

    speakers = [
        SpeakerTone(
            speaker=sp.get("speaker", "UNKNOWN"),
            dominant_tone=sp.get("dominant_tone", "unknown"),
            tone_distribution=sp.get("tone_distribution", {}),
            avg_pitch=sp.get("avg_pitch", 0.0),
            avg_energy=sp.get("avg_energy", 0.0),
        )
        for sp in data.get("speakers", [])
    ]

    return ToneResponse(
        task_id=data.get("task_id", ""),
        status=data.get("status", "unknown"),
        segments=segments,
        speakers=speakers,
        overall_tone=data.get("overall_tone", "unknown"),
        error_message=data.get("error_message") or data.get("error"),
    )
