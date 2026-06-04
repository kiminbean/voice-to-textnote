"""
SPEC-TEAM-001: 팀 관리 API 엔드포인트

모든 엔드포인트는 JWT 인증 필요 (get_current_user 의존성):
- POST   /teams         - 팀 생성
- GET    /teams         - 내 팀 목록
- GET    /teams/{id}    - 팀 상세 조회 (멤버만 접근)
- PUT    /teams/{id}    - 팀 수정 (admin만)
- DELETE /teams/{id}    - 팀 삭제 (admin만)
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.app.errors import (
    bad_request,
    conflict,
    forbidden,
    not_found,
    unprocessable,
)
from backend.services.meeting_share_service import MeetingShareService
from backend.services.team_service import TeamService
from backend.schemas.meeting_share import MeetingListResponse, MeetingOwnershipResponse
from backend.schemas.team import (
    MemberInviteRequest,
    MemberListResponse,
    MemberRoleUpdateRequest,
    TeamCreateRequest,
    TeamDetailResponse,
    TeamListResponse,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdateRequest,
)

router = APIRouter(prefix="/teams", tags=["teams"])

# TeamService 인스턴스 (재사용)
_team_service = TeamService()

# MeetingShareService 인스턴스 (재사용)
_meeting_service = MeetingShareService()


@router.post(
    "",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="팀 생성",
)
async def create_team(
    req: TeamCreateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TeamResponse:
    """
    새 팀을 생성합니다.
    생성자는 자동으로 admin 역할로 팀에 추가됩니다.
    """
    team = await _team_service.create_team(
        session=db,
        name=req.name,
        description=req.description,
        creator_id=current_user.id,
    )
    return TeamResponse(
        id=str(team.id),
        name=team.name,
        description=team.description,
        created_by=str(team.created_by),
        created_at=team.created_at,
        member_count=1,  # 생성 직후 creator 1명
    )


@router.get(
    "",
    response_model=TeamListResponse,
    summary="내 팀 목록 조회",
)
async def list_teams(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TeamListResponse:
    """
    현재 사용자가 속한 팀 목록을 반환합니다.
    """
    teams = await _team_service.list_user_teams(session=db, user_id=current_user.id)
    items = [
        TeamResponse(
            id=str(t["id"]),
            name=t["name"],
            description=t["description"],
            created_by=t["created_by"],
            created_at=t["created_at"],
            member_count=t["member_count"],
        )
        for t in teams
    ]
    return TeamListResponse(items=items, total=len(items))


@router.get(
    "/{team_id}",
    response_model=TeamDetailResponse,
    summary="팀 상세 조회",
)
async def get_team(
    team_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TeamDetailResponse:
    """
    팀 상세 정보와 멤버 목록을 반환합니다.
    팀 멤버만 접근 가능합니다.
    """
    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        unprocessable("유효하지 않은 팀 ID 형식입니다")

    # 멤버십 확인
    role = await _team_service.get_user_role(
        session=db, team_id=team_uuid, user_id=current_user.id
    )
    if role is None:
        forbidden("팀에 접근할 권한이 없습니다")

    detail = await _team_service.get_team_with_members(session=db, team_id=team_uuid)
    if detail is None:
        not_found("팀을 찾을 수 없습니다")

    return TeamDetailResponse(
        id=str(detail["id"]),
        name=detail["name"],
        description=detail["description"],
        created_by=detail["created_by"],
        created_at=detail["created_at"],
        member_count=detail["member_count"],
        members=[
            TeamMemberResponse(**m) for m in detail["members"]
        ],
    )


@router.put(
    "/{team_id}",
    response_model=TeamResponse,
    summary="팀 수정",
)
async def update_team(
    team_id: str,
    req: TeamUpdateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TeamResponse:
    """
    팀 이름 또는 설명을 수정합니다.
    admin 역할만 가능합니다.
    """
    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        unprocessable("유효하지 않은 팀 ID 형식입니다")

    # admin 권한 확인
    role = await _team_service.get_user_role(
        session=db, team_id=team_uuid, user_id=current_user.id
    )
    if role != "admin":
        forbidden("팀 수정은 admin만 가능합니다")

    team = await _team_service.update_team(
        session=db,
        team_id=team_uuid,
        name=req.name,
        description=req.description,
    )
    return TeamResponse(
        id=str(team.id),
        name=team.name,
        description=team.description,
        created_by=str(team.created_by),
        created_at=team.created_at,
        member_count=0,  # 수정 응답에서는 별도 집계 생략
    )


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="팀 삭제",
)
async def delete_team(
    team_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    팀을 삭제합니다.
    admin 역할만 가능합니다.
    """
    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        unprocessable("유효하지 않은 팀 ID 형식입니다")

    # admin 권한 확인
    role = await _team_service.get_user_role(
        session=db, team_id=team_uuid, user_id=current_user.id
    )
    if role != "admin":
        forbidden("팀 삭제는 admin만 가능합니다")

    deleted = await _team_service.delete_team(session=db, team_id=team_uuid)
    if not deleted:
        not_found("팀을 찾을 수 없습니다")


# ---------------------------------------------------------------------------
# REQ-TEAM-003: 팀 멤버 관리 엔드포인트
# ---------------------------------------------------------------------------


