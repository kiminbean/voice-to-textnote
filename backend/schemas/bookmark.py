"""
SPEC-BOOKMARK-001: 북마크/하이라이트 Pydantic 스키마
"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# #RRGGBB 또는 짧은 색 이름 (red, blue, #fff 등) 허용
_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{3,8}$|^[a-zA-Z]{3,20}$")


class BookmarkBase(BaseModel):
    """북마크 공통 필드."""

    segment_start: float = Field(..., ge=0, description="구간 시작 (초)")
    segment_end: float = Field(..., gt=0, description="구간 종료 (초, start 초과)")
    text_snippet: str | None = Field(default=None, max_length=10_000)
    note: str | None = Field(default=None)
    color: str | None = Field(default=None, max_length=20)

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


class BookmarkCreate(BookmarkBase):
    """북마크 생성 요청. task_id는 URL 경로가 아닌 body에서 받음."""

    task_id: str = Field(..., min_length=1, max_length=255)


class BookmarkUpdate(BaseModel):
    """북마크 부분 수정 (PATCH)."""

    segment_start: float | None = Field(default=None, ge=0)
    segment_end: float | None = Field(default=None, gt=0)
    text_snippet: str | None = Field(default=None, max_length=10_000)
    note: str | None = None
    color: str | None = Field(default=None, max_length=20)

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
    created_at: datetime
    updated_at: datetime


class BookmarkListResponse(BaseModel):
    """북마크 목록 응답."""

    items: list[BookmarkResponse]
    total: int
