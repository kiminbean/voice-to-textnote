"""
SPEC-SEARCH-001: 검색 API 응답 스키마

REQ-SEARCH-001: 검색 결과 목록 응답 {items, total, page, page_size, query}
REQ-SEARCH-002: 검색 결과 항목 {task_id, task_type, snippet, created_at, completed_at}
"""

from datetime import datetime

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    """
    검색 결과 항목 스키마

    FTS5 snippet 함수로 생성된 컨텍스트 스니펫을 포함합니다.
    """

    task_id: str
    task_type: str
    snippet: str
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    """
    검색 API 응답 스키마

    FTS5 전문 검색 결과를 페이지네이션 형태로 반환합니다.
    """

    items: list[SearchResultItem]
    total: int
    page: int
    page_size: int
    query: str
