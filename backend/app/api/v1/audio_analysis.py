"""
SPEC-AUDIO-ANALYSIS-001: 오디오 품질 분석 API

엔드포인트:
- POST /api/v1/audio-analysis   오디오 파일 품질 분석
"""

import os
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.app.config import settings
from backend.ml.audio_analysis_engine import analyze_audio
from backend.schemas.audio_analysis import (
    AudioAnalysisResponse,
    SilenceSegment,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/audio-analysis", tags=["audio-analysis"])

# 지원 오디오 포맷
_ALLOWED_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".flac", ".ogg",
    ".opus", ".wma", ".aac", ".webm",
}


@router.post(
    "",
    response_model=AudioAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_audio_file(
    file: UploadFile = File(..., description="분석할 오디오 파일"),
    include_silence_detection: bool = Form(default=True),
    silence_threshold_db: float = Form(default=-40.0),
    min_silence_duration_ms: int = Form(default=500),
) -> AudioAnalysisResponse:
    """
    오디오 파일 품질 분석

    파일의 포맷, 볼륨, 무음 구간, STT 적합성 등을 분석합니다.
    실제 STT 처리 전에 오디오 품질을 사전 점검할 때 유용합니다.
    """
    # 파일 확장자 검증
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"지원하지 않는 파일 포맷: {ext}. 지원 포맷: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    # 파일 크기 검증
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 크기 초과: {len(contents)} bytes (최대 {settings.max_file_size_mb}MB)",
        )

    # 임시 파일로 저장 후 분석
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        result = analyze_audio(
            file_path=tmp_path,
            include_silence_detection=include_silence_detection,
            silence_threshold_db=silence_threshold_db,
            min_silence_duration_ms=min_silence_duration_ms,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("오디오 분석 실패", error=str(e), filename=filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"오디오 분석 중 오류 발생: {e}",
        ) from e
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    logger.info(
        "오디오 분석 완료",
        filename=filename,
        duration=result.duration_seconds,
        quality_score=result.quality_score,
    )

    return AudioAnalysisResponse(
        filename=result.filename,
        format=result.format,
        duration_seconds=result.duration_seconds,
        sample_rate=result.sample_rate,
        channels=result.channels,
        sample_width=result.sample_width,
        bitrate=result.bitrate,
        file_size_bytes=result.file_size_bytes,
        max_dbfs=result.max_dbfs,
        avg_dbfs=result.avg_dbfs,
        rms_dbfs=result.rms_dbfs,
        silence_segments=[
            SilenceSegment(
                start_ms=round(s.start_ms, 1),
                end_ms=round(s.end_ms, 1),
                duration_ms=round(s.duration_ms, 1),
                avg_dbfs=s.avg_dbfs,
            )
            for s in result.silence_segments
        ],
        silence_ratio=result.silence_ratio,
        speech_ratio=result.speech_ratio,
        quality_score=result.quality_score,
        quality_issues=result.quality_issues,
        recommendation=result.recommendation,
    )
