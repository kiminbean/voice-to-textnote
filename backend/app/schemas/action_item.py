"""
액션 아이템 관련 스키마
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ActionItemStatus(StrEnum):
    """액션 아이템 상태"""

    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class ActionItemPriority(StrEnum):
    """액션 아이템 우선순위"""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ActionItemCreate(BaseModel):
    """액션 아이템 생성 요청"""

    title: str = Field(..., min_length=1, max_length=200, description="액션 아이템 제목")
    description: str | None = Field(default=None, max_length=2000, description="상세 설명")
    assignee_id: uuid.UUID | None = Field(default=None, description="담당자 ID")
    priority: ActionItemPriority = Field(default=ActionItemPriority.medium, description="우선순위")
    due_date: datetime | None = Field(default=None, description="마감일")
    meeting_id: str | None = Field(default=None, description="관련 회의 ID")
    tags: list[str] = Field(default_factory=list, description="태그 목록")
    estimated_hours: float | None = Field(
        default=None, ge=0, le=1000, description="예상 소요 시간(시간)"
    )
    category: str | None = Field(default=None, max_length=50, description="카테고리")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        """제목 공백 제거"""
        return v.strip()


class ActionItemUpdate(BaseModel):
    """액션 아이템 수정 요청"""

    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="액션 아이템 제목"
    )
    description: str | None = Field(default=None, max_length=2000, description="상세 설명")
    assignee_id: uuid.UUID | None = Field(default=None, description="담당자 ID")
    priority: ActionItemPriority | None = Field(default=None, description="우선순위")
    status: ActionItemStatus | None = Field(default=None, description="상태")
    due_date: datetime | None = Field(default=None, description="마감일")
    completed_at: datetime | None = Field(default=None, description="완료일")
    completed_by: uuid.UUID | None = Field(default=None, description="완료자 ID")
    completion_notes: str | None = Field(default=None, max_length=1000, description="완료 메모")
    estimated_hours: float | None = Field(default=None, ge=0, le=1000, description="예상 소요 시간")
    actual_hours: float | None = Field(default=None, ge=0, le=1000, description="실제 소요 시간")
    tags: list[str] | None = Field(default=None, description="태그 목록")
    category: str | None = Field(default=None, max_length=50, description="카테고리")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        """제목 공백 제거 (None이 아닐 경우)"""
        if v is not None:
            return v.strip()
        return v

    @field_validator("completion_notes")
    @classmethod
    def validate_completion_notes(cls, v):
        """완료 메모 공백 제거 (None이 아닐 경우)"""
        if v is not None:
            return v.strip()
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """태그 중복 제거"""
        if v is not None:
            # 중복 제거 및 정렬
            return list(set(tag.strip() for tag in v if tag.strip()))
        return v


class ActionItemResponse(BaseModel):
    """액션 아이템 응답"""

    id: uuid.UUID
    title: str
    description: str | None
    status: ActionItemStatus
    priority: ActionItemPriority
    assignee_id: uuid.UUID | None
    assignee_name: str | None
    created_by: uuid.UUID
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    due_date: datetime | None
    completed_at: datetime | None
    completed_by: uuid.UUID | None
    completed_by_name: str | None
    completion_notes: str | None
    meeting_id: str | None
    meeting_title: str | None
    tags: list[str]
    estimated_hours: float | None
    actual_hours: float | None
    category: str | None
    is_overdue: bool
    time_remaining_hours: float | None
    progress_percentage: float

    class Config:
        from_attributes = True


class ActionItemFilter(BaseModel):
    """액션 아이템 필터"""

    status: ActionItemStatus | None = None
    priority: ActionItemPriority | None = None
    assignee_id: uuid.UUID | None = None
    meeting_id: str | None = None
    due_from: datetime | None = None
    due_to: datetime | None = None
    is_overdue: bool | None = None
    category: str | None = None
    tags: list[str] | None = None


class ActionItemListResponse(BaseModel):
    """액션 아이템 목록 응답"""

    items: list[ActionItemResponse]
    total: int
    page: int
    page_size: int


class ActionItemOverview(BaseModel):
    """액션 아이템 개요"""

    total_count: int
    pending_count: int
    in_progress_count: int
    completed_count: int
    cancelled_count: int
    overdue_count: int
    critical_count: int
    high_priority_count: int
    by_category: dict[str, int]
    by_assignee: dict[str, int]
    completion_rate: float
    overdue_rate: float
    avg_estimated_hours: float | None
    avg_actual_hours: float | None
    efficiency_ratio: float | None  # actual/estimated ratio
    trending_status: Literal["improving", "declining", "stable"]
    weekly_completion_trend: list[dict]
    productivity_metrics: dict[str, float]


class ActionItemBulkUpdate(BaseModel):
    """액션 아이템 배치 업데이트 요청"""

    item_ids: list[uuid.UUID] = Field(
        ..., min_length=1, max_length=100, description="업데이트할 아이템 ID 목록"
    )
    update_data: ActionItemUpdate = Field(..., description="업데이트 데이터")


class ActionItemComment(BaseModel):
    """액션 아이템 댓글"""

    id: uuid.UUID
    action_item_id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    content: str
    created_at: datetime
    updated_at: datetime
    is_internal: bool

    class Config:
        from_attributes = True


class ActionItemCommentCreate(BaseModel):
    """액션 아이템 댓글 생성 요청"""

    content: str = Field(..., min_length=1, max_length=1000, description="댓글 내용")
    is_internal: bool = Field(default=False, description="내부 댓글 여부")


class ActionItemCommentResponse(BaseModel):
    """액션 아이템 댓글 응답"""

    id: uuid.UUID
    action_item_id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    content: str
    created_at: datetime
    updated_at: datetime
    is_internal: bool

    class Config:
        from_attributes = True


class ActionItemHistory(BaseModel):
    """액션 아이템 변경 이력"""

    id: uuid.UUID
    action_item_id: uuid.UUID
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_by: uuid.UUID
    changed_by_name: str
    changed_at: datetime
    change_type: Literal["create", "update", "status_change", "complete", "cancel"]

    class Config:
        from_attributes = True


class ActionItemReminder(BaseModel):
    """액션 아이템 알림 설정"""

    id: uuid.UUID
    action_item_id: uuid.UUID
    reminder_type: Literal["before_due", "overdue", "daily"]
    reminder_time: datetime
    is_active: bool
    last_sent_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
