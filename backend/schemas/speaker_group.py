"""
화자 그룹 관리 Schema
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import Field


class SpeakerGroupBase:
    """화자 그룁 기본 스키마"""
    name: str = Field(..., min_length=1, max_length=100, description="그룹 이름")
    description: Optional[str] = Field(None, description="그룹 설명")
    color: Optional[str] = Field(
        None, 
        description="HEX 색상 코드 (예: #FF5733)",
        regex=r"^#[0-9A-Fa-f]{6}$"
    )


class SpeakerGroupCreate(SpeakerGroupBase):
    """화자 그룁 생성 스키마"""
    pass


class SpeakerGroupUpdate(SpeakerGroupBase):
    """화자 그룁 수정 스키마"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="그룹 이름")
    description: Optional[str] = Field(None, description="그룹 설명")
    color: Optional[str] = Field(
        None, 
        description="HEX 색상 코드 (예: #FF5733)",
        regex=r"^#[0-9A-Fa-f]{6}$"
    )


class SpeakerGroupResponse(SpeakerGroupBase):
    """화자 그룁 응답 스키마"""
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SpeakerGroupMemberBase:
    """화자 그룹 멤버 기본 스키마"""
    speaker_id: uuid.UUID
    joined_at: datetime


class SpeakerGroupMemberResponse(SpeakerGroupMemberBase):
    """화자 그룁 멤버 응답 스키마"""
    id: uuid.UUID
    group_id: uuid.UUID
    speaker: Optional[dict] = None  # SpeakerProfile 간단한 정보
    
    class Config:
        from_attributes = True


class SpeakerGroupWithMembersResponse(SpeakerGroupResponse):
    """화자 그룁 상세 응답 (멤버 포함)"""
    members: list[SpeakerGroupMemberResponse] = []
    
    class Config:
        from_attributes = True


class SpeakerGroupListResponse:
    """화자 그룁 목록 응답 스키마"""
    items: list[SpeakerGroupResponse]
    total: int
    
    class Config:
        from_attributes = True