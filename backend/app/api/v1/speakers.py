"""
SPEC-SPEAKER-001: 화자 프로필 관리 API

엔드포인트 (모두 JWT 인증 필요):
- POST   /api/v1/speakers              생성
- GET    /api/v1/speakers              목록 (task_id, speaker_label 필터링)
- GET    /api/v1/speakers/{id}         단건 조회
- PATCH  /api/v1/speakers/{id}         부분 수정 (이름/역할/메모)
- DELETE /api/v1/speakers/{id}         삭제
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.auth_models import User
from backend.db.speaker_service import SpeakerService
from backend.schemas.speaker import (
    SpeakerProfileCreate,
    SpeakerProfileListResponse,
    SpeakerProfileResponse,
    SpeakerProfileUpdate,
)

router = APIRouter(prefix="/speakers", tags=["speakers"])

_service = SpeakerService()


@router.post(
    "",
    response_model=SpeakerProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_speaker(
    payload: SpeakerProfileCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> SpeakerProfileResponse:
    """REQ-SPEAKER-001: 화자 프로필 생성."""
    profile = await _service.create(db, user.id, payload)
    return SpeakerProfileResponse.model_validate(profile)


@router.get("", response_model=SpeakerProfileListResponse)
async def list_speakers(
    task_id: str | None = Query(
        default=None,
        max_length=255,
        description="특정 회의록의 화자 프로필만 조회 (전역 프로필 포함)",
    ),
    speaker_label: str | None = Query(
        default=None,
        max_length=50,
        description="특정 화자 레이블만 조회 (예: SPEAKER_00)",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> SpeakerProfileListResponse:
    """REQ-SPEAKER-002: 화자 프로필 목록. task_id 지정 시 해당 회의록 + 전역 프로필 반환."""
    offset = (page - 1) * page_size
    items, total = await _service.list_for_user(
        session=db,
        user_id=user.id,
        task_id=task_id,
        speaker_label=speaker_label,
        limit=page_size,
        offset=offset,
    )
    return SpeakerProfileListResponse(
        items=[SpeakerProfileResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{speaker_id}", response_model=SpeakerProfileResponse)
async def get_speaker(
    speaker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> SpeakerProfileResponse:
    profile = await _service.get_by_id(db, speaker_id, user.id)
    return SpeakerProfileResponse.model_validate(profile)


@router.patch("/{speaker_id}", response_model=SpeakerProfileResponse)
async def update_speaker(
    speaker_id: uuid.UUID,
    payload: SpeakerProfileUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> SpeakerProfileResponse:
    profile = await _service.update(db, speaker_id, user.id, payload)
    return SpeakerProfileResponse.model_validate(profile)


@router.delete("/{speaker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_speaker(
    speaker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> None:
    await _service.delete(db, speaker_id, user.id)
