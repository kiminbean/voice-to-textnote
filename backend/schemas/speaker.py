"""
SPEC-SPEAKER-001: 화자 프로필 Pydantic 스키마
SPEC-SPEAKER-VOICE-001: 화자 음성 프로파일 스키마 확장
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SpeakerProfileCreate(BaseModel):
    """화자 프로필 생성 요청"""

    speaker_label: str = Field(..., min_length=1, max_length=50, description="화자 레이블 (예: SPEAKER_00)")
    display_name: str = Field(..., min_length=1, max_length=100, description="표시 이름")
    role: str | None = Field(default=None, max_length=100, description="역할 (예: 팀장)")
    note: str | None = Field(default=None, max_length=1000, description="메모")
    task_id: str | None = Field(default=None, max_length=255, description="회의록 전용 오버라이드용 task_id. None이면 전역 프로필.")


class SpeakerProfileUpdate(BaseModel):
    """화자 프로필 부분 수정 요청 (모든 필드 선택)"""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class SpeakerProfileResponse(BaseModel):
    """화자 프로필 응답"""

    id: uuid.UUID
    user_id: uuid.UUID
    speaker_label: str
    display_name: str
    role: str | None
    note: str | None
    task_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SpeakerProfileListResponse(BaseModel):
    """화자 프로필 목록 응답"""

    items: list[SpeakerProfileResponse]
    total: int


# ---------------------------------------------------------------------------
# SPEC-SPEAKER-VOICE-001: 화자 음성 프로파일 스키마
# ---------------------------------------------------------------------------


class VoiceSampleAnalysis(BaseModel):
    """단일 오디오 샘플 분석 결과"""

    duration_seconds: float = Field(..., ge=0.0)
    sample_rate: int | None = Field(default=None, ge=0)
    avg_dbfs: float | None = None
    rms_dbfs: float | None = None
    speech_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    silence_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_issues: list[str] = Field(default_factory=list)


class VoiceCharacteristics(BaseModel):
    """누적 음성 특성 응답"""

    speaker_profile_id: uuid.UUID
    sample_count: int = Field(..., ge=0)
    total_duration_seconds: float = Field(..., ge=0.0)
    avg_energy_dbfs: float | None = None
    avg_rms_dbfs: float | None = None
    avg_speech_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    avg_sample_rate: float | None = None
    avg_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    features: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VoiceProfileCreateRequest(BaseModel):
    """음성 프로파일 생성/초기화 요청 (기존 분석 결과를 직접 주입)"""

    samples: list[VoiceSampleAnalysis] = Field(
        default_factory=list,
        description="누적할 분석 샘플 목록. 비어있으면 빈 프로파일을 생성한다.",
    )
    overwrite: bool = Field(
        default=False,
        description="True면 기존 프로파일을 덮어쓰고, False면 누적한다.",
    )


class VoiceSampleAnalyzeResponse(BaseModel):
    """오디오 샘플 분석 후 응답"""

    speaker_profile_id: uuid.UUID
    analyzed: VoiceSampleAnalysis
    characteristics: VoiceCharacteristics
