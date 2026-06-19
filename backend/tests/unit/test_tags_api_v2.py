"""
SPEC-TAG-001: 회의록 태그 관리 API 유닛 테스트 (v2)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# TestClient 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def tags_client():
    """
    태그 API 테스트용 TestClient
    - DB 세션을 mock으로 대체
    """
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    user_id = uuid.uuid4()
    mock_tag = MagicMock()
    mock_tag.id = uuid.uuid4()
    mock_tag.user_id = user_id
    mock_tag.task_id = "test-123"
    mock_tag.tag_type = "topic"
    mock_tag.tag_value = "프로젝트A"
    mock_tag.source = "manual"
    mock_tag.confidence = None
    mock_tag.note = None
    mock_tag.created_at = None
    mock_tag.updated_at = None

    async def mock_db_session():
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_result.scalar_one_or_none.return_value = mock_tag
        mock_result.first.return_value = None
        mock_result.scalars.return_value.all.return_value = [mock_tag]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.delete = AsyncMock()
        yield mock_session

    async def mock_current_user():
        # Mock User 객체
        mock_user = MagicMock()
        mock_user.id = user_id
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
# API 엔드포인트 테스트
# ---------------------------------------------------------------------------


class TestAutoTagEndpoint:
    """자동 태깅 API 테스트."""

    def test_auto_tag_endpoint_exists(self, tags_client):
        """자동 태깅 엔드포인트가 존재하는지 확인."""
        response = tags_client.post(
            "/api/v1/tags/auto",
            json={
                "task_id": "test-123",
                "content": "회의 내용입니다",
                "max_tags": 5,
            },
        )
        # 의존성이 모두 mock이므로 엔드포인트 존재만 확인
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_auto_tag_invalid_input(self, tags_client):
        """유효하지 않은 입력으로 422 검증."""
        response = tags_client.post(
            "/api/v1/tags/auto",
            json={
                # task_id 누락
                "content": "회의 내용",
                "max_tags": 5,
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestCreateTagEndpoint:
    """태그 생성 API 테스트."""

    def test_create_tag_endpoint_exists(self, tags_client):
        """태그 생성 엔드포인트가 존재하는지 확인."""
        response = tags_client.post(
            "/api/v1/tags",
            json={
                "task_id": "test-123",
                "tag_type": "topic",
                "tag_value": "프로젝트A",
                "source": "manual",
            },
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_create_tag_invalid_type(self, tags_client):
        """유효하지 않은 태그 타입으로 422."""
        response = tags_client.post(
            "/api/v1/tags",
            json={
                "task_id": "test-123",
                "tag_type": "invalid_type",
                "tag_value": "test",
            },
        )
        # 스키마 검증에 실패하면 422
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestListTagsEndpoint:
    """태그 목록 조회 API 테스트."""

    def test_list_tags_endpoint_exists(self, tags_client):
        """태그 목록 엔드포인트가 존재하는지 확인."""
        response = tags_client.get("/api/v1/tags?task_id=test-123")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_list_tags_missing_task_id(self, tags_client):
        """task_id 누락 시 422."""
        response = tags_client.get("/api/v1/tags")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestGetTagEndpoint:
    """태그 단건 조회 API 테스트."""

    def test_get_tag_endpoint_exists(self, tags_client):
        """태그 단건 조회 엔드포인트가 존재하는지 확인."""
        tag_id = uuid.uuid4()
        response = tags_client.get(f"/api/v1/tags/{tag_id}")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_get_tag_invalid_uuid(self, tags_client):
        """유효하지 않은 UUID로 422."""
        response = tags_client.get("/api/v1/tags/invalid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestUpdateTagEndpoint:
    """태그 수정 API 테스트."""

    def test_update_tag_endpoint_exists(self, tags_client):
        """태그 수정 엔드포인트가 존재하는지 확인."""
        tag_id = uuid.uuid4()
        response = tags_client.patch(
            f"/api/v1/tags/{tag_id}",
            json={"tag_value": "새로운 값"},
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_update_tag_invalid_uuid(self, tags_client):
        """유효하지 않은 UUID로 422."""
        response = tags_client.patch(
            "/api/v1/tags/invalid-uuid",
            json={"tag_value": "새로운 값"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestDeleteTagEndpoint:
    """태그 삭제 API 테스트."""

    def test_delete_tag_endpoint_exists(self, tags_client):
        """태그 삭제 엔드포인트가 존재하는지 확인."""
        tag_id = uuid.uuid4()
        response = tags_client.delete(f"/api/v1/tags/{tag_id}")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_delete_tag_invalid_uuid(self, tags_client):
        """유효하지 않은 UUID로 422."""
        response = tags_client.delete("/api/v1/tags/invalid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestBulkDeleteTagsEndpoint:
    """태그 일괄 삭제 API 테스트."""

    def test_bulk_delete_endpoint_exists(self, tags_client):
        """일괄 삭제 엔드포인트가 존재하는지 확인."""
        response = tags_client.delete("/api/v1/tags/bulk/delete?task_id=test-123")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_bulk_delete_missing_task_id(self, tags_client):
        """task_id 누락 시 422."""
        response = tags_client.delete("/api/v1/tags/bulk/delete")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
