"""
SPEC-SPEAKER-001: 화자 프로필 CRUD 서비스
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.speaker_models import SpeakerProfile
from backend.schemas.speaker import SpeakerProfileCreate, SpeakerProfileUpdate

# 사용자당 최대 화자 프로필 수 (전역 + 회의록별 합산)
_MAX_PROFILES_PER_USER = 500


class SpeakerService:
    """화자 프로필 CRUD. 소유권 검증 포함."""

    async def _ensure_no_duplicate(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        speaker_label: str,
        task_id: str | None,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        """동일 (user_id, speaker_label, task_id) 조합 중복 확인."""
        stmt = select(SpeakerProfile.id).where(
            SpeakerProfile.user_id == user_id,
            SpeakerProfile.speaker_label == speaker_label,
            SpeakerProfile.task_id == task_id,
        )
        if exclude_id is not None:
            stmt = stmt.where(SpeakerProfile.id != exclude_id)
        result = await session.execute(stmt)
        if result.first() is not None:
            scope = f"task_id={task_id}" if task_id else "전역"
            raise HTTPException(
                status_code=409,
                detail=f"이미 동일한 화자 프로필이 존재합니다 ({scope}, label={speaker_label})",
            )

    async def _enforce_user_limit(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        stmt = select(func.count(SpeakerProfile.id)).where(SpeakerProfile.user_id == user_id)
        result = await session.execute(stmt)
        count = result.scalar_one()
        if count >= _MAX_PROFILES_PER_USER:
            raise HTTPException(
                status_code=409,
                detail=f"화자 프로필은 사용자당 최대 {_MAX_PROFILES_PER_USER}개까지 등록할 수 있습니다",
            )

    async def create(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        payload: SpeakerProfileCreate,
    ) -> SpeakerProfile:
        """화자 프로필 생성."""
        await self._enforce_user_limit(session, user_id)
        await self._ensure_no_duplicate(session, user_id, payload.speaker_label, payload.task_id)

        profile = SpeakerProfile()
        profile.id = uuid.uuid4()
        profile.user_id = user_id
        profile.speaker_label = payload.speaker_label
        profile.display_name = payload.display_name
        profile.role = payload.role
        profile.note = payload.note
        profile.task_id = payload.task_id

        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        return profile

    async def get_by_id(
        self,
        session: AsyncSession,
        profile_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SpeakerProfile:
        stmt = select(SpeakerProfile).where(SpeakerProfile.id == profile_id)
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None or profile.user_id != user_id:
            raise HTTPException(status_code=404, detail="화자 프로필을 찾을 수 없습니다")
        return profile

    async def list_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        task_id: str | None,
        speaker_label: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SpeakerProfile], int]:
        """사용자 화자 프로필 목록. 전역 + 특정 회의록 프로필 모두 반환."""
        base = select(SpeakerProfile).where(SpeakerProfile.user_id == user_id)
        count_base = select(func.count(SpeakerProfile.id)).where(SpeakerProfile.user_id == user_id)

        if task_id is not None:
            # 해당 회의록 오버라이드 + 전역 프로필 모두 반환
            base = base.where(
                (SpeakerProfile.task_id == task_id) | (SpeakerProfile.task_id.is_(None))
            )
            count_base = count_base.where(
                (SpeakerProfile.task_id == task_id) | (SpeakerProfile.task_id.is_(None))
            )
        if speaker_label is not None:
            base = base.where(SpeakerProfile.speaker_label == speaker_label)
            count_base = count_base.where(SpeakerProfile.speaker_label == speaker_label)

        count_result = await session.execute(count_base)
        total = count_result.scalar_one()

        list_stmt = (
            base.order_by(SpeakerProfile.speaker_label, SpeakerProfile.task_id)
            .limit(limit)
            .offset(offset)
        )
        list_result = await session.execute(list_stmt)
        items = list(list_result.scalars().all())
        return items, total

    async def update(
        self,
        session: AsyncSession,
        profile_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: SpeakerProfileUpdate,
    ) -> SpeakerProfile:
        profile = await self.get_by_id(session, profile_id, user_id)

        if payload.display_name is not None:
            profile.display_name = payload.display_name
        if payload.role is not None:
            profile.role = payload.role
        if payload.note is not None:
            profile.note = payload.note

        await session.commit()
        await session.refresh(profile)
        return profile

    async def delete(
        self,
        session: AsyncSession,
        profile_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        profile = await self.get_by_id(session, profile_id, user_id)
        await session.delete(profile)
        await session.commit()
