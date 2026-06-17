"""
Advanced Audio Enhancement API 스키마
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class EnhancementMode(str, Enum):
    """음향 향상 모드"""
    CLEAN = "clean"  # 노이즈 제거만
    ENHANCED = "enhanced"  # 음향 향상 + 노이즈 제거
    SPEECH_ONLY = "speech_only"  # 음성만 추출
    MUSIC_FOCUSED = "music_focused"  # 배경음악 강조


class NoiseReductionLevel(str, Enum):
    """노이즈 감소 레벨"""
    LIGHT = "light"  # 가벼운 노이즈 제거
    MODERATE = "moderate"  # 중간 수준 노이즈 제거
    AGGRESSIVE = "aggressive"  # 강력한 노이즈 제거


class VoiceEnhancementMode(str, Enum):
    """보이스 향상 모드"""
    NATURAL = "natural"  # 자연스러운 향상
    CLEAR = "clear"  # 명확성 중심 향상
    BROADCAST = "broadcast"  방송용 강조


class AudioEnhancementRequest(BaseModel):
    """오디오 향상 요청"""
    enhancement_mode: EnhancementMode = Field(
        default=EnhancementMode.ENHANCED,
        description="향상 모드"
    )
    noise_reduction_level: NoiseReductionLevel = Field(
        default=NoiseReductionLevel.MODERATE,
        description="노이즈 감소 레벨"
    )
    voice_enhancement: VoiceEnhancementMode = Field(
        default=VoiceEnhancementMode.NATURAL,
        description="보이스 향상 모드"
    )
    extract_speech_only: bool = Field(
        default=False,
        description="순수 음성만 추출하여 배경음 제거"
    )
    target_sample_rate: int | None = Field(
        default=16000,
        description="목표 샘플 레이트 (Hz)"
    )
    normalize_audio: bool = Field(
        default=True,
        description="오디오 정규화 적용"
    )


class AudioQualityScore(BaseModel):
    """오디오 품질 점수"""
    overall_score: float = Field(
        ge=0.0, le=1.0,
        description="전체 품질 점수 (0.0-1.0)"
    )
    clarity_score: float = Field(
        ge=0.0, le=1.0,
        description="명확도 점수"
    )
    noise_level: float = Field(
        ge=0.0, le=1.0,
        description="노이즈 레벨 (0.0=깨끗, 1.0=노이즈 많음)"
    )
    volume_level: float = Field(
        ge=0.0, le=1.0,
        description="볼륨 레벨 (0.0=낮음, 1.0=높음)"
    )
    voice_activity_ratio: float = Field(
        ge=0.0, le=1.0,
        description="음성 활동 비율"
    )


class EnhancementResult(BaseModel):
    """향상 결과"""
    enhanced_task_id: str = Field(description="향상 작업 ID")
    original_file_size: int = Field(description="원본 파일 크기 (bytes)")
    enhanced_file_size: int = Field(description="향상된 파일 크기 (bytes)")
    processing_time_seconds: float = Field(description="처리 시간 (초)")
    compression_ratio: float = Field(description="압축 비율")
    quality_scores: AudioQualityScore = Field(description="품질 점수")
    segments: list[dict] = Field(description="분할된 세그먼트 정보")
    warnings: list[str] = Field(default_factory=list, description="처리 경고")
    metadata: dict = Field(default_factory=dict, description="추가 메타데이터")


class AudioEnhancementResponse(BaseModel):
    """오디오 향상 응답"""
    task_id: str = Field(description="작업 ID")
    status: str = Field(default="processing", description="상태")
    request: AudioEnhancementRequest = Field(description="요청 데이터")
    result: EnhancementResult | None = Field(default=None, description="처리 결과")
    created_at: datetime = Field(description="생성 시간")
    completed_at: datetime | None = Field(default=None, description="완료 시간")
    error_message: str | None = Field(default=None, description="에러 메시지")


class AudioEnhancementStatus(BaseModel):
    """오디오 향상 상태"""
    task_id: str = Field(description="작업 ID")
    status: str = Field(description="상태")
    progress_percent: float = Field(ge=0.0, le=100.0, description="진행률 (%)")
    current_step: str = Field(description="현재 처리 단계")
    estimated_remaining_seconds: float | None = Field(default=None, description="예상 남은 시간 (초)")
    error_message: str | None = Field(default=None, description="에러 메시지")