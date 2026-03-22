"""
SPEC-TEAM-001 REQ-TEAM-005: 회의록 공유 API 엔드포인트

- POST   /meetings/{task_id}/share        - 회의록 팀 공유
- DELETE /meetings/{task_id}/share/{team_id} - 회의록 공유 해제
- GET    /meetings/mine                   - 내 회의록 목록
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.meeting_share_service import MeetingShareService
from backend.schemas.meeting_share import (
    MeetingListResponse,
    MeetingOwnershipResponse,
    MeetingShareRequest,
    MeetingShareResponse,
)

router = APIRouter(prefix="/meetings", tags=["meetings"])

# MeetingShareService 인스턴스 (재사용)
_meeting_service = MeetingShareService()


@router.get(
    "/mine",
    response_model=MeetingListResponse,
    summary="내 회의록 목록 조회",
)
async def list_my_meetings(
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    page_size: int = Query(default=20, ge=1, le=100, description="페이지당 항목 수"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MeetingListResponse:
    """
    현재 사용자가 소유한 회의록 목록을 반환합니다.
    """
    result = await _meeting_service.list_user_meetings(
        session=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    items = [MeetingOwnershipResponse(**item) for item in result["items"]]
    return MeetingListResponse(
        items=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.post(
    "/{task_id}/share",
    response_model=MeetingShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회의록 팀 공유",
)
async def share_meeting(
    task_id: str,
    req: MeetingShareRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MeetingShareResponse:
    """
    회의록을 팀에 공유합니다.

    - 요청자가 회의록 소유자이거나 팀의 admin/member 역할이어야 합니다.
    - 요청자가 대상 팀의 멤버(admin 또는 member)여야 합니다.
    - 이미 같은 팀에 공유된 경우 409 Conflict를 반환합니다.
    """
    # team_id 유효성 검증
    try:
        team_uuid = uuid.UUID(req.team_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="유효하지 않은 팀 ID 형식입니다")

    # 요청자가 대상 팀 멤버인지 확인 (admin/member만 허용, viewer 제외)
    role = await _meeting_service.get_team_member_role(
        session=db,
        team_id=team_uuid,
        user_id=current_user.id,
    )
    if role is None or role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="팀 멤버(admin 또는 member)만 회의록을 공유할 수 있습니다",
        )

    # 공유 수행
    ownership = await _meeting_service.share_meeting(
        session=db,
        task_id=task_id,
        owner_id=current_user.id,
        team_id=team_uuid,
    )

    return MeetingShareResponse(
        task_id=ownership.task_id,
        team_id=str(ownership.team_id),
        shared_at=ownership.shared_at,
    )


@router.delete(
    "/{task_id}/share/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="회의록 공유 해제",
)
async def unshare_meeting(
    task_id: str,
    team_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    회의록 팀 공유를 해제합니다.

    - 회의록 소유자 또는 해당 팀의 admin만 공유 해제할 수 있습니다.
    """
    # team_id 유효성 검증
    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="유효하지 않은 팀 ID 형식입니다")

    # 소유자 또는 팀 admin 권한 확인
    is_owner = await _meeting_service.is_meeting_owner(
        session=db,
        task_id=task_id,
        user_id=current_user.id,
    )
    role = await _meeting_service.get_team_member_role(
        session=db,
        team_id=team_uuid,
        user_id=current_user.id,
    )

    if not is_owner and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="회의록 소유자 또는 팀 admin만 공유 해제할 수 있습니다",
        )

    deleted = await _meeting_service.unshare_meeting(
        session=db,
        task_id=task_id,
        team_id=team_uuid,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="공유 정보를 찾을 수 없습니다")
