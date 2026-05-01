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
