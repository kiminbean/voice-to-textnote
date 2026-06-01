"""
REQ-VOCAB-001: 커스텀 어휘 관리 API

엔드포인트:
- POST   /api/v1/vocabulary              생성
- GET    /api/v1/vocabulary               목록
- GET    /api/v1/vocabulary/{vocab_id}    단건 조회
- PUT    /api/v1/vocabulary/{vocab_id}    수정
- DELETE /api/v1/vocabulary/{vocab_id}    삭제
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session
from backend.db.vocabulary_service import VocabularyService
from backend.schemas.vocabulary import (
    VocabularyCreate,
    VocabularyListResponse,
    VocabularyResponse,
    VocabularyUpdate,
)

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])

_service = VocabularyService()


@router.post(
    "",
    response_model=VocabularyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_vocabulary(
    payload: VocabularyCreate,
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyResponse:
    """어휘 리스트 생성"""
    vocab = await _service.create(db, payload)
    return VocabularyResponse.model_validate(vocab)


@router.get("", response_model=VocabularyListResponse)
async def list_vocabularies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyListResponse:
    """어휘 리스트 목록 조회"""
    offset = (page - 1) * page_size
    items, total = await _service.list_all(db, limit=page_size, offset=offset)
    return VocabularyListResponse(
        items=[VocabularyResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{vocab_id}", response_model=VocabularyResponse)
async def get_vocabulary(
    vocab_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyResponse:
    """어휘 리스트 단건 조회"""
    vocab = await _service.get_by_id(db, vocab_id)
    return VocabularyResponse.model_validate(vocab)


@router.put("/{vocab_id}", response_model=VocabularyResponse)
async def update_vocabulary(
    vocab_id: uuid.UUID,
    payload: VocabularyUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyResponse:
    """어휘 리스트 수정"""
    vocab = await _service.update(db, vocab_id, payload)
    return VocabularyResponse.model_validate(vocab)


@router.delete("/{vocab_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vocabulary(
    vocab_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """어휘 리스트 삭제"""
    await _service.delete(db, vocab_id)
