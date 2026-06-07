"""
고급 오디오 전처리 Pydantic 스키마
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OutputFormat(StrEnum):
    """출력 형식"""

    ZIP = "zip"
    INDIVIDUAL = "individual"


class AIProcessingStatus(StrEnum):
    """AI 처리 상태"""

    ENABLED = "enabled"
    DISABLED = "disabled"
    LOADING = "loading"
    ERROR = "error"


class FormatInfo(BaseModel):
    """오디오 포맷 정보"""

    extension: str = Field(..., description="파일 확장자")
    description: str = Field(..., description="포맷 설명")
    supported_codecs: list[str] = Field(..., description="지원 코덱 목록")


class ModelStatusResponse(BaseModel):
    """AI 모델 상태 응답"""

    ai_noise_removal_enabled: bool = Field(..., description="AI 노이즈 제거 활성화 여부")
    model_loaded: bool = Field(..., description="AI 모델 로드 상태")
    supported_formats: int = Field(..., description="지원 오디오 포맷 수")
    batch_max_files: int = Field(..., description="배치 처리 최대 파일 수")
    batch_max_concurrent: int = Field(..., description="동시 처리 수")
    supported_ai_features: list[str] = Field(..., description="지원 AI 기능")
    processing_limits: dict[str, Any] = Field(..., description="처리 한계")


class EnhancedPreprocessOptions(BaseModel):
    """고급 전처리 옵션"""

    convert_to_16k_mono: bool = Field(default=True, description="16kHz 모노로 변환")
    normalize: bool = Field(default=True, description="오디오 레벨 정규화")
    target_dbfs: float = Field(default=-20.0, description="목표 dBFS (선형적)")
    high_pass_hz: int | None = Field(default=None, description="하이-패스 필터 (Hz)")
    low_pass_hz: int | None = Field(default=None, description="로우-패스 필터 (Hz)")
    trim_silence: bool = Field(default=False, description="앞뒤 무음 제거")
    silence_threshold_db: float = Field(default=-40.0, description="무음 임계값 (dB)")
    silence_min_len_ms: int = Field(default=700, description="최소 무음 길이 (ms)")
    ai_noise_removal: bool = Field(default=True, description="AI 노이즈 제거")
    noise_threshold: float = Field(default=0.1, description="노이즈 감지 임계값")
    denoise_strength: float = Field(default=0.8, description="노이즈 제거 강도 (0.0~1.0)")

    @field_validator("target_dbfs")
    @classmethod
    def validate_target_dbfs(cls, v: float) -> float:
        if not (-60.0 <= v <= 0.0):
            raise ValueError("target_dbfs는 -60.0 ~ 0.0 범위여야 합니다.")
        return v

    @field_validator("high_pass_hz")
    @classmethod
    def validate_high_pass_hz(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 500):
            raise ValueError("high_pass_hz는 1~500Hz 사이여야 합니다.")
        return v

    @field_validator("low_pass_hz")
    @classmethod
    def validate_low_pass_hz(cls, v: int | None) -> int | None:
        if v is not None and not (1000 <= v <= 16000):
            raise ValueError("low_pass_hz는 1000~16000Hz 사이여야 합니다.")
        return v

    @field_validator("silence_threshold_db")
    @classmethod
    def validate_silence_threshold_db(cls, v: float) -> float:
        if not (-60.0 <= v <= 0.0):
            raise ValueError("silence_threshold_db는 -60.0 ~ 0.0 범위여야 합니다.")
        return v

    @field_validator("silence_min_len_ms")
    @classmethod
    def validate_silence_min_len_ms(cls, v: int) -> int:
        if not (100 <= v <= 5000):
            raise ValueError("silence_min_len_ms는 100~5000ms 사이여야 합니다.")
        return v

    @field_validator("noise_threshold")
    @classmethod
    def validate_noise_threshold(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("noise_threshold는 0.0~1.0 범위여야 합니다.")
        return v

    @field_validator("denoise_strength")
    @classmethod
    def validate_denoise_strength(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("denoise_strength는 0.0~1.0 범위여야 합니다.")
        return v


class AudioFileInfo(BaseModel):
    """오디오 파일 정보"""

    model_config = ConfigDict(from_attributes=True)

    original_path: str = Field(..., description="원본 파일 경로")
    processed_path: str = Field(..., description="처리된 파일 경로")
    original_format: str = Field(..., description="원본 파일 형식")
    original_size: int = Field(..., description="원본 파일 크기 (바이트)")
    processed_size: int = Field(..., description="처리된 파일 크기 (바이트)")
    duration_seconds: float = Field(..., description="오디오 길이 (초)")
    sample_rate: int = Field(..., description="샘플 레이트 (Hz)")
    channels: int = Field(..., description="채널 수")
    metadata: dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class BatchPreprocessRequest(BaseModel):
    """배치 전처리 요청"""

    files: list[str] = Field(..., min_length=1, max_length=20, description="처리할 파일 경로 목록")
    options: EnhancedPreprocessOptions = Field(
        default_factory=EnhancedPreprocessOptions, description="전처리 옵션"
    )
    output_format: OutputFormat = Field(default=OutputFormat.ZIP, description="출력 형식")
    return_report: bool = Field(default=True, description="상세 보고서 포함")


class PreprocessResponse(BaseModel):
    """단일 전처리 응답"""

    original_filename: str = Field(..., description="원본 파일명")
    processed_filename: str = Field(..., description="처리된 파일명")
    original_size_bytes: int = Field(..., description="원본 파일 크기")
    processed_size_bytes: int = Field(..., description="처리된 파일 크기")
    duration_seconds: float = Field(..., description="오디오 길이 (초)")
    sample_rate: int = Field(..., description="샘플 레이트")
    channels: int = Field(..., description="채널 수")
    applied_options: dict[str, Any] = Field(..., description="적용된 옵션")
    ai_noise_removed: bool = Field(..., description="AI 노이즈 제거 적용 여부")
    processing_time_seconds: float = Field(..., description="처리 시간 (초)")
    compression_ratio: float = Field(..., description="압축률")


class BatchSummary(BaseModel):
    """배치 처리 요약"""

    total_input_size_bytes: int = Field(..., description="총 입력 파일 크기")
    total_output_size_bytes: int = Field(..., description="총 출력 파일 크기")
    compression_ratio: float = Field(..., description="평균 압축률")
    total_duration_seconds: float = Field(..., description="총 오디오 길이 (초)")
    average_duration_seconds: float = Field(..., description="평균 오디오 길이")
    average_sample_rate: int = Field(..., description="평균 샘플 레이트")
    format_distribution: dict[str, int] = Field(..., description="포맷별 파일 수")


class BatchPreprocessResponse(BaseModel):
    """배치 전처리 응답"""

    task_id: str = Field(..., description="배치 작업 ID")
    total_files: int = Field(..., description="총 파일 수")
    processed_files: int = Field(..., description="성공 처리된 파일 수")
    failed_files: int = Field(..., description="실패 파일 수")
    processing_time_seconds: float = Field(..., description="총 처리 시간 (초)")
    summary: BatchSummary = Field(..., description="처리 요약")
    results: list[AudioFileInfo] = Field(default_factory=list, description="개별 처리 결과")
    report: str | None = Field(default=None, description="상세 보고서 (JSON 문자열)")
    errors: list[dict[str, Any]] = Field(default_factory=list, description="오류 목록")


class ProcessingStatus(BaseModel):
    """처리 상태"""

    task_id: str = Field(..., description="작업 ID")
    status: str = Field(..., description="상태 (running, completed, failed)")
    progress_percent: float = Field(..., description="진행률 (%)")
    processed_files: int = Field(..., description="처리된 파일 수")
    total_files: int = Field(..., description="총 파일 수")
    elapsed_seconds: float = Field(..., description="경과 시간 (초)")
    estimated_remaining_seconds: float | None = Field(default=None, description="예상 남은 시간")
    current_file: str | None = Field(default=None, description="현재 처리 중인 파일")
    error_message: str | None = Field(default=None, description="오류 메시지")


class AudioAnalysisResult(BaseModel):
    """오디오 분석 결과"""

    filename: str = Field(..., description="파일명")
    duration_seconds: float = Field(..., description="오디오 길이 (초)")
    sample_rate: int = Field(..., description="샘플 레이트")
    channels: int = Field(..., description="채널 수")
    bit_depth: int = Field(..., description="비트 깊이")
    channels_info: list[dict[str, Any]] = Field(..., description="채널별 정보")
    audio_quality_score: float = Field(..., description="오디오 품질 점수 (0.0~1.0)")
    noise_level: float = Field(..., description="노이즈 레벨 (dB)")
    signal_to_noise_ratio: float = Field(..., description="신호 대 잡음비 (dB)")
    clipping_detected: bool = Field(..., description="클리핑 감지 여부")
    silence_percentage: float = Field(..., description="무음 비율 (%)")
    peak_amplitude: float = Field(..., description="피크 진폭")
    rms_amplitude: float = Field(..., description="RMS 진폭")
    recommended_settings: dict[str, Any] = Field(..., description="권장 설정")


class ProcessingReport(BaseModel):
    """처리 보고서"""

    task_id: str = Field(..., description="작업 ID")
    created_at: datetime = Field(..., description="보고서 생성 시각")
    summary: BatchSummary = Field(..., description="처리 요약")
    processing_log: list[dict[str, Any]] = Field(..., description="처리 로그")
    recommendations: list[str] = Field(..., description="개선 권장사항")
    metadata: dict[str, Any] = Field(..., description="추가 메타데이터")
