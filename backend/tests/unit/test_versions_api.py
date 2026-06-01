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

# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


def _make_version(
    task_id: str = "task-1",
    version_number: int = 1,
    content: dict | None = None,
    change_summary: str | None = None,
):
    """테스트용 MinutesVersion mock 객체 생성"""
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
    """인증된 사용자 mock"""
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


@pytest.fixture
def mock_db():
    """AsyncSession mock"""
    return AsyncMock()


@pytest.fixture
def client_with_versions(mock_user, mock_db):
    """버전 API 테스트 클라이언트"""
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    async def override_user():
        return mock_user

    async def override_db():
        return mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db_session] = override_db

    with patch("backend.app.main.WhisperEngine") as mock_engine_cls:
        mock_inst = MagicMock()
        mock_inst.is_loaded = True
        mock_inst.load.return_value = None
        mock_engine_cls.get_instance.return_value = mock_inst

        yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# create_version 테스트
# ---------------------------------------------------------------------------


class TestCreateVersion:
    """POST /api/v1/minutes/{task_id}/versions 테스트"""

    @patch("backend.app.api.v1.versions._service")
    def test_returns_201_on_success(self, mock_service, client_with_versions):
        """버전 생성 성공 시 201 반환"""
        version = _make_version()
        mock_service.create_version = AsyncMock(return_value=version)

        response = client_with_versions.post(
            "/api/v1/minutes/task-1/versions",
            json={"content": {"summary": "hello"}, "change_summary": "초안"},
        )

        assert response.status_code == 201

    @patch("backend.app.api.v1.versions._service")
    def test_response_contains_version_fields(self, mock_service, client_with_versions):
        """응답에 필수 버전 필드 포함"""
        version = _make_version(change_summary="초안 생성")
        mock_service.create_version = AsyncMock(return_value=version)

        response = client_with_versions.post(
            "/api/v1/minutes/task-1/versions",
            json={"content": {"summary": "hello"}},
        )

        data = response.json()
        assert "id" in data
        assert "task_id" in data
        assert "version_number" in data
        assert "content" in data
        assert "created_at" in data


# ---------------------------------------------------------------------------
# list_versions 테스트
# ---------------------------------------------------------------------------


class TestListVersions:
    """GET /api/v1/minutes/{task_id}/versions 테스트"""

    @patch("backend.app.api.v1.versions._service")
    def test_returns_version_list(self, mock_service, client_with_versions):
        """버전 목록 반환"""
        versions = [_make_version(version_number=i) for i in range(1, 4)]
        mock_service.list_versions = AsyncMock(return_value=(versions, 3))

        response = client_with_versions.get("/api/v1/minutes/task-1/versions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @patch("backend.app.api.v1.versions._service")
    def test_empty_list(self, mock_service, client_with_versions):
        """버전이 없으면 빈 목록 반환"""
        mock_service.list_versions = AsyncMock(return_value=([], 0))

        response = client_with_versions.get("/api/v1/minutes/task-1/versions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


# ---------------------------------------------------------------------------
# get_version 테스트
# ---------------------------------------------------------------------------


class TestGetVersion:
    """GET /api/v1/minutes/{task_id}/versions/{version_id} 테스트"""

    @patch("backend.app.api.v1.versions._service")
    def test_returns_single_version(self, mock_service, client_with_versions):
        """특정 버전 단건 조회"""
        version = _make_version(version_number=2)
        mock_service.get_version = AsyncMock(return_value=version)

        version_id = str(version.id)
        response = client_with_versions.get(
            f"/api/v1/minutes/task-1/versions/{version_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version_number"] == 2


# ---------------------------------------------------------------------------
# get_diff 테스트
# ---------------------------------------------------------------------------


class TestGetDiff:
    """GET /api/v1/minutes/{task_id}/versions/{from}/diff/{to} 테스트"""

    @patch("backend.app.api.v1.versions._service")
    def test_returns_text_diff(self, mock_service, client_with_versions):
        """두 버전 간 텍스트 diff 반환"""
        v1 = _make_version(version_number=1, content={"summary": "old"})
        v2 = _make_version(version_number=2, content={"summary": "new"})

        mock_service.get_version = AsyncMock(side_effect=[v1, v2])
        mock_service.compute_diff.return_value = {
            "unified_diff": "--- \n+++ \n-old\n+new",
            "added_lines": 1,
            "removed_lines": 1,
            "changed": True,
        }

        from_id = str(v1.id)
        to_id = str(v2.id)
        response = client_with_versions.get(
            f"/api/v1/minutes/task-1/versions/{from_id}/diff/{to_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["from_version"] == 1
        assert data["to_version"] == 2
        assert data["changed"] is True
        assert data["added_lines"] == 1
        assert data["removed_lines"] == 1


# ---------------------------------------------------------------------------
# get_structured_diff 테스트
# ---------------------------------------------------------------------------


class TestGetStructuredDiff:
    """GET /api/v1/minutes/{task_id}/versions/{from}/structured-diff/{to} 테스트"""

    @patch("backend.app.api.v1.versions._service")
    def test_returns_structured_diff(self, mock_service, client_with_versions):
        """JSON 구조 diff 반환"""
        v1 = _make_version(version_number=1, content={"summary": "old"})
        v2 = _make_version(version_number=2, content={"summary": "new"})

        mock_service.get_version = AsyncMock(side_effect=[v1, v2])
        mock_service.compute_structured_diff.return_value = {
            "summary_text": {"changed": True, "before": "old", "after": "new"},
            "sections": {"added": [], "removed": [], "modified": []},
            "action_items": {"added": [], "removed": [], "modified": []},
            "total_changes": 1,
            "changed": True,
        }

        from_id = str(v1.id)
        to_id = str(v2.id)
        response = client_with_versions.get(
            f"/api/v1/minutes/task-1/versions/{from_id}/structured-diff/{to_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["from_version"] == 1
        assert data["to_version"] == 2
        assert data["changed"] is True
        assert data["total_changes"] == 1
        assert data["summary_text"]["changed"] is True


# ---------------------------------------------------------------------------
# delete_version 테스트
# ---------------------------------------------------------------------------


class TestDeleteVersion:
    """DELETE /api/v1/minutes/{task_id}/versions/{version_id} 테스트"""

    @patch("backend.app.api.v1.versions._service")
    def test_returns_204_on_success(self, mock_service, client_with_versions):
        """버전 삭제 성공 시 204 반환"""
        mock_service.delete_version = AsyncMock(return_value=None)

        version_id = str(uuid.uuid4())
        response = client_with_versions.delete(
            f"/api/v1/minutes/task-1/versions/{version_id}"
        )

        assert response.status_code == 204
