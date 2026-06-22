"""
화자 그룹/팀 관리 API

엔드포인트:
- POST   /api/v1/speaker-groups                 생성
- GET    /api/v1/speaker-groups                 목록
- GET    /api/v1/speaker-groups/{id}            단건 조회
- PATCH  /api/v1/speaker-groups/{id}            부분 수정
- DELETE /api/v1/speaker-groups/{id}            삭제
- POST   /api/v1/speaker-groups/{id}/members    멤버 추가
- DELETE /api/v1/speaker-groups/{id}/members/{speaker_id} 멤버 제외
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.auth_models import User
from backend.db.speaker_group_models import SpeakerGroup, SpeakerGroupMember
from backend.schemas.speaker_group import (
    SpeakerGroupCreate,
    SpeakerGroupListResponse,
    SpeakerGroupMemberResponse,
    SpeakerGroupResponse,
    SpeakerGroupUpdate,
    SpeakerGroupWithMembersResponse,
)
from backend.services.speaker_group_service import SpeakerGroupService

router = APIRouter(prefix="/speaker-groups", tags=["speaker-groups"])


def get_speaker_group_service() -> SpeakerGroupService:
    """SpeakerGroupService 인스턴스 제공 (FastAPI Depends)"""
    return SpeakerGroupService()


@router.post(
    "",
    response_model=SpeakerGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_speaker_group(
    payload: SpeakerGroupCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerGroupService = Depends(get_speaker_group_service),
) -> SpeakerGroupResponse:
    """화자 그룹 생성."""
    group = await svc.create(db, user.id, payload)
    return SpeakerGroupResponse.model_validate(group)


@router.get("", response_model=SpeakerGroupListResponse)
async def list_speaker_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    name: Optional[str] = Query(default=None, description="그룹명 필터"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerGroupService = Depends(get_speaker_group_service),
) -> SpeakerGroupListResponse:
    """화자 그룹 목록 조회."""
    offset = (page - 1) * page_size
    items, total = await svc.list_for_user(
        session=db,
        user_id=user.id,
        name_filter=name,
        limit=page_size,
        offset=offset,
    )
    return SpeakerGroupListResponse(
        items=[SpeakerGroupResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{group_id}", response_model=SpeakerGroupWithMembersResponse)
async def get_speaker_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerGroupService = Depends(get_speaker_group_service),
) -> SpeakerGroupWithMembersResponse:
    """화자 그룹 상세 조회 (멤버 포함)."""
    group = await svc.get_by_id(db, group_id, user.id)
    return SpeakerGroupWithMembersResponse.model_validate(group)


@router.patch("/{group_id}", response_model=SpeakerGroupResponse)
async def update_speaker_group(
    group_id: uuid.UUID,
    payload: SpeakerGroupUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerGroupService = Depends(get_speaker_group_service),
) -> SpeakerGroupResponse:
    """화자 그료 수정."""
    group = await svc.update(db, group_id, user.id, payload)
    return SpeakerGroupResponse.model_validate(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_speaker_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerGroupService = Depends(get_speaker_group_service),
) -> None:
    """화자 그룹 삭제."""
    await svc.delete(db, group_id, user.id)


@router.post("/{group_id}/members", response_model=SpeakerGroupMemberResponse)
async def add_speaker_to_group(
    group_id: uuid.UUID,
    speaker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerGroupService = Depends(get_speaker_group_service),
) -> SpeakerGroupMemberResponse:
    """화자 그룹에 멤버 추가."""
    member = await svc.add_member(db, group_id, speaker_id, user.id)
    return SpeakerGroupMemberResponse.model_validate(member)


@router.delete("/{group_id}/members/{speaker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_speaker_from_group(
    group_id: uuid.UUID,
    speaker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerGroupService = Depends(get_speaker_group_service),
) -> None:
    """화자 그룹에서 멤버 제외."""
    await svc.remove_member(db, group_id, speaker_id, user.id)