"""
SPEC-SEARCH-002: 검색 스키마 테스트

REQ-SEARCH-007: 날짜 범위 필터 (date_from, date_to)
REQ-SEARCH-008: 정렬 옵션 (sort: relevance | newest | oldest)
REQ-SEARCH-011: 화자 이름 필터 (speaker)
REQ-SEARCH-012: 액션 아이템/핵심 결정 필터 (has_action_items, has_key_decisions)
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.schemas.search import SearchRequest, SortOption


class TestSearchRequestSchema:
    """SearchRequest 스키마 확장 테스트"""

    def test_minimal_request(self):
        """최소 검색 요청 (q만 필수)"""
        request = SearchRequest(q="회의록")
        assert request.q == "회의록"
        assert request.task_type == "all"
        assert request.date_from is None
        assert request.date_to is None
        assert request.sort is None
        assert request.speaker is None
        assert request.has_action_items is None
        assert request.has_key_decisions is None

    def test_date_range_filter(self):
        """REQ-SEARCH-007: 날짜 범위 필터"""
        date_from = datetime(2026, 1, 1)
        date_to = datetime(2026, 3, 31)

        request = SearchRequest(
            q="프로젝트",
            date_from=date_from,
            date_to=date_to,
        )

        assert request.date_from == date_from
        assert request.date_to == date_to

    def test_date_from_only(self):
        """REQ-SEARCH-007: date_from만 지정"""
        date_from = datetime(2026, 2, 1)
        request = SearchRequest(q="회의", date_from=date_from)
        assert request.date_from == date_from
        assert request.date_to is None

    def test_date_to_only(self):
        """REQ-SEARCH-007: date_to만 지정"""
        date_to = datetime(2026, 3, 31)
        request = SearchRequest(q="회의", date_to=date_to)
        assert request.date_to == date_to
        assert request.date_from is None

    def test_invalid_date_format(self):
        """REQ-SEARCH-007: 유효하지 않은 날짜 형식"""
        with pytest.raises(ValidationError):
            SearchRequest(q="회의", date_from="invalid-date")

        with pytest.raises(ValidationError):
            SearchRequest(q="회의", date_to="not-a-date")

    def test_sort_relevance(self):
        """REQ-SEARCH-008: relevance 정렬"""
        request = SearchRequest(q="회의록", sort="relevance")
        assert request.sort == SortOption.RELEVANCE

    def test_sort_newest(self):
        """REQ-SEARCH-008: newest 정렬"""
        request = SearchRequest(q="회의", sort="newest")
        assert request.sort == SortOption.NEWEST

    def test_sort_oldest(self):
        """REQ-SEARCH-008: oldest 정렬"""
        request = SearchRequest(q="회의", sort="oldest")
        assert request.sort == SortOption.OLDEST

    def test_invalid_sort_value(self):
        """REQ-SEARCH-008: 유효하지 않은 sort 값"""
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(q="회의", sort="invalid")

        errors = exc_info.value.errors()
        assert any("sort" in str(err.get("loc", [])) for err in errors)

    def test_speaker_filter(self):
        """REQ-SEARCH-011: 화자 이름 필터"""
        request = SearchRequest(q="회의", speaker="김팀장")
        assert request.speaker == "김팀장"

    def test_has_action_items_true(self):
        """REQ-SEARCH-012: has_action_items 필터"""
        request = SearchRequest(q="프로젝트", has_action_items=True)
        assert request.has_action_items is True

    def test_has_action_items_false(self):
        """REQ-SEARCH-012: has_action_items=false (no-op)"""
        request = SearchRequest(q="프로젝트", has_action_items=False)
        assert request.has_action_items is False

    def test_has_key_decisions_true(self):
        """REQ-SEARCH-012: has_key_decisions 필터"""
        request = SearchRequest(q="결정", has_key_decisions=True)
        assert request.has_key_decisions is True

    def test_combined_filters(self):
        """REQ-SEARCH-012: 복합 필터 조합"""
        date_from = datetime(2026, 1, 1)
        request = SearchRequest(
            q="회의",
            task_type="summary",
            date_from=date_from,
            sort="newest",
            speaker="김팀장",
            has_action_items=True,
            has_key_decisions=True,
        )

        assert request.q == "회의"
        assert request.task_type == "summary"
        assert request.date_from == date_from
        assert request.sort == SortOption.NEWEST
        assert request.speaker == "김팀장"
        assert request.has_action_items is True
        assert request.has_key_decisions is True


class TestSearchResponseSchema:
    """SearchResponse 스키마 확장 테스트"""

    def test_response_with_sort_field(self):
        """REQ-SEARCH-008: 응답에 sort 필드 포함"""
        from backend.schemas.search import SearchResponse, SearchResultItem

        items = [
            SearchResultItem(
                task_id="task-1",
                task_type="minutes",
                snippet="<b>회의록</b> 내용...",
                created_at=datetime(2026, 3, 15),
            )
        ]

        response = SearchResponse(
            items=items,
            total=1,
            page=1,
            page_size=20,
            query="회의록",
            sort="relevance",
        )

        assert response.sort == "relevance"

    def test_response_without_sort_field(self):
        """REQ-SEARCH-008: sort 미지정 시 응답에 null 포함"""
        from backend.schemas.search import SearchResponse, SearchResultItem

        items = [
            SearchResultItem(
                task_id="task-1",
                task_type="minutes",
                snippet="<b>회의</b> 내용...",
                created_at=datetime(2026, 3, 15),
            )
        ]

        response = SearchResponse(
            items=items,
            total=1,
            page=1,
            page_size=20,
            query="회의",
            sort=None,
        )

        assert response.sort is None
