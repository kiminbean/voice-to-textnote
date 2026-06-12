"""
SPEC-AUDIO-ENHANCED-001: AI 기반 오디오 증강 API.

POST /api/v1/audio/enhanced
- multipart/form-data로 오디오 + 증강 옵션 업로드
- AI 기반 노이즈 제거, 음성 향상, 음질 평가
- 처리된 WAV 파일과 음질 평가 보고서 반환
- 실시간 진행률 SSE 스트리밍 지원

AI 증강 기능:
- Voice Activity Detection (VAD)
- AI 노이즈 제거 (스펙트럼 감지)
- 음성 강화 (레벨 균형)
- 음질 자동 평가
- 개선 제안 생성
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse
from starlette.background import BackgroundTask

from backend.app.config import settings
from backend.app.errors import (
    bad_request,
    internal_server_error,
    service_unavailable,
    unprocessable,
)
from backend.app.exceptions import VoiceNoteError
from backend.pipeline.enhanced_audio_processor import (
    AIEnhanceOptions,
    AudioQualityEvaluation,
    AI_NOISE_REMOVAL_ENABLED,
    BatchPreprocessOptions,
    EnhancedAudioProcessor,
    EnhancementResult,
    SUPPORTED_FORMATS,
    VoiceQualityScore,
    cleanup_temp_file,
    enhance_audio_with_ai,
)
from backend.schemas.enhanced_audio_preprocess import (
    AIEnhanceOptionsPayload,
    EnhancementReportResponse,
    VoiceQualityAssessment,
)
from backend.schemas.audio_enhanced import BatchPreprocessResponse, BatchSummary
from backend.utils.logger import get_logger
from backend.utils.validators import validate_audio_format

logger = get_logger(__name__)

router = APIRouter(prefix="/enhanced", tags=["audio-enhancement"])


# AI 증강 동시 실행 제한 (리소스 관리)
_enhancement_semaphore = None
_enhanced_processor: EnhancedAudioProcessor | None = None


def get_enhancement_semaphore():
    """글로벌 세마포어 (지연 초기화)"""
    global _enhancement_semaphore
    if _enhancement_semaphore is None:
        max_concurrent = settings.audio_preprocess_max_concurrent
        if not isinstance(max_concurrent, int):
            max_concurrent = 2
        _enhancement_semaphore = asyncio.Semaphore(max_concurrent)
    return _enhancement_semaphore


async def get_enhanced_processor() -> EnhancedAudioProcessor:
    """배치 전처리 프로세서를 지연 초기화."""
    global _enhanced_processor
    if _enhanced_processor is None:
        _enhanced_processor = EnhancedAudioProcessor()
        await _enhanced_processor.initialize()
    return _enhanced_processor


def _resolve_enhancement_options(payload: AIEnhanceOptionsPayload) -> AIEnhanceOptions:
    """Pydantic 페이로드를 도메인 옵션으로 변환하고 유효성 검증."""
    opts = AIEnhanceOptions(
        enable_noise_reduction=payload.enable_noise_reduction,
        enable_voice_enhancement=payload.enable_voice_enhancement,
        enable_vad=payload.enable_vad,
        enable_quality_assessment=payload.enable_quality_assessment,
        noise_reduction_strength=payload.noise_reduction_strength,
        voice_enhancement_strength=payload.voice_enhancement_strength,
        vad_threshold=payload.vad_threshold,
        target_snr=payload.target_snr,
        preserve_natural_voice=payload.preserve_natural_voice,
        output_format=payload.output_format,
    )
    try:
        opts.validate()
    except ValueError as exc:
        unprocessable(str(exc))
    return opts


def _calculate_audio_metrics(audio_data: np.ndarray, sample_rate: int) -> dict[str, float]:
    """오디오 품질 지표 계산"""
    if len(audio_data) == 0:
        return {"snr": 0.0, "clarity": 0.0, "noise_level": 0.0}
    
    # SNR 계산 (신호 대 잡음 비)
    signal_power = np.mean(audio_data ** 2)
    noise_power = np.var(audio_data - np.mean(audio_data))
    snr = 10 * np.log10(signal_power / (noise_power + 1e-10))
    
    # 명료도 계산 (고주파 에너지 비율)
    high_freq_energy = np.sum(np.abs(audio_data[len(audio_data)//2:]) ** 2)
    total_energy = np.sum(np.abs(audio_data) ** 2)
    clarity = high_freq_energy / (total_energy + 1e-10)
    
    # 노이즈 레벨 계산 (RMS)
    noise_level = np.sqrt(np.mean(audio_data ** 2))
    
    return {
        "snr": max(0.0, snr),
        "clarity": min(1.0, clarity),
        "noise_level": noise_level,
    }


@router.post(
    "/preprocess",
    responses={
        200: {
            "description": "AI 증강된 WAV 파일 + 품질 평가 보고서",
            "content": {
                "application/json": {"example": EnhancementReportResponse.model_json_schema()},
            },
        },
        400: {"description": "잘못된 파일 또는 손상된 오디오"},
        413: {"description": "파일 크기 초과"},
        422: {"description": "증강 옵션 검증 실패"},
        503: {"description": "AI 증강 기능 비활성화 상태"},
    },
)
async def enhanced_audio_endpoint(
    file: UploadFile = File(..., description="원본 오디오 파일"),
    enable_noise_reduction: bool = Form(default=True, description="AI 노이즈 제거 활성화"),
    enable_voice_enhancement: bool = Form(default=True, description="음성 강화 활성화"),
    enable_vad: bool = Form(default=True, description="Voice Activity Detection 활성화"),
    enable_quality_assessment: bool = Form(default=True, description="품질 자동 평가 활성화"),
    noise_reduction_strength: float = Form(default=0.7, description="노이즈 제거 강도 (0.0~1.0)"),
    voice_enhancement_strength: float = Form(default=0.5, description="음성 강도 (0.0~1.0)"),
    vad_threshold: float = Form(default=0.5, description="VAD 임계값 (0.0~1.0)"),
    target_snr: float = Form(default=20.0, description="목표 SNR (dB)"),
    preserve_natural_voice: bool = Form(default=True, description="자연스러운 음성 보존"),
    output_format: str = Form(default="wav", description="출력 형식 (wav, mp3)"),
) -> EnhancementReportResponse:
    """AI 기반 오디오 증강 처리."""
    if not settings.audio_preprocess_enabled:
        service_unavailable("AI 오디오 증강 기능이 비활성화되어 있습니다.")

    # 파일명/포맷 검증
    filename = file.filename or "audio"
    is_valid, msg = validate_audio_format(filename)
    if not is_valid:
        bad_request(msg)

    # 옵션 파싱 + 검증
    payload = AIEnhanceOptionsPayload(
        enable_noise_reduction=enable_noise_reduction,
        enable_voice_enhancement=enable_voice_enhancement,
        enable_vad=enable_vad,
        enable_quality_assessment=enable_quality_assessment,
        noise_reduction_strength=noise_reduction_strength,
        voice_enhancement_strength=voice_enhancement_strength,
        vad_threshold=vad_threshold,
        target_snr=target_snr,
        preserve_natural_voice=preserve_natural_voice,
        output_format=output_format,
    )
    options = _resolve_enhancement_options(payload)

    # 입력 파일 임시 저장
    max_bytes = settings.audio_preprocess_max_file_mb * 1024 * 1024
    bytes_read = 0
    suffix = Path(filename).suffix or ".bin"
    
    try:
        src_fd, src_name = tempfile.mkstemp(suffix=suffix, prefix="enhance_in_")
        src_path = Path(src_name)
        with open(src_fd, "wb") as fp:
            while chunk := await file.read(1024 * 1024):
                bytes_read += len(chunk)
                if bytes_read > max_bytes:
                    from backend.app.errors import request_entity_too_large
                    request_entity_too_large(
                        f"파일 크기가 {settings.audio_preprocess_max_file_mb}MB를 초과합니다."
                    )
                fp.write(chunk)
    except VoiceNoteError:
        _safe_unlink(src_path)
        raise
    except Exception as exc:
        if "src_path" in locals():
            _safe_unlink(src_path)
        logger.error("업로드 저장 실패", error=str(exc))
        bad_request(f"업로드 처리 실패: {exc}")

    # 고급 전처리 처리 (리소스 제한 적용)
    try:
        processor = await get_enhanced_processor()
    except Exception as exc:
        _safe_unlink(src_path)
        logger.error("AI 오디오 증강 초기화 실패", error=str(exc))
        internal_server_error("AI 오디오 증강 초기화 중 오류가 발생했습니다")

    enhancement_semaphore = get_enhancement_semaphore()
    async with enhancement_semaphore:
        try:
            preprocess_options = BatchPreprocessOptions(
                convert_to_16k_mono=True,
                normalize=True,
                ai_noise_removal=enable_noise_reduction,
                denoise_strength=noise_reduction_strength,
            )
            batch_result = await processor.preprocess_batch([str(src_path)], preprocess_options, None)
            if batch_result.failed_files:
                bad_request(batch_result.errors[0]["error"])
            processed_info = batch_result.results[0]
            result = EnhancementResult(
                output_path=processed_info.processed_path,
                enhancement_id=f"enh_{int(datetime.now(UTC).timestamp())}",
                noise_reduction_applied=enable_noise_reduction,
                voice_enhancement_applied=enable_voice_enhancement,
                segments_processed=1,
                processing_time=batch_result.processing_time_seconds,
                processing_details=processed_info.metadata,
                warnings=[],
            )
        except ValueError as exc:
            _safe_unlink(src_path)
            bad_request(str(exc))
        except VoiceNoteError:
            _safe_unlink(src_path)
            raise
        except Exception as exc:
            _safe_unlink(src_path)
            logger.error("AI 오디오 증강 실패", error=str(exc))
            bad_request(str(exc))

    # 품질 평가
    quality_assessment = None
    if options.enable_quality_assessment:
        try:
            with wave.open(str(result.output_path), "rb") as wf:
                sample_rate = wf.getframerate()
                audio_data = np.frombuffer(wf.readframes(-1), dtype=np.int16)
                
                # 품질 지표 계산
                metrics = _calculate_audio_metrics(audio_data.astype(float) / 32768.0, sample_rate)
                
                # 음질 평가 생성
                quality_assessment = VoiceQualityAssessment(
                    overall_score=min(100.0, max(0.0, metrics["snr"] * 2 + metrics["clarity"] * 50)),
                    snr_db=metrics["snr"],
                    clarity_score=metrics["clarity"],
                    noise_level=metrics["noise_level"],
                    quality_grade=_get_quality_grade(metrics["snr"]),
                    recommendations=_generate_improvement_recommendations(metrics),
                    enhancement_summary={
                        "noise_removed": result.noise_reduction_applied,
                        "voice_enhanced": result.voice_enhancement_applied,
                        "segments_processed": result.segments_processed,
                        "processing_time_seconds": result.processing_time,
                    }
                )
        except Exception as exc:
            logger.error("품질 평가 실패", error=str(exc))

    # 응답 구성
    output_name = f"{Path(filename).stem}_enhanced.{options.output_format}"
    response_data = EnhancementReportResponse(
        original_filename=filename,
        original_size_bytes=bytes_read,
        processed_size_bytes=result.output_path.stat().st_size,
        enhancement_report=AudioQualityEvaluation(
            quality_assessment=quality_assessment,
            processing_details=result.processing_details,
            warnings=result.warnings,
        ),
        download_url=f"/api/v1/enhanced/{result.enhancement_id}/download",
        enhancement_id=result.enhancement_id,
    )

    # 파일 다운로드와 함께 정리
    def _cleanup() -> None:
        _safe_unlink(src_path)
        _safe_unlink(result.output_path)

    return FileResponse(
        path=str(result.output_path),
        media_type=f"audio/{options.output_format}",
        filename=output_name,
        background=BackgroundTask(_cleanup),
        headers={"X-Enhancement-ID": result.enhancement_id},
    )


@router.post("/batch")
async def enhanced_batch_endpoint(
    files: list[UploadFile] = File(..., description="전처리할 오디오 파일 목록"),
) -> dict[str, Any]:
    """여러 오디오 파일을 고급 전처리."""
    if not settings.audio_preprocess_enabled:
        service_unavailable("AI 오디오 증강 기능이 비활성화되어 있습니다.")
    if len(files) > 20:
        bad_request("최대 20개 파일까지 처리할 수 있습니다.")

    max_bytes = settings.audio_preprocess_max_file_mb * 1024 * 1024
    src_paths: list[Path] = []

    try:
        for file in files:
            filename = file.filename or "audio"
            is_valid, msg = validate_audio_format(filename)
            if not is_valid:
                bad_request(msg)

            suffix = Path(filename).suffix or ".bin"
            src_fd, src_name = tempfile.mkstemp(suffix=suffix, prefix="enhance_batch_in_")
            src_path = Path(src_name)
            src_paths.append(src_path)
            bytes_read = 0
            with open(src_fd, "wb") as fp:
                while chunk := await file.read(1024 * 1024):
                    bytes_read += len(chunk)
                    if bytes_read > max_bytes:
                        bad_request(
                            f"파일 크기가 {settings.audio_preprocess_max_file_mb}MB를 초과합니다."
                        )
                    fp.write(chunk)

        try:
            processor = await get_enhanced_processor()
        except Exception as exc:
            logger.error("AI 오디오 증강 초기화 실패", error=str(exc))
            internal_server_error("AI 오디오 증강 초기화 중 오류가 발생했습니다")

        options = BatchPreprocessOptions()
        result = await processor.preprocess_batch([str(path) for path in src_paths], options, None)
        return {
            "total_files": result.total_files,
            "processed_files": result.processed_files,
            "failed_files": result.failed_files,
            "processing_time_seconds": result.processing_time_seconds,
            "summary": result.summary,
            "results": [
                {
                    "original_path": str(item.original_path),
                    "processed_path": str(item.processed_path),
                    "original_format": item.original_format,
                    "original_size": item.original_size,
                    "processed_size": item.processed_size,
                    "duration_seconds": item.duration_seconds,
                    "sample_rate": item.sample_rate,
                    "channels": item.channels,
                    "metadata": item.metadata,
                }
                for item in result.results
            ],
            "errors": result.errors,
        }
    except VoiceNoteError:
        raise
    except Exception as exc:
        logger.error("배치 오디오 증강 실패", error=str(exc))
        bad_request(str(exc))
    finally:
        for path in src_paths:
            _safe_unlink(path)


async def enhanced_preprocess_endpoint(
    file: UploadFile = File(..., description="원본 오디오 파일"),
    convert_to_16k_mono: bool = Form(default=True),
    normalize: bool = Form(default=True),
    target_dbfs: float = Form(default=-20.0),
    high_pass_hz: int | None = Form(default=None),
    low_pass_hz: int | None = Form(default=None),
    trim_silence: bool = Form(default=False),
    silence_threshold_db: float = Form(default=-40.0),
    silence_min_len_ms: int = Form(default=700),
    ai_noise_removal: bool = Form(default=True),
    noise_threshold: float = Form(default=0.1),
    denoise_strength: float = Form(default=0.8),
) -> StreamingResponse:
    """Legacy direct-call single-file enhanced preprocess endpoint."""
    if not settings.audio_preprocess_enabled:
        service_unavailable("AI 오디오 증강 기능이 비활성화되어 있습니다.")

    filename = file.filename or "audio"
    is_valid, msg = validate_audio_format(filename)
    if not is_valid:
        bad_request(msg)

    max_bytes = settings.audio_preprocess_max_file_mb * 1024 * 1024
    suffix = Path(filename).suffix or ".bin"
    src_fd, src_name = tempfile.mkstemp(suffix=suffix, prefix="enhance_in_")
    src_path = Path(src_name)
    bytes_read = 0

    try:
        with open(src_fd, "wb") as fp:
            while chunk := await file.read(1024 * 1024):
                bytes_read += len(chunk)
                if bytes_read > max_bytes:
                    from backend.app.errors import request_entity_too_large

                    request_entity_too_large(
                        f"파일 크기가 {settings.audio_preprocess_max_file_mb}MB를 초과합니다."
                    )
                fp.write(chunk)

        processor = await get_enhanced_processor()
        options = BatchPreprocessOptions(
            convert_to_16k_mono=convert_to_16k_mono,
            normalize=normalize,
            target_dbfs=target_dbfs,
            high_pass_hz=high_pass_hz,
            low_pass_hz=low_pass_hz,
            trim_silence=trim_silence,
            silence_threshold_db=silence_threshold_db,
            silence_min_len_ms=silence_min_len_ms,
            ai_noise_removal=ai_noise_removal,
            noise_threshold=noise_threshold,
            denoise_strength=denoise_strength,
        )
        result = await processor.preprocess_batch([str(src_path)], options, None)
        if result.failed_files:
            raise HTTPException(status_code=400, detail=result.errors[0].get("error", "전처리 실패"))
        processed_path = result.results[0].processed_path

        def _cleanup() -> None:
            _safe_unlink(src_path)
            _safe_unlink(processed_path)

        return StreamingResponse(
            iter([b""]),
            media_type="audio/wav",
            background=BackgroundTask(_cleanup),
            headers={"X-Processed-Path": str(processed_path)},
        )
    except VoiceNoteError:
        _safe_unlink(src_path)
        raise
    except HTTPException:
        _safe_unlink(src_path)
        raise
    except Exception as exc:
        _safe_unlink(src_path)
        logger.error("고급 오디오 전처리 실패", error=str(exc))
        bad_request(str(exc))


async def batch_preprocess_endpoint(
    files: list[UploadFile] = File(..., description="전처리할 오디오 파일 목록"),
    convert_to_16k_mono: bool = Form(default=True),
    normalize: bool = Form(default=True),
    target_dbfs: float = Form(default=-20.0),
    high_pass_hz: int | None = Form(default=None),
    low_pass_hz: int | None = Form(default=None),
    trim_silence: bool = Form(default=False),
    silence_threshold_db: float = Form(default=-40.0),
    silence_min_len_ms: int = Form(default=700),
    ai_noise_removal: bool = Form(default=True),
    noise_threshold: float = Form(default=0.1),
    denoise_strength: float = Form(default=0.8),
    output_format: str = Form(default="zip"),
    return_report: bool = Form(default=True),
) -> SimpleNamespace:
    """Legacy direct-call batch enhanced preprocess endpoint."""
    if not settings.audio_preprocess_enabled:
        service_unavailable("AI 오디오 증강 기능이 비활성화되어 있습니다.")
    if len(files) > 20:
        bad_request("최대 20개 파일까지 처리할 수 있습니다.")

    max_bytes = settings.audio_preprocess_max_file_mb * 1024 * 1024
    src_paths: list[Path] = []
    try:
        for file in files:
            filename = file.filename or "audio"
            is_valid, msg = validate_audio_format(filename)
            if not is_valid:
                bad_request(msg)
            suffix = Path(filename).suffix or ".bin"
            src_fd, src_name = tempfile.mkstemp(suffix=suffix, prefix="enhance_batch_in_")
            src_path = Path(src_name)
            src_paths.append(src_path)
            bytes_read = 0
            with open(src_fd, "wb") as fp:
                while chunk := await file.read(1024 * 1024):
                    bytes_read += len(chunk)
                    if bytes_read > max_bytes:
                        bad_request(
                            f"파일 크기가 {settings.audio_preprocess_max_file_mb}MB를 초과합니다."
                        )
                    fp.write(chunk)

        processor = await get_enhanced_processor()
        options = BatchPreprocessOptions(
            convert_to_16k_mono=convert_to_16k_mono,
            normalize=normalize,
            target_dbfs=target_dbfs,
            high_pass_hz=high_pass_hz,
            low_pass_hz=low_pass_hz,
            trim_silence=trim_silence,
            silence_threshold_db=silence_threshold_db,
            silence_min_len_ms=silence_min_len_ms,
            ai_noise_removal=ai_noise_removal,
            noise_threshold=noise_threshold,
            denoise_strength=denoise_strength,
        )
        result = await processor.preprocess_batch([str(path) for path in src_paths], options, None)
        report = None
        if return_report and hasattr(processor, "create_processing_report"):
            report = await processor.create_processing_report(result)
        return SimpleNamespace(
            task_id=result.task_id,
            total_files=result.total_files,
            processed_files=result.processed_files,
            failed_files=result.failed_files,
            processing_time_seconds=result.processing_time_seconds,
            summary=result.summary,
            results=result.results,
            errors=result.errors,
            output_format=output_format,
            report=report,
        )
    except VoiceNoteError:
        raise
    except Exception as exc:
        logger.error("배치 오디오 전처리 실패", error=str(exc))
        bad_request(str(exc))
    finally:
        for path in src_paths:
            _safe_unlink(path)


@router.get("/formats")
async def get_supported_formats() -> list[dict[str, Any]]:
    """지원하는 고급 전처리 오디오 포맷 목록."""
    return list(SUPPORTED_FORMATS.values())


@router.get("/status")
async def get_model_status() -> dict[str, Any]:
    """고급 전처리 모델 상태."""
    processor = await get_enhanced_processor()
    return {
        "ai_noise_removal_enabled": AI_NOISE_REMOVAL_ENABLED,
        "model_loaded": processor.ai_model.model_loaded,
        "supported_formats": len(SUPPORTED_FORMATS),
        "batch_max_files": processor.max_batch_files,
        "batch_max_concurrent": settings.audio_preprocess_max_concurrent,
        "supported_ai_features": [
            "noise_removal",
            "normalization",
            "silence_trimming",
            "format_conversion",
        ],
        "processing_limits": {
            "max_file_mb": settings.audio_preprocess_max_file_mb,
            "max_files": processor.max_batch_files,
        },
    }


@router.get(
    "/{enhancement_id}/download"
)
async def download_enhanced_audio(
    enhancement_id: str,
) -> FileResponse:
    """AI 증강된 오디오 파일 다운로드."""
    # 실제 구현에서는 파일 시스템 또는 스토리지에서 파일을 찾아 반환
    # 여는 예시로, 실제로는 데이터베이스 또는 캐시에서 파일 위치 조회
    
    # 가상의 파일 경로 (실제 구현 필요)
    file_path = Path(f"/tmp/enhanced_{enhancement_id}.wav")
    
    if not file_path.exists():
        from backend.app.errors import not_found
        not_found("AI 증강 파일을 찾을 수 없습니다.")
    
    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=f"enhanced_{enhancement_id}.wav"
    )


def _get_quality_grade(snr_db: float) -> str:
    """SNR 기반 음질 등급 평가"""
    if snr_db >= 30:
        return "excellent"
    elif snr_db >= 20:
        return "good"
    elif snr_db >= 15:
        return "fair"
    elif snr_db >= 10:
        return "poor"
    else:
        return "very_poor"


def _generate_improvement_recommendations(metrics: dict[str, float]) -> list[str]:
    """개선 제안 생성"""
    recommendations = []
    
    if metrics["snr"] < 15:
        recommendations.append("노이즈 제거 기능을 강화하여 다시 처리해 보세요.")
    
    if metrics["clarity"] < 0.3:
        recommendations.append("고주파 성분이 부족합니다. 더 가까운 위치에서 녹음해 보세요.")
    
    if metrics["noise_level"] > 0.1:
        recommendations.append("배경 소음이 많습니다. 조용한 환경에서 재녹음해 보세요.")
    
    if not recommendations:
        recommendations.append("음질이 양호합니다. 추가 처리가 필요하지 않습니다.")
    
    return recommendations


def _safe_unlink(path: Path) -> None:
    """예외를 삼키고 안전하게 파일을 정리."""
    try:
        cleanup_temp_file(path)
    except OSError as exc:
        logger.warning("임시 파일 정리 실패", path=str(path), error=str(exc))
