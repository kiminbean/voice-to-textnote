"""
SPEC-HISTORY-001: History API 응답 스키마

REQ-HIST-004: 목록 응답 {items, total, page, page_size}
REQ-HIST-005: 상세 응답에 result_data, input_metadata 포함
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HistoryItem(BaseModel):
    """
    작업 이력 목록 항목 스키마

    목록 조회에서 result_data를 제외하여 응답 크기를 최소화합니다.
    """

    task_id: str
    task_type: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    shared_team_ids: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class HistoryDetailItem(HistoryItem):
    """
    작업 이력 상세 항목 스키마

    REQ-HIST-005: 상세 조회에는 result_data, input_metadata를 포함합니다.
    """

    result_data: dict[str, Any] | None = None
    input_metadata: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class HistoryListResponse(BaseModel):
    """
    REQ-HIST-004: 페이지네이션 목록 응답 스키마

    items: 현재 페이지의 작업 이력 목록
    total: 필터 조건에 해당하는 전체 레코드 수
    page: 현재 페이지 번호 (1부터 시작)
    page_size: 페이지당 항목 수
    """

    items: list[HistoryItem]
    total: int
    page: int
    page_size: int
