"""
SPEC-TONE-001: 발화 톤/운율 분석 Pydantic v2 스키마
REQ-TONE-009: SentimentResponse와 독립적 — sentiment.py 변경 금지
"""

from pydantic import BaseModel, Field


class ToneSegment(BaseModel):
    """개별 발화 구간의 톤 분석 결과 (ToneEngine.analyze_segments 출력 단위)"""

    start: float = Field(..., description="시작 시간 (초)")
    end: float = Field(..., description="종료 시간 (초)")
    speaker: str = Field(..., description="화자 ID")
    tone: str = Field(
        ...,
        description="톤 분류 (calm/excited/authoritative/hesitant/monotone/unknown/skipped)",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="분류 신뢰도 (0.0~1.0)")
    prosody_features: dict[str, float] = Field(
        default_factory=dict,
        description="운율 특징 (f0_mean, f0_std, rms_energy, speaking_rate, opensmile subset)",
    )


class SpeakerTone(BaseModel):
    """화자별 톤 분석 요약"""

    speaker: str = Field(..., description="화자 ID")
    dominant_tone: str = Field(..., description="가장 빈도 높은 톤")
    tone_distribution: dict[str, float] = Field(
        default_factory=dict,
        description="톤별 발화 횟수 ({calm: 3, excited: 1, ...})",
    )
    avg_pitch: float = Field(default=0.0, description="평균 F0 (Hz)")
    avg_energy: float = Field(default=0.0, description="평균 RMS 에너지")


class ToneResponse(BaseModel):
    """톤 분석 전체 응답 (GET /api/v1/tone/{task_id})"""

    task_id: str = Field(..., description="태스크 ID (DIA task_id와 동일)")
    status: str = Field(..., description="작업 상태 (completed/failed/skipped)")
    segments: list[ToneSegment] = Field(default_factory=list, description="구간별 톤 분석 결과")
    speakers: list[SpeakerTone] = Field(default_factory=list, description="화자별 톤 요약")
    overall_tone: str = Field(default="unknown", description="회의 전체 대표 톤")
    error_message: str | None = Field(default=None, description="에러 메시지 (실패/skipped 시)")


class ToneStatusResponse(BaseModel):
    """톤 분석 작업 상태 (GET /api/v1/tone/{task_id}/status)"""

    task_id: str
    status: str = Field(..., description="작업 상태 (pending/processing/completed/failed/skipped)")
    progress: float | None = Field(default=None, description="진행률 (0.0~1.0)")
    message: str | None = Field(default=None, description="상태 메시지")
    error_message: str | None = Field(default=None, description="에러 메시지")
