"""
배치 전사 요청/응답 Pydantic v2 스키마
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from backend.schemas.transcription import TaskStatus


class BatchItemResult(BaseModel):
    """배치 내 개별 파일 처리 결과"""

    task_id: UUID | None = None
    filename: str
    status: TaskStatus
    status_url: str | None = None
    result_url: str | None = None
    error: str | None = None


class BatchTranscriptionCreate(BaseModel):
    """POST /api/v1/transcriptions/batch 응답 (201 Created)"""

    batch_id: UUID
    total: int = Field(..., ge=1, description="제출된 파일 수")
    accepted: int = Field(..., ge=0, description="수락된 파일 수")
    items: list[BatchItemResult]
    created_at: datetime


class BatchStatusResponse(BaseModel):
    """GET /api/v1/transcriptions/batch/{batch_id} 응답"""

    batch_id: UUID
    total: int
    pending: int
    processing: int
    completed: int
    failed: int
    items: list[BatchItemResult]
