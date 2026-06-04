"""
SPEC-TEAM-001: 회의록 공유 API 단위 테스트

테스트 범위:
- share_meeting: team_id 유효성 검증 (ValueError → 422)
- unshare_meeting: team_id 유효성 검증 (ValueError → 422)
- unshare_meeting: 권한 없음 (403)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from backend.app.error_handlers import register_exception_handlers
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_db_session

# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


@pytest.fixture
def app_client(mock_user):
    from backend.app.api.v1.meetings import router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    async def override_user():
        return mock_user

    async def override_db():
        return AsyncMock()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db_session] = override_db

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, mock_user

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# share_meeting ValueError 테스트
# ---------------------------------------------------------------------------


class TestShareMeetingValidation:
    """POST /api/v1/meetings/{task_id}/share 검증 테스트"""

    def test_invalid_team_id_returns_422(self, app_client):
        """유효하지 않은 team_id → 422"""
        client, _ = app_client
        resp = client.post(
            "/api/v1/meetings/task-1/share",
            json={"team_id": "not-a-uuid"},
        )
        assert resp.status_code == 422
        assert "팀 ID" in resp.json()["message"]


# ---------------------------------------------------------------------------
# unshare_meeting ValueError 테스트
# ---------------------------------------------------------------------------


class TestUnshareMeetingValidation:
    """DELETE /api/v1/meetings/{task_id}/share/{team_id} 검증 테스트"""

    def test_invalid_team_id_returns_422(self, app_client):
        """유효하지 않은 team_id → 422"""
        client, _ = app_client
        resp = client.delete("/api/v1/meetings/task-1/share/not-a-uuid")
        assert resp.status_code == 422
        assert "팀 ID" in resp.json()["message"]

    @patch("backend.app.api.v1.meetings._meeting_service")
    def test_permission_denied_returns_403(self, mock_service, app_client):
        """소유자도 아니고 admin도 아니면 403"""
        client, user = app_client

        mock_service.is_meeting_owner = AsyncMock(return_value=False)
        mock_service.get_team_member_role = AsyncMock(return_value="member")

        team_id = str(uuid.uuid4())
        resp = client.delete(f"/api/v1/meetings/task-1/share/{team_id}")

        assert resp.status_code == 403
        assert "admin" in resp.json()["message"]
