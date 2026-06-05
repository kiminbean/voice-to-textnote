"""
웹훅 URL 검증 및 SSRF 방어 회귀 테스트.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from backend.schemas.webhook import WebhookEndpointCreate, WebhookEndpointUpdate
from backend.services.webhook_service import WebhookService
from backend.utils.validators import validate_webhook_url


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "ftp://example.com/hook",
        "http://localhost:8000/hook",
        "http://localhost.localdomain/hook",
        "http://127.0.0.1/hook",
        "http://10.0.0.5/hook",
        "http://172.16.0.5/hook",
        "http://192.168.1.10/hook",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/hook",
    ],
)
def test_webhook_create_rejects_invalid_or_private_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        WebhookEndpointCreate(url=url)


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "ftp://example.com/hook",
        "http://localhost:8000/hook",
        "http://127.0.0.1/hook",
    ],
)
def test_webhook_update_rejects_invalid_or_private_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        WebhookEndpointUpdate(url=url)


def test_webhook_create_accepts_public_https_url() -> None:
    payload = WebhookEndpointCreate(
        url="https://example.com/webhook",
        events=["summary.completed", "summary.completed"],
    )

    assert payload.url == "https://example.com/webhook"
    assert payload.events == ["summary.completed"]


def test_webhook_runtime_validation_rejects_private_literal() -> None:
    with pytest.raises(ValueError):
        validate_webhook_url("http://127.0.0.1:8000/hook", resolve_host=True)


def test_webhook_runtime_validation_rejects_private_dns_resolution(monkeypatch) -> None:
    def fake_getaddrinfo(host, port, type=None):  # noqa: A002
        return [(None, None, None, "", ("10.0.0.10", port))]

    monkeypatch.setattr("socket.getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ValueError, match="사설/로컬 네트워크"):
        validate_webhook_url("https://webhook.example.com/hook", resolve_host=True)


async def test_webhook_ping_rejects_private_url_before_send(monkeypatch) -> None:
    service = WebhookService()
    user_id = uuid.uuid4()
    endpoint = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        url="http://127.0.0.1:8000/hook",
        secret=None,
    )
    service.get_by_id = AsyncMock(return_value=endpoint)
    post = AsyncMock()
    monkeypatch.setattr("httpx.AsyncClient.post", post)

    status_code, success, message = await service.ping(
        AsyncMock(),
        endpoint.id,
        user_id,
    )

    assert status_code is None
    assert success is False
    assert "사설/로컬 네트워크" in message
    post.assert_not_called()
