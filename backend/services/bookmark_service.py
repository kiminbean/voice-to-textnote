"""
SPEC-BOOKMARK-001: 북마크/하이라이트 CRUD 서비스
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.bookmark_models import Bookmark
from backend.db.models import TaskResult
from backend.schemas.bookmark import (
    BookmarkBulkOperation,
    BookmarkBulkResponse,
    BookmarkCategory,
    BookmarkCleanupRequest,
    BookmarkCleanupResponse,
    BookmarkCreate,
    BookmarkPriority,
    BookmarkResponse,
    BookmarkSearchRequest,
    BookmarkSearchResponse,
    BookmarkSummaryResponse,
    BookmarkUpdate,
)


class BookmarkService:
    """북마크 CRUD. 소유권 검증 포함."""

    async def _ensure_task_exists(self, session: AsyncSession, task_id: str) -> None:
        """task_id가 실제 task_results에 존재하는지 확인."""
        stmt = select(TaskResult.id).where(TaskResult.task_id == task_id)
        result = await session.execute(stmt)
        if result.first() is None:
            raise HTTPException(
                status_code=404,
                detail=f"대상 회의록을 찾을 수 없습니다: task_id={task_id}",
            )

    async def _enforce_per_meeting_limit(
        self, session: AsyncSession, user_id: uuid.UUID, task_id: str
    ) -> None:
        """회의록 1건당 사용자가 생성할 수 있는 북마크 최대치 확인."""
        count_stmt = select(func.count(Bookmark.id)).where(
            Bookmark.user_id == user_id,
            Bookmark.task_id == task_id,
        )
        result = await session.execute(count_stmt)
        current = result.scalar_one()
        if current >= settings.bookmark_max_per_meeting:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"회의록당 북마크 최대 {settings.bookmark_max_per_meeting}개를 초과했습니다"
                ),
            )

    def _validate_segment_range(self, segment_start: float, segment_end: float) -> None:
        if segment_end <= segment_start:
            raise HTTPException(
                status_code=422,
                detail="segment_end는 segment_start보다 커야 합니다",
            )

    def _validate_note_length(self, note: str | None) -> None:
        if note is not None and len(note) > settings.bookmark_note_max_length:
            raise HTTPException(
                status_code=422,
                detail=(f"note는 {settings.bookmark_note_max_length}자를 초과할 수 없습니다"),
            )

    async def create(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        payload: BookmarkCreate,
    ) -> Bookmark:
        self._validate_segment_range(payload.segment_start, payload.segment_end)
        self._validate_note_length(payload.note)
        await self._ensure_task_exists(session, payload.task_id)
        await self._enforce_per_meeting_limit(session, user_id, payload.task_id)

        bookmark = Bookmark()
        bookmark.id = uuid.uuid4()
        bookmark.user_id = user_id
        bookmark.task_id = payload.task_id
        bookmark.segment_start = payload.segment_start
        bookmark.segment_end = payload.segment_end
        bookmark.text_snippet = payload.text_snippet
        bookmark.note = payload.note
        bookmark.color = payload.color

        session.add(bookmark)
        await session.commit()
        await session.refresh(bookmark)
        return bookmark

    async def get_by_id(
        self,
        session: AsyncSession,
        bookmark_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Bookmark:
        stmt = select(Bookmark).where(Bookmark.id == bookmark_id)
        result = await session.execute(stmt)
        bookmark = result.scalar_one_or_none()
        if bookmark is None:
            raise HTTPException(status_code=404, detail="북마크를 찾을 수 없습니다")
        if bookmark.user_id != user_id:
            # 타 사용자의 북마크는 존재 자체를 노출하지 않음 (404 반환)
            raise HTTPException(status_code=404, detail="북마크를 찾을 수 없습니다")
        return bookmark

    async def list_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        task_id: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Bookmark], int]:
        base = select(Bookmark).where(Bookmark.user_id == user_id)
        count_base = select(func.count(Bookmark.id)).where(Bookmark.user_id == user_id)
        if task_id is not None:
            base = base.where(Bookmark.task_id == task_id)
            count_base = count_base.where(Bookmark.task_id == task_id)

        count_result = await session.execute(count_base)
        total = count_result.scalar_one()

        list_stmt = (
            base.order_by(Bookmark.task_id, Bookmark.segment_start).limit(limit).offset(offset)
        )
        list_result = await session.execute(list_stmt)
        items = list(list_result.scalars().all())
        return items, total

    async def update(
        self,
        session: AsyncSession,
        bookmark_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: BookmarkUpdate,
    ) -> Bookmark:
        bookmark = await self.get_by_id(session, bookmark_id, user_id)

        # 적용 대상 값 계산 (None 은 미수정으로 처리)
        new_start = (
            payload.segment_start if payload.segment_start is not None else bookmark.segment_start
        )
        new_end = payload.segment_end if payload.segment_end is not None else bookmark.segment_end
        self._validate_segment_range(new_start, new_end)
        if payload.note is not None:
            self._validate_note_length(payload.note)

        bookmark.segment_start = new_start
        bookmark.segment_end = new_end
        if payload.text_snippet is not None:
            bookmark.text_snippet = payload.text_snippet
        if payload.note is not None:
            bookmark.note = payload.note
        if payload.color is not None:
            bookmark.color = payload.color

        await session.commit()
        await session.refresh(bookmark)
        return bookmark

    async def delete(
        self,
        session: AsyncSession,
        bookmark_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        bookmark = await self.get_by_id(session, bookmark_id, user_id)
        await session.delete(bookmark)
        await session.commit()

    async def bulk_operation(
        self, session: AsyncSession, user_id: uuid.UUID, payload: BookmarkBulkOperation
    ) -> BookmarkBulkResponse:
        processed_count = 0
        errors: list[dict[str, str]] = []
        for bookmark_id in payload.bookmark_ids:
            try:
                bookmark = await self.get_by_id(session, bookmark_id, user_id)
                if payload.operation == "delete":
                    await session.delete(bookmark)
                elif payload.operation == "update_category":
                    bookmark.category = str((payload.data or {}).get("category", bookmark.category))
                elif payload.operation == "update_priority":
                    bookmark.priority = str((payload.data or {}).get("priority", bookmark.priority))
                else:
                    raise HTTPException(status_code=422, detail="지원하지 않는 북마크 작업입니다")
                processed_count += 1
            except Exception as exc:
                errors.append({"id": str(bookmark_id), "error": str(exc)})
        await session.commit()
        return BookmarkBulkResponse(
            processed_count=processed_count, failed_count=len(errors), errors=errors
        )

    async def get_summary(
        self, session: AsyncSession, user_id: uuid.UUID, task_id: str | None = None
    ) -> BookmarkSummaryResponse:
        query = select(Bookmark).where(Bookmark.user_id == user_id)
        if task_id is not None:
            query = query.where(Bookmark.task_id == task_id)
        result = await session.execute(query.order_by(Bookmark.created_at.desc()).limit(10))
        recent = list(result.scalars().all())

        all_result = await session.execute(query)
        all_items = list(all_result.scalars().all())
        category_counts: dict[BookmarkCategory, int] = {}
        priority_counts: dict[BookmarkPriority, int] = {}
        tag_counts: dict[str, int] = {}
        for item in all_items:
            category = BookmarkCategory(item.category)
            priority = BookmarkPriority(item.priority)
            category_counts[category] = category_counts.get(category, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            for tag in item.tags or []:
                tag_counts[str(tag)] = tag_counts.get(str(tag), 0) + 1
        return BookmarkSummaryResponse(
            total_count=len(all_items),
            category_counts=category_counts,
            priority_counts=priority_counts,
            tag_counts=tag_counts,
            recent_bookmarks=[BookmarkResponse.model_validate(item) for item in recent],
        )

    async def search_bookmarks(
        self, session: AsyncSession, user_id: uuid.UUID, request: BookmarkSearchRequest
    ) -> BookmarkSearchResponse:
        query = select(Bookmark).where(Bookmark.user_id == user_id)
        if request.task_id:
            query = query.where(Bookmark.task_id == request.task_id)
        if request.category:
            query = query.where(Bookmark.category == request.category.value)
        if request.priority:
            query = query.where(Bookmark.priority == request.priority.value)
        if request.date_from:
            query = query.where(Bookmark.created_at >= request.date_from)
        if request.date_to:
            query = query.where(Bookmark.created_at <= request.date_to)

        result = await session.execute(query)
        items = list(result.scalars().all())
        if request.query:
            q = request.query.lower()
            items = [
                item
                for item in items
                if q in (item.text_snippet or "").lower() or q in (item.note or "").lower()
            ]
        if request.tags:
            required = set(request.tags)
            items = [item for item in items if required.intersection(set(item.tags or []))]
        if request.has_tags is not None:
            items = [item for item in items if bool(item.tags) is request.has_tags]

        total = len(items)
        start = (request.page - 1) * request.page_size
        page_items = items[start : start + request.page_size]
        return BookmarkSearchResponse(
            items=[BookmarkResponse.model_validate(item) for item in page_items],
            total=total,
            page=request.page,
            page_size=request.page_size,
            total_pages=(total + request.page_size - 1) // request.page_size,
        )

    async def cleanup_bookmarks(
        self, session: AsyncSession, user_id: uuid.UUID, payload: BookmarkCleanupRequest
    ) -> BookmarkCleanupResponse:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=payload.older_than_days)
        query = select(Bookmark).where(Bookmark.user_id == user_id, Bookmark.created_at < cutoff)
        if payload.category:
            query = query.where(Bookmark.category == payload.category.value)
        if payload.priority:
            query = query.where(Bookmark.priority == payload.priority.value)
        result = await session.execute(query)
        items = list(result.scalars().all())
        preview = [BookmarkResponse.model_validate(item) for item in items[:20]]
        deleted_count = 0
        if not payload.dry_run and items:
            await session.execute(
                delete(Bookmark).where(Bookmark.id.in_([item.id for item in items]))
            )
            await session.commit()
            deleted_count = len(items)
        return BookmarkCleanupResponse(
            total_count=len(items),
            deleted_count=deleted_count,
            preview=preview,
        )

    async def export_bookmarks(
        self, session: AsyncSession, user_id: uuid.UUID, task_id: str | None, format: str
    ) -> dict[str, object]:
        result = await self.search_bookmarks(
            session,
            user_id,
            BookmarkSearchRequest(task_id=task_id, page=1, page_size=200),
        )
        return {
            "format": format,
            "count": result.total,
            "items": [item.model_dump() for item in result.items],
        }
