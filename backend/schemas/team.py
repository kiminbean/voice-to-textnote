"""
SPEC-TEAM-001: 팀 관리 Pydantic 스키마

REQ-TEAM-001: TeamCreateRequest
REQ-TEAM-002: TeamListResponse
REQ-TEAM-003: TeamDetailResponse (멤버 포함)
REQ-TEAM-004: TeamUpdateRequest
"""

from datetime import datetime

from pydantic import BaseModel, Field


class TeamCreateRequest(BaseModel):
    """팀 생성 요청 스키마"""

    name: str = Field(min_length=1, max_length=200, description="팀 이름")
    description: str | None = Field(default=None, description="팀 설명")


class TeamUpdateRequest(BaseModel):
    """팀 수정 요청 스키마 (부분 업데이트 지원)"""

    name: str | None = Field(default=None, min_length=1, max_length=200, description="팀 이름")
    description: str | None = Field(default=None, description="팀 설명")


class TeamMemberResponse(BaseModel):
    """팀 멤버 응답 스키마"""

    user_id: str
    email: str
    display_name: str
    role: str
    joined_at: datetime


class TeamResponse(BaseModel):
    """팀 응답 스키마 (목록용)"""

    id: str
    name: str
    description: str | None
    created_by: str
    created_at: datetime
    member_count: int


class TeamListResponse(BaseModel):
    """팀 목록 응답 스키마"""

    items: list[TeamResponse]
    total: int


class TeamDetailResponse(TeamResponse):
    """팀 상세 응답 스키마 (멤버 목록 포함)"""

    members: list[TeamMemberResponse]