@router.get(
    "/{team_id}/members",
    response_model=MemberListResponse,
    summary="팀 멤버 목록 조회",
)
async def list_team_members(
    team_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MemberListResponse:
    """
    팀 멤버 목록을 반환합니다.
    팀 멤버라면 누구나 조회 가능합니다.
    """
    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        unprocessable("유효하지 않은 팀 ID 형식입니다")

    # 멤버십 확인
    role = await _team_service.get_user_role(
        session=db, team_id=team_uuid, user_id=current_user.id
    )
    if role is None:
        forbidden("팀에 접근할 권한이 없습니다")

    members = await _team_service.list_members(session=db, team_id=team_uuid)
    items = [TeamMemberResponse(**m) for m in members]
    return MemberListResponse(items=items, total=len(items))


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="팀 멤버 초대",
)
async def add_team_member(
    team_id: str,
    req: MemberInviteRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TeamMemberResponse:
    """
    이메일로 사용자를 팀에 초대합니다.
    admin 역할만 가능합니다.
    """
    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        unprocessable("유효하지 않은 팀 ID 형식입니다")

    # admin 권한 확인
    role = await _team_service.get_user_role(
        session=db, team_id=team_uuid, user_id=current_user.id
    )
    if role != "admin":
        forbidden("멤버 초대는 admin만 가능합니다")

    try:
        member = await _team_service.add_member(
            session=db,
            team_id=team_uuid,
            email=req.email,
            role=req.role,
            invited_by=current_user.id,
        )
    except LookupError as e:
        not_found(str(e))
    except ValueError as e:
        # 이미 멤버이거나 유효하지 않은 역할
        error_msg = str(e)
        if "이미 팀 멤버" in error_msg:
            conflict(error_msg)
        bad_request(error_msg)

    # 멤버 상세 조회 (email, display_name 포함 반환)
    members = await _team_service.list_members(session=db, team_id=team_uuid)
    for m in members:
        if m["user_id"] == str(member.user_id):
            return TeamMemberResponse(**m)

    # 폴백: 최소 정보로 반환
    return TeamMemberResponse(
        user_id=str(member.user_id),
        email=req.email,
        display_name="",
        role=member.role,
        joined_at=member.joined_at,
    )


@router.put(
    "/{team_id}/members/{user_id}",
    response_model=TeamMemberResponse,
    summary="팀 멤버 역할 변경",
)
async def update_member_role(
    team_id: str,
    user_id: str,
    req: MemberRoleUpdateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TeamMemberResponse:
    """
    팀 멤버의 역할을 변경합니다.
    admin만 가능하며, 자신의 역할은 변경할 수 없습니다.
    마지막 admin의 역할은 변경할 수 없습니다.
    """
    try:
        team_uuid = uuid.UUID(team_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        unprocessable("유효하지 않은 ID 형식입니다")

    # admin 권한 확인
    role = await _team_service.get_user_role(
        session=db, team_id=team_uuid, user_id=current_user.id
    )
    if role != "admin":
        forbidden("역할 변경은 admin만 가능합니다")

    try:
        member = await _team_service.update_member_role(
            session=db,
            team_id=team_uuid,
            user_id=user_uuid,
            new_role=req.role,
            requester_id=current_user.id,
        )
    except LookupError as e:
        not_found(str(e))
    except ValueError as e:
        bad_request(str(e))

    # 업데이트된 멤버 상세 조회
    members = await _team_service.list_members(session=db, team_id=team_uuid)
    for m in members:
        if m["user_id"] == str(member.user_id):
            return TeamMemberResponse(**m)

    return TeamMemberResponse(
        user_id=str(member.user_id),
        email="",
        display_name="",
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="팀 멤버 제거 / 팀 탈퇴",
)
async def remove_team_member(
    team_id: str,
    user_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    팀 멤버를 제거하거나 팀에서 탈퇴합니다.
    - admin: 다른 멤버 제거 가능
    - 자기 자신 탈퇴: 역할 무관 허용
    - 마지막 admin은 제거 불가
    """
    try:
        team_uuid = uuid.UUID(team_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        unprocessable("유효하지 않은 ID 형식입니다")

    # 요청자의 역할 확인
    requester_role = await _team_service.get_user_role(
        session=db, team_id=team_uuid, user_id=current_user.id
    )

    # 자기 자신 탈퇴는 허용 (역할 무관)
    is_self_removal = current_user.id == user_uuid

    if not is_self_removal and requester_role != "admin":
        forbidden("멤버 제거는 admin만 가능합니다")

    if requester_role is None and not is_self_removal:
        forbidden("팀에 접근할 권한이 없습니다")

    try:
        await _team_service.remove_member(
            session=db,
            team_id=team_uuid,
            user_id=user_uuid,
            requester_id=current_user.id,
        )
    except LookupError as e:
        not_found(str(e))
    except ValueError as e:
        bad_request(str(e))


# ---------------------------------------------------------------------------
# REQ-TEAM-005: 팀 회의록 목록 엔드포인트
# ---------------------------------------------------------------------------


@router.get(
    "/{team_id}/meetings",
    response_model=MeetingListResponse,
    summary="팀 공유 회의록 목록 조회",
)
async def list_team_meetings(
    team_id: str,
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    page_size: int = Query(default=20, ge=1, le=100, description="페이지당 항목 수"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MeetingListResponse:
    """
    팀에 공유된 회의록 목록을 반환합니다.
    팀 멤버라면 누구나 조회 가능합니다.
    """
    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        unprocessable("유효하지 않은 팀 ID 형식입니다")

    # 멤버십 확인 (모든 역할 허용)
    role = await _team_service.get_user_role(
        session=db, team_id=team_uuid, user_id=current_user.id
    )
    if role is None:
        forbidden("팀에 접근할 권한이 없습니다")

    result = await _meeting_service.list_team_meetings(
        session=db,
        team_id=team_uuid,
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
