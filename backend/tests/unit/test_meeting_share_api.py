"""
SPEC-TEAM-001 REQ-TEAM-005: 회의록 공유 API 단위 테스트

테스트 대상:
- POST   /api/v1/meetings/{task_id}/share        - 회의록 팀 공유
- DELETE /api/v1/meetings/{task_id}/share/{team_id} - 회의록 공유 해제
- GET    /api/v1/meetings/mine                   - 내 회의록 목록
- GET    /api/v1/teams/{team_id}/meetings        - 팀 회의록 목록
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.display_name = "테스트 사용자"
    user.is_active = True
    return user


def _make_ownership(task_id: str, owner_id: uuid.UUID, team_id: uuid.UUID | None = None) -> dict:
    return {
        "task_id": task_id,
        "task_type": "transcription",
        "status": "completed",
        "owner_id": str(owner_id),
        "team_id": str(team_id) if team_id else None,
        "shared_at": datetime.now(UTC).replace(tzinfo=None),
        "created_at": datetime.now(UTC).replace(tzinfo=None),
    }


@pytest.fixture
def current_user():
    return _make_user()


@pytest.fixture
def meeting_client(current_user):
    from backend.app.api.v1.collaboration.meetings import get_meeting_share_service
    from backend.app.api.v1.collaboration.teams import (
        get_meeting_share_service as get_teams_meeting_svc,
    )
    from backend.app.api.v1.collaboration.teams import (
        get_team_service as get_team_svc,
    )
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    async def mock_db_session():
        yield AsyncMock()

    async def mock_current_user():
        return current_user

    meeting_svc_mock = AsyncMock()
    team_svc_mock = AsyncMock()
    teams_meeting_svc_mock = AsyncMock()

    async def override_meeting_svc():
        return meeting_svc_mock

    async def override_team_svc():
        return team_svc_mock

    async def override_teams_meeting_svc():
        return teams_meeting_svc_mock

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_current_user
    app.dependency_overrides[get_meeting_share_service] = override_meeting_svc
    app.dependency_overrides[get_team_svc] = override_team_svc
    app.dependency_overrides[get_teams_meeting_svc] = override_teams_meeting_svc

    with patch("backend.app.main.WhisperEngine"), patch("backend.app.main.DiarizationEngine"):
        with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
            with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                with TestClient(app) as client:
                    yield client, meeting_svc_mock, team_svc_mock, teams_meeting_svc_mock

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_share_meeting_endpoint(meeting_client, current_user):
    client, meeting_svc_mock, _, _ = meeting_client
    task_id = "task-share-001"
    team_id = str(uuid.uuid4())
    shared_at = datetime.now(UTC).replace(tzinfo=None)

    mock_ownership = MagicMock()
    mock_ownership.task_id = task_id
    mock_ownership.team_id = uuid.UUID(team_id)
    mock_ownership.shared_at = shared_at

    meeting_svc_mock.get_team_member_role = AsyncMock(return_value="member")
    meeting_svc_mock.share_meeting = AsyncMock(return_value=mock_ownership)

    response = client.post(
        f"/api/v1/meetings/{task_id}/share",
        json={"team_id": team_id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["task_id"] == task_id
    assert data["team_id"] == team_id


@pytest.mark.asyncio
async def test_share_meeting_not_team_member(meeting_client, current_user):
    client, meeting_svc_mock, _, _ = meeting_client
    task_id = "task-share-002"
    team_id = str(uuid.uuid4())

    meeting_svc_mock.get_team_member_role = AsyncMock(return_value=None)

    response = client.post(
        f"/api/v1/meetings/{task_id}/share",
        json={"team_id": team_id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_share_meeting_viewer_forbidden(meeting_client, current_user):
    client, meeting_svc_mock, _, _ = meeting_client
    task_id = "task-share-003"
    team_id = str(uuid.uuid4())

    meeting_svc_mock.get_team_member_role = AsyncMock(return_value="viewer")

    response = client.post(
        f"/api/v1/meetings/{task_id}/share",
        json={"team_id": team_id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unshare_meeting_endpoint(meeting_client, current_user):
    client, meeting_svc_mock, _, _ = meeting_client
    task_id = "task-unshare-001"
    team_id = str(uuid.uuid4())

    meeting_svc_mock.is_meeting_owner = AsyncMock(return_value=True)
    meeting_svc_mock.get_team_member_role = AsyncMock(return_value="member")
    meeting_svc_mock.unshare_meeting = AsyncMock(return_value=True)

    response = client.delete(
        f"/api/v1/meetings/{task_id}/share/{team_id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_unshare_meeting_not_found(meeting_client, current_user):
    client, meeting_svc_mock, _, _ = meeting_client
    task_id = "task-unshare-002"
    team_id = str(uuid.uuid4())

    meeting_svc_mock.is_meeting_owner = AsyncMock(return_value=True)
    meeting_svc_mock.get_team_member_role = AsyncMock(return_value="admin")
    meeting_svc_mock.unshare_meeting = AsyncMock(return_value=False)

    response = client.delete(
        f"/api/v1/meetings/{task_id}/share/{team_id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_my_meetings(meeting_client, current_user):
    client, meeting_svc_mock, _, _ = meeting_client
    ownership_data = _make_ownership(
        task_id="task-mine-001",
        owner_id=current_user.id,
    )

    mock_result = {
        "items": [ownership_data],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }

    meeting_svc_mock.list_user_meetings = AsyncMock(return_value=mock_result)

    response = client.get(
        "/api/v1/meetings/mine",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["task_id"] == "task-mine-001"


@pytest.mark.asyncio
async def test_list_team_meetings_endpoint(meeting_client, current_user):
    client, _, team_svc_mock, teams_meeting_svc_mock = meeting_client
    team_id = str(uuid.uuid4())
    ownership_data = _make_ownership(
        task_id="task-team-001",
        owner_id=current_user.id,
        team_id=uuid.UUID(team_id),
    )

    mock_result = {
        "items": [ownership_data],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }

    team_svc_mock.get_user_role = AsyncMock(return_value="member")
    teams_meeting_svc_mock.list_team_meetings = AsyncMock(return_value=mock_result)

    response = client.get(
        f"/api/v1/teams/{team_id}/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["task_id"] == "task-team-001"


@pytest.mark.asyncio
async def test_list_team_meetings_not_member(meeting_client, current_user):
    client, _, team_svc_mock, _ = meeting_client
    team_id = str(uuid.uuid4())

    team_svc_mock.get_user_role = AsyncMock(return_value=None)

    response = client.get(
        f"/api/v1/teams/{team_id}/meetings",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
