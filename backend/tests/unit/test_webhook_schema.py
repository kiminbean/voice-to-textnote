"""
SPEC-WEBHOOK-001: 웹훅 엔드포인트 Pydantic 스키마 유닛 테스트
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from backend.schemas.webhook import (
    WebhookEndpointCreate,
    WebhookEndpointListResponse,
    WebhookEndpointResponse,
    WebhookEndpointUpdate,
    WebhookPingResponse,
)


class TestWebhookEndpointCreate:
    """WebhookEndpointCreate 스키마 테스트"""

    def test_valid_webhook_create(self):
        """유효한 웹훅 생성 요청"""
        payload = WebhookEndpointCreate(
            url="https://example.com/webhook",
            events=["minutes.completed"],
            description="테스트 웹훅"
        )
        assert payload.url == "https://example.com/webhook"
        assert payload.events == ["minutes.completed"]
        assert payload.description == "테스트 웹훅"

    def test_webhook_create_with_empty_events(self):
        """빈 events 리스트로 생성 (전체 이벤트 수신)"""
        payload = WebhookEndpointCreate(url="https://example.com/webhook", events=[])
        assert payload.events == []

    def test_webhook_create_duplicate_events_removed(self):
        """중복 이벤트 자동 제거"""
        payload = WebhookEndpointCreate(
            url="https://example.com/webhook",
            events=["minutes.completed", "minutes.completed", "transcription.completed"]
        )
        # 중복 제거되고 순서 유지
        assert payload.events == ["minutes.completed", "transcription.completed"]

    def test_webhook_create_invalid_event_type(self):
        """지원하지 않는 이벤트 타입으로 ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            WebhookEndpointCreate(
                url="https://example.com/webhook",
                events=["invalid.event"]
            )
        errors = exc_info.value.errors()
        assert any("지원하지 않는 이벤트 타입" in str(error["msg"]) for error in errors)

    def test_webhook_create_with_secret(self):
        """secret 포함 생성"""
        payload = WebhookEndpointCreate(
            url="https://example.com/webhook",
            secret="test-secret-key"
        )
        assert payload.secret == "test-secret-key"

    def test_webhook_create_url_too_long(self):
        """URL 길이 제한 초과로 ValidationError"""
        long_url = "https://example.com/" + "a" * 500
        with pytest.raises(ValidationError) as exc_info:
            WebhookEndpointCreate(url=long_url)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("url",) for error in errors)

    def test_webhook_create_missing_url(self):
        """URL 누락 시 ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            WebhookEndpointCreate(events=["minutes.completed"])
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("url",) for error in errors)


class TestWebhookEndpointUpdate:
    """WebhookEndpointUpdate 스키마 테스트"""

    def test_valid_webhook_update_all_fields(self):
        """모든 필드 포함 유효한 수정 요청"""
        payload = WebhookEndpointUpdate(
            url="https://example.com/updated",
            events=["minutes.completed"],
            secret="new-secret",
            is_active=True,
            description="수정된 설명"
        )
        assert payload.url == "https://example.com/updated"
        assert payload.events == ["minutes.completed"]
        assert payload.secret == "new-secret"
        assert payload.is_active is True
        assert payload.description == "수정된 설명"

    def test_webhook_update_partial_fields(self):
        """일부 필드만 수정"""
        payload = WebhookEndpointUpdate(description="설명만 수정")
        assert payload.description == "설명만 수정"
        assert payload.url is None
        assert payload.events is None

    def test_webhook_update_none_events(self):
        """events가 None이면 그대로 반환"""
        payload = WebhookEndpointUpdate(events=None)
        assert payload.events is None

    def test_webhook_update_duplicate_events_removed(self):
        """수정 시에도 중복 이벤트 제거"""
        payload = WebhookEndpointUpdate(
            events=["minutes.completed", "minutes.completed", "transcription.completed"]
        )
        assert payload.events == ["minutes.completed", "transcription.completed"]

    def test_webhook_update_invalid_event_type(self):
        """지원하지 않는 이벤트 타입으로 ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            WebhookEndpointUpdate(events=["invalid.event"])
        errors = exc_info.value.errors()
        assert any("지원하지 않는 이벤트 타입" in str(error["msg"]) for error in errors)

    def test_webhook_update_none_url(self):
        """url이 None이면 그대로 반환"""
        payload = WebhookEndpointUpdate(url=None)
        assert payload.url is None


