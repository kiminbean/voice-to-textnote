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

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def tags_client():
    """태그 API 테스트용 TestClient"""
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

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_current_user

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 엔드포인트 테스트는 스키마 유효성 검증으로 인해 어려움이 있음
# bulk_delete만 테스트 (라인 148-157)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# bulk_delete_tags 엔드포인트 테스트 (라인 148-157)
# ---------------------------------------------------------------------------


class TestBulkDeleteTagsEndpoint:
    """태그 일괄 삭제 엔드포인트 테스트"""

    def test_bulk_delete_tags_success(self, tags_client) -> None:
        """태그 일괄 삭제 성공 (라인 156-157 커버)"""
        from backend.app.api.v1 import tags
        with patch.object(tags._service, "delete_all_for_meeting", return_value=5):
            response = tags_client.delete(
                "/api/v1/tags/bulk/delete?task_id=task-123"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted"] == 5
        assert data["task_id"] == "task-123"

    def test_bulk_delete_tags_with_source_filter(self, tags_client) -> None:
        """소스 필터와 함께 일괄 삭제"""
        from backend.app.api.v1 import tags
        with patch.object(tags._service, "delete_all_for_meeting", return_value=3):
            response = tags_client.delete(
                "/api/v1/tags/bulk/delete?task_id=task-123&source=auto"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted"] == 3
