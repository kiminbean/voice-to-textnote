"""
SPEC-TEAM-001: Team API 엔드포인트 단위 테스트 (TDD RED Phase)

테스트 대상:
- POST   /api/v1/teams         - 팀 생성
- GET    /api/v1/teams         - 팀 목록
- GET    /api/v1/teams/{id}    - 팀 상세
- PUT    /api/v1/teams/{id}    - 팀 수정 (admin 전용)
- DELETE /api/v1/teams/{id}    - 팀 삭제 (admin 전용)
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------


def _make_user(role: str = "admin"):
    """테스트용 User mock"""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = f"{role}@example.com"
    user.display_name = f"{role} 사용자"
    user.is_active = True
    user.created_at = datetime.now(UTC).replace(tzinfo=None)
    return user


def _make_team(creator_id=None):
    """테스트용 Team mock"""
    team = MagicMock()
    team.id = uuid.uuid4()
    team.name = "개발팀"
    team.description = "백엔드 팀"
    team.created_by = creator_id or uuid.uuid4()
    team.created_at = datetime.now(UTC).replace(tzinfo=None)
    team.updated_at = datetime.now(UTC).replace(tzinfo=None)
    return team


@pytest.fixture
def admin_user():
    return _make_user("admin")


@pytest.fixture
def member_user():
    return _make_user("member")


@pytest.fixture
def team_client(admin_user):
    """
    팀 API 테스트용 TestClient
    - admin_user로 인증된 상태
    """
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    async def mock_db_session():
        yield AsyncMock()

    async def mock_admin_user():
        return admin_user

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_admin_user

    from backend.app.api.v1.teams import get_team_service

    svc_mock = AsyncMock()

    async def override_svc():
        return svc_mock

    app.dependency_overrides[get_team_service] = override_svc

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield TestClient(app, raise_server_exceptions=False), svc_mock

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 팀 생성 테스트
# ---------------------------------------------------------------------------


def test_create_team_201(team_client, admin_user):
    client, mock_svc = team_client
    """팀 생성 성공 시 201 + TeamResponse 반환"""
    team = _make_team(creator_id=admin_user.id)

    mock_svc.create_team = AsyncMock(return_value=team)
    mock_svc.list_user_teams = AsyncMock(
        return_value=[
            {
                "id": team.id,
                "name": team.name,
                "description": team.description,
                "created_by": str(team.created_by),
                "created_at": team.created_at,
                "member_count": 1,
            }
        ]
    )
    response = client.post(
        "/api/v1/teams",
        json={"name": "개발팀", "description": "백엔드 팀"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "개발팀"


# ---------------------------------------------------------------------------
# 팀 목록 테스트
# ---------------------------------------------------------------------------


def test_list_teams(team_client, admin_user):
    client, mock_svc = team_client
    """팀 목록 조회 성공"""
    team = _make_team(creator_id=admin_user.id)

    mock_svc.list_user_teams = AsyncMock(
        return_value=[
            {
                "id": team.id,
                "name": team.name,
                "description": team.description,
                "created_by": str(team.created_by),
                "created_at": team.created_at,
                "member_count": 1,
            }
        ]
    )
    response = client.get("/api/v1/teams")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# 팀 상세 조회 테스트
# ---------------------------------------------------------------------------


def test_get_team_detail(team_client, admin_user):
    client, mock_svc = team_client
    """팀 상세 조회 성공"""
    team = _make_team(creator_id=admin_user.id)
    team_id = str(team.id)

    mock_svc.get_user_role = AsyncMock(return_value="admin")
    mock_svc.get_team_with_members = AsyncMock(
        return_value={
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "created_by": str(team.created_by),
            "created_at": team.created_at,
            "member_count": 1,
            "members": [
                {
                    "user_id": str(admin_user.id),
                    "email": admin_user.email,
                    "display_name": admin_user.display_name,
                    "role": "admin",
                    "joined_at": datetime.now(UTC).replace(tzinfo=None),
                }
            ],
        }
    )
    response = client.get(f"/api/v1/teams/{team_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "개발팀"
    assert len(data["members"]) == 1


# ---------------------------------------------------------------------------
# 팀 수정 테스트
# ---------------------------------------------------------------------------


def test_update_team_admin_only(team_client, admin_user):
    client, mock_svc = team_client
    """admin이 팀 수정 성공"""
    team = _make_team(creator_id=admin_user.id)
    team.name = "수정된 팀명"
    team_id = str(team.id)

    mock_svc.get_user_role = AsyncMock(return_value="admin")
    mock_svc.update_team = AsyncMock(return_value=team)
    response = client.put(
        f"/api/v1/teams/{team_id}",
        json={"name": "수정된 팀명"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "수정된 팀명"


def test_update_team_non_admin_403(admin_user):
    from backend.app.api.v1.teams import get_team_service
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    non_admin = _make_user("member")

    async def mock_db_session():
        yield AsyncMock()

    async def mock_member_user():
        return non_admin

    mock_svc = AsyncMock()

    async def override_svc():
        return mock_svc

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_member_user
    app.dependency_overrides[get_team_service] = override_svc

    team_id = str(uuid.uuid4())

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    client = TestClient(app, raise_server_exceptions=False)
                    mock_svc.get_user_role = AsyncMock(return_value="member")
                    response = client.put(
                        f"/api/v1/teams/{team_id}",
                        json={"name": "수정 시도"},
                    )

    app.dependency_overrides.clear()
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 팀 삭제 테스트
# ---------------------------------------------------------------------------


def test_delete_team_admin_only(team_client, admin_user):
    client, mock_svc = team_client
    """admin이 팀 삭제 성공 시 204"""
    team_id = str(uuid.uuid4())

    mock_svc.get_user_role = AsyncMock(return_value="admin")
    mock_svc.delete_team = AsyncMock(return_value=True)
    response = client.delete(f"/api/v1/teams/{team_id}")

    assert response.status_code == 204


def test_delete_team_non_admin_403(admin_user):
    from backend.app.api.v1.teams import get_team_service
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    non_admin = _make_user("viewer")

    async def mock_db_session():
        yield AsyncMock()

    async def mock_viewer_user():
        return non_admin

    mock_svc = AsyncMock()

    async def override_svc():
        return mock_svc

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_viewer_user
    app.dependency_overrides[get_team_service] = override_svc

    team_id = str(uuid.uuid4())

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    client = TestClient(app, raise_server_exceptions=False)
                    mock_svc.get_user_role = AsyncMock(return_value="viewer")
                    response = client.delete(f"/api/v1/teams/{team_id}")

    app.dependency_overrides.clear()
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# REQ-TEAM-003: 팀 멤버 관리 API 테스트
# ---------------------------------------------------------------------------


def _make_member_dict(user_id=None, email="member@example.com", display_name="멤버", role="member"):
    """TeamMemberResponse 딕셔너리 생성 헬퍼"""
    return {
        "user_id": str(user_id or uuid.uuid4()),
        "email": email,
        "display_name": display_name,
        "role": role,
        "joined_at": datetime.now(UTC).replace(tzinfo=None),
    }


def test_list_team_members_200(team_client, admin_user):
    client, mock_svc = team_client
    """팀 멤버 목록 조회 성공 (200)"""
    team_id = str(uuid.uuid4())
    member_dict = _make_member_dict(
        user_id=admin_user.id,
        email=admin_user.email,
        display_name=admin_user.display_name,
        role="admin",
    )

    mock_svc.get_user_role = AsyncMock(return_value="admin")
    mock_svc.list_members = AsyncMock(return_value=[member_dict])
    response = client.get(f"/api/v1/teams/{team_id}/members")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["role"] == "admin"


def test_list_team_members_403_non_member(team_client):
    client, mock_svc = team_client
    """비멤버의 팀 멤버 목록 조회 시 403"""
    team_id = str(uuid.uuid4())

    mock_svc.get_user_role = AsyncMock(return_value=None)
    response = client.get(f"/api/v1/teams/{team_id}/members")

    assert response.status_code == 403


def test_add_team_member_201(team_client, admin_user):
    client, mock_svc = team_client
    """admin이 멤버 초대 성공 (201)"""
    team_id = str(uuid.uuid4())
    new_user_id = uuid.uuid4()
    new_member_dict = _make_member_dict(
        user_id=new_user_id,
        email="new@example.com",
        display_name="새 멤버",
        role="member",
    )

    mock_svc.get_user_role = AsyncMock(return_value="admin")

    # add_member가 반환하는 TeamMember mock
    added_member = MagicMock()
    added_member.user_id = new_user_id
    added_member.role = "member"
    added_member.team_id = uuid.UUID(team_id)
    added_member.joined_at = datetime.now(UTC).replace(tzinfo=None)
    mock_svc.add_member = AsyncMock(return_value=added_member)

    # 이후 list_members에서 상세 정보 반환
    mock_svc.list_members = AsyncMock(return_value=[new_member_dict])

    response = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"email": "new@example.com", "role": "member"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@example.com"
    assert data["role"] == "member"


def test_add_team_member_404_user_not_found(team_client):
    client, mock_svc = team_client
    """존재하지 않는 이메일 초대 시 404"""
    team_id = str(uuid.uuid4())

    mock_svc.get_user_role = AsyncMock(return_value="admin")
    mock_svc.add_member = AsyncMock(
        side_effect=LookupError("이메일 'ghost@example.com'에 해당하는 사용자를 찾을 수 없습니다")
    )
    response = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"email": "ghost@example.com", "role": "member"},
    )

    assert response.status_code == 404


def test_add_team_member_409_already_member(team_client):
    client, mock_svc = team_client
    """이미 멤버인 사용자 초대 시 409"""
    team_id = str(uuid.uuid4())

    mock_svc.get_user_role = AsyncMock(return_value="admin")
    mock_svc.add_member = AsyncMock(side_effect=ValueError("이미 팀 멤버입니다"))
    response = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"email": "existing@example.com", "role": "member"},
    )

    assert response.status_code == 409


def test_add_team_member_403_non_admin(team_client):
    client, mock_svc = team_client
    """non-admin이 멤버 초대 시도 시 403"""
    team_id = str(uuid.uuid4())

    mock_svc.get_user_role = AsyncMock(return_value="member")
    response = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"email": "someone@example.com", "role": "viewer"},
    )

    assert response.status_code == 403


def test_update_member_role_200(team_client, admin_user):
    client, mock_svc = team_client
    """admin이 멤버 역할 변경 성공 (200)"""
    team_id = str(uuid.uuid4())
    target_user_id = uuid.uuid4()
    updated_member_dict = _make_member_dict(
        user_id=target_user_id,
        email="target@example.com",
        display_name="대상 멤버",
        role="admin",
    )

    mock_svc.get_user_role = AsyncMock(return_value="admin")

    updated_member = MagicMock()
    updated_member.user_id = target_user_id
    updated_member.role = "admin"
    updated_member.joined_at = datetime.now(UTC).replace(tzinfo=None)
    mock_svc.update_member_role = AsyncMock(return_value=updated_member)
    mock_svc.list_members = AsyncMock(return_value=[updated_member_dict])

    response = client.put(
        f"/api/v1/teams/{team_id}/members/{target_user_id}",
        json={"role": "admin"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"


def test_update_member_role_400_cannot_change_own(team_client, admin_user):
    client, mock_svc = team_client
    """자신의 역할 변경 시도 시 400"""
    team_id = str(uuid.uuid4())

    mock_svc.get_user_role = AsyncMock(return_value="admin")
    mock_svc.update_member_role = AsyncMock(
        side_effect=ValueError("자신의 역할은 변경할 수 없습니다")
    )
    response = client.put(
        f"/api/v1/teams/{team_id}/members/{admin_user.id}",
        json={"role": "member"},
    )

    assert response.status_code == 400


def test_update_member_role_400_last_admin(team_client):
    client, mock_svc = team_client
    """마지막 admin 역할 변경 시도 시 400"""
    team_id = str(uuid.uuid4())
    target_user_id = uuid.uuid4()

    mock_svc.get_user_role = AsyncMock(return_value="admin")
    mock_svc.update_member_role = AsyncMock(
        side_effect=ValueError("마지막 admin의 역할은 변경할 수 없습니다")
    )
    response = client.put(
        f"/api/v1/teams/{team_id}/members/{target_user_id}",
        json={"role": "member"},
    )

    assert response.status_code == 400


def test_remove_team_member_204(team_client, admin_user):
    client, mock_svc = team_client
    """admin이 멤버 제거 성공 (204)"""
    team_id = str(uuid.uuid4())
    target_user_id = uuid.uuid4()

    mock_svc.get_user_role = AsyncMock(return_value="admin")
    mock_svc.remove_member = AsyncMock(return_value=True)
    response = client.delete(f"/api/v1/teams/{team_id}/members/{target_user_id}")

    assert response.status_code == 204


def test_remove_team_member_400_last_admin(team_client, admin_user):
    client, mock_svc = team_client
    """마지막 admin 제거 시도 시 400"""
    team_id = str(uuid.uuid4())

    mock_svc.get_user_role = AsyncMock(return_value="admin")
    mock_svc.remove_member = AsyncMock(
        side_effect=ValueError(
            "마지막 admin은 팀에서 나갈 수 없습니다. 다른 admin을 먼저 지정해주세요"
        )
    )
    response = client.delete(f"/api/v1/teams/{team_id}/members/{admin_user.id}")

    assert response.status_code == 400


def test_remove_team_member_403_non_admin(team_client, admin_user):
    client, mock_svc = team_client
    from backend.app.api.v1.teams import get_team_service
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    non_admin = _make_user("member")

    async def mock_db_session():
        yield AsyncMock()

    async def mock_member_user():
        return non_admin

    mock_svc_local = AsyncMock()

    async def override_svc():
        return mock_svc_local

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_member_user
    app.dependency_overrides[get_team_service] = override_svc

    team_id = str(uuid.uuid4())
    other_user_id = str(uuid.uuid4())

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    client = TestClient(app, raise_server_exceptions=False)
                    mock_svc_local.get_user_role = AsyncMock(return_value="member")
                    response = client.delete(f"/api/v1/teams/{team_id}/members/{other_user_id}")

    app.dependency_overrides.clear()
    assert response.status_code == 403
