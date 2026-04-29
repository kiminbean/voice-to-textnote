"""
SPEC-SPEAKER-001: 화자 프로필 Pydantic 스키마
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


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
