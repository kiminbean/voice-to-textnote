"""
배치 전사 API 엔드포인트
POST /api/v1/transcriptions/batch  — 다중 오디오 파일 일괄 업로드 및 처리 요청
GET  /api/v1/transcriptions/batch/{batch_id} — 배치 처리 상태 일괄 조회
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from backend.app.config import settings
from backend.app.dependencies import get_redis_client
from backend.app.errors import not_found, unprocessable
from backend.pipeline.audio_processor import get_audio_duration_seconds
from backend.schemas.batch import (
    BatchItemResult,
    BatchStatusResponse,
    BatchTranscriptionCreate,
)
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger
from backend.utils.validators import validate_audio_format, validate_file_size

logger = get_logger(__name__)

# 배치 라우터는 transcription 라우터보다 먼저 등록되어야
# /transcriptions/{task_id} 경로 충돌을 방지한다.
router = APIRouter(prefix="/transcriptions/batch", tags=["batch"])

_BATCH_MAX_FILES = 10


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=BatchTranscriptionCreate,
    responses={
        422: {"description": "파일 검증 실패"},
        429: {"description": "동시 처리 한도 초과"},
    },
)
async def upload_batch_transcription(
    files: list[UploadFile] = File(..., description="오디오 파일 목록 (최대 10개)"),
    language: str = Form(default="ko", description="전사 언어 코드"),
    model: str = Form(default="mlx-community/whisper-small-mlx"),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> BatchTranscriptionCreate:
    """
    다중 오디오 파일 일괄 업로드 및 전사 작업 생성.
    개별 파일 검증 실패 시 해당 항목만 failed 처리하고 나머지는 계속 진행한다.

    Note: files 빈 리스트 검증은 FastAPI File(...) 필수 검증이 먼저 동작하므로
    이 함수에 도달할 때 files는 항상 최소 1개 이상임.
    """
    if len(files) > _BATCH_MAX_FILES:
        unprocessable(f"최대 {_BATCH_MAX_FILES}개 파일까지 한 번에 업로드할 수 있습니다.")

    batch_id = uuid.uuid4()
    now = datetime.now(UTC)
    items: list[BatchItemResult] = []
    task_ids: list[str] = []

    for upload_file in files:
        filename = upload_file.filename or "unknown"
        task_id = uuid.uuid4()
        task_id_str = str(task_id)

        # 파일 형식 검증
        is_valid_format, format_error = validate_audio_format(filename, upload_file.content_type)
        if not is_valid_format:
            items.append(
                BatchItemResult(filename=filename, status=TaskStatus.failed, error=format_error)
            )
            continue

        # 파일 읽기 및 크기 검증
        raw_content = await upload_file.read()
        file_size = len(raw_content)
        is_valid_size, size_error = validate_file_size(file_size, settings.max_file_size_bytes)
        if not is_valid_size:
            items.append(
                BatchItemResult(filename=filename, status=TaskStatus.failed, error=size_error)
            )
            continue

        # 임시 파일 저장
        suffix = Path(filename).suffix.lower()
        temp_path = settings.temp_dir / f"{task_id_str}{suffix}"
        temp_path.write_bytes(raw_content)

        # 재생 시간 검증
        try:
            duration_seconds = get_audio_duration_seconds(temp_path)
            if duration_seconds > settings.max_duration_seconds:
                temp_path.unlink(missing_ok=True)
                items.append(
                    BatchItemResult(
                        filename=filename,
                        status=TaskStatus.failed,
                        error=(
                            f"재생 시간이 제한({settings.max_duration_hours}시간)을 초과합니다. "
                            f"실제: {duration_seconds / 3600:.1f}시간"
                        ),
                    )
                )
                continue
        except VoiceNoteError:
            raise
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            items.append(
                BatchItemResult(
                    filename=filename,
                    status=TaskStatus.failed,
                    error=f"오디오 파일을 읽을 수 없습니다: {e}",
                )
            )
            continue

        # Redis 초기 상태 저장
        initial_status = {
            "task_id": task_id_str,
            "status": TaskStatus.pending.value,
            "progress": 0.0,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "file_size": file_size,
            "language": language,
            "model": model,
            "batch_id": str(batch_id),
            "original_filename": filename,
        }
        status_key = f"task:status:{task_id_str}"
        await redis_client.setex(
            status_key, settings.cache_ttl_seconds, json.dumps(initial_status)
        )

        # Celery 작업 등록
        from backend.workers.tasks.transcription_task import transcription_task

        transcription_task.delay(
            task_id=task_id_str,
            audio_file_path=str(temp_path),
            language=language,
            model_name=model,
            original_filename=filename,
            file_size_bytes=file_size,
        )

        task_ids.append(task_id_str)
        items.append(
            BatchItemResult(
                task_id=task_id,
                filename=filename,
                status=TaskStatus.pending,
                status_url=f"/api/v1/transcriptions/{task_id_str}/status",
                result_url=f"/api/v1/transcriptions/{task_id_str}",
            )
        )
        logger.info(
            "배치 전사 작업 등록",
            batch_id=str(batch_id),
            task_id=task_id_str,
            filename=filename,
        )

    # 배치 메타데이터를 Redis에 저장
    batch_data = {
        "batch_id": str(batch_id),
        "task_ids": task_ids,
        "created_at": now.isoformat(),
    }
    await redis_client.setex(
        f"batch:{batch_id}", settings.cache_ttl_seconds, json.dumps(batch_data)
    )

    accepted = sum(1 for item in items if item.status != TaskStatus.failed)
    return BatchTranscriptionCreate(
        batch_id=batch_id,
        total=len(files),
        accepted=accepted,
        items=items,
        created_at=now,
    )


@router.get(
    "/{batch_id}",
    response_model=BatchStatusResponse,
    responses={404: {"description": "배치 없음"}},
)
async def get_batch_status(
    batch_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> BatchStatusResponse:
    """
    배치 처리 상태 일괄 조회.
    Pipeline으로 모든 태스크 상태를 단일 왕복에 가져온다.
    """
    # batch_id UUID 형식 검증
    try:
        batch_uuid = uuid.UUID(batch_id)
    except ValueError:
        unprocessable("올바른 batch_id 형식이 아닙니다.")

    batch_raw = await redis_client.get(f"batch:{batch_id}")
    if batch_raw is None:
        not_found("배치를 찾을 수 없습니다.")

    batch_data = json.loads(batch_raw)
    task_ids: list[str] = batch_data.get("task_ids", [])

    items: list[BatchItemResult] = []
    counts: dict[str, int] = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}

    if task_ids:
        pipe = redis_client.pipeline()
        for tid in task_ids:
            pipe.get(f"task:status:{tid}")
        raw_results = await pipe.execute()

        for tid, raw in zip(task_ids, raw_results):
            if raw is None:
                counts["failed"] += 1
                items.append(
                    BatchItemResult(
                        filename=tid,
                        status=TaskStatus.failed,
                        error="상태 정보를 찾을 수 없습니다.",
                    )
                )
                continue

            task_data = json.loads(raw)
            task_status_str = task_data.get("status", "failed")
            try:
                task_status = TaskStatus(task_status_str)
            except ValueError:
                task_status = TaskStatus.failed

            counts[task_status.value] = counts.get(task_status.value, 0) + 1
            items.append(
                BatchItemResult(
                    task_id=uuid.UUID(tid),
                    filename=task_data.get("original_filename", tid),
                    status=task_status,
                    status_url=f"/api/v1/transcriptions/{tid}/status",
                    result_url=f"/api/v1/transcriptions/{tid}",
                )
            )

    return BatchStatusResponse(
        batch_id=batch_uuid,
        total=len(task_ids),
        pending=counts["pending"],
        processing=counts["processing"],
        completed=counts["completed"],
        failed=counts["failed"],
        items=items,
    )
