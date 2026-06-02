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

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def teams_client():
    """팀 API 테스트용 TestClient"""
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

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_current_user

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# get_team 엔드포인트 테스트 (라인 100-140)
# ---------------------------------------------------------------------------


class TestGetTeamEndpointEdgeCases:
    """팀 상세 조회 엔드포인트 엣지 케이스 테스트"""

    def test_get_team_invalid_uuid(self, teams_client) -> None:
        """잘못된 UUID 형식 (라인 116-117 커버)"""
        response = teams_client.get("/api/v1/teams/invalid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["detail"]

    def test_get_team_not_member(self, teams_client) -> None:
        """팀 멤버가 아님 (라인 124 커버)"""
        from backend.app.api.v1 import teams

        team_id = str(uuid.uuid4())
        with patch.object(teams._team_service, "get_user_role", return_value=None):
            response = teams_client.get(f"/api/v1/teams/{team_id}")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "팀에 접근할 권한이 없습니다" in response.json()["detail"]

    def test_get_team_not_found(self, teams_client) -> None:
        """팀을 찾을 수 없음 (라인 128 커버)"""
        from backend.app.api.v1 import teams

        team_id = str(uuid.uuid4())
        with patch.object(teams._team_service, "get_user_role", return_value="admin"):
            with patch.object(teams._team_service, "get_team_with_members", return_value=None):
                response = teams_client.get(f"/api/v1/teams/{team_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "팀을 찾을 수 없습니다" in response.json()["detail"]


# ---------------------------------------------------------------------------
# update_team 엔드포인트 테스트 (라인 143-183)
# ---------------------------------------------------------------------------


class TestUpdateTeamEndpointEdgeCases:
    """팀 수정 엔드포인트 엣지 케이스 테스트"""

    def test_update_team_invalid_uuid(self, teams_client) -> None:
        """잘못된 UUID 형식 (라인 160-161 커버)"""
        response = teams_client.put(
            "/api/v1/teams/invalid-uuid",
            json={"name": "Updated Name"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["detail"]


# ---------------------------------------------------------------------------
# delete_team 엔드포인트 테스트 (라인 186-215)
# ---------------------------------------------------------------------------


class TestDeleteTeamEndpointEdgeCases:
    """팀 삭제 엔드포인트 엣지 케이스 테스트"""

    def test_delete_team_invalid_uuid(self, teams_client) -> None:
        """잘못된 UUID 형식 (라인 202-203 커버)"""
        response = teams_client.delete("/api/v1/teams/invalid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["detail"]

    def test_delete_team_not_found(self, teams_client) -> None:
        """팀을 찾을 수 없음 (라인 214 커버)"""
        from backend.app.api.v1 import teams

        team_id = str(uuid.uuid4())
        with patch.object(teams._team_service, "get_user_role", return_value="admin"):
            with patch.object(teams._team_service, "delete_team", return_value=False):
                response = teams_client.delete(f"/api/v1/teams/{team_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "팀을 찾을 수 없습니다" in response.json()["detail"]


# ---------------------------------------------------------------------------
# list_team_members 엔드포인트 테스트 (라인 222-251)
# ---------------------------------------------------------------------------


class TestListTeamMembersEndpointEdgeCases:
    """팀 멤버 목록 조회 엣지 케이스 테스트"""

    def test_list_team_members_invalid_uuid(self, teams_client) -> None:
        """잘못된 UUID 형식 (라인 238-239 커버)"""
        response = teams_client.get("/api/v1/teams/invalid-uuid/members")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["detail"]


# ---------------------------------------------------------------------------
# add_team_member 엔드포인트 테스트 (라인 253-312)
# ---------------------------------------------------------------------------


class TestAddTeamMemberEndpointEdgeCases:
    """팀 멤버 초대 엣지 케이스 테스트"""

    def test_add_team_member_invalid_uuid(self, teams_client) -> None:
        """잘못된 UUID 형식 (라인 271-272 커버)"""
        response = teams_client.post(
            "/api/v1/teams/invalid-uuid/members",
            json={"email": "new@example.com", "role": "member"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["detail"]

    def test_add_team_member_already_exists(self, teams_client) -> None:
        """이미 멤버인 경우 (라인 296 커버)"""
        from backend.app.api.v1 import teams

        team_id = str(uuid.uuid4())
        mock_member = MagicMock()
        mock_member.user_id = uuid.uuid4()

        with patch.object(teams._team_service, "get_user_role", return_value="admin"):
            with patch.object(
                teams._team_service, "add_member",
                side_effect=ValueError("이미 팀 멤버입니다")
            ):
                response = teams_client.post(
                    f"/api/v1/teams/{team_id}/members",
                    json={"email": "existing@example.com", "role": "member"}
                )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "이미 팀 멤버" in response.json()["detail"]

    def test_add_team_member_fallback_response(self, teams_client) -> None:
        """폴백 응답 (라인 305 커버)"""
        from backend.app.api.v1 import teams

        team_id = str(uuid.uuid4())
        mock_member = MagicMock()
        mock_member.user_id = uuid.uuid4()
        mock_member.role = "member"
        mock_member.joined_at = "2024-01-01T00:00:00Z"

        with patch.object(teams._team_service, "get_user_role", return_value="admin"):
            with patch.object(teams._team_service, "add_member", return_value=mock_member):
                # list_members가 빈 목록 반환 (폴백 트리거)
                with patch.object(teams._team_service, "list_members", return_value=[]):
                    response = teams_client.post(
                        f"/api/v1/teams/{team_id}/members",
                        json={"email": "new@example.com", "role": "member"}
                    )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["display_name"] == ""


# ---------------------------------------------------------------------------
# update_member_role 엔드포인트 테스트 (라인 314-370)
# ---------------------------------------------------------------------------


class TestUpdateMemberRoleEndpointEdgeCases:
    """멤버 역할 변경 엣지 케이스 테스트"""

    def test_update_member_role_invalid_uuid(self, teams_client) -> None:
        """잘못된 UUID 형식 (라인 334-335 커버)"""
        team_id = str(uuid.uuid4())
        response = teams_client.put(
            f"/api/v1/teams/{team_id}/members/invalid-uuid",
            json={"role": "admin"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 ID 형식입니다" in response.json()["detail"]

    def test_update_member_role_non_admin(self, teams_client) -> None:
        """권한 없음 (라인 342 커버)"""
        from backend.app.api.v1 import teams

        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        with patch.object(teams._team_service, "get_user_role", return_value="member"):
            response = teams_client.put(
                f"/api/v1/teams/{team_id}/members/{user_id}",
                json={"role": "admin"}
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "역할 변경은 admin만 가능합니다" in response.json()["detail"]

    def test_update_member_role_user_not_found(self, teams_client) -> None:
        """사용자를 찾을 수 없음 (라인 353 커버)"""
        from backend.app.api.v1 import teams

        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        with patch.object(teams._team_service, "get_user_role", return_value="admin"):
            with patch.object(
                teams._team_service, "update_member_role",
                side_effect=LookupError("사용자를 찾을 수 없습니다")
            ):
                response = teams_client.put(
                    f"/api/v1/teams/{team_id}/members/{user_id}",
                    json={"role": "admin"}
                )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "사용자를 찾을 수 없습니다" in response.json()["detail"]

    def test_update_member_role_fallback_response(self, teams_client) -> None:
        """폴백 응답 (라인 363 커버)"""
        from backend.app.api.v1 import teams

        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        mock_member = MagicMock()
        mock_member.user_id = uuid.UUID(user_id)
        mock_member.role = "admin"
        mock_member.joined_at = "2024-01-01T00:00:00Z"

        with patch.object(teams._team_service, "get_user_role", return_value="admin"):
            with patch.object(teams._team_service, "update_member_role", return_value=mock_member):
                # list_members가 빈 목록 반환 (폴백 트리거)
                with patch.object(teams._team_service, "list_members", return_value=[]):
                    response = teams_client.put(
                        f"/api/v1/teams/{team_id}/members/{user_id}",
                        json={"role": "admin"}
                    )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == ""
        assert data["display_name"] == ""


# ---------------------------------------------------------------------------
# remove_team_member 엔드포인트 테스트 (라인 372-420)
# ---------------------------------------------------------------------------


class TestRemoveTeamMemberEndpointEdgeCases:
    """멤버 제거 엣지 케이스 테스트"""

    def test_remove_team_member_invalid_uuid(self, teams_client) -> None:
        """잘못된 UUID 형식 (라인 392-393 커버)"""
        team_id = str(uuid.uuid4())
        response = teams_client.delete(f"/api/v1/teams/{team_id}/members/invalid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 ID 형식입니다" in response.json()["detail"]

    def test_remove_team_member_no_permission(self, teams_client) -> None:
        """권한 없음 - 멤버가 다른 멤버 제거 시도 (라인 407 커버)"""
        from backend.app.api.v1 import teams

        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        # member가 다른 멤버 제거 시도 -> 403
        with patch.object(teams._team_service, "get_user_role", return_value="member"):
            response = teams_client.delete(f"/api/v1/teams/{team_id}/members/{user_id}")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "멤버 제거는 admin만 가능합니다" in response.json()["detail"]

    def test_remove_team_member_value_error(self, teams_client) -> None:
        """값 오류 (라인 417 커버)"""
        from backend.app.api.v1 import teams

        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        with patch.object(teams._team_service, "get_user_role", return_value="admin"):
            with patch.object(
                teams._team_service, "remove_member",
                side_effect=ValueError("마지막 admin은 제거할 수 없습니다")
            ):
                response = teams_client.delete(f"/api/v1/teams/{team_id}/members/{user_id}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "마지막 admin은 제거할 수 없습니다" in response.json()["detail"]


# ---------------------------------------------------------------------------
# list_team_meetings 엔드포인트 테스트 (라인 427-468)
# ---------------------------------------------------------------------------


class TestListTeamMeetingsEndpoint:
    """팀 회의록 목록 조회 엔드포인트 테스트 (전체 커버)"""

    def test_list_team_meetings_success(self, teams_client) -> None:
        """팀 회의록 목록 조회 성공 (라인 443-462 커버)"""
        from backend.app.api.v1 import teams

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
                    "created_at": "2024-01-01T00:00:00Z"
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20
        }

        with patch.object(teams._team_service, "get_user_role", return_value="member"):
            with patch.object(teams._meeting_service, "list_team_meetings", return_value=mock_result):
                response = teams_client.get(
                    f"/api/v1/teams/{team_id}/meetings?page=1&page_size=20"
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert len(data["items"]) == 1

    def test_list_team_meetings_invalid_uuid(self, teams_client) -> None:
        """잘못된 UUID 형식"""
        response = teams_client.get("/api/v1/teams/invalid-uuid/meetings")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "유효하지 않은 팀 ID 형식입니다" in response.json()["detail"]

    def test_list_team_meetings_not_member(self, teams_client) -> None:
        """팀 멤버가 아님"""
        from backend.app.api.v1 import teams

        team_id = str(uuid.uuid4())
        with patch.object(teams._team_service, "get_user_role", return_value=None):
            response = teams_client.get(f"/api/v1/teams/{team_id}/meetings")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "팀에 접근할 권한이 없습니다" in response.json()["detail"]
