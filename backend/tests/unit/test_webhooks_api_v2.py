"""
SPEC-WEBHOOK-001: 웹훅 엔드포인트 관리 API 유닛 테스트
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
def webhooks_client():
    """
    웹훅 API 테스트용 TestClient
    - DB 세션, 사용자 인증을 mock으로 대체
    """
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    async def mock_db_session():
        yield AsyncMock()

    async def mock_current_user():
        # Mock User 객체
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        yield mock_user

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_current_user

    with patch("backend.app.main.WhisperEngine"), patch("backend.app.main.DiarizationEngine"):
        with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
            with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# API 엔드포인트 테스트
# ---------------------------------------------------------------------------


class TestCreateWebhookEndpoint:
    """웹훅 생성 API 테스트."""

    def test_create_webhook_endpoint_exists(self, webhooks_client):
        """웹훅 생성 엔드포인트가 존재하는지 확인."""
        response = webhooks_client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/webhook",
                "event_types": ["minutes.completed"],
                "description": "테스트 웹훅",
            },
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_create_webhook_invalid_url(self, webhooks_client):
        """유효하지 않은 URL로 422."""
        response = webhooks_client.post(
            "/api/v1/webhooks",
            json={
                "url": "not-a-valid-url",
                "event_types": ["minutes.completed"],
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_webhook_missing_url(self, webhooks_client):
        """URL 누락 시 422."""
        response = webhooks_client.post(
            "/api/v1/webhooks",
            json={
                "event_types": ["minutes.completed"],
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestListWebhooksEndpoint:
    """웹훅 목록 조회 API 테스트."""

    def test_list_webhooks_endpoint_exists(self, webhooks_client):
        """웹훅 목록 엔드포인트가 존재하는지 확인."""
        response = webhooks_client.get("/api/v1/webhooks")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_list_webhooks_pagination(self, webhooks_client):
        """페이지네이션 파라미터 확인."""
        response = webhooks_client.get("/api/v1/webhooks?page=1&page_size=10")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_list_webhooks_invalid_page(self, webhooks_client):
        """유효하지 않은 페이지 번호로 422."""
        response = webhooks_client.get("/api/v1/webhooks?page=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_webhooks_invalid_page_size(self, webhooks_client):
        """page_size 범위 초과로 422."""
        response = webhooks_client.get("/api/v1/webhooks?page_size=200")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetWebhookEndpoint:
    """웹훅 단건 조회 API 테스트."""

    def test_get_webhook_endpoint_exists(self, webhooks_client):
        """웹훅 단건 조회 엔드포인트가 존재하는지 확인."""
        webhook_id = uuid.uuid4()
        response = webhooks_client.get(f"/api/v1/webhooks/{webhook_id}")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_get_webhook_invalid_uuid(self, webhooks_client):
        """유효하지 않은 UUID로 422."""
        response = webhooks_client.get("/api/v1/webhooks/invalid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestUpdateWebhookEndpoint:
    """웹훅 수정 API 테스트."""

    def test_update_webhook_endpoint_exists(self, webhooks_client):
        """웹훅 수정 엔드포인트가 존재하는지 확인."""
        webhook_id = uuid.uuid4()
        response = webhooks_client.patch(
            f"/api/v1/webhooks/{webhook_id}",
            json={"description": "수정된 설명"},
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_update_webhook_invalid_uuid(self, webhooks_client):
        """유효하지 않은 UUID로 422."""
        response = webhooks_client.patch(
            "/api/v1/webhooks/invalid-uuid",
            json={"description": "수정된 설명"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_update_webhook_empty_body(self, webhooks_client):
        """빈 body로도 엔드포인트는 응답해야 함."""
        webhook_id = uuid.uuid4()
        response = webhooks_client.patch(f"/api/v1/webhooks/{webhook_id}", json={})
        # 모든 필드가 optional이므로 404가 아니어야 함
        assert response.status_code != status.HTTP_404_NOT_FOUND


class TestDeleteWebhookEndpoint:
    """웹훅 삭제 API 테스트."""

    def test_delete_webhook_endpoint_exists(self, webhooks_client):
        """웹훅 삭제 엔드포인트가 존재하는지 확인."""
        webhook_id = uuid.uuid4()
        response = webhooks_client.delete(f"/api/v1/webhooks/{webhook_id}")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_delete_webhook_invalid_uuid(self, webhooks_client):
        """유효하지 않은 UUID로 422."""
        response = webhooks_client.delete("/api/v1/webhooks/invalid-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestPingWebhookEndpoint:
    """웹훅 테스트 전송 API 테스트."""

    def test_ping_webhook_endpoint_exists(self, webhooks_client):
        """웹훅 ping 엔드포인트가 존재하는지 확인."""
        webhook_id = uuid.uuid4()
        response = webhooks_client.post(f"/api/v1/webhooks/{webhook_id}/ping")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_ping_webhook_invalid_uuid(self, webhooks_client):
        """유효하지 않은 UUID로 422."""
        response = webhooks_client.post("/api/v1/webhooks/invalid-uuid/ping")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_ping_webhook_success_response(self, webhooks_client):
        """ping 요청이 성공하면 WebhookPingResponse 반환."""
        from backend.services.webhook_service import WebhookService

        webhook_id = uuid.uuid4()

        # WebhookService.ping 메서드 mock
        with patch.object(
            WebhookService, "ping", new_callable=AsyncMock, return_value=(200, True, "Success")
        ):
            # WebhookService.get_by_id mock
            mock_endpoint = MagicMock()
            mock_endpoint.id = webhook_id
            mock_endpoint.url = "https://example.com/webhook"

            with patch.object(
                WebhookService, "get_by_id", new_callable=AsyncMock, return_value=mock_endpoint
            ):
                response = webhooks_client.post(f"/api/v1/webhooks/{webhook_id}/ping")

                # 성공 응답 확인
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["webhook_id"] == str(webhook_id)
                assert data["url"] == "https://example.com/webhook"
                assert data["status_code"] == 200
                assert data["success"] is True
                assert data["message"] == "Success"

    def test_ping_webhook_failure_response(self, webhooks_client):
        """ping 요청이 실패하면 실패 메시지 반환."""
        from backend.services.webhook_service import WebhookService

        webhook_id = uuid.uuid4()

        # WebhookService.ping 메서드 mock (실패 케이스)
        with patch.object(
            WebhookService,
            "ping",
            new_callable=AsyncMock,
            return_value=(500, False, "Connection failed"),
        ):
            mock_endpoint = MagicMock()
            mock_endpoint.id = webhook_id
            mock_endpoint.url = "https://example.com/webhook"

            with patch.object(
                WebhookService, "get_by_id", new_callable=AsyncMock, return_value=mock_endpoint
            ):
                response = webhooks_client.post(f"/api/v1/webhooks/{webhook_id}/ping")

                # 실패 응답 확인
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["success"] is False
                assert data["message"] == "Connection failed"
