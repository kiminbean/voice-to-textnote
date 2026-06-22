"""
화자 그룹 관리 Schema
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SpeakerGroupBase(BaseModel):
    """화자 그룁 기본 스키마"""

    name: str = Field(..., min_length=1, max_length=100, description="그룹 이름")
    description: str | None = Field(None, description="그룹 설명")
    color: str | None = Field(
        None,
        description="HEX 색상 코드 (예: #FF5733)",
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )


class SpeakerGroupCreate(SpeakerGroupBase):
    """화자 그룁 생성 스키마"""
    pass


class SpeakerGroupUpdate(BaseModel):
    """화자 그룁 수정 스키마"""

    name: str | None = Field(None, min_length=1, max_length=100, description="그룹 이름")
    description: str | None = Field(None, description="그룹 설명")
    color: str | None = Field(
        None,
        description="HEX 색상 코드 (예: #FF5733)",
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )


class SpeakerGroupResponse(SpeakerGroupBase):
    """화자 그룁 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class SpeakerGroupMemberBase(BaseModel):
    """화자 그룹 멤버 기본 스키마"""

    speaker_id: uuid.UUID
    joined_at: datetime


class SpeakerGroupMemberResponse(SpeakerGroupMemberBase):
    """화자 그룁 멤버 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    speaker: dict | None = None  # SpeakerProfile 간단한 정보


class SpeakerGroupWithMembersResponse(SpeakerGroupResponse):
    """화자 그룁 상세 응답 (멤버 포함)"""

    model_config = ConfigDict(from_attributes=True)

    members: list[SpeakerGroupMemberResponse] = Field(default_factory=list)


class SpeakerGroupListResponse(BaseModel):
    """화자 그룁 목록 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    items: list[SpeakerGroupResponse]
    total: int
