"""
SPEC-SEARCH-001/002: 검색 API 스키마

REQ-SEARCH-001: 검색 결과 목록 응답 {items, total, page, page_size, query}
REQ-SEARCH-002: 검색 결과 항목 {task_id, task_type, snippet, created_at, completed_at}
REQ-SEARCH-007: 날짜 범위 필터 (date_from, date_to)
REQ-SEARCH-008: 정렬 옵션 (sort: relevance | newest | oldest)
REQ-SEARCH-011: 화자 이름 필터 (speaker)
REQ-SEARCH-012: 액션 아이템/핵심 결정 필터 (has_action_items, has_key_decisions)
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, field_validator


class SortOption(StrEnum):
    """정렬 옵션 (REQ-SEARCH-008)"""

    RELEVANCE = "relevance"  # FTS5 rank 기준 (bm25)
    NEWEST = "newest"  # created_at DESC
    OLDEST = "oldest"  # created_at ASC


class SearchRequest(BaseModel):
    """
    검색 요청 스키마 (SPEC-SEARCH-002)

    기존 쿼리 파라미터와 새로운 필터/정렬 옵션을 포함합니다.
    """

    q: str  # 검색 쿼리 (필수, 최소 2자)
    task_type: str = "all"  # 작업 유형 필터 (all, minutes, summary)
    page: int = 1  # 페이지 번호
    page_size: int = 20  # 페이지당 항목 수

    # REQ-SEARCH-007: 날짜 범위 필터
    date_from: datetime | None = None  # 시작 날짜 (ISO 8601)
    date_to: datetime | None = None  # 종료 날짜 (ISO 8601)

    # REQ-SEARCH-008: 정렬 옵션
    sort: SortOption | None = None  # 정렬 기준 (relevance, newest, oldest)

    # REQ-SEARCH-011: 화자 이름 필터
    speaker: str | None = None  # 화자 이름 문자열

    # REQ-SEARCH-012: 상세 필터
    has_action_items: bool | None = None  # 액션 아이템 존재 여부
    has_key_decisions: bool | None = None  # 핵심 결정 존재 여부

    @field_validator("q")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """검색 쿼리 검증 (공백 제거 후 최소 2자)"""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("검색 쿼리는 최소 2자 이상이어야 합니다.")
        return v


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
    sort: SortOption | None = None  # REQ-SEARCH-008: 적용된 정렬 옵션
