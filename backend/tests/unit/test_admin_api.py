"""
Admin API 테스트 - SPEC-RETENTION-001

테스트 범위:
- POST /api/v1/admin/cleanup: 즉시 정리 실행 및 결과 반환
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient 픽스처 - admin 라우터 포함"""
    from backend.app.main import app
    from backend.app.middleware.auth import verify_api_key

    async def override_verify_api_key():
        return "test-bypass"

    app.dependency_overrides[verify_api_key] = override_verify_api_key
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


class TestTriggerCleanup:
    """REQ-RET-007: POST /api/v1/admin/cleanup 테스트"""

    def test_cleanup_returns_200(self, client):
        """cleanup 요청이 200 OK를 반환한다"""
        with (
            patch("backend.app.api.v1.admin.admin.cleanup_expired_results", return_value=5),
            patch(
                "backend.app.api.v1.admin.admin.cleanup_temp_files", return_value=(3, 1024 * 1024)
            ),
            patch("backend.app.api.v1.admin.admin.get_sync_session") as mock_session_cm,
        ):
            mock_session = MagicMock()
            mock_session_cm.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cm.return_value.__exit__ = MagicMock(return_value=False)

            response = client.post("/api/v1/admin/cleanup")

        assert response.status_code == 200

    def test_cleanup_returns_result_counts(self, client):
        """cleanup 결과에 삭제된 DB 레코드 수와 파일 수가 포함된다"""
        with (
            patch("backend.app.api.v1.admin.admin.cleanup_expired_results", return_value=10),
            patch(
                "backend.app.api.v1.admin.admin.cleanup_temp_files",
                return_value=(7, 2 * 1024 * 1024),
            ),
            patch("backend.app.api.v1.admin.admin.get_sync_session") as mock_session_cm,
        ):
            mock_session = MagicMock()
            mock_session_cm.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cm.return_value.__exit__ = MagicMock(return_value=False)

            response = client.post("/api/v1/admin/cleanup")

        data = response.json()
        assert data["db_deleted"] == 10
        assert data["files_deleted"] == 7

    def test_cleanup_returns_freed_bytes(self, client):
        """cleanup 결과에 해제된 바이트 크기가 포함된다"""
        freed_bytes = 5 * 1024 * 1024  # 5 MB
        with (
            patch("backend.app.api.v1.admin.admin.cleanup_expired_results", return_value=0),
            patch(
                "backend.app.api.v1.admin.admin.cleanup_temp_files", return_value=(3, freed_bytes)
            ),
            patch("backend.app.api.v1.admin.admin.get_sync_session") as mock_session_cm,
        ):
            mock_session = MagicMock()
            mock_session_cm.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cm.return_value.__exit__ = MagicMock(return_value=False)

            response = client.post("/api/v1/admin/cleanup")

        data = response.json()
        assert data["freed_bytes"] == freed_bytes

    def test_cleanup_zero_results_when_nothing_to_delete(self, client):
        """삭제할 항목이 없으면 0을 반환한다"""
        with (
            patch("backend.app.api.v1.admin.admin.cleanup_expired_results", return_value=0),
            patch("backend.app.api.v1.admin.admin.cleanup_temp_files", return_value=(0, 0)),
            patch("backend.app.api.v1.admin.admin.get_sync_session") as mock_session_cm,
        ):
            mock_session = MagicMock()
            mock_session_cm.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cm.return_value.__exit__ = MagicMock(return_value=False)

            response = client.post("/api/v1/admin/cleanup")

        data = response.json()
        assert data["db_deleted"] == 0
        assert data["files_deleted"] == 0
        assert data["freed_bytes"] == 0
