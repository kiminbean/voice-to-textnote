"""
고급 검색 API 스키마
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SearchFilter(BaseModel):
    """검색 필터 조건"""
    start_date: datetime | None = Field(
        default=None,
        description="검색 시작 일시 (UTC)"
    )
    end_date: datetime | None = Field(
        default=None,
        description="검색 종료 일시 (UTC)"
    )
    speaker_ids: list[str] | None = Field(
        default=None,
        description="화자 ID 목록 (필터링)"
    )
    content_types: list[str] | None = Field(
        default=None,
        description="콘텐츠 유형 필터 (minutes, summary)"
    )
    min_word_count: int | None = Field(
        default=None,
        description="최소 단어 수"
    )
    max_word_count: int | None = Field(
        default=None,
        description="최대 단어 수"
    )
    tags: list[str] | None = Field(
        default=None,
        description="태그 필터"
    )


class AdvancedSearchRequest(BaseModel):
    """고급 검색 요청"""
    query: str = Field(..., min_length=2, description="검색 쿼리")
    filters: SearchFilter = Field(default_factory=SearchFilter)
    sort_by: str = Field(
        default="relevance",
        description="정렬 기준 (relevance, date, speaker, word_count)"
    )
    sort_order: str = Field(
        default="desc",
        description="정렬 순서 (asc, desc)"
    )
    page: int = Field(default=1, ge=1, description="페이지 번호")
    page_size: int = Field(default=20, ge=1, le=100, description="페이지당 항목 수")


class SearchResultItem(BaseModel):
    """검색 결과 항목"""
    id: str = Field(..., description="고유 ID")
    task_id: str = Field(..., description="태스크 ID")
    title: str = Field(..., description="제목")
    content: str = Field(..., description="내용 요약")
    content_type: str = Field(..., description="콘텐츠 유형 (minutes, summary)")
    speaker_ids: list[str] = Field(..., description="화자 ID 목록")
    word_count: int = Field(..., description="단어 수")
    tags: list[str] = Field(..., description="태그 목록")
    created_at: datetime = Field(..., description="생성 시간")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="관련도 점수")
    highlights: list[str] = Field(..., description="검색 결과 하이라이트")


class SearchAnalytics(BaseModel):
    """검색 분석 결과"""
    total_results: int = Field(..., description="총 검색 결과 수")
    search_time_ms: float = Field(..., description="검색 소요 시간 (ms)")
    distribution_by_type: dict[str, int] = Field(..., description="콘텐츠 유형별 분포")
    distribution_by_speaker: dict[str, int] = Field(..., description="화자별 분포")
    popular_tags: list[dict[str, Any]] = Field(..., description="인기 태그")
    average_word_count: float = Field(..., description="평균 단어 수")
    search_trends: list[dict[str, Any]] = Field(..., description="검색 트렌드")


class AdvancedSearchResponse(BaseModel):
    """고급 검색 응답"""
    results: list[SearchResultItem] = Field(..., description="검색 결과")
    pagination: dict[str, Any] = Field(..., description="페이지네이션 정보")
    analytics: SearchAnalytics = Field(..., description="검색 분석")
    query_info: dict[str, Any] = Field(..., description="검색 쿼리 정보")


class SearchHistoryItem(BaseModel):
    """검색 기록 항목"""
    id: str = Field(..., description="검색 기록 ID")
    query: str = Field(..., description="검색 쿼리")
    filters: SearchFilter | None = Field(None, description="사용된 필터")
    result_count: int = Field(..., description="검색 결과 수")
    search_time_ms: float = Field(..., description="검색 소요 시간")
    created_at: datetime = Field(..., description="검색 시간")
    is_saved: bool = Field(default=False, description="저장된 검색 여부")


class SavedSearch(BaseModel):
    """저장된 검색"""
    id: str = Field(..., description="저장된 검색 ID")
    name: str = Field(..., description="검색 이름")
    query: str = Field(..., description="검색 쿼리")
    filters: SearchFilter = Field(..., description="검색 필터")
    created_at: datetime = Field(..., description="생성 시간")
    last_used_at: datetime | None = Field(None, description="마지막 사용 시간")
    usage_count: int = Field(default=0, description="사용 횟수")


class SearchHistoryResponse(BaseModel):
    """검색 기록 응답"""
    history: list[SearchHistoryItem] = Field(..., description="검색 기록")
    saved_searches: list[SavedSearch] = Field(..., description="저장된 검색")
