"""
SPEC-VERSION-001: 회의록 버전 관리 API 단위 테스트

테스트 범위:
- create_version, list_versions, get_version
- get_diff, get_structured_diff, delete_version
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_version(
    task_id: str = "task-1",
    version_number: int = 1,
    content: dict | None = None,
    change_summary: str | None = None,
):
    version = MagicMock()
    version.id = uuid.uuid4()
    version.task_id = task_id
    version.version_number = version_number
    version.content = content or {"summary": "test"}
    version.change_summary = change_summary
    version.author_id = uuid.uuid4()
    version.created_at = datetime.now(UTC)
    return version


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def client_with_versions(mock_user, mock_db):
    from backend.app.api.v1.collaboration.versions import get_version_service
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    async def override_user():
        return mock_user

    async def override_db():
        return mock_db

    svc_mock = AsyncMock()

    async def override_svc():
        return svc_mock

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_version_service] = override_svc

    with patch("backend.app.main.WhisperEngine") as mock_engine_cls:
        mock_inst = MagicMock()
        mock_inst.is_loaded = True
        mock_inst.load.return_value = None
        mock_engine_cls.get_instance.return_value = mock_inst

        yield TestClient(app, raise_server_exceptions=True), svc_mock

    app.dependency_overrides.clear()


class TestCreateVersion:
    def test_returns_201_on_success(self, client_with_versions):
        client, mock_svc = client_with_versions
        version = _make_version()
        mock_svc.create_version = AsyncMock(return_value=version)

        response = client.post(
            "/api/v1/minutes/task-1/versions",
            json={"content": {"summary": "hello"}, "change_summary": "초안"},
        )

        assert response.status_code == 201

    def test_response_contains_version_fields(self, client_with_versions):
        client, mock_svc = client_with_versions
        version = _make_version(change_summary="초안 생성")
        mock_svc.create_version = AsyncMock(return_value=version)

        response = client.post(
            "/api/v1/minutes/task-1/versions",
            json={"content": {"summary": "hello"}},
        )

        data = response.json()
        assert "id" in data
        assert "task_id" in data
        assert "version_number" in data
        assert "content" in data
        assert "created_at" in data


class TestListVersions:
    def test_returns_version_list(self, client_with_versions):
        client, mock_svc = client_with_versions
        versions = [_make_version(version_number=i) for i in range(1, 4)]
        mock_svc.list_versions = AsyncMock(return_value=(versions, 3))

        response = client.get("/api/v1/minutes/task-1/versions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_empty_list(self, client_with_versions):
        client, mock_svc = client_with_versions
        mock_svc.list_versions = AsyncMock(return_value=([], 0))

        response = client.get("/api/v1/minutes/task-1/versions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestGetVersion:
    def test_returns_single_version(self, client_with_versions):
        client, mock_svc = client_with_versions
        version = _make_version(version_number=2)
        mock_svc.get_version = AsyncMock(return_value=version)

        version_id = str(version.id)
        response = client.get(f"/api/v1/minutes/task-1/versions/{version_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["version_number"] == 2


class TestGetDiff:
    def test_returns_text_diff(self, client_with_versions):
        client, mock_svc = client_with_versions
        v1 = _make_version(version_number=1, content={"summary": "old"})
        v2 = _make_version(version_number=2, content={"summary": "new"})

        mock_svc.get_version = AsyncMock(side_effect=[v1, v2])
        mock_svc.compute_diff = MagicMock(
            return_value={
                "unified_diff": "--- \n+++ \n-old\n+new",
                "added_lines": 1,
                "removed_lines": 1,
                "changed": True,
            }
        )

        from_id = str(v1.id)
        to_id = str(v2.id)
        response = client.get(f"/api/v1/minutes/task-1/versions/{from_id}/diff/{to_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["from_version"] == 1
        assert data["to_version"] == 2
        assert data["changed"] is True
        assert data["added_lines"] == 1
        assert data["removed_lines"] == 1


class TestGetStructuredDiff:
    def test_returns_structured_diff(self, client_with_versions):
        client, mock_svc = client_with_versions
        v1 = _make_version(version_number=1, content={"summary": "old"})
        v2 = _make_version(version_number=2, content={"summary": "new"})

        mock_svc.get_version = AsyncMock(side_effect=[v1, v2])
        mock_svc.compute_structured_diff = MagicMock(
            return_value={
                "summary_text": {"changed": True, "before": "old", "after": "new"},
                "sections": {"added": [], "removed": [], "modified": []},
                "action_items": {"added": [], "removed": [], "modified": []},
                "total_changes": 1,
                "changed": True,
            }
        )

        from_id = str(v1.id)
        to_id = str(v2.id)
        response = client.get(f"/api/v1/minutes/task-1/versions/{from_id}/structured-diff/{to_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["from_version"] == 1
        assert data["to_version"] == 2
        assert data["changed"] is True
        assert data["total_changes"] == 1
        assert data["summary_text"]["changed"] is True


class TestDeleteVersion:
    def test_returns_204_on_success(self, client_with_versions):
        client, mock_svc = client_with_versions
        mock_svc.delete_version = AsyncMock(return_value=None)

        version_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/minutes/task-1/versions/{version_id}")

        assert response.status_code == 204
