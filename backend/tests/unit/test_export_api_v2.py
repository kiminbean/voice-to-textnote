"""
SPEC-EXPORT-001: 회의록 내보내기 API 유닛 테스트
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# TestClient 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def export_client():
    """
    내보내기 API 테스트용 TestClient
    - DB 세션, Redis 클라이언트를 mock으로 대체
    """
    from backend.app.dependencies import get_db_session, get_redis_client
    from backend.app.main import app

    async def mock_db_session():
        yield AsyncMock()

    async def mock_redis():
        yield AsyncMock()

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_redis_client] = mock_redis

    with patch("backend.app.main.WhisperEngine"), patch("backend.app.main.DiarizationEngine"):
        with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
            with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 헬퍼 함수 테스트
# ---------------------------------------------------------------------------


class TestSafeExportFilename:
    """파일명 생성 헬퍼 함수 테스트."""

    def test_normal_task_id(self):
        """정상적인 task_id로 파일명 생성."""
        from backend.app.api.v1.admin.export import _safe_export_filename

        result = _safe_export_filename("task-123", "pdf")
        assert result == "minutes_task-123.pdf"

    def test_special_characters_removed(self):
        """특수문자가 제거되는지 확인."""
        from backend.app.api.v1.admin.export import _safe_export_filename

        result = _safe_export_filename("task/123\\test:file", "pdf")
        assert "task123testfile" in result
        assert result.endswith(".pdf")

    def test_long_task_id_truncated(self):
        """긴 task_id가 64자로 제한되는지 확인."""
        from backend.app.api.v1.admin.export import _safe_export_filename

        long_id = "a" * 100
        result = _safe_export_filename(long_id, "pdf")
        # 'minutes_' + 'a' * 64 + .pdf
        assert len(result) == len("minutes_") + 64 + 4

    def test_empty_task_id_uses_default(self):
        """빈 task_id가 'minutes'를 사용하는지 확인."""
        from backend.app.api.v1.admin.export import _safe_export_filename

        result = _safe_export_filename("", "pdf")
        # 빈 문자열은 "minutes"로 대체되고, "minutes_" 접두사가 붙음
        assert result == "minutes_minutes.pdf"

    def test_special_only_uses_default(self):
        """특수문자만 있는 경우 기본값을 사용."""
        from backend.app.api.v1.admin.export import _safe_export_filename

        result = _safe_export_filename("!!!@###", "pdf")
        assert result == "minutes_minutes.pdf"


# ---------------------------------------------------------------------------
# 엔드포인트 통합 테스트
# ---------------------------------------------------------------------------


class TestExportPDFEndpoint:
    """PDF 내보내기 엔드포인트 테스트."""

    def test_export_pdf_endpoint_exists(self, export_client):
        """PDF 내보내기 엔드포인트가 존재하는지 확인."""
        response = export_client.get("/api/v1/export/pdf/test-123")
        # 의존성이 모두 mock이므로 에러가 발생하더라도 엔드포인트는 존재해야 함
        # 404가 아니면 엔드포인트가 존재하는 것
        assert response.status_code != status.HTTP_404_NOT_FOUND


class TestExportDOCXEndpoint:
    """DOCX 내보내기 엔드포인트 테스트."""

    def test_export_docx_endpoint_exists(self, export_client):
        """DOCX 내보내기 엔드포인트가 존재하는지 확인."""
        response = export_client.get("/api/v1/export/docx/test-123")
        assert response.status_code != status.HTTP_404_NOT_FOUND


class TestExportMarkdownEndpoint:
    """Markdown 내보내기 엔드포인트 테스트."""

    def test_export_markdown_endpoint_exists(self, export_client):
        """Markdown 내보내기 엔드포인트가 존재하는지 확인."""
        response = export_client.get("/api/v1/export/markdown/test-123")
        assert response.status_code != status.HTTP_404_NOT_FOUND
