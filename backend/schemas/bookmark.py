"""
SPEC-BOOKMARK-001: 북마크/하이라이트 Pydantic 스키마
"""

import re
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# #RRGGBB 또는 짧은 색 이름 (red, blue, #fff 등) 허용
_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{3,8}$|^[a-zA-Z]{3,20}$")


class BookmarkCategory(StrEnum):
    """북마크 카테고리"""
    IMPORTANT = "important"  # 중요
    ACTION = "action"        # 액션 아이템
    DECISION = "decision"    # 결정 사항
    QUESTION = "question"    # 질문
    SUMMARY = "summary"      # 핵심 요약
    FOLLOW_UP = "follow_up"  # 후속 조치
    NOTE = "note"           # 참고 사항
    CUSTOM = "custom"       # 사용자 정의


class BookmarkPriority(StrEnum):
    """북마크 우선순위"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class BookmarkBase(BaseModel):
    """북마크 공통 필드."""

    segment_start: float = Field(..., ge=0, description="구간 시작 (초)")
    segment_end: float = Field(..., gt=0, description="구간 종료 (초, start 초과)")
    text_snippet: str | None = Field(default=None, max_length=10_000)
    note: str | None = Field(default=None)
    color: str | None = Field(default=None, max_length=20)
    category: BookmarkCategory = Field(default=BookmarkCategory.NOTE)
    priority: BookmarkPriority = Field(default=BookmarkPriority.MEDIUM)
    tags: list[str] = Field(default_factory=list, max_length=20)
    is_private: bool = Field(default=True)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not _COLOR_PATTERN.match(v):
            raise ValueError(
                "color 는 #RRGGBB 형식 또는 3~20자 알파벳 색상명이어야 합니다"
            )
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """태그 검증: 공백 제거, 중복 제거, 길이 제한"""
        if not v:
            return []
        validated = []
        seen = set()
        for tag in v:
            if tag in seen:
                continue
            tag = tag.strip()
            if tag and len(tag) <= 30:  # 태그당 최대 30자
                validated.append(tag)
                seen.add(tag)
        return validated


class BookmarkCreate(BookmarkBase):
    """북마크 생성 요청."""

    task_id: str = Field(..., min_length=1, max_length=255)


class BookmarkUpdate(BaseModel):
    """북마크 부분 수정 (PATCH)."""

    segment_start: float | None = Field(default=None, ge=0)
    segment_end: float | None = Field(default=None, gt=0)
    text_snippet: str | None = Field(default=None, max_length=10_000)
    note: str | None = None
    color: str | None = Field(default=None, max_length=20)
    category: BookmarkCategory | None = None
    priority: BookmarkPriority | None = None
    tags: list[str] | None = None
    is_private: bool | None = None

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not _COLOR_PATTERN.match(v):
            raise ValueError(
                "color 는 #RRGGBB 형식 또는 3~20자 알파벳 색상명이어야 합니다"
            )
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        validated = []
        seen = set()
        for tag in v:
            if tag in seen:
                continue
            tag = tag.strip()
            if tag and len(tag) <= 30:
                validated.append(tag)
                seen.add(tag)
        return validated


class BookmarkResponse(BaseModel):
    """북마크 응답 모델."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    task_id: str
    segment_start: float
    segment_end: float
    text_snippet: str | None
    note: str | None
    color: str | None
    category: BookmarkCategory
    priority: BookmarkPriority
    tags: list[str]
    is_private: bool
    created_at: datetime
    updated_at: datetime


class BookmarkListResponse(BaseModel):
    """북마크 목록 응답."""

    items: list[BookmarkResponse]
    total: int


class BookmarkBulkOperation(BaseModel):
    """북마크 대량 작업."""

    operation: str = Field(..., description="수행할 작업: 'delete', 'update_category', 'update_priority'")
    bookmark_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)
    data: dict[str, Any] | None = Field(default=None, description="작업 데이터 (예: {'category': 'important'})")


class BookmarkBulkResponse(BaseModel):
    """대량 작업 응답."""

    processed_count: int
    failed_count: int
    errors: list[dict[str, Any]] = Field(default_factory=list)


class BookmarkSummaryResponse(BaseModel):
    """북마크 요약 정보."""

    total_count: int
    category_counts: dict[BookmarkCategory, int] = Field(default_factory=dict)
    priority_counts: dict[BookmarkPriority, int] = Field(default_factory=dict)
    tag_counts: dict[str, int] = Field(default_factory=dict)
    recent_bookmarks: list[BookmarkResponse] = Field(default_factory=list)


class BookmarkSearchRequest(BaseModel):
    """북마크 검색 요청."""

    query: str | None = Field(default=None, max_length=100, description="검색어")
    category: BookmarkCategory | None = Field(default=None)
    priority: BookmarkPriority | None = Field(default=None)
    tags: list[str] | None = Field(default=None)
    task_id: str | None = Field(default=None)
    date_from: datetime | None = Field(default=None)
    date_to: datetime | None = Field(default=None)
    has_tags: bool | None = Field(default=None, description="태그가 있는 북마크만")
    is_private: bool | None = Field(default=None)

    # 페이징 정보
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)

    # 정렬 옵션
    sort_by: str = Field(default="created_at", description="정렬 기준: created_at, priority, category")
    sort_order: str = Field(default="desc", description="정렬 순서: asc, desc")


class BookmarkSearchResponse(BaseModel):
    """북마크 검색 응답."""

    items: list[BookmarkResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class BookmarkCleanupRequest(BaseModel):
    """북마크 정리 요청."""

    older_than_days: int = Field(default=30, ge=1, le=365, description="지정일 이전 북마크 정리")
    category: BookmarkCategory | None = Field(default=None, description="특정 카테고리만 정리")
    priority: BookmarkPriority | None = Field(default=None, description="특정 우선순위만 정리")
    tags: list[str] | None = Field(default=None, description="특정 태그를 가진 북마크만 정리")
    dry_run: bool = Field(default=True, description="실제 삭제 없이 예제 표시")

    # 조건 추가
    duplicates_only: bool = Field(default=False, description="중복된 북마크만 정리")
    empty_only: bool = Field(default=False, description="내용이 없는 북마크만 정리")


class BookmarkCleanupResponse(BaseModel):
    """북마크 정리 응답."""

    total_count: int
    deleted_count: int = 0
    archived_count: int = 0  # 삭제 대신 아카이빙
    duplicate_count: int = 0
    empty_count: int = 0
    categories: dict[BookmarkCategory, int] = Field(default_factory=dict)
    preview: list[BookmarkResponse] = Field(default_factory=list)
