"""
SPEC-TEAM-001 REQ-TEAM-005: 회의록 공유 API 스키마
"""

from datetime import datetime

from pydantic import BaseModel, Field


class MeetingShareRequest(BaseModel):
    """회의록 팀 공유 요청 스키마"""

    team_id: str = Field(description="공유할 팀 ID (UUID 문자열)")


class MeetingShareResponse(BaseModel):
    """회의록 팀 공유 응답 스키마"""

    task_id: str
    team_id: str
    shared_at: datetime


class MeetingOwnershipResponse(BaseModel):
    """
    회의록 소유권 항목 응답 스키마

    task_results 테이블과 JOIN하여 task_type, status를 포함합니다.
    """

    task_id: str
    task_type: str | None = None
    status: str | None = None
    owner_id: str
    team_id: str | None = None
    shared_at: datetime | None = None
    created_at: datetime


class MeetingListResponse(BaseModel):
    """페이지네이션 회의록 목록 응답 스키마"""

    items: list[MeetingOwnershipResponse]
    total: int
    page: int
    page_size: int
