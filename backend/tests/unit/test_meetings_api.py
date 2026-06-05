"""
SPEC-TEAM-001: 회의록 공유 API 단위 테스트

테스트 범위:
- share_meeting: team_id 유효성 검증 (ValueError → 422)
- unshare_meeting: team_id 유효성 검증 (ValueError → 422)
- unshare_meeting: 권한 없음 (403)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_db_session
from backend.app.error_handlers import register_exception_handlers

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
    from backend.app.api.v1.meetings import get_meeting_share_service, router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    async def override_user():
        return mock_user

    async def override_db():
        return AsyncMock()

    svc_mock = AsyncMock()

    async def override_svc():
        return svc_mock

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_meeting_share_service] = override_svc

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, mock_user, svc_mock

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# share_meeting ValueError 테스트
# ---------------------------------------------------------------------------


class TestShareMeetingValidation:
    """POST /api/v1/meetings/{task_id}/share 검증 테스트"""

    def test_invalid_team_id_returns_422(self, app_client):
        """유효하지 않은 team_id → 422"""
        client, _, _ = app_client
        resp = client.post(
            "/api/v1/meetings/task-1/share",
            json={"team_id": "not-a-uuid"},
        )
        assert resp.status_code == 422
        assert "팀 ID" in resp.json()["message"]


class TestUnshareMeetingValidation:
    def test_invalid_team_id_returns_422(self, app_client):
        client, _, _ = app_client
        resp = client.delete("/api/v1/meetings/task-1/share/not-a-uuid")
        assert resp.status_code == 422
        assert "팀 ID" in resp.json()["message"]

    def test_permission_denied_returns_403(self, app_client):
        client, _, mock_svc = app_client

        mock_svc.is_meeting_owner = AsyncMock(return_value=False)
        mock_svc.get_team_member_role = AsyncMock(return_value="member")

        team_id = str(uuid.uuid4())
        resp = client.delete(f"/api/v1/meetings/task-1/share/{team_id}")

        assert resp.status_code == 403
        assert "admin" in resp.json()["message"]