class TestWebhookEndpointResponse:
    """WebhookEndpointResponse 스키마 테스트"""

    def test_from_orm_masked_with_secret(self):
        """ORM 객체에서 생성 (secret 있음)"""
        mock_obj = MagicMock()
        mock_obj.id = uuid.uuid4()
        mock_obj.user_id = uuid.uuid4()
        mock_obj.url = "https://example.com/webhook"
        mock_obj.events = ["minutes.completed"]
        mock_obj.secret = "test-secret"
        mock_obj.is_active = True
        mock_obj.description = "테스트"
        mock_obj.created_at = datetime(2025, 1, 1, 0, 0, 0)
        mock_obj.updated_at = datetime(2025, 1, 2, 0, 0, 0)

        response = WebhookEndpointResponse.from_orm_masked(mock_obj)

        assert response.id == mock_obj.id
        assert response.user_id == mock_obj.user_id
        assert response.url == mock_obj.url
        assert response.events == mock_obj.events
        assert response.has_secret is True  # secret이 마스킹됨
        assert response.is_active is True
        assert response.description == "테스트"

    def test_from_orm_masked_without_secret(self):
        """ORM 객체에서 생성 (secret 없음)"""
        mock_obj = MagicMock()
        mock_obj.id = uuid.uuid4()
        mock_obj.user_id = uuid.uuid4()
        mock_obj.url = "https://example.com/webhook"
        mock_obj.events = ["minutes.completed"]
        mock_obj.secret = None
        mock_obj.is_active = True
        mock_obj.description = None
        mock_obj.created_at = datetime(2025, 1, 1, 0, 0, 0)
        mock_obj.updated_at = datetime(2025, 1, 2, 0, 0, 0)

        response = WebhookEndpointResponse.from_orm_masked(mock_obj)

        assert response.has_secret is False
        assert response.description is None

    def test_from_orm_masked_empty_events(self):
        """events가 None이면 빈 리스트로 변환"""
        mock_obj = MagicMock()
        mock_obj.id = uuid.uuid4()
        mock_obj.user_id = uuid.uuid4()
        mock_obj.url = "https://example.com/webhook"
        mock_obj.events = None
        mock_obj.secret = None
        mock_obj.is_active = True
        mock_obj.description = None
        mock_obj.created_at = datetime(2025, 1, 1, 0, 0, 0)
        mock_obj.updated_at = datetime(2025, 1, 2, 0, 0, 0)

        response = WebhookEndpointResponse.from_orm_masked(mock_obj)

        assert response.events == []


class TestWebhookEndpointListResponse:
    """WebhookEndpointListResponse 스키마 테스트"""

    def test_webhook_list_response(self):
        """웹훅 목록 응답 생성"""
        mock_endpoint = MagicMock()
        mock_endpoint.id = uuid.uuid4()
        mock_endpoint.user_id = uuid.uuid4()
        mock_endpoint.url = "https://example.com/webhook"
        mock_endpoint.events = ["minutes.completed"]
        mock_endpoint.secret = None
        mock_endpoint.is_active = True
        mock_endpoint.description = "테스트"
        mock_endpoint.created_at = datetime(2025, 1, 1, 0, 0, 0)
        mock_endpoint.updated_at = datetime(2025, 1, 2, 0, 0, 0)

        response = WebhookEndpointListResponse(
            items=[WebhookEndpointResponse.from_orm_masked(mock_endpoint)],
            total=1
        )

        assert len(response.items) == 1
        assert response.total == 1
        assert response.items[0].url == "https://example.com/webhook"

    def test_webhook_list_empty(self):
        """빈 웹훅 목록"""
        response = WebhookEndpointListResponse(items=[], total=0)
        assert response.items == []
        assert response.total == 0


class TestWebhookPingResponse:
    """WebhookPingResponse 스키마 테스트"""

    def test_ping_response_success(self):
        """ping 성공 응답"""
        webhook_id = uuid.uuid4()
        response = WebhookPingResponse(
            webhook_id=webhook_id,
            url="https://example.com/webhook",
            status_code=200,
            success=True,
            message="Success"
        )

        assert response.webhook_id == webhook_id
        assert response.url == "https://example.com/webhook"
        assert response.status_code == 200
        assert response.success is True
        assert response.message == "Success"

    def test_ping_response_failure(self):
        """ping 실패 응답"""
        webhook_id = uuid.uuid4()
        response = WebhookPingResponse(
            webhook_id=webhook_id,
            url="https://example.com/webhook",
            status_code=500,
            success=False,
            message="Connection failed"
        )

        assert response.success is False
        assert response.status_code == 500
        assert response.message == "Connection failed"

    def test_ping_response_no_status_code(self):
        """status_code가 None일 수 있음"""
        webhook_id = uuid.uuid4()
        response = WebhookPingResponse(
            webhook_id=webhook_id,
            url="https://example.com/webhook",
            status_code=None,
            success=False,
            message="Timeout"
        )

        assert response.status_code is None
        assert response.success is False
