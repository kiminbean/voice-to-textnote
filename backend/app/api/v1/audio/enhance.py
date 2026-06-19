"""
Advanced Audio Enhancement API 엔드포인트
AI 기반 오디오 향상 및 노이즈 제거
"""

import json
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from backend.app.dependencies import get_redis_client
from backend.app.errors import bad_request, not_found, request_entity_too_large, unprocessable
from backend.schemas.audio_enhancement import (
    AudioEnhancementRequest,
    AudioEnhancementResponse,
    AudioEnhancementStatus,
    EnhancementMode,
    EnhancementResult,
    NoiseReductionLevel,
    VoiceEnhancementMode,
)
from backend.services.audio_enhancement_service import AudioEnhancementService

router = APIRouter(prefix="/enhance", tags=["audio-enhancement"])

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
TASK_TTL_SECONDS = 86400
SUPPORTED_FORMATS = {".wav", ".mp3", ".flac", ".m4a"}


def get_audio_enhancement_service() -> AudioEnhancementService:
    """AudioEnhancementService 인스턴스 제공"""
    return AudioEnhancementService()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def _save_task_status(
    redis_client: aioredis.Redis,
    task_id: str,
    status_data: dict,
) -> None:
    await redis_client.setex(
        f"task:audio:enhance:{task_id}",
        TASK_TTL_SECONDS,
        json.dumps(status_data, ensure_ascii=False, default=_json_default),
    )


async def _load_task_status(redis_client: aioredis.Redis, task_id: str) -> dict:
    raw_status = await redis_client.get(f"task:audio:enhance:{task_id}")
    if raw_status is None:
        not_found(f"작업을 찾을 수 없습니다: {task_id}", error_code="AUDIO_ENHANCE_NOT_FOUND")

    if isinstance(raw_status, bytes):
        raw_status = raw_status.decode("utf-8")

    try:
        status_data = json.loads(raw_status)
    except (TypeError, json.JSONDecodeError):
        bad_request("작업 상태 데이터 파싱 실패", error_code="AUDIO_ENHANCE_STATUS_INVALID")

    if not isinstance(status_data, dict):
        bad_request("작업 상태 데이터 형식이 올바르지 않습니다", error_code="AUDIO_ENHANCE_STATUS_INVALID")

    return status_data


