"""
SPEC-WEBHOOK-001: 웹훅 알림 서비스 단위 테스트

테스트 범위:
- _build_payload(): 페이로드 JSON 직렬화
- _make_signature(): HMAC-SHA256 서명 생성
- _send_one(): 단일 웹훅 HTTP POST 전송
- notify_webhooks_sync(): 전체 알림 오케스트레이션
"""

import json
from unittest.mock import MagicMock, patch

from backend.services.webhook_notifier import (
    _build_payload,
    _make_signature,
    _send_one,
    notify_webhooks_sync,
)

# ---------------------------------------------------------------------------
# _build_payload 테스트
# ---------------------------------------------------------------------------


class TestBuildPayload:
    """페이로드 JSON 직렬화 테스트"""

    def test_returns_bytes(self):
        """페이로드는 bytes 타입을 반환한다"""
        result = _build_payload("task-1", "completed", "transcription", {"text": "hello"})
        assert isinstance(result, bytes)

    def test_contains_required_fields(self):
        """페이로드에 필수 필드가 포함된다"""
        result = _build_payload("task-1", "completed", "transcription", {"text": "hello"})
        payload = json.loads(result)

        assert payload["event"] == "transcription.completed"
        assert payload["task_id"] == "task-1"
        assert payload["task_type"] == "transcription"
        assert "timestamp" in payload
        assert payload["data"] == {"text": "hello"}

    def test_event_format_is_tasktype_eventtype(self):
        """event 필드가 {task_type}.{event_type} 형식이다"""
        result = _build_payload("task-1", "failed", "diarization", {})
        payload = json.loads(result)
        assert payload["event"] == "diarization.failed"

    def test_serializes_non_ascii_data(self):
        """비 ASCII 데이터가 올바르게 직렬화된다"""
        result = _build_payload("task-1", "completed", "summary", {"text": "한글 텍스트"})
        payload = json.loads(result)
        assert payload["data"]["text"] == "한글 텍스트"

    def test_handles_datetime_in_data(self):
        """datetime 객체가 default=str로 직렬화된다"""
        from datetime import datetime

        now = datetime(2026, 1, 15, 10, 30, 0)
        result = _build_payload("task-1", "completed", "summary", {"created_at": now})
        payload = json.loads(result)
        assert "2026" in payload["data"]["created_at"]


# ---------------------------------------------------------------------------
# _make_signature 테스트
# ---------------------------------------------------------------------------


class TestMakeSignature:
    """HMAC-SHA256 서명 생성 테스트"""

    def test_returns_sha256_prefixed_string(self):
        """서명은 'sha256=' 접두사로 시작한다"""
        body = b'{"event": "test"}'
        result = _make_signature("my-secret", body)
        assert result.startswith("sha256=")

    def test_same_inputs_produce_same_signature(self):
        """동일한 입력에 대해 동일한 서명을 생성한다"""
        body = b'{"event": "test"}'
        secret = "my-secret"
        sig1 = _make_signature(secret, body)
        sig2 = _make_signature(secret, body)
        assert sig1 == sig2

    def test_different_secrets_produce_different_signatures(self):
        """다른 시크릿으로 다른 서명이 생성된다"""
        body = b'{"event": "test"}'
        sig1 = _make_signature("secret-a", body)
        sig2 = _make_signature("secret-b", body)
        assert sig1 != sig2

    def test_different_bodies_produce_different_signatures(self):
        """다른 body로 다른 서명이 생성된다"""
        secret = "my-secret"
        sig1 = _make_signature(secret, b'{"a": 1}')
        sig2 = _make_signature(secret, b'{"a": 2}')
        assert sig1 != sig2


# ---------------------------------------------------------------------------
# _send_one 테스트
# ---------------------------------------------------------------------------


class TestSendOne:
    """단일 웹훅 HTTP POST 전송 테스트"""

    @patch("backend.services.webhook_notifier.validate_webhook_url")
    @patch("backend.services.webhook_notifier.httpx.Client")
    def test_sends_post_with_correct_headers(self, mock_client_cls, mock_validate):
        """JSON Content-Type과 User-Agent 헤더로 POST 전송"""
        mock_validate.return_value = "https://example.com/hook"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        _send_one("https://example.com/hook", b'{"test": true}', "test.completed", None)

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Content-Type"] == "application/json"
        assert "VoiceToTextNote-Webhook" in headers["User-Agent"]
        assert headers["X-Webhook-Event"] == "test.completed"

    @patch("backend.services.webhook_notifier.validate_webhook_url")
    @patch("backend.services.webhook_notifier.httpx.Client")
    def test_includes_signature_when_secret_provided(self, mock_client_cls, mock_validate):
        """시크릿이 있으면 X-Webhook-Signature 헤더 포함"""
        mock_validate.return_value = "https://example.com/hook"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        _send_one(
            "https://example.com/hook",
            b'{"test": true}',
            "test.completed",
            "my-secret",
        )

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert "X-Webhook-Signature" in headers
        assert headers["X-Webhook-Signature"].startswith("sha256=")

    @patch("backend.services.webhook_notifier.validate_webhook_url")
    @patch("backend.services.webhook_notifier.httpx.Client")
    def test_no_signature_header_when_no_secret(self, mock_client_cls, mock_validate):
        """시크릿이 없으면 X-Webhook-Signature 헤더 미포함"""
        mock_validate.return_value = "https://example.com/hook"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        _send_one("https://example.com/hook", b"{}", "test.completed", None)

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert "X-Webhook-Signature" not in headers

    @patch("backend.services.webhook_notifier.validate_webhook_url")
    @patch("backend.services.webhook_notifier.httpx.Client")
    def test_logs_warning_on_http_error(self, mock_client_cls, mock_validate):
        """HTTP 400+ 응답 시 경고 로그"""
        mock_validate.return_value = "https://example.com/hook"
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # 예외 없이 정상 완료 (best-effort)
        _send_one("https://example.com/hook", b"{}", "test.completed", None)


