"""
SPEC-BOOKMARK-001: 북마크/하이라이트 CRUD 서비스
"""

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.bookmark_models import Bookmark
from backend.db.models import TaskResult
from backend.schemas.bookmark import (
    BookmarkBulkOperation,
    BookmarkCleanupRequest,
    BookmarkCreate,
    BookmarkSearchRequest,
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

    # @MX:TODO: SPEC-BOOKMARK-001 — 미구현 고급 기능 스텁 (Phase 2 mypy 해결용)
    # 각 메서드는 API 라우트에서 참조하므로 최소 시그니처만 정의

    async def bulk_operation(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        payload: BookmarkBulkOperation,
    ) -> dict[str, Any]:
        """대량 북마크 작업 (삭제, 카테고리/우선순위 업데이트)."""
        raise HTTPException(status_code=501, detail="bulk_operation 미구현")

    async def get_summary(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """북마크 통계 및 요약 정보."""
        raise HTTPException(status_code=501, detail="get_summary 미구현")

    async def search_bookmarks(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        request: BookmarkSearchRequest,
    ) -> dict[str, Any]:
        """고급 북마크 검색."""
        raise HTTPException(status_code=501, detail="search_bookmarks 미구현")

    async def cleanup_bookmarks(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        payload: BookmarkCleanupRequest,
    ) -> dict[str, Any]:
        """북마크 정리."""
        raise HTTPException(status_code=501, detail="cleanup_bookmarks 미구현")

    async def export_bookmarks(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        task_id: str | None = None,
        format: str = "json",  # noqa: A002
    ) -> dict[str, Any]:
        """북마크 내보내기."""
        raise HTTPException(status_code=501, detail="export_bookmarks 미구현")
