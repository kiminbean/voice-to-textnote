"""
화자 그룁 관리 서비스
"""

import uuid
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.speaker_group_models import SpeakerGroup, SpeakerGroupMember
from backend.db.speaker_models import SpeakerProfile
from backend.exceptions import VoiceNoteError
from backend.schemas.speaker_group import SpeakerGroupCreate, SpeakerGroupUpdate


class SpeakerGroupService:
    """화자 그룁 관리 서비스"""
    
    async def create(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        payload: SpeakerGroupCreate,
    ) -> SpeakerGroup:
        """화자 그룁 생성."""
        # 그룹명 중복 확인
        existing = await self._get_by_name(session, payload.name, user_id)
        if existing:
            raise VoiceNoteError(f"그룹명 '{payload.name}'은(는) 이미 존재합니다.")
        
        group = SpeakerGroup(
            name=payload.name,
            description=payload.description,
            color=payload.color,
            user_id=user_id,
        )
        
        session.add(group)
        await session.commit()
        await session.refresh(group)
        
        return group
    
    async def list_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        name_filter: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[SpeakerGroup], int]:
        """사용자의 화자 그룁 목록 조회."""
        query = select(SpeakerGroup).where(SpeakerGroup.user_id == user_id)
        
        if name_filter:
            query = query.where(SpeakerGroup.name.ilike(f"%{name_filter}%"))
        
        # 총 개수 조회
        count_query = select(SpeakerGroup).where(SpeakerGroup.user_id == user_id)
        if name_filter:
            count_query = count_query.where(SpeakerGroup.name.ilike(f"%{name_filter}%"))
        
        total = await session.scalar(count_query.count())
        
        # 목록 조회
        query = query.order_by(SpeakerGroup.created_at.desc())
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        groups = result.scalars().all()
        
        return groups, total
    
    async def get_by_id(
        self,
        session: AsyncSession,
        group_id: uuid.UUID,
        user_id: uuid.UUID,
        include_members: bool = False,
    ) -> SpeakerGroup:
        """화자 그룁 단건 조회."""
        query = select(SpeakerGroup).where(
            SpeakerGroup.id == group_id,
            SpeakerGroup.user_id == user_id,
        )
        
        if include_members:
            query = options(selectinload(SpeakerGroup.members))
        
        result = await session.execute(query)
        group = result.scalar_one_or_none()
        
        if not group:
            raise VoiceNoteError("화자 그룁을 찾을 수 없습니다.")
        
        return group
    
    async def update(
        self,
        session: AsyncSession,
        group_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: SpeakerGroupUpdate,
    ) -> SpeakerGroup:
        """화자 그룁 수정."""
        group = await self.get_by_id(session, group_id, user_id)
        
        # 이름 변경 시 중복 확인
        if payload.name and payload.name != group.name:
            existing = await self._get_by_name(session, payload.name, user_id)
            if existing:
                raise VoiceNoteError(f"그룹명 '{payload.name}'은(는) 이미 존재합니다.")
            
            group.name = payload.name
        
        # 다른 필드 업데이트
        if payload.description is not None:
            group.description = payload.description
        if payload.color is not None:
            group.color = payload.color
        
        await session.commit()
        await session.refresh(group)
        
        return group
    
    async def delete(
        self,
        session: AsyncSession,
        group_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """화자 그룁 삭제."""
        group = await self.get_by_id(session, group_id, user_id)
        await session.delete(group)
        await session.commit()
    
    async def add_member(
        self,
        session: AsyncSession,
        group_id: uuid.UUID,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SpeakerGroupMember:
        """화자 그룁에 멤버 추가."""
        # 그룁 소유권 확인
        group = await self.get_by_id(session, group_id, user_id)
        
        # 화자 존재 확인
        speaker_result = await session.execute(
            select(SpeakerProfile).where(
                SpeakerProfile.id == speaker_id,
                SpeakerProfile.user_id == user_id,
            )
        )
        speaker = speaker_result.scalar_one_or_none()
        if not speaker:
            raise VoiceNoteError("화자 프로필을 찾을 수 없습니다.")
        
        # 중복 멤버 확인
        existing_member = await session.execute(
            select(SpeakerGroupMember).where(
                SpeakerGroupMember.group_id == group_id,
                SpeakerGroupMember.speaker_id == speaker_id,
            )
        )
        if existing_member.scalar_one_or_none():
            raise VoiceNoteError("해당 화자는 이미 그룁에 포함되어 있습니다.")
        
        member = SpeakerGroupMember(
            group_id=group_id,
            speaker_id=speaker_id,
        )
        
        session.add(member)
        await session.commit()
        await session.refresh(member)
        
        return member
    
    async def remove_member(
        self,
        session: AsyncSession,
        group_id: uuid.UUID,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """화자 그룁에서 멤버 제외."""
        # 그룁 소유권 확인
        await self.get_by_id(session, group_id, user_id)
        
        # 멤버 제거
        result = await session.execute(
            delete(SpeakerGroupMember).where(
                SpeakerGroupMember.group_id == group_id,
                SpeakerGroupMember.speaker_id == speaker_id,
            )
        )
        
        if result.rowcount == 0:
            raise VoiceNoteError("해당 화자는 그룁에 포함되어 있지 않습니다.")
        
        await session.commit()
    
    async def _get_by_name(
        self,
        session: AsyncSession,
        name: str,
        user_id: uuid.UUID,
    ) -> Optional[SpeakerGroup]:
        """그룁명으로 그룁 조회 (중복 확인용)."""
        result = await session.execute(
            select(SpeakerGroup).where(
                SpeakerGroup.name == name,
                SpeakerGroup.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()