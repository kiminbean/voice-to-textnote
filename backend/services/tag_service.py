"""
SPEC-TAG-001: 회의록 태그 CRUD 서비스
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.tag_models import MeetingTag
from backend.schemas.tag import TagCreate, TagUpdate

# 회의록당 최대 태그 수
_MAX_TAGS_PER_MEETING = 100

# 유효한 태그 타입
VALID_TAG_TYPES = {"topic", "category", "priority", "custom"}

# 유효한 태그 소스
VALID_SOURCES = {"auto", "manual"}


class TagService:
    """회의록 태그 CRUD. 소유권 검증 포함."""

    async def _enforce_meeting_limit(
        self, session: AsyncSession, user_id: uuid.UUID, task_id: str
    ) -> None:
        stmt = select(func.count(MeetingTag.id)).where(
            MeetingTag.user_id == user_id,
            MeetingTag.task_id == task_id,
        )
        result = await session.execute(stmt)
        count = result.scalar_one()
        if count >= _MAX_TAGS_PER_MEETING:
            raise HTTPException(
                status_code=409,
                detail=f"회의록당 태그는 최대 {_MAX_TAGS_PER_MEETING}개까지 등록할 수 있습니다",
            )

    async def _get_tag_or_404(
        self,
        session: AsyncSession,
        tag_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MeetingTag:
        stmt = select(MeetingTag).where(MeetingTag.id == tag_id)
        result = await session.execute(stmt)
        tag = result.scalar_one_or_none()
        if tag is None or tag.user_id != user_id:
            raise HTTPException(status_code=404, detail="태그를 찾을 수 없습니다")
        return tag

    async def create(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        payload: TagCreate,
    ) -> MeetingTag:
        """태그 생성."""
        if payload.tag_type not in VALID_TAG_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"유효하지 않은 태그 타입입니다. 가능: {', '.join(sorted(VALID_TAG_TYPES))}",
            )

        await self._enforce_meeting_limit(session, user_id, payload.task_id)

        tag = MeetingTag()
        tag.id = uuid.uuid4()
        tag.user_id = user_id
        tag.task_id = payload.task_id
        tag.tag_type = payload.tag_type
        tag.tag_value = payload.tag_value
        tag.source = payload.source or "manual"
        tag.confidence = payload.confidence
        tag.note = payload.note

        session.add(tag)
        await session.commit()
        await session.refresh(tag)
        return tag

    async def bulk_create(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        task_id: str,
        tags: list[TagCreate],
    ) -> list[MeetingTag]:
        """태그 일괄 생성 (자동 태깅 결과 저장용)."""
        if len(tags) > _MAX_TAGS_PER_MEETING:
            raise HTTPException(
                status_code=422,
                detail=f"한 번에 최대 {_MAX_TAGS_PER_MEETING}개 태그까지 생성 가능합니다",
            )

        created = []
        for payload in tags:
            tag = MeetingTag()
            tag.id = uuid.uuid4()
            tag.user_id = user_id
            tag.task_id = task_id
            tag.tag_type = payload.tag_type
            tag.tag_value = payload.tag_value
            tag.source = payload.source or "auto"
            tag.confidence = payload.confidence
            tag.note = payload.note
            session.add(tag)
            created.append(tag)

        await session.commit()
        for tag in created:
            await session.refresh(tag)
        return created

    async def get_by_id(
        self,
        session: AsyncSession,
        tag_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MeetingTag:
        return await self._get_tag_or_404(session, tag_id, user_id)

    async def list_for_meeting(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        task_id: str,
        tag_type: str | None = None,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[MeetingTag], int]:
        """특정 회의록의 태그 목록."""
        base = select(MeetingTag).where(
            MeetingTag.user_id == user_id,
            MeetingTag.task_id == task_id,
        )
        count_base = select(func.count(MeetingTag.id)).where(
            MeetingTag.user_id == user_id,
            MeetingTag.task_id == task_id,
        )

        if tag_type is not None:
            base = base.where(MeetingTag.tag_type == tag_type)
            count_base = count_base.where(MeetingTag.tag_type == tag_type)
        if source is not None:
            base = base.where(MeetingTag.source == source)
            count_base = count_base.where(MeetingTag.source == source)

        count_result = await session.execute(count_base)
        total = count_result.scalar_one()

        list_stmt = (
            base.order_by(MeetingTag.tag_type, MeetingTag.created_at).limit(limit).offset(offset)
        )
        list_result = await session.execute(list_stmt)
        items = list(list_result.scalars().all())
        return items, total

    async def update(
        self,
        session: AsyncSession,
        tag_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: TagUpdate,
    ) -> MeetingTag:
        tag = await self._get_tag_or_404(session, tag_id, user_id)

        if payload.tag_type is not None:
            if payload.tag_type not in VALID_TAG_TYPES:
                raise HTTPException(
                    status_code=422,
                    detail=f"유효하지 않은 태그 타입입니다. 가능: {', '.join(sorted(VALID_TAG_TYPES))}",
                )
            tag.tag_type = payload.tag_type
        if payload.tag_value is not None:
            tag.tag_value = payload.tag_value
        if payload.note is not None:
            tag.note = payload.note

        await session.commit()
        await session.refresh(tag)
        return tag

    async def delete(
        self,
        session: AsyncSession,
        tag_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        tag = await self._get_tag_or_404(session, tag_id, user_id)
        await session.delete(tag)
        await session.commit()

    async def delete_all_for_meeting(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        task_id: str,
        source: str | None = None,
    ) -> int:
        """회의록의 태그 전체/선택 삭제. 삭제된 개수 반환."""
        base = select(MeetingTag).where(
            MeetingTag.user_id == user_id,
            MeetingTag.task_id == task_id,
        )
        if source is not None:
            base = base.where(MeetingTag.source == source)

        result = await session.execute(base)
        tags = list(result.scalars().all())
        count = len(tags)
        for tag in tags:
            await session.delete(tag)
        await session.commit()
        return count
