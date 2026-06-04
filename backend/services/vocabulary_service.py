"""
REQ-VOCAB-001: 커스텀 어휘 CRUD 서비스
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.vocabulary_models import CustomVocabulary
from backend.schemas.vocabulary import (
    VocabularyCreate,
    VocabularyUpdate,
)


class VocabularyService:
    """커스텀 어휘 비동기 CRUD 서비스"""

    async def list_all(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[CustomVocabulary], int]:
        stmt = select(CustomVocabulary).order_by(CustomVocabulary.created_at.desc())
        from sqlalchemy import func

        count_stmt = select(func.count()).select_from(CustomVocabulary)
        total = (await session.execute(count_stmt)).scalar_one()

        result = await session.execute(stmt.limit(limit).offset(offset))
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(
        self,
        session: AsyncSession,
        vocab_id: uuid.UUID,
    ) -> CustomVocabulary:
        stmt = select(CustomVocabulary).where(CustomVocabulary.id == vocab_id)
        result = await session.execute(stmt)
        vocab = result.scalar_one_or_none()
        if vocab is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="어휘 리스트를 찾을 수 없습니다.")
        return vocab

    async def create(
        self,
        session: AsyncSession,
        payload: VocabularyCreate,
    ) -> CustomVocabulary:
        vocab = CustomVocabulary(
            name=payload.name,
            words=payload.words,
        )
        session.add(vocab)
        await session.commit()
        await session.refresh(vocab)
        return vocab

    async def update(
        self,
        session: AsyncSession,
        vocab_id: uuid.UUID,
        payload: VocabularyUpdate,
    ) -> CustomVocabulary:
        vocab = await self.get_by_id(session, vocab_id)
        if payload.name is not None:
            vocab.name = payload.name
        if payload.words is not None:
            vocab.words = payload.words
        await session.commit()
        await session.refresh(vocab)
        return vocab

    async def delete(
        self,
        session: AsyncSession,
        vocab_id: uuid.UUID,
    ) -> None:
        vocab = await self.get_by_id(session, vocab_id)
        await session.delete(vocab)
        await session.commit()

    async def get_initial_prompt(
        self,
        session: AsyncSession,
        vocab_id: uuid.UUID,
    ) -> str | None:
        """어휘 ID로부터 Whisper initial_prompt 문자열 생성.

        Whisper는 initial_prompt를 스페이스로 구분된 토큰으로 처리한다.
        빈 리스트이거나 존재하지 않는 ID면 None을 반환.
        """
        stmt = select(CustomVocabulary.words).where(CustomVocabulary.id == vocab_id)
        result = await session.execute(stmt)
        words = result.scalar_one_or_none()
        if not words:
            return None
        return " ".join(words)