async def _write_upload_to_temp_file(file: UploadFile, suffix: str) -> tuple[Path, int]:
    size = 0
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_file_path = Path(temp_file.name)
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                temp_file.close()
                temp_file_path.unlink(missing_ok=True)
                request_entity_too_large(
                    f"파일 크기 초과: {size} bytes. 최대 100MB까지 허용됩니다.",
                    error_code="AUDIO_ENHANCE_FILE_TOO_LARGE",
                )
            temp_file.write(chunk)

    if size == 0:
        temp_file_path.unlink(missing_ok=True)
        unprocessable("빈 오디오 파일은 처리할 수 없습니다.", error_code="AUDIO_ENHANCE_EMPTY_FILE")

    return temp_file_path, size


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AudioEnhancementResponse,
    responses={
        400: {"description": "잘못된 요청 파라미터"},
        422: {"description": "파일 검증 실패"},
    },
)
async def enhance_audio(
    file: UploadFile = File(..., description="오디오 파일 (WAV, MP3, FLAC, M4A)"),
    enhancement_mode: EnhancementMode = Form(EnhancementMode.ENHANCED),
    noise_reduction_level: NoiseReductionLevel = Form(NoiseReductionLevel.MODERATE),
    voice_enhancement: VoiceEnhancementMode = Form(VoiceEnhancementMode.NATURAL),
    extract_speech_only: bool = Form(False),
    target_sample_rate: int | None = Form(16000),
    normalize_audio: bool = Form(True),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: AudioEnhancementService = Depends(get_audio_enhancement_service),
) -> AudioEnhancementResponse:
    """
    AI 기반 오디오 향산 처리

    지원 형식: WAV, MP3, FLAC, M4A
    최대 크기: 100MB

    - 노이즈 제거 및 음향 향상
    - 음성 활동 검출 및 세분화
    - 품질 평가 및 점수 계산
    - 다양한 향상 옵션 지원
    """
    enhancement_request = AudioEnhancementRequest(
        enhancement_mode=enhancement_mode,
        noise_reduction_level=noise_reduction_level,
        voice_enhancement=voice_enhancement,
        extract_speech_only=extract_speech_only,
        target_sample_rate=target_sample_rate,
        normalize_audio=normalize_audio,
    )

    # 1. 파일 검증
    if not file.filename:
        unprocessable("파일이 제공되지 않았습니다.")

    filename = file.filename
    file_ext = Path(filename).suffix.lower()

    # 지원 형식 검증
    if file_ext not in SUPPORTED_FORMATS:
        unprocessable(f"지원하지 않는 파일 형식: {file_ext}. WAV, MP3, FLAC, M4A만 허용됩니다.")

    # 2. 임시 파일 저장
    temp_file_path, file_size = await _write_upload_to_temp_file(file, file_ext)
    task_id = str(uuid.uuid4())
    created_at = _utc_now()
    task_status = {
        "task_id": task_id,
        "status": "processing",
        "enhancement_request": enhancement_request.model_dump(mode="json"),
        "filename": filename,
        "file_size": file_size,
        "created_at": created_at,
        "progress": 0.0,
        "current_step": "audio_processing",
    }

    try:
        await _save_task_status(redis_client, task_id, task_status)

        # 5. 비동기 오디오 향상 처리 시작
        enhanced_result = await svc.enhance_audio(temp_file_path, enhancement_request)
        completed_at = _utc_now()

        # 6. 결과 저장
        task_status.update({
            "status": "completed",
            "result": enhanced_result.model_dump(mode="json"),
            "completed_at": completed_at,
            "progress": 100.0,
            "current_step": "completed",
        })

        await _save_task_status(redis_client, task_id, task_status)

        # 7. 응답 생성
        return AudioEnhancementResponse(
            task_id=task_id,
            status="completed",
            request=enhancement_request,
            result=enhanced_result,
            created_at=created_at,
            completed_at=completed_at,
        )

    except Exception as e:
        # 오류 발생 시 상태 업데이트
        task_status.update({
            "status": "failed",
            "error_message": str(e),
            "progress": 100.0,
            "current_step": "failed",
        })
        await _save_task_status(redis_client, task_id, task_status)

        # 재발생
        raise

    finally:
        # 임시 파일 삭제
        temp_file_path.unlink(missing_ok=True)


@router.get("/status/{task_id}", response_model=AudioEnhancementStatus)
async def get_enhancement_status(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> AudioEnhancementStatus:
    """
    오디오 향상 작업 상태 조회

    - 진행률 확인
    - 현재 처리 단계 조회
    - 오류 메시지 확인
    """

    status_data = await _load_task_status(redis_client, task_id)

    return AudioEnhancementStatus(
        task_id=status_data["task_id"],
        status=status_data["status"],
        progress_percent=status_data.get("progress", 0.0),
        current_step=status_data.get("current_step", ""),
        estimated_remaining_seconds=status_data.get("estimated_remaining_seconds"),
        error_message=status_data.get("error_message")
    )


@router.get("/results/{task_id}", response_model=AudioEnhancementResponse)
async def get_enhancement_result(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> AudioEnhancementResponse:
    """
    오디오 향상 결과 조회

    - 최종 처리 결과
    - 품질 점수 정보
    - 세그먼트 정보
    - 향상된 파일 다운로드 링크
    """

    status_data = await _load_task_status(redis_client, task_id)

    if status_data["status"] != "completed":
        bad_request(
            f"작업이 완료되지 않았습니다: {status_data['status']}",
            error_code="AUDIO_ENHANCE_NOT_COMPLETED",
        )

    # EnhancementResult 객체 재구성
    result_data = status_data["result"]
    enhancement_request = AudioEnhancementRequest.model_validate(status_data["enhancement_request"])

    return AudioEnhancementResponse(
        task_id=status_data["task_id"],
        status=status_data["status"],
        request=enhancement_request,
        result=EnhancementResult.model_validate(result_data),
        created_at=datetime.fromisoformat(status_data["created_at"]),
        completed_at=datetime.fromisoformat(status_data["completed_at"]),
    )
