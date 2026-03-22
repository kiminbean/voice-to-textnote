"""
SPEC-TEAM-001: TeamService 단위 테스트 (TDD RED Phase)

REQ-TEAM-001: 팀 생성 - creator가 admin으로 자동 등록
REQ-TEAM-002: 팀 목록 - 사용자가 속한 팀 조회
REQ-TEAM-003: 팀 상세 조회 (멤버 포함)
REQ-TEAM-004: 팀 수정 (admin만)
REQ-TEAM-005: 팀 삭제 (admin만)
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.auth_models import Team, TeamMember, User


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def team_service():
    """TeamService 인스턴스"""
    from backend.db.team_service import TeamService
    return TeamService()


@pytest.fixture
def mock_session():
    """SQLAlchemy AsyncSession mock"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_user() -> User:
    """테스트용 User"""
    user = User()
    user.id = uuid.uuid4()
    user.email = "creator@example.com"
    user.display_name = "팀장"
    user.is_active = True
    return user


@pytest.fixture
def sample_team(sample_user) -> Team:
    """테스트용 Team"""
    team = Team()
    team.id = uuid.uuid4()
    team.name = "개발팀"
    team.description = "백엔드 개발 팀"
    team.created_by = sample_user.id
    team.created_at = datetime.now(UTC).replace(tzinfo=None)
    team.updated_at = datetime.now(UTC).replace(tzinfo=None)
    return team


@pytest.fixture
def sample_member(sample_user, sample_team) -> TeamMember:
    """팀 admin 멤버"""
    member = TeamMember()
    member.id = uuid.uuid4()
    member.team_id = sample_team.id
    member.user_id = sample_user.id
    member.role = "admin"
    member.joined_at = datetime.now(UTC).replace(tzinfo=None)
    return member


# ---------------------------------------------------------------------------
# 팀 생성 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_team_with_admin_member(team_service, mock_session, sample_user):
    """
    팀 생성 시 Team과 TeamMember(admin)가 함께 생성된다
    REQ-TEAM-001
    """
    team = await team_service.create_team(
        session=mock_session,
        name="새 팀",
        description="팀 설명",
        creator_id=sample_user.id,
    )

    assert isinstance(team, Team)
    assert team.name == "새 팀"
    assert team.description == "팀 설명"
    assert team.created_by == sample_user.id
    # Team + TeamMember 2번 add
    assert mock_session.add.call_count == 2
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_team_adds_admin_role(team_service, mock_session, sample_user):
    """생성자가 admin 역할로 팀에 추가된다"""
    await team_service.create_team(
        session=mock_session,
        name="팀",
        description=None,
        creator_id=sample_user.id,
    )

    # add 호출된 두 번째 인수가 TeamMember이고 role이 admin
    calls = mock_session.add.call_args_list
    assert len(calls) == 2
    member_arg = calls[1][0][0]  # 두 번째 add 호출의 첫 번째 인수
    assert isinstance(member_arg, TeamMember)
    assert member_arg.role == "admin"
    assert member_arg.user_id == sample_user.id


# ---------------------------------------------------------------------------
# 팀 목록 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_user_teams(team_service, mock_session, sample_user, sample_team, sample_member):
    """사용자가 속한 팀 목록을 반환한다 REQ-TEAM-002"""
    # 팀 조회 결과 mock
    mock_result = MagicMock()
    mock_result.all.return_value = [(sample_team, 1)]  # (Team, member_count)
    mock_session.execute.return_value = mock_result

    teams = await team_service.list_user_teams(
        session=mock_session,
        user_id=sample_user.id,
    )

    assert len(teams) == 1
    assert teams[0]["id"] == sample_team.id
    assert teams[0]["name"] == "개발팀"
    assert teams[0]["member_count"] == 1


# ---------------------------------------------------------------------------
# 팀 상세 조회 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_team(team_service, mock_session, sample_team):
    """팀 ID로 팀을 조회한다"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_team
    mock_session.execute.return_value = mock_result

    team = await team_service.get_team(
        session=mock_session,
        team_id=sample_team.id,
    )

    assert team is not None
    assert team.id == sample_team.id


@pytest.mark.asyncio
async def test_get_team_detail(team_service, mock_session, sample_team, sample_user, sample_member):
    """팀 상세 조회 시 멤버 목록 포함"""
    # 팀 조회
    mock_result_team = MagicMock()
    mock_result_team.scalar_one_or_none.return_value = sample_team

    # 멤버 조회 (user + member join)
    mock_result_members = MagicMock()
    mock_result_members.all.return_value = [(sample_user, sample_member)]

    mock_session.execute.side_effect = [mock_result_team, mock_result_members]

    detail = await team_service.get_team_with_members(
        session=mock_session,
        team_id=sample_team.id,
    )

    assert detail is not None
    assert detail["id"] == sample_team.id
    assert len(detail["members"]) == 1
    assert detail["members"][0]["role"] == "admin"


# ---------------------------------------------------------------------------
# 팀 수정 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_team(team_service, mock_session, sample_team):
    """팀 이름/설명 수정"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_team
    mock_session.execute.return_value = mock_result

    updated = await team_service.update_team(
        session=mock_session,
        team_id=sample_team.id,
        name="수정된 팀명",
        description="새 설명",
    )

    assert updated.name == "수정된 팀명"
    assert updated.description == "새 설명"
    mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# 팀 삭제 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_team(team_service, mock_session, sample_team):
    """팀 삭제 성공 시 True 반환"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_team
    mock_session.execute.return_value = mock_result

    result = await team_service.delete_team(
        session=mock_session,
        team_id=sample_team.id,
    )

    assert result is True
    mock_session.delete.assert_called_once_with(sample_team)
    mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# 역할 조회 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_role(team_service, mock_session, sample_team, sample_user, sample_member):
    """사용자의 팀 역할 반환"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_member
    mock_session.execute.return_value = mock_result

    role = await team_service.get_user_role(
        session=mock_session,
        team_id=sample_team.id,
        user_id=sample_user.id,
    )

    assert role == "admin"


@pytest.mark.asyncio
async def test_get_user_role_not_member(team_service, mock_session, sample_team):
    """팀 멤버가 아닌 경우 None 반환"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    role = await team_service.get_user_role(
        session=mock_session,
        team_id=sample_team.id,
        user_id=uuid.uuid4(),  # 존재하지 않는 user_id
    )

    assert role is None