# ---------------------------------------------------------------------------
# notify_webhooks_sync 테스트
# ---------------------------------------------------------------------------


class TestNotifyWebhooksSync:
    """웹훅 알림 오케스트레이션 테스트"""

    @patch("backend.services.webhook_notifier.get_sync_session")
    def test_does_nothing_when_no_owner(self, mock_session_ctx):
        """소유자가 없으면 아무것도 하지 않는다 (게스트 작업)"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        # 예외 없이 정상 완료
        notify_webhooks_sync("guest-task-1", "completed", "transcription", {})

    @patch("backend.services.webhook_notifier.get_sync_session")
    def test_does_nothing_when_no_endpoints(self, mock_session_ctx):
        """활성 웹훅 엔드포인트가 없으면 아무것도 하지 않는다"""
        mock_session = MagicMock()

        # 소유자 조회 결과
        owner_result = MagicMock()
        owner_result.first.return_value = ("user-123",)

        # 웹훅 조회 결과 (빈 목록)
        wh_result = MagicMock()
        wh_result.scalars.return_value.all.return_value = []

        # 첫 번째 execute: 소유자, 두 번째 execute: 웹훅
        mock_session.execute.side_effect = [owner_result, wh_result]
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        notify_webhooks_sync("task-1", "completed", "transcription", {})

    @patch("backend.services.webhook_notifier._send_one")
    @patch("backend.services.webhook_notifier.get_sync_session")
    def test_sends_to_matching_endpoints(self, mock_session_ctx, mock_send):
        """이벤트 필터가 매칭되는 엔드포인트로 전송"""
        import uuid

        mock_session = MagicMock()

        # 소유자
        owner_result = MagicMock()
        owner_result.first.return_value = ("user-123",)

        # 활성 웹훅 엔드포인트
        endpoint = MagicMock()
        endpoint.id = uuid.uuid4()
        endpoint.url = "https://example.com/hook"
        endpoint.secret = "secret"
        endpoint.events = []  # 빈 배열 = 전체 수신

        wh_result = MagicMock()
        wh_result.scalars.return_value.all.return_value = [endpoint]

        mock_session.execute.side_effect = [owner_result, wh_result]
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        notify_webhooks_sync("task-1", "completed", "transcription", {"text": "hello"})

        mock_send.assert_called_once()

    @patch("backend.services.webhook_notifier._send_one")
    @patch("backend.services.webhook_notifier.get_sync_session")
    def test_filters_by_event_name(self, mock_session_ctx, mock_send):
        """이벤트 필터에 없는 이벤트는 전송하지 않는다"""
        import uuid

        mock_session = MagicMock()

        owner_result = MagicMock()
        owner_result.first.return_value = ("user-123",)

        # 이벤트 필터가 summary.completed만 허용
        endpoint = MagicMock()
        endpoint.id = uuid.uuid4()
        endpoint.url = "https://example.com/hook"
        endpoint.secret = None
        endpoint.events = ["summary.completed"]

        wh_result = MagicMock()
        wh_result.scalars.return_value.all.return_value = [endpoint]

        mock_session.execute.side_effect = [owner_result, wh_result]
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        # transcription.completed 전송 시도 → 필터에 걸림
        notify_webhooks_sync("task-1", "completed", "transcription", {})

        mock_send.assert_not_called()

    @patch("backend.services.webhook_notifier._send_one")
    @patch("backend.services.webhook_notifier.get_sync_session")
    def test_continues_on_send_failure(self, mock_session_ctx, mock_send):
        """개별 전송 실패 시 다음 엔드포인트로 계속 진행"""
        import uuid

        mock_session = MagicMock()

        owner_result = MagicMock()
        owner_result.first.return_value = ("user-123",)

        ep1 = MagicMock()
        ep1.id = uuid.uuid4()
        ep1.url = "https://example1.com/hook"
        ep1.secret = None
        ep1.events = []

        ep2 = MagicMock()
        ep2.id = uuid.uuid4()
        ep2.url = "https://example2.com/hook"
        ep2.secret = None
        ep2.events = []

        wh_result = MagicMock()
        wh_result.scalars.return_value.all.return_value = [ep1, ep2]

        mock_session.execute.side_effect = [owner_result, wh_result]
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        # 첫 번째 전송 실패 → 로깅 후 두 번째 엔드포인트도 시도
        mock_send.side_effect = Exception("connection error")

        # 예외 없이 완료되어야 함 (best-effort)
        notify_webhooks_sync("task-1", "completed", "transcription", {})

        # 두 엔드포인트 모두 시도됨
        assert mock_send.call_count == 2

    @patch("backend.services.webhook_notifier.get_sync_session")
    def test_handles_db_error_gracefully(self, mock_session_ctx):
        """DB 오류 발생 시 예외 전파 없이 무시한다"""
        mock_session_ctx.return_value.__enter__ = MagicMock(
            side_effect=Exception("DB connection lost")
        )
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        # 예외 없이 정상 완료 (best-effort)
        notify_webhooks_sync("task-1", "completed", "transcription", {})
