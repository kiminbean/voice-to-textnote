"""
전사 요청/응답 Pydantic v2 스키마
REQ-STT-002, REQ-STT-008, REQ-STT-010, REQ-STT-011 관련
"""
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class SegmentResult(BaseModel):
    """단일 전사 세그먼트 (REQ-STT-008: 세그먼트별 타임스탬프 + 신뢰도)"""
    model_config = ConfigDict(frozen=True)

    id: int
    start: float = Field(..., description="세그먼트 시작 시간 (초)")
    end: float = Field(..., description="세그먼트 종료 시간 (초)")
    text: str = Field(..., description="전사된 텍스트")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="신뢰도 점수")


class TranscriptionMetadata(BaseModel):
    """파일 메타데이터"""
    file_name: str
    file_size_bytes: int
    sample_rate: int = 16000
    processing_time_seconds: float | None = None


class TranscriptionCreate(BaseModel):
    """POST /api/v1/transcriptions 응답 (201 Created)"""
    task_id: UUID
    status: TaskStatus = TaskStatus.pending
    status_url: str
    result_url: str
    created_at: datetime


class TaskStatusResponse(BaseModel):
    """GET /api/v1/transcriptions/{task_id}/status 응답"""
    task_id: UUID
    status: TaskStatus
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class TranscriptionResponse(BaseModel):
    """GET /api/v1/transcriptions/{task_id} 응답 (completed 상태)"""
    task_id: UUID
    status: TaskStatus
    language: str | None = None
    duration: float | None = Field(default=None, description="총 재생 시간 (초)")
    model: str | None = None
    segments: list[SegmentResult] = Field(default_factory=list)
    metadata: TranscriptionMetadata | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class ValidationErrorDetail(BaseModel):
    """422 응답 내 개별 오류 상세"""
    field: str
    message: str
    type: str


class ValidationErrorResponse(BaseModel):
    """422 Unprocessable Entity 응답"""
    detail: list[ValidationErrorDetail]
