"""
SPEC-TAG-001: Tags API v3 테스트
커버되지 않은 라인을 위한 테스트
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.db.auth_models import User


@pytest.fixture
def tags_client():
    from backend.app.api.v1.tags import get_tag_service
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    async def mock_db_session():
        yield AsyncMock()

    async def mock_current_user():
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        yield mock_user

    svc_mock = AsyncMock()

    async def override_svc():
        return svc_mock

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_current_user
    app.dependency_overrides[get_tag_service] = override_svc

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield TestClient(app, raise_server_exceptions=False), svc_mock

    app.dependency_overrides.clear()


class TestBulkDeleteTagsEndpoint:
    def test_bulk_delete_tags_success(self, tags_client) -> None:
        client, mock_svc = tags_client
        mock_svc.delete_all_for_meeting = AsyncMock(return_value=5)

        response = client.delete("/api/v1/tags/bulk/delete?task_id=task-123")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted"] == 5
        assert data["task_id"] == "task-123"

    def test_bulk_delete_tags_with_source_filter(self, tags_client) -> None:
        client, mock_svc = tags_client
        mock_svc.delete_all_for_meeting = AsyncMock(return_value=3)

        response = client.delete("/api/v1/tags/bulk/delete?task_id=task-123&source=auto")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted"] == 3
