"""
SPEC-TEAM-001: Teams API v2 테스트
커버되지 않은 라인을 위한 추가 테스트

커버되지 않은 라인:
- 116-117, 124, 128: get_team - UUID 변환 실패, 권한 없음, 팀 없음
- 160-161, 202-203: update_team, delete_team - UUID 변환 실패
- 214: delete_team - 팀을 찾을 수 없음
- 238-239: list_team_members - UUID 변환 실패
- 271-272, 296, 305: add_team_member - UUID 변환 실패, 이미 멤버, 폴백
- 334-335, 342, 353, 363: update_member_role - UUID 변환, 권한, 사용자 없음, 폴백
- 392-393, 407, 417: remove_team_member - UUID 변환, 권한, 값 오류
- 443-462: list_team_meetings - 전체 엔드포인트
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.db.auth_models import User


@pytest.fixture
def teams_client():
    from backend.app.api.v1.teams import get_meeting_share_service, get_team_service
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    async def mock_db_session():
        yield AsyncMock()

    async def mock_current_user():
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.email = "admin@example.com"
        mock_user.is_active = True
        yield mock_user

    team_svc_mock = AsyncMock()
    meeting_svc_mock = AsyncMock()

    async def override_team_svc():
        return team_svc_mock

    async def override_meeting_svc():
        return meeting_svc_mock

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_current_user
    app.dependency_overrides[get_team_service] = override_team_svc
    app.dependency_overrides[get_meeting_share_service] = override_meeting_svc

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield (
                        TestClient(app, raise_server_exceptions=False),
                        team_svc_mock,
                        meeting_svc_mock,
                    )

    app.dependency_overrides.clear()


class TestGetTeamEndpointEdgeCases:
    def test_get_team_invalid_uuid(self, teams_client) -> None:
        client, _, _ = teams_client
        response = client.get("/api/v1/teams/invalid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["message"]

    def test_get_team_not_member(self, teams_client) -> None:
        client, team_svc_mock, _ = teams_client
        team_id = str(uuid.uuid4())
        team_svc_mock.get_user_role = AsyncMock(return_value=None)
        response = client.get(f"/api/v1/teams/{team_id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "팀에 접근할 권한이 없습니다" in response.json()["message"]

    def test_get_team_not_found(self, teams_client) -> None:
        client, team_svc_mock, _ = teams_client
        team_id = str(uuid.uuid4())
        team_svc_mock.get_user_role = AsyncMock(return_value="admin")
        team_svc_mock.get_team_with_members = AsyncMock(return_value=None)
        response = client.get(f"/api/v1/teams/{team_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "팀을 찾을 수 없습니다" in response.json()["message"]


class TestUpdateTeamEndpointEdgeCases:
    def test_update_team_invalid_uuid(self, teams_client) -> None:
        client, _, _ = teams_client
        response = client.put("/api/v1/teams/invalid-uuid", json={"name": "Updated Name"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["message"]


class TestDeleteTeamEndpointEdgeCases:
    def test_delete_team_invalid_uuid(self, teams_client) -> None:
        client, _, _ = teams_client
        response = client.delete("/api/v1/teams/invalid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["message"]

    def test_delete_team_not_found(self, teams_client) -> None:
        client, team_svc_mock, _ = teams_client
        team_id = str(uuid.uuid4())
        team_svc_mock.get_user_role = AsyncMock(return_value="admin")
        team_svc_mock.delete_team = AsyncMock(return_value=False)
        response = client.delete(f"/api/v1/teams/{team_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "팀을 찾을 수 없습니다" in response.json()["message"]


class TestListTeamMembersEndpointEdgeCases:
    def test_list_team_members_invalid_uuid(self, teams_client) -> None:
        client, _, _ = teams_client
        response = client.get("/api/v1/teams/invalid-uuid/members")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["message"]


class TestAddTeamMemberEndpointEdgeCases:
    def test_add_team_member_invalid_uuid(self, teams_client) -> None:
        client, _, _ = teams_client
        response = client.post(
            "/api/v1/teams/invalid-uuid/members",
            json={"email": "new@example.com", "role": "member"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["message"]

    def test_add_team_member_already_exists(self, teams_client) -> None:
        client, team_svc_mock, _ = teams_client
        team_id = str(uuid.uuid4())
        team_svc_mock.get_user_role = AsyncMock(return_value="admin")
        team_svc_mock.add_member = AsyncMock(side_effect=ValueError("이미 팀 멤버입니다"))
        response = client.post(
            f"/api/v1/teams/{team_id}/members",
            json={"email": "existing@example.com", "role": "member"},
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "이미 팀 멤버" in response.json()["message"]

    def test_add_team_member_fallback_response(self, teams_client) -> None:
        client, team_svc_mock, _ = teams_client
        team_id = str(uuid.uuid4())
        mock_member = MagicMock()
        mock_member.user_id = uuid.uuid4()
        mock_member.role = "member"
        mock_member.joined_at = "2024-01-01T00:00:00Z"
        team_svc_mock.get_user_role = AsyncMock(return_value="admin")
        team_svc_mock.add_member = AsyncMock(return_value=mock_member)
        team_svc_mock.list_members = AsyncMock(return_value=[])
        response = client.post(
            f"/api/v1/teams/{team_id}/members", json={"email": "new@example.com", "role": "member"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["display_name"] == ""


class TestUpdateMemberRoleEndpointEdgeCases:
    def test_update_member_role_invalid_uuid(self, teams_client) -> None:
        client, _, _ = teams_client
        team_id = str(uuid.uuid4())
        response = client.put(
            f"/api/v1/teams/{team_id}/members/invalid-uuid", json={"role": "admin"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 ID 형식입니다" in response.json()["message"]

    def test_update_member_role_non_admin(self, teams_client) -> None:
        client, team_svc_mock, _ = teams_client
        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        team_svc_mock.get_user_role = AsyncMock(return_value="member")
        response = client.put(f"/api/v1/teams/{team_id}/members/{user_id}", json={"role": "admin"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "역할 변경은 admin만 가능합니다" in response.json()["message"]

    def test_update_member_role_user_not_found(self, teams_client) -> None:
        client, team_svc_mock, _ = teams_client
        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        team_svc_mock.get_user_role = AsyncMock(return_value="admin")
        team_svc_mock.update_member_role = AsyncMock(
            side_effect=LookupError("사용자를 찾을 수 없습니다")
        )
        response = client.put(f"/api/v1/teams/{team_id}/members/{user_id}", json={"role": "admin"})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "사용자를 찾을 수 없습니다" in response.json()["message"]

    def test_update_member_role_fallback_response(self, teams_client) -> None:
        client, team_svc_mock, _ = teams_client
        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        mock_member = MagicMock()
        mock_member.user_id = uuid.UUID(user_id)
        mock_member.role = "admin"
        mock_member.joined_at = "2024-01-01T00:00:00Z"
        team_svc_mock.get_user_role = AsyncMock(return_value="admin")
        team_svc_mock.update_member_role = AsyncMock(return_value=mock_member)
        team_svc_mock.list_members = AsyncMock(return_value=[])
        response = client.put(f"/api/v1/teams/{team_id}/members/{user_id}", json={"role": "admin"})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == ""
        assert data["display_name"] == ""


class TestRemoveTeamMemberEndpointEdgeCases:
    def test_remove_team_member_invalid_uuid(self, teams_client) -> None:
        client, _, _ = teams_client
        team_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/teams/{team_id}/members/invalid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 ID 형식입니다" in response.json()["message"]

    def test_remove_team_member_no_permission(self, teams_client) -> None:
        client, team_svc_mock, _ = teams_client
        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        team_svc_mock.get_user_role = AsyncMock(return_value="member")
        response = client.delete(f"/api/v1/teams/{team_id}/members/{user_id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "멤버 제거는 admin만 가능합니다" in response.json()["message"]

    def test_remove_team_member_value_error(self, teams_client) -> None:
        client, team_svc_mock, _ = teams_client
        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        team_svc_mock.get_user_role = AsyncMock(return_value="admin")
        team_svc_mock.remove_member = AsyncMock(
            side_effect=ValueError("마지막 admin은 제거할 수 없습니다")
        )
        response = client.delete(f"/api/v1/teams/{team_id}/members/{user_id}")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "마지막 admin은 제거할 수 없습니다" in response.json()["message"]


class TestListTeamMeetingsEndpoint:
    def test_list_team_meetings_success(self, teams_client) -> None:
        client, team_svc_mock, meeting_svc_mock = teams_client
        team_id = str(uuid.uuid4())
        mock_result = {
            "items": [
                {
                    "task_id": str(uuid.uuid4()),
                    "task_type": "meeting",
                    "status": "completed",
                    "owner_id": str(uuid.uuid4()),
                    "team_id": team_id,
                    "shared_at": "2024-01-01T00:00:00Z",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
        }
        team_svc_mock.get_user_role = AsyncMock(return_value="member")
        meeting_svc_mock.list_team_meetings = AsyncMock(return_value=mock_result)
        response = client.get(f"/api/v1/teams/{team_id}/meetings?page=1&page_size=20")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert len(data["items"]) == 1

    def test_list_team_meetings_invalid_uuid(self, teams_client) -> None:
        client, _, _ = teams_client
        response = client.get("/api/v1/teams/invalid-uuid/meetings")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["message"]

    def test_list_team_meetings_not_member(self, teams_client) -> None:
        client, team_svc_mock, _ = teams_client
        team_id = str(uuid.uuid4())
        team_svc_mock.get_user_role = AsyncMock(return_value=None)
        response = client.get(f"/api/v1/teams/{team_id}/meetings")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "팀에 접근할 권한이 없습니다" in response.json()["message"]
