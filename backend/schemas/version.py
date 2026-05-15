"""
회의록 버전 관리 Pydantic v2 스키마
SPEC-VERSION-001
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class VersionCreate(BaseModel):
    """POST /api/v1/minutes/{task_id}/versions 요청"""

    content: dict[str, Any] = Field(..., description="회의록 전체 내용 스냅샷 (JSON)")
    change_summary: str | None = Field(
        default=None, max_length=500, description="변경 요약 메모 (선택)"
    )


class VersionResponse(BaseModel):
    """버전 단건 응답"""

    id: UUID
    task_id: str
    version_number: int
    content: dict[str, Any]
    change_summary: str | None
    author_id: UUID | None
    created_at: datetime


class VersionListResponse(BaseModel):
    """버전 목록 응답"""

    total: int
    items: list[VersionResponse]


class VersionDiffResponse(BaseModel):
    """두 버전 간 텍스트 diff 응답"""

    from_version: int
    to_version: int
    unified_diff: str
    added_lines: int
    removed_lines: int
    changed: bool


# ---------------------------------------------------------------------------
# SPEC-VERSION-002: 구조화 diff (회의록 JSON 항목 단위 비교)
# ---------------------------------------------------------------------------


class TextDiff(BaseModel):
    """단일 텍스트 필드의 변경 표현."""

    changed: bool
    before: str | None = None
    after: str | None = None


class SectionDiffItem(BaseModel):
    """sections 배열 한 항목의 diff 표현."""

    title: str
    before_content: str | None = None
    after_content: str | None = None


class ActionItemDiff(BaseModel):
    """action_items 배열 한 항목의 diff 표현."""

    key: str = Field(..., description="매칭에 사용된 식별자 (id 또는 text 해시)")
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


class SectionsDiff(BaseModel):
    added: list[SectionDiffItem] = Field(default_factory=list)
    removed: list[SectionDiffItem] = Field(default_factory=list)
    modified: list[SectionDiffItem] = Field(default_factory=list)


class ActionItemsDiff(BaseModel):
    added: list[ActionItemDiff] = Field(default_factory=list)
    removed: list[ActionItemDiff] = Field(default_factory=list)
    modified: list[ActionItemDiff] = Field(default_factory=list)


class StructuredDiffResponse(BaseModel):
    """JSON 구조 기반 회의록 diff 응답."""

    from_version: int
    to_version: int
    summary_text: TextDiff
    sections: SectionsDiff
    action_items: ActionItemsDiff
    total_changes: int
    changed: bool
