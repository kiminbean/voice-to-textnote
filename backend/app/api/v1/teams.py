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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.team_service import TeamService
from backend.schemas.team import (
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
        raise HTTPException(status_code=422, detail="유효하지 않은 팀 ID 형식입니다")

    # 멤버십 확인
    role = await _team_service.get_user_role(
        session=db, team_id=team_uuid, user_id=current_user.id
    )
    if role is None:
        raise HTTPException(status_code=403, detail="팀에 접근할 권한이 없습니다")

    detail = await _team_service.get_team_with_members(session=db, team_id=team_uuid)
    if detail is None:
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다")

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
        raise HTTPException(status_code=422, detail="유효하지 않은 팀 ID 형식입니다")

    # admin 권한 확인
    role = await _team_service.get_user_role(
        session=db, team_id=team_uuid, user_id=current_user.id
    )
    if role != "admin":
        raise HTTPException(status_code=403, detail="팀 수정은 admin만 가능합니다")

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
        raise HTTPException(status_code=422, detail="유효하지 않은 팀 ID 형식입니다")

    # admin 권한 확인
    role = await _team_service.get_user_role(
        session=db, team_id=team_uuid, user_id=current_user.id
    )
    if role != "admin":
        raise HTTPException(status_code=403, detail="팀 삭제는 admin만 가능합니다")

    deleted = await _team_service.delete_team(session=db, team_id=team_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다")
