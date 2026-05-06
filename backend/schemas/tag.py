"""
SPEC-TAG-001: 회의록 태그 스키마
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    """태그 생성 요청."""

    task_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="대상 회의록 task_id",
    )
    tag_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="태그 종류 (topic, category, priority, custom)",
    )
    tag_value: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="태그 값",
    )
    source: str | None = Field(
        default="manual",
        max_length=20,
        description="생성 방식 (auto, manual)",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="AI 신뢰도 (0.0~1.0)",
    )
    note: str | None = Field(
        default=None,
        max_length=2000,
        description="메모",
    )


class TagUpdate(BaseModel):
    """태그 수정 요청."""

    tag_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    tag_value: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    note: str | None = Field(
        default=None,
        max_length=2000,
    )


class TagResponse(BaseModel):
    """태그 응답."""

    id: uuid.UUID
    task_id: str
    tag_type: str
    tag_value: str
    source: str
    confidence: float | None
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TagListResponse(BaseModel):
    """태그 목록 응답."""

    items: list[TagResponse]
    total: int
    task_id: str


class AutoTagRequest(BaseModel):
    """자동 태깅 요청."""

    task_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="자동 태깅할 회의록 task_id",
    )
    content: str = Field(
        ...,
        min_length=10,
        description="태깅할 텍스트 내용 (회의록 본문)",
    )
    max_tags: int = Field(
        default=10,
        ge=1,
        le=30,
        description="최대 태그 개수",
    )


class AutoTagResponse(BaseModel):
    """자동 태깅 결과 응답."""

    task_id: str
    tags: list[TagResponse]
    total: int
