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
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.dependencies import get_db_session, get_current_user

    async def mock_db_session():
        yield AsyncMock()

    async def mock_admin_user():
        return admin_user

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_admin_user

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 팀 생성 테스트
# ---------------------------------------------------------------------------


def test_create_team_201(team_client, admin_user):
    """팀 생성 성공 시 201 + TeamResponse 반환"""
    team = _make_team(creator_id=admin_user.id)

    with patch("backend.app.api.v1.teams._team_service") as mock_svc:
        mock_svc.create_team = AsyncMock(return_value=team)
        mock_svc.list_user_teams = AsyncMock(return_value=[{
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "created_by": str(team.created_by),
            "created_at": team.created_at,
            "member_count": 1,
        }])
        response = team_client.post(
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
    """팀 목록 조회 성공"""
    team = _make_team(creator_id=admin_user.id)

    with patch("backend.app.api.v1.teams._team_service") as mock_svc:
        mock_svc.list_user_teams = AsyncMock(return_value=[{
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "created_by": str(team.created_by),
            "created_at": team.created_at,
            "member_count": 1,
        }])
        response = team_client.get("/api/v1/teams")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# 팀 상세 조회 테스트
# ---------------------------------------------------------------------------


def test_get_team_detail(team_client, admin_user):
    """팀 상세 조회 성공"""
    team = _make_team(creator_id=admin_user.id)
    team_id = str(team.id)

    with patch("backend.app.api.v1.teams._team_service") as mock_svc:
        mock_svc.get_user_role = AsyncMock(return_value="admin")
        mock_svc.get_team_with_members = AsyncMock(return_value={
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "created_by": str(team.created_by),
            "created_at": team.created_at,
            "member_count": 1,
            "members": [{
                "user_id": str(admin_user.id),
                "email": admin_user.email,
                "display_name": admin_user.display_name,
                "role": "admin",
                "joined_at": datetime.now(UTC).replace(tzinfo=None),
            }],
        })
        response = team_client.get(f"/api/v1/teams/{team_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "개발팀"
    assert len(data["members"]) == 1


# ---------------------------------------------------------------------------
# 팀 수정 테스트
# ---------------------------------------------------------------------------


def test_update_team_admin_only(team_client, admin_user):
    """admin이 팀 수정 성공"""
    team = _make_team(creator_id=admin_user.id)
    team.name = "수정된 팀명"
    team_id = str(team.id)

    with patch("backend.app.api.v1.teams._team_service") as mock_svc:
        mock_svc.get_user_role = AsyncMock(return_value="admin")
        mock_svc.update_team = AsyncMock(return_value=team)
        response = team_client.put(
            f"/api/v1/teams/{team_id}",
            json={"name": "수정된 팀명"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "수정된 팀명"


def test_update_team_non_admin_403(admin_user):
    """non-admin 사용자가 팀 수정 시도 시 403"""
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.dependencies import get_db_session, get_current_user

    non_admin = _make_user("member")

    async def mock_db_session():
        yield AsyncMock()

    async def mock_member_user():
        return non_admin

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_member_user

    team_id = str(uuid.uuid4())

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    client = TestClient(app, raise_server_exceptions=False)
                    with patch("backend.app.api.v1.teams._team_service") as mock_svc:
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
    """admin이 팀 삭제 성공 시 204"""
    team_id = str(uuid.uuid4())

    with patch("backend.app.api.v1.teams._team_service") as mock_svc:
        mock_svc.get_user_role = AsyncMock(return_value="admin")
        mock_svc.delete_team = AsyncMock(return_value=True)
        response = team_client.delete(f"/api/v1/teams/{team_id}")

    assert response.status_code == 204


def test_delete_team_non_admin_403(admin_user):
    """non-admin 사용자가 팀 삭제 시도 시 403"""
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.dependencies import get_db_session, get_current_user

    non_admin = _make_user("viewer")

    async def mock_db_session():
        yield AsyncMock()

    async def mock_viewer_user():
        return non_admin

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_viewer_user

    team_id = str(uuid.uuid4())

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    client = TestClient(app, raise_server_exceptions=False)
                    with patch("backend.app.api.v1.teams._team_service") as mock_svc:
                        mock_svc.get_user_role = AsyncMock(return_value="viewer")
                        response = client.delete(f"/api/v1/teams/{team_id}")

    app.dependency_overrides.clear()
    assert response.status_code == 403
