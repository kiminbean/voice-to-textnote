"""
AI 기반 오디오 증강 API 스키마
"""

from typing import Any

from pydantic import BaseModel, Field, confloat, constr


class AIEnhanceOptionsPayload(BaseModel):
    """AI 증강 옵션 요청 스키마"""

    enable_noise_reduction: bool = Field(
        default=True,
        description="AI 노이즈 제거 활성화"
    )
    enable_voice_enhancement: bool = Field(
        default=True,
        description="음성 강화 활성화"
    )
    enable_vad: bool = Field(
        default=True,
        description="Voice Activity Detection 활성화"
    )
    enable_quality_assessment: bool = Field(
        default=True,
        description="품질 자동 평가 활성화"
    )
    noise_reduction_strength: confloat(ge=0.0, le=1.0) = Field(
        default=0.7,
        description="노이즈 제거 강도 (0.0=미적용, 1.0=최대 강도)"
    )
    voice_enhancement_strength: confloat(ge=0.0, le=1.0) = Field(
        default=0.5,
        description="음성 강도 (0.0=미적용, 1.0=최대 강도)"
    )
    vad_threshold: confloat(ge=0.0, le=1.0) = Field(
        default=0.5,
        description="VAD 임계값 (낮을수록 더 민감하게 탐지)"
    )
    target_snr: confloat(ge=0.0) = Field(
        default=20.0,
        description="목표 SNR (dB)"
    )
    preserve_natural_voice: bool = Field(
        default=True,
        description="자연스러운 음성 보존"
    )
    output_format: constr(pattern="^(wav|mp3)$") = Field(
        default="wav",
        description="출력 형식 (wav, mp3)"
    )


class VoiceQualityScore(BaseModel):
    """음질 평가 점수"""

    overall_score: float = Field(
        description="종합 점수 (0-100)"
    )
    clarity_score: float = Field(
        description="명료도 점수 (0-1)"
    )
    noise_level: float = Field(
        description="노이즈 레벨"
    )
    snr_db: float = Field(
        description="신호 대 잡음 비 (dB)"
    )
    quality_grade: str = Field(
        description="품질 등급 (excellent, good, fair, poor, very_poor)"
    )


class AudioQualityEvaluation(BaseModel):
    """오디오 품질 평가 결과"""

    quality_assessment: VoiceQualityScore | None = Field(
        description="음질 평가 결과"
    )
    processing_details: dict[str, Any] = Field(
        description="처리 상세 정보"
    )
    warnings: list[str] = Field(
        description="처리 경고 메시지"
    )


class EnhancementReportResponse(BaseModel):
    """AI 증강 응답"""

    original_filename: str = Field(description="원본 파일명")
    original_size_bytes: int = Field(description="원본 파일 크기 (바이트)")
    processed_size_bytes: int = Field(description="처리된 파일 크기 (바이트)")
    enhancement_report: AudioQualityEvaluation = Field(description="증강 보고서")
    download_url: str = Field(description="다운로드 URL")
    enhancement_id: str = Field(description="증강 ID")


class VoiceQualityAssessment(BaseModel):
    """음질 평가 세부 정보"""

    overall_score: float = Field(
        description="종합 점수 (0-100)"
    )
    snr_db: float = Field(
        description="신호 대 잡음 비 (dB)"
    )
    clarity_score: float = Field(
        description="명료도 점수 (0-1)"
    )
    noise_level: float = Field(
        description="노이즈 레벨"
    )
    quality_grade: str = Field(
        description="품질 등급"
    )
    recommendations: list[str] = Field(
        description="개선 제안"
    )
    enhancement_summary: dict[str, Any] = Field(
        description="처리 요약"
    )
