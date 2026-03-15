"""
화자 분리 요청/응답 Pydantic v2 스키마
REQ-DIA-001, REQ-DIA-002 관련
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.transcription import TaskStatus


class DiarizedSegmentResult(BaseModel):
    """화자 정보가 포함된 STT 세그먼트 결과"""

    # frozen=True: 불변 객체 (기존 SegmentResult 패턴과 동일)
    model_config = ConfigDict(frozen=True)

    # 기존 SegmentResult 필드 (STT 결과에서 상속 역할)
    id: int
    start: float = Field(..., description="세그먼트 시작 시간 (초)")
    end: float = Field(..., description="세그먼트 종료 시간 (초)")
    text: str = Field(..., description="전사된 텍스트")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="STT 신뢰도 점수")

    # 화자 분리 추가 필드
    speaker_id: str | None = Field(default=None, description="식별된 화자 ID (예: SPEAKER_00)")
    speaker_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="화자 식별 신뢰도 (overlap_time / segment_duration)",
    )


class SpeakerInfo(BaseModel):
    """화자별 통계 정보"""

    speaker_id: str = Field(..., description="화자 ID (예: SPEAKER_00)")
    total_speaking_time: float = Field(..., description="총 발화 시간 (초)")
    segment_count: int = Field(..., ge=0, description="발화 세그먼트 수")


class DiarizationCreateRequest(BaseModel):
    """POST /api/v1/diarizations 요청 본문"""

    stt_task_id: UUID = Field(..., description="화자 분리 대상 STT 작업 ID")
    num_speakers: int | None = Field(
        default=None, ge=1, description="예상 화자 수 (None이면 자동 감지)"
    )
    min_speakers: int = Field(default=1, ge=1, description="최소 화자 수")
    max_speakers: int = Field(default=10, ge=1, description="최대 화자 수")


class DiarizationResponse(BaseModel):
    """GET /api/v1/diarizations/{task_id} 응답 (completed 상태)"""

    task_id: UUID
    stt_task_id: UUID
    status: TaskStatus
    segments: list[DiarizedSegmentResult] = Field(default_factory=list)
    speakers: list[SpeakerInfo] = Field(default_factory=list)
    num_speakers: int | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class DiarizationStatusResponse(BaseModel):
    """GET /api/v1/diarizations/{task_id}/status 응답"""

    task_id: UUID
    stt_task_id: UUID
    status: TaskStatus
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
