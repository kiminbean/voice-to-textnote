"""
확장된 북마크 스키마/계약 테스트.

DB 통합 동작은 test_bookmarks_api.py와 test_bookmarks_coverage.py에서 검증하고,
이 파일은 확장 요청/응답 모델의 검증 규칙을 빠른 단위 테스트로 고정한다.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from backend.schemas.bookmark import (
    BookmarkBulkOperation,
    BookmarkCategory,
    BookmarkCleanupRequest,
    BookmarkPriority,
    BookmarkResponse,
    BookmarkSearchRequest,
    BookmarkSummaryResponse,
)


def _bookmark_response(
    *,
    category: BookmarkCategory = BookmarkCategory.NOTE,
    priority: BookmarkPriority = BookmarkPriority.MEDIUM,
    tags: list[str] | None = None,
) -> BookmarkResponse:
    now = datetime.now()
    return BookmarkResponse(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        task_id="task-001",
        segment_start=0,
        segment_end=30,
        text_snippet="중요한 회의 내용",
        note="후속 확인 필요",
        color="blue",
        category=category,
        priority=priority,
        tags=tags or [],
        is_private=True,
        created_at=now,
        updated_at=now,
    )


class TestEnhancedBookmarkSchemas:
    def test_bulk_operation_requires_at_least_one_bookmark_id(self):
        with pytest.raises(ValidationError):
            BookmarkBulkOperation(operation="delete", bookmark_ids=[])

    def test_bulk_operation_accepts_category_update_payload(self):
        bookmark_id = uuid.uuid4()

        operation = BookmarkBulkOperation(
            operation="update_category",
            bookmark_ids=[bookmark_id],
            data={"category": BookmarkCategory.IMPORTANT.value},
        )

        assert operation.bookmark_ids == [bookmark_id]
        assert operation.data == {"category": "important"}

    def test_summary_response_keeps_counts_and_recent_bookmarks(self):
        recent = [
            _bookmark_response(
                category=BookmarkCategory.IMPORTANT,
                priority=BookmarkPriority.HIGH,
                tags=["common", "urgent"],
            ),
            _bookmark_response(tags=["common"]),
        ]

        summary = BookmarkSummaryResponse(
            total_count=2,
            category_counts={
                BookmarkCategory.IMPORTANT: 1,
                BookmarkCategory.NOTE: 1,
            },
            priority_counts={
                BookmarkPriority.HIGH: 1,
                BookmarkPriority.MEDIUM: 1,
            },
            tag_counts={"common": 2, "urgent": 1},
            recent_bookmarks=recent,
        )

        assert summary.total_count == 2
        assert summary.category_counts[BookmarkCategory.IMPORTANT] == 1
        assert summary.priority_counts[BookmarkPriority.HIGH] == 1
        assert summary.tag_counts["common"] == 2
        assert summary.recent_bookmarks[0].category == BookmarkCategory.IMPORTANT

    def test_search_request_preserves_filters_and_pagination(self):
        date_from = datetime.now() - timedelta(days=7)
        date_to = datetime.now()

        search_request = BookmarkSearchRequest(
            query="important",
            category=BookmarkCategory.IMPORTANT,
            priority=BookmarkPriority.HIGH,
            tags=["urgent", "review"],
            task_id="task-123",
            date_from=date_from,
            date_to=date_to,
            has_tags=True,
            is_private=False,
            page=2,
            page_size=25,
            sort_by="priority",
            sort_order="asc",
        )

        assert search_request.query == "important"
        assert search_request.category == BookmarkCategory.IMPORTANT
        assert search_request.priority == BookmarkPriority.HIGH
        assert search_request.tags == ["urgent", "review"]
        assert search_request.page == 2
        assert search_request.page_size == 25
        assert search_request.sort_by == "priority"
        assert search_request.sort_order == "asc"

    def test_search_request_rejects_invalid_page_size(self):
        with pytest.raises(ValidationError):
            BookmarkSearchRequest(page_size=201)

    def test_cleanup_request_defaults_to_dry_run(self):
        cleanup_request = BookmarkCleanupRequest(
            older_than_days=30,
            category=BookmarkCategory.NOTE,
            priority=BookmarkPriority.LOW,
            tags=["old", "unused"],
            duplicates_only=False,
            empty_only=True,
        )

        assert cleanup_request.dry_run is True
        assert cleanup_request.older_than_days == 30
        assert cleanup_request.category == BookmarkCategory.NOTE
        assert cleanup_request.priority == BookmarkPriority.LOW
        assert cleanup_request.empty_only is True

    def test_cleanup_request_rejects_more_than_one_year(self):
        with pytest.raises(ValidationError):
            BookmarkCleanupRequest(older_than_days=400)

    @pytest.mark.parametrize("category", list(BookmarkCategory))
    def test_bookmark_category_enum_values_are_strings(self, category):
        assert isinstance(category.value, str)
        assert category.value

    @pytest.mark.parametrize("priority", list(BookmarkPriority))
    def test_bookmark_priority_enum_values_are_strings(self, priority):
        assert isinstance(priority.value, str)
        assert priority.value

    @pytest.mark.parametrize("category", ["invalid", "nonexistent", ""])
    def test_invalid_bookmark_category_rejected(self, category):
        with pytest.raises(ValueError):
            BookmarkCategory(category)

    @pytest.mark.parametrize("priority", ["invalid", "nonexistent", ""])
    def test_invalid_bookmark_priority_rejected(self, priority):
        with pytest.raises(ValueError):
            BookmarkPriority(priority)
