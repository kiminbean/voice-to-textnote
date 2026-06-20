"""BookmarkService branch coverage for bulk/search/cleanup/export flows."""

import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.schemas.bookmark import (
    BookmarkBulkOperation,
    BookmarkCategory,
    BookmarkCleanupRequest,
    BookmarkPriority,
    BookmarkSearchRequest,
)
from backend.services.bookmark_service import BookmarkService


def _bookmark(
    *,
    bookmark_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    task_id: str = "task-1",
    text_snippet: str | None = "meeting note",
    note: str | None = None,
    category: str = "note",
    priority: str = "medium",
    tags: list[str] | None = None,
    created_at: datetime | None = None,
):
    timestamp = created_at or datetime(2026, 1, 1, 12, 0, 0)
    return SimpleNamespace(
        id=bookmark_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        task_id=task_id,
        segment_start=1.0,
        segment_end=2.0,
        text_snippet=text_snippet,
        note=note,
        color="#fff",
        category=category,
        priority=priority,
        tags=tags or [],
        is_private=True,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _scalars_result(items):
    scalars = MagicMock()
    scalars.all.return_value = items
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


@pytest.mark.asyncio
async def test_bulk_operation_updates_deletes_and_collects_errors():
    service = BookmarkService()
    user_id = uuid.uuid4()
    delete_id = uuid.uuid4()
    category_id = uuid.uuid4()
    priority_id = uuid.uuid4()
    missing_id = uuid.uuid4()
    deleted = _bookmark(bookmark_id=delete_id, user_id=user_id)
    category_target = _bookmark(bookmark_id=category_id, user_id=user_id, category="note")
    priority_target = _bookmark(bookmark_id=priority_id, user_id=user_id, priority="low")
    session = AsyncMock()

    async def fake_get_by_id(_session, bookmark_id, _user_id):
        if bookmark_id == missing_id:
            raise HTTPException(status_code=404, detail="missing")
        return {
            delete_id: deleted,
            category_id: category_target,
            priority_id: priority_target,
        }[bookmark_id]

    with patch.object(service, "get_by_id", side_effect=fake_get_by_id):
        delete_result = await service.bulk_operation(
            session,
            user_id,
            BookmarkBulkOperation(operation="delete", bookmark_ids=[delete_id, missing_id]),
        )
        category_result = await service.bulk_operation(
            session,
            user_id,
            BookmarkBulkOperation(
                operation="update_category",
                bookmark_ids=[category_id],
                data={"category": "important"},
            ),
        )
        priority_result = await service.bulk_operation(
            session,
            user_id,
            BookmarkBulkOperation(
                operation="update_priority",
                bookmark_ids=[priority_id],
                data={"priority": "urgent"},
            ),
        )
        unsupported = await service.bulk_operation(
            session,
            user_id,
            BookmarkBulkOperation(operation="archive", bookmark_ids=[delete_id]),
        )

    assert delete_result.processed_count == 1
    assert delete_result.failed_count == 1
    assert delete_result.errors[0]["id"] == str(missing_id)
    assert category_result.processed_count == 1
    assert category_target.category == "important"
    assert priority_result.processed_count == 1
    assert priority_target.priority == "urgent"
    assert unsupported.processed_count == 0
    assert unsupported.failed_count == 1
    session.delete.assert_awaited_once_with(deleted)
    assert session.commit.await_count == 4


@pytest.mark.asyncio
async def test_get_summary_counts_categories_priorities_tags_and_recent():
    service = BookmarkService()
    user_id = uuid.uuid4()
    recent = _bookmark(
        user_id=user_id,
        category="important",
        priority="urgent",
        tags=["alpha", "beta"],
    )
    older = _bookmark(
        user_id=user_id,
        category="note",
        priority="medium",
        tags=["alpha"],
    )
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[_scalars_result([recent]), _scalars_result([recent, older])]
    )

    result = await service.get_summary(session, user_id, task_id="task-1")

    assert result.total_count == 2
    assert result.category_counts[BookmarkCategory.IMPORTANT] == 1
    assert result.category_counts[BookmarkCategory.NOTE] == 1
    assert result.priority_counts[BookmarkPriority.URGENT] == 1
    assert result.priority_counts[BookmarkPriority.MEDIUM] == 1
    assert result.tag_counts == {"alpha": 2, "beta": 1}
    assert result.recent_bookmarks[0].id == recent.id


@pytest.mark.asyncio
async def test_search_bookmarks_applies_filters_and_pagination_in_memory():
    service = BookmarkService()
    user_id = uuid.uuid4()
    matching = _bookmark(
        user_id=user_id,
        task_id="task-1",
        text_snippet="Budget review",
        note=None,
        category="important",
        priority="high",
        tags=["finance"],
    )
    second = _bookmark(
        user_id=user_id,
        task_id="task-1",
        text_snippet=None,
        note="budget follow-up",
        category="important",
        priority="high",
        tags=["finance", "next"],
    )
    excluded = _bookmark(
        user_id=user_id,
        task_id="task-2",
        text_snippet="unrelated",
        note=None,
        category="note",
        priority="low",
        tags=[],
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalars_result([matching, second, excluded]))

    result = await service.search_bookmarks(
        session,
        user_id,
        BookmarkSearchRequest(
            task_id="task-1",
            category=BookmarkCategory.IMPORTANT,
            priority=BookmarkPriority.HIGH,
            query="budget",
            tags=["finance"],
            has_tags=True,
            date_from=datetime(2025, 1, 1),
            date_to=datetime(2027, 1, 1),
            page=2,
            page_size=1,
        ),
    )

    assert result.total == 2
    assert result.total_pages == 2
    assert result.page == 2
    assert result.items[0].id == second.id


@pytest.mark.asyncio
async def test_cleanup_bookmarks_supports_dry_run_and_delete_modes():
    service = BookmarkService()
    user_id = uuid.uuid4()
    stale = _bookmark(
        user_id=user_id,
        category="note",
        priority="low",
        created_at=datetime.now() - timedelta(days=90),
    )

    dry_session = AsyncMock()
    dry_session.execute = AsyncMock(return_value=_scalars_result([stale]))
    dry = await service.cleanup_bookmarks(
        dry_session,
        user_id,
        BookmarkCleanupRequest(
            older_than_days=30,
            category=BookmarkCategory.NOTE,
            priority=BookmarkPriority.LOW,
            dry_run=True,
        ),
    )

    delete_session = AsyncMock()
    delete_session.execute = AsyncMock(return_value=_scalars_result([stale]))
    deleted = await service.cleanup_bookmarks(
        delete_session,
        user_id,
        BookmarkCleanupRequest(older_than_days=30, dry_run=False),
    )

    assert dry.total_count == 1
    assert dry.deleted_count == 0
    assert dry.preview[0].id == stale.id
    assert deleted.total_count == 1
    assert deleted.deleted_count == 1
    delete_session.commit.assert_awaited_once()
    assert delete_session.execute.await_count == 2


@pytest.mark.asyncio
async def test_export_bookmarks_serializes_search_results():
    service = BookmarkService()
    user_id = uuid.uuid4()
    item = _bookmark(user_id=user_id, text_snippet="export me")
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalars_result([item]))

    result = await service.export_bookmarks(session, user_id, task_id="task-1", format="json")

    assert result["format"] == "json"
    assert result["count"] == 1
    assert result["items"][0]["id"] == item.id
    assert result["items"][0]["text_snippet"] == "export me"
