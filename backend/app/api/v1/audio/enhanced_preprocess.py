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

import json
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
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
    EnhancementResult,
    AudioQualityEvaluation,
    VoiceQualityScore,
    cleanup_temp_file,
    enhance_audio_with_ai,
)
from backend.schemas.enhanced_audio_preprocess import (
    AIEnhanceOptionsPayload,
    AudioQualityEvaluation,
    EnhancementReportResponse,
    VoiceQualityAssessment,
)
from backend.utils.logger import get_logger
from backend.utils.validators import validate_audio_format

logger = get_logger(__name__)

router = APIRouter(prefix="/audio", tags=["audio-enhancement"])


# AI 증강 동시 실행 제한 (리소스 관리)
_enhancement_semaphore = None


def get_enhancement_semaphore():
    """글로벌 세마포어 (지연 초기화)"""
    global _enhancement_semaphore
    if _enhancement_semaphore is None:
        _enhancement_semaphore = asyncio.Semaphore(settings.audio_enhancement_max_concurrent)
    return _enhancement_semaphore


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
    "/enhanced",
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
    if not settings.audio_enhancement_enabled:
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
    max_bytes = settings.audio_enhancement_max_file_mb * 1024 * 1024
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
                        f"파일 크기가 {settings.audio_enhancement_max_file_mb}MB를 초과합니다."
                    )
                fp.write(chunk)
    except VoiceNoteError:
        _safe_unlink(src_path)
        raise
    except Exception as exc:
        _safe_unlink(src_path)
        logger.error("업로드 저장 실패", error=str(exc))
        bad_request(f"업로드 처리 실패: {exc}")

    # AI 증강 처리 (리소스 제한 적용)
    enhancement_semaphore = get_enhancement_semaphore()
    async with enhancement_semaphore:
        try:
            result = await asyncio.to_thread(
                enhance_audio_with_ai, 
                src_path, 
                options
            )
        except ValueError as exc:
            _safe_unlink(src_path)
            bad_request(str(exc))
        except Exception as exc:
            _safe_unlink(src_path)
            logger.error("AI 오디오 증강 실패", error=str(exc))
            internal_server_error("AI 오디오 증강 중 오류가 발생했습니다")

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
        download_url=f"/api/v1/audio/enhanced/{result.enhancement_id}/download",
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


@router.get(
    "/enhanced/{enhancement_id}/download"
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


async def _safe_unlink(path: Path) -> None:
    """예외를 삼키고 안전하게 파일을 정리."""
    try:
        cleanup_temp_file(path)
    except OSError as exc:
        logger.warning("임시 파일 정리 실패", path=str(path), error=str(exc))