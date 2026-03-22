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


# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------


def _make_user():
    """테스트용 User mock"""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.display_name = "테스트 사용자"
    user.is_active = True
    return user


def _make_ownership(task_id: str, owner_id: uuid.UUID, team_id: uuid.UUID | None = None) -> dict:
    """MeetingOwnershipResponse 형식 딕셔너리"""
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
    """
    회의록 API 테스트용 TestClient
    - current_user로 인증된 상태
    """
    from backend.app.main import app
    from backend.app.dependencies import get_db_session, get_current_user

    async def mock_db_session():
        yield AsyncMock()

    async def mock_current_user():
        return current_user

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_current_user

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    with TestClient(app) as client:
                        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/meetings/{task_id}/share 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_share_meeting_endpoint(meeting_client, current_user):
    """
    회의록 팀 공유 성공 - 201 Created
    REQ-TEAM-005
    """
    task_id = "task-share-001"
    team_id = str(uuid.uuid4())
    shared_at = datetime.now(UTC).replace(tzinfo=None)

    # MeetingShareService.get_team_member_role → "member" (공유 가능)
    # MeetingShareService.share_meeting → MeetingOwnership mock
    mock_ownership = MagicMock()
    mock_ownership.task_id = task_id
    mock_ownership.team_id = uuid.UUID(team_id)
    mock_ownership.shared_at = shared_at

    with patch(
        "backend.app.api.v1.meetings._meeting_service.get_team_member_role",
        new_callable=AsyncMock,
        return_value="member",
    ):
        with patch(
            "backend.app.api.v1.meetings._meeting_service.share_meeting",
            new_callable=AsyncMock,
            return_value=mock_ownership,
        ):
            response = meeting_client.post(
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
    """
    팀 멤버가 아닌 경우 403 Forbidden
    REQ-TEAM-005
    """
    task_id = "task-share-002"
    team_id = str(uuid.uuid4())

    with patch(
        "backend.app.api.v1.meetings._meeting_service.get_team_member_role",
        new_callable=AsyncMock,
        return_value=None,  # 팀 멤버 아님
    ):
        response = meeting_client.post(
            f"/api/v1/meetings/{task_id}/share",
            json={"team_id": team_id},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_share_meeting_viewer_forbidden(meeting_client, current_user):
    """
    viewer 역할은 공유 불가 - 403 Forbidden
    REQ-TEAM-005
    """
    task_id = "task-share-003"
    team_id = str(uuid.uuid4())

    with patch(
        "backend.app.api.v1.meetings._meeting_service.get_team_member_role",
        new_callable=AsyncMock,
        return_value="viewer",
    ):
        response = meeting_client.post(
            f"/api/v1/meetings/{task_id}/share",
            json={"team_id": team_id},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/v1/meetings/{task_id}/share/{team_id} 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unshare_meeting_endpoint(meeting_client, current_user):
    """
    회의록 공유 해제 성공 - 204 No Content
    REQ-TEAM-005
    """
    task_id = "task-unshare-001"
    team_id = str(uuid.uuid4())

    with patch(
        "backend.app.api.v1.meetings._meeting_service.is_meeting_owner",
        new_callable=AsyncMock,
        return_value=True,  # 소유자
    ):
        with patch(
            "backend.app.api.v1.meetings._meeting_service.get_team_member_role",
            new_callable=AsyncMock,
            return_value="member",
        ):
            with patch(
                "backend.app.api.v1.meetings._meeting_service.unshare_meeting",
                new_callable=AsyncMock,
                return_value=True,
            ):
                response = meeting_client.delete(
                    f"/api/v1/meetings/{task_id}/share/{team_id}",
                    headers={"Authorization": "Bearer test-token"},
                )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_unshare_meeting_not_found(meeting_client, current_user):
    """
    공유 레코드 없을 때 404 Not Found
    """
    task_id = "task-unshare-002"
    team_id = str(uuid.uuid4())

    with patch(
        "backend.app.api.v1.meetings._meeting_service.is_meeting_owner",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with patch(
            "backend.app.api.v1.meetings._meeting_service.get_team_member_role",
            new_callable=AsyncMock,
            return_value="admin",
        ):
            with patch(
                "backend.app.api.v1.meetings._meeting_service.unshare_meeting",
                new_callable=AsyncMock,
                return_value=False,  # 레코드 없음
            ):
                response = meeting_client.delete(
                    f"/api/v1/meetings/{task_id}/share/{team_id}",
                    headers={"Authorization": "Bearer test-token"},
                )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/meetings/mine 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_my_meetings(meeting_client, current_user):
    """
    내 회의록 목록 조회 - 200 OK
    REQ-TEAM-005
    """
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

    with patch(
        "backend.app.api.v1.meetings._meeting_service.list_user_meetings",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = meeting_client.get(
            "/api/v1/meetings/mine",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["task_id"] == "task-mine-001"


# ---------------------------------------------------------------------------
# GET /api/v1/teams/{team_id}/meetings 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_team_meetings_endpoint(meeting_client, current_user):
    """
    팀 회의록 목록 조회 - 200 OK
    REQ-TEAM-005
    """
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

    with patch(
        "backend.app.api.v1.teams._team_service.get_user_role",
        new_callable=AsyncMock,
        return_value="member",  # 팀 멤버
    ):
        with patch(
            "backend.app.api.v1.teams._meeting_service.list_team_meetings",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = meeting_client.get(
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
    """
    팀 멤버가 아닌 경우 403 Forbidden
    """
    team_id = str(uuid.uuid4())

    with patch(
        "backend.app.api.v1.teams._team_service.get_user_role",
        new_callable=AsyncMock,
        return_value=None,  # 팀 멤버 아님
    ):
        response = meeting_client.get(
            f"/api/v1/teams/{team_id}/meetings",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 403
