"""
SPEC-AUDIO-PREP-001: 오디오 전처리 API.

POST /api/v1/audio/preprocess
- multipart/form-data로 오디오 + 전처리 옵션 업로드
- 처리된 WAV 파일을 즉시 다운로드 응답
- 메타데이터는 응답 헤더 X-Audio-Preprocess-Meta(JSON)로 함께 전달

전처리 옵션은 PreprocessOptions의 1:1 매핑이며, 옵션 검증 실패 시 422를
반환합니다. 모든 처리는 단일 비동기 워커 풀에서 동시 실행 수를 제한합니다.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import wave
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.app.config import settings
from backend.pipeline.audio_processor import (
    PreprocessOptions,
    cleanup_temp_file,
    preprocess_audio,
)
from backend.schemas.audio_preprocess import (
    PreprocessOptionsPayload,
    PreprocessResultMetadata,
)
from backend.utils.logger import get_logger
from backend.utils.validators import validate_audio_format

logger = get_logger(__name__)

router = APIRouter(prefix="/audio", tags=["audio-preprocess"])

# 서버 측 전처리 동시 실행 제한 (라우터 모듈 로드시 1회 생성)
# @MX:NOTE: 단일 프로세스 기준 세마포어. multi-worker uvicorn에서는 워커별로 독립.
_preprocess_semaphore = asyncio.Semaphore(settings.audio_preprocess_max_concurrent)


def _resolve_options(payload: PreprocessOptionsPayload) -> PreprocessOptions:
    """Pydantic 페이로드를 도메인 옵션으로 변환하고 유효성 검증."""
    # default high-pass: 사용자가 명시하지 않았고 서버 기본값이 활성이면 적용
    high_pass = payload.high_pass_hz
    if high_pass is None and settings.audio_preprocess_default_high_pass_hz > 0:
        high_pass = settings.audio_preprocess_default_high_pass_hz

    opts = PreprocessOptions(
        convert_to_16k_mono=payload.convert_to_16k_mono,
        normalize=payload.normalize,
        target_dbfs=payload.target_dbfs,
        high_pass_hz=high_pass,
        low_pass_hz=payload.low_pass_hz,
        trim_silence=payload.trim_silence,
        silence_threshold_db=payload.silence_threshold_db,
        silence_min_len_ms=payload.silence_min_len_ms,
    )
    try:
        opts.validate()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return opts


def _safe_unlink(path: Path) -> None:
    """예외를 삼키고 안전하게 임시 파일을 정리."""
    try:
        cleanup_temp_file(path)
    except OSError as exc:  # 디스크 오류 등은 로그만 남기고 무시
        logger.warning("임시 파일 정리 실패", path=str(path), error=str(exc))


@router.post(
    "/preprocess",
    responses={
        200: {"description": "전처리된 WAV 파일 (audio/wav)"},
        400: {"description": "잘못된 파일 또는 손상된 오디오"},
        413: {"description": "파일 크기 초과"},
        422: {"description": "전처리 옵션 검증 실패"},
        503: {"description": "전처리 비활성화 상태"},
    },
)
async def preprocess_endpoint(
    file: UploadFile = File(..., description="원본 오디오 파일"),
    convert_to_16k_mono: bool = Form(default=True),
    normalize: bool = Form(default=True),
    target_dbfs: float = Form(default=-20.0),
    high_pass_hz: int | None = Form(default=None),
    low_pass_hz: int | None = Form(default=None),
    trim_silence: bool = Form(default=False),
    silence_threshold_db: float = Form(default=-40.0),
    silence_min_len_ms: int = Form(default=700),
) -> FileResponse:
    """오디오 파일에 사용자 선택형 전처리를 적용하여 WAV로 반환."""
    if not settings.audio_preprocess_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="오디오 전처리 기능이 비활성화되어 있습니다.",
        )

    # 파일명/포맷 검증 (기존 검증기 재사용)
    filename = file.filename or "audio"
    is_valid, msg = validate_audio_format(filename)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    # 옵션 파싱 + 검증
    payload = PreprocessOptionsPayload(
        convert_to_16k_mono=convert_to_16k_mono,
        normalize=normalize,
        target_dbfs=target_dbfs,
        high_pass_hz=high_pass_hz,
        low_pass_hz=low_pass_hz,
        trim_silence=trim_silence,
        silence_threshold_db=silence_threshold_db,
        silence_min_len_ms=silence_min_len_ms,
    )
    options = _resolve_options(payload)

    # 입력 파일 임시 저장 (스트림 한도 검증)
    max_bytes = settings.audio_preprocess_max_file_mb * 1024 * 1024
    suffix = Path(filename).suffix or ".bin"
    src_fd, src_name = tempfile.mkstemp(suffix=suffix, prefix="preprocess_in_")
    src_path = Path(src_name)
    bytes_read = 0
    try:
        with open(src_fd, "wb") as fp:
            while chunk := await file.read(1024 * 1024):
                bytes_read += len(chunk)
                if bytes_read > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"파일 크기가 {settings.audio_preprocess_max_file_mb}MB를 초과합니다."
                        ),
                    )
                fp.write(chunk)
    except HTTPException:
        _safe_unlink(src_path)
        raise
    except Exception as exc:  # noqa: BLE001 - 업로드 실패는 다양함
        _safe_unlink(src_path)
        logger.error("업로드 저장 실패", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"업로드 처리 실패: {exc}",
        ) from exc

    # 실제 전처리 (CPU 바운드 → threadpool + 세마포어)
    async with _preprocess_semaphore:
        try:
            out_path = await asyncio.to_thread(preprocess_audio, src_path, options)
        except ValueError as exc:
            _safe_unlink(src_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except Exception as exc:  # noqa: BLE001 - pydub/ffmpeg failure modes vary
            _safe_unlink(src_path)
            logger.error("오디오 전처리 실패", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="오디오 전처리 중 오류가 발생했습니다",
            ) from exc

    # 메타데이터 헤더 구성
    try:
        with wave.open(str(out_path), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            duration = wf.getnframes() / float(sr or 1)
    except (wave.Error, EOFError) as exc:
        _safe_unlink(src_path)
        _safe_unlink(out_path)
        logger.error("전처리 결과 메타데이터 읽기 실패", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="전처리 결과 검증 실패",
        ) from exc
    except OSError as exc:
        _safe_unlink(src_path)
        _safe_unlink(out_path)
        logger.error("전처리 결과 파일 접근 실패", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="전처리 결과 파일 접근 실패",
        ) from exc

    meta = PreprocessResultMetadata(
        original_filename=filename,
        original_size_bytes=bytes_read,
        processed_size_bytes=out_path.stat().st_size,
        duration_seconds=round(duration, 3),
        sample_rate=sr,
        channels=ch,
        applied=payload,
    )

    # 응답 전송 직후 두 임시 파일 모두 삭제
    def _cleanup() -> None:
        _safe_unlink(src_path)
        _safe_unlink(out_path)

    output_name = f"{Path(filename).stem}_processed.wav"
    return FileResponse(
        path=str(out_path),
        media_type="audio/wav",
        filename=output_name,
        background=BackgroundTask(_cleanup),
        headers={"X-Audio-Preprocess-Meta": json.dumps(meta.model_dump())},
    )
