"""
전사 API 엔드포인트
REQ-STT-001~004: 오디오 업로드 및 검증
REQ-STT-010~014: 상태 조회 및 결과 반환
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from backend.app.config import settings
from backend.app.dependencies import get_redis_client
from backend.pipeline.audio_processor import get_audio_duration_seconds
from backend.schemas.transcription import (
    TaskStatus,
    TaskStatusResponse,
    TranscriptionCreate,
    TranscriptionResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
)
from backend.utils.logger import get_logger
from backend.utils.validators import validate_audio_format, validate_file_size

logger = get_logger(__name__)

router = APIRouter(prefix="/transcriptions", tags=["transcriptions"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TranscriptionCreate,
    responses={
        422: {"model": ValidationErrorResponse, "description": "파일 검증 실패"},
        429: {"description": "동시 처리 한도 초과"},
    },
)
async def upload_transcription(
    file: UploadFile = File(..., description="오디오 파일 (WAV, MP3, M4A, OGG)"),
    language: str = Form(default="ko", description="전사 언어 코드"),
    model: str = Form(default="mlx-community/whisper-small-mlx"),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> TranscriptionCreate:
    """
    오디오 파일 업로드 및 전사 작업 생성
    POST /api/v1/transcriptions
    """
    errors: list[ValidationErrorDetail] = []

    # --- 파일 형식 검증 (REQ-STT-001, REQ-STT-003) ---
    filename = file.filename or "unknown"
    is_valid_format, format_error = validate_audio_format(filename, file.content_type)
    if not is_valid_format:
        errors.append(
            ValidationErrorDetail(
                field="file",
                message=format_error,
                type="unsupported_format",
            )
        )

    # --- 파일 크기 검증 (REQ-STT-003) ---
    # content_length가 없으면 실제 파일 읽어서 확인
    raw_content = await file.read()
    file_size = len(raw_content)
    is_valid_size, size_error = validate_file_size(file_size, settings.max_file_size_bytes)
    if not is_valid_size:
        errors.append(
            ValidationErrorDetail(
                field="file",
                message=size_error,
                type="file_too_large",
            )
        )

    if errors:
        # REQ-STT-004: 검증 실패 시 파일 저장 안 함
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[e.model_dump() for e in errors],
        )

    # --- 동시 처리 제한 확인 (REQ: 최대 3개) ---
    active_count_str = await redis_client.get("active_job_count")
    active_count = int(active_count_str) if active_count_str else 0
    if active_count >= settings.max_concurrent_jobs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"동시 처리 한도({settings.max_concurrent_jobs}개)를 초과했습니다. 잠시 후 재시도하세요.",
        )

    # --- 임시 파일 저장 ---
    task_id = uuid.uuid4()
    task_id_str = str(task_id)

    suffix = Path(filename).suffix.lower()
    temp_path = settings.temp_dir / f"{task_id_str}{suffix}"
    temp_path.write_bytes(raw_content)

    # --- 재생 시간 검증 (REQ-STT-003: 4시간 초과 거부) ---
    try:
        duration_seconds = get_audio_duration_seconds(temp_path)
        if duration_seconds > settings.max_duration_seconds:
            temp_path.unlink(missing_ok=True)  # REQ-STT-004
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "field": "file",
                        "message": (
                            f"재생 시간이 제한({settings.max_duration_hours}시간)을 초과합니다. "
                            f"실제 재생 시간: {duration_seconds / 3600:.1f}시간"
                        ),
                        "type": "duration_exceeded",
                    }
                ],
            )
    except HTTPException:
        raise
    except Exception as e:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[
                {
                    "field": "file",
                    "message": f"오디오 파일을 읽을 수 없습니다: {e}",
                    "type": "invalid_audio",
                }
            ],
        )

    # --- 초기 상태 Redis 저장 ---
    now = datetime.now(UTC)
    initial_status = {
        "task_id": task_id_str,
        "status": TaskStatus.pending.value,
        "progress": 0.0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    status_key = f"task:status:{task_id_str}"
    await redis_client.setex(status_key, settings.cache_ttl_seconds, json.dumps(initial_status))

    # --- Celery 작업 등록 ---
    from backend.workers.tasks.transcription_task import transcription_task

    transcription_task.delay(
        task_id=task_id_str,
        audio_file_path=str(temp_path),
        language=language,
        model_name=model,
        original_filename=filename,
        file_size_bytes=file_size,
    )

    logger.info(
        "전사 작업 등록",
        task_id=task_id_str,
        filename=filename,
        file_size_bytes=file_size,
        duration_seconds=round(duration_seconds, 2),
    )

    status_url = f"/api/v1/transcriptions/{task_id_str}/status"
    result_url = f"/api/v1/transcriptions/{task_id_str}"

    return TranscriptionCreate(
        task_id=task_id,
        status=TaskStatus.pending,
        status_url=status_url,
        result_url=result_url,
        created_at=now,
    )


@router.get(
    "/{task_id}/status",
    response_model=TaskStatusResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_task_status(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> TaskStatusResponse:
    """
    작업 상태 폴링
    GET /api/v1/transcriptions/{task_id}/status
    """
    status_key = f"task:status:{task_id}"
    raw = await redis_client.get(status_key)

    if raw is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    data = json.loads(raw)

    now = datetime.now(UTC)
    created_at_str = data.get("created_at")
    updated_at_str = data.get("updated_at")

    return TaskStatusResponse(
        task_id=task_id,  # type: ignore[arg-type]
        status=TaskStatus(data["status"]),
        progress=data.get("progress", 0.0),
        message=data.get("message"),
        error_message=data.get("error_message"),
        created_at=datetime.fromisoformat(created_at_str) if created_at_str else now,
        updated_at=datetime.fromisoformat(updated_at_str) if updated_at_str else now,
    )


@router.get(
    "/{task_id}",
    response_model=TranscriptionResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_transcription_result(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> TranscriptionResponse:
    """
    전사 결과 조회 (REQ-STT-011, REQ-STT-012)
    GET /api/v1/transcriptions/{task_id}
    """
    # Redis 캐시 우선 조회 (REQ-STT-012)
    result_key = f"task:result:{task_id}"
    raw = await redis_client.get(result_key)

    if raw is None:
        # 캐시 미스 → 파일 시스템에서 복원
        result_file = settings.results_dir / f"{task_id}.json"
        if not result_file.exists():
            # 상태만 확인해서 적절한 응답
            status_key = f"task:status:{task_id}"
            status_raw = await redis_client.get(status_key)
            if status_raw is None:
                raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

            status_data = json.loads(status_raw)
            task_status = TaskStatus(status_data["status"])
            created_at = datetime.fromisoformat(status_data["created_at"])

            return TranscriptionResponse(
                task_id=task_id,  # type: ignore[arg-type]
                status=task_status,
                segments=[],
                created_at=created_at,
                error_message=status_data.get("error_message"),
            )

        data = json.loads(result_file.read_text(encoding="utf-8"))
        # 파일에서 복원 후 Redis 재캐싱
        await redis_client.setex(result_key, settings.cache_ttl_seconds, json.dumps(data))
    else:
        data = json.loads(raw)

    from backend.schemas.transcription import SegmentResult, TranscriptionMetadata

    segments = [SegmentResult(**seg) for seg in data.get("segments", [])]

    metadata_raw = data.get("metadata")
    metadata = TranscriptionMetadata(**metadata_raw) if metadata_raw else None

    return TranscriptionResponse(
        task_id=data["task_id"],  # type: ignore[arg-type]
        status=TaskStatus(data["status"]),
        language=data.get("language"),
        duration=data.get("duration"),
        model=data.get("model"),
        segments=segments,
        metadata=metadata,
        created_at=datetime.fromisoformat(data["created_at"]),
        completed_at=(
            datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
        ),
        error_message=data.get("error_message"),
    )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_transcription(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> None:
    """
    작업 및 관련 파일 삭제 (REQ-STT-014)
    DELETE /api/v1/transcriptions/{task_id}
    """
    # Redis 캐시 삭제
    await redis_client.delete(f"task:status:{task_id}", f"task:result:{task_id}")

    # 결과 파일 삭제
    result_file = settings.results_dir / f"{task_id}.json"
    result_file.unlink(missing_ok=True)

    # 임시 오디오 파일 삭제 (확장자 순회)
    for ext in [".wav", ".mp3", ".m4a", ".ogg"]:
        temp_file = settings.temp_dir / f"{task_id}{ext}"
        temp_file.unlink(missing_ok=True)

    logger.info("전사 작업 삭제", task_id=task_id)
