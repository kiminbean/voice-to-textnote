"""
전사 API 엔드포인트
REQ-STT-001~004: 오디오 업로드 및 검증
REQ-STT-010~014: 상태 조회 및 결과 반환
"""

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.dependencies import get_db_session, get_redis_client
from backend.db.vocabulary_service import VocabularyService
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
    vocabulary_id: str | None = Form(default=None, description="커스텀 어휘 리스트 UUID (REQ-VOCAB-001)"),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
) -> TranscriptionCreate:
    """
    오디오 파일 업로드 및 전사 작업 생성
    POST /api/v1/transcriptions
    """
    # REQ-VOCAB-001: 어휘 ID가 제공되면 initial_prompt 문자열로 변환
    initial_prompt: str | None = None
    if vocabulary_id:
        try:
            vocab_uuid = UUID(vocabulary_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[{"field": "vocabulary_id", "message": "유효하지 않은 UUID 형식입니다", "type": "invalid_uuid"}],
            )
        vocab_service = VocabularyService()
        initial_prompt = await vocab_service.get_initial_prompt(db, vocab_uuid)

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
    # Stream to disk first to avoid loading entire file into memory (up to 500MB).
    # Then validate size from file stats.
    task_id = uuid.uuid4()
    task_id_str = str(task_id)
    suffix = Path(filename).suffix.lower()
    temp_path = settings.temp_dir / f"{task_id_str}{suffix}"

    try:
        with temp_path.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB 청크
                if not chunk:
                    break
                f.write(chunk)
    except OSError as e:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"field": "file", "message": f"파일 저장 실패: {e}", "type": "write_error"}],
        )

    file_size = temp_path.stat().st_size
    is_valid_size, size_error = validate_file_size(file_size, settings.max_file_size_bytes)
    if not is_valid_size:
        temp_path.unlink(missing_ok=True)
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

    # --- 동시 처리 제한 확인 (REQ: 최대 N개) ---
    # Soft check: 워커의 ZSET 기반 카운트와 다를 수 있지만 과도한 큐잉은 방지합니다.
    try:
        now_ts = time.time()
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore("active_jobs_ts", "-inf", now_ts - 7200)
        pipe.zcard("active_jobs_ts")
        active_count = (await pipe.execute())[1]
    except Exception:
        active_count = 0
    if active_count >= settings.max_concurrent_jobs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"동시 처리 한도({settings.max_concurrent_jobs}개)를 초과했습니다. 잠시 후 재시도하세요.",
        )

    # temp_path, task_id_str already set above during streaming upload

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
        "file_size": file_size,
        "language": language,
        "model": model,
    }
    status_key = f"task:status:{task_id_str}"
    await redis_client.setex(status_key, settings.cache_ttl_seconds, json.dumps(initial_status))

    # --- Celery 작업 등록 (STT + DIA 병렬 시작) ---
    # REQ-STT-PERF-002: STT와 화자 분리는 둘 다 WAV만 필요하므로 동시에 시작한다.
    # DIA는 audio_path를 직접 받아 STT 완료를 기다리지 않는다 (matched=False 결과).
    # minutes_task가 STT와 DIA 결과를 모두 받아 SpeakerMatcher로 매칭한다.
    from backend.workers.tasks.diarization_task import diarization_celery_task
    from backend.workers.tasks.transcription_task import transcription_task

    transcription_task.delay(
        task_id=task_id_str,
        audio_file_path=str(temp_path),
        language=language,
        model_name=model,
        original_filename=filename,
        file_size_bytes=file_size,
        initial_prompt=initial_prompt,
    )

    # 화자 분리 태스크 사전 등록 - 클라이언트가 별도 POST를 하지 않아도 자동 시작
    dia_task_id = str(uuid.uuid4())
    dia_initial_status = {
        "task_id": dia_task_id,
        "stt_task_id": task_id_str,
        "status": TaskStatus.pending.value,
        "progress": 0.0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    dia_status_key = f"task:dia:status:{dia_task_id}"
    await redis_client.setex(
        dia_status_key,
        settings.diarization_result_ttl,
        json.dumps(dia_initial_status),
    )

    # DIA는 STT가 만드는 DIA 전용 WAV 사본(settings.temp_dir/{task_id_str}_dia.wav)을 입력으로 받는다.
    # transcription_task가 convert_and_normalize 직후 그 경로에 WAV를 복사한다.
    # 원본({task_id}.wav)과 경로를 분리해, 순차 실행(concurrency=1) 시 STT가 원본을
    # 삭제해도 DIA 입력이 사라지지 않게 한다. 사본은 DIA가 완료 후 직접 정리한다.
    # WAV가 아직 없을 수 있으므로 짧은 지연(countdown) 후 시작한다.
    #
    # REQ-DIA-PERF-001: 회의록 앱 기본 max_speakers=4로 clustering 후보를 좁혀
    # 화자 분리 추론 시간을 10~20% 단축한다. 더 많은 화자가 예상되면
    # /diarizations 엔드포인트로 별도 호출 가능하다.
    dia_audio_path = str(settings.temp_dir / f"{task_id_str}_dia.wav")
    diarization_celery_task.apply_async(
        kwargs={
            "task_id": dia_task_id,
            "stt_task_id": task_id_str,  # 매칭에는 사용 안 하지만 추적용
            "audio_path": dia_audio_path,
            "max_speakers": 4,
        },
        countdown=2,  # WAV 변환 완료 여유 (보통 1초 이내)
    )

    logger.info(
        "전사+화자분리 작업 동시 등록",
        stt_task_id=task_id_str,
        dia_task_id=dia_task_id,
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
        diarization_task_id=dia_task_id,
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
    # Redis 캐시 우선 조회 (REQ-STT-012) - Pipeline 사용으로 네트워크 라운드트립 감소
    pipe = redis_client.pipeline()
    pipe.get(f"task:result:{task_id}")
    pipe.get(f"task:status:{task_id}")
    result_raw, status_raw = await pipe.execute()

    if result_raw is None:
        # 캐시 미스 → 파일 시스템에서 복원
        result_file = settings.results_dir / f"{task_id}.json"
        if not result_file.exists():
            # 상태만 확인해서 적절한 응답
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

        # 파일에서 읽을 때 메모리 최적화: 스트리밍으로 읽기
        data = json.loads(result_file.read_text(encoding="utf-8"))
        # 파일에서 복원 후 Redis 재캐싱
        await redis_client.setex(f"task:result:{task_id}", settings.cache_ttl_seconds, json.dumps(data))
    else:
        data = json.loads(result_raw)

    from backend.schemas.transcription import SegmentResult, TranscriptionMetadata

    # 리스트 컴프리헨션으로 메모리 효율화
    segments = [SegmentResult(**seg) for seg in data.get("segments", [])]

    metadata_raw = data.get("metadata")
    metadata = TranscriptionMetadata(**metadata_raw) if metadata_raw else None

    completed_at = (
        datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
    )

    return TranscriptionResponse(
        task_id=data["task_id"],  # type: ignore[arg-type]
        status=TaskStatus(data["status"]),
        language=data.get("language"),
        duration=data.get("duration"),
        model=data.get("model"),
        segments=segments,
        metadata=metadata,
        created_at=datetime.fromisoformat(data["created_at"]),
        completed_at=completed_at,
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
