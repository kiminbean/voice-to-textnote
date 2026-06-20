"""PushService production-mode and branch coverage tests."""

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import backend.services.push_service as push_module
from backend.services.push_service import PushService


def _install_fake_firebase(monkeypatch, *, apps=None):
    firebase_admin = types.ModuleType("firebase_admin")
    credentials = types.ModuleType("firebase_admin.credentials")
    messaging = types.ModuleType("firebase_admin.messaging")

    firebase_admin._apps = apps if apps is not None else []
    firebase_admin.initialize_app = MagicMock()
    credentials.Certificate = MagicMock(return_value="credential")

    class Notification:
        def __init__(self, title, body):
            self.title = title
            self.body = body

    class Message:
        def __init__(self, notification, data, token):
            self.notification = notification
            self.data = data
            self.token = token

    class MulticastMessage:
        def __init__(self, notification, data, tokens):
            self.notification = notification
            self.data = data
            self.tokens = tokens

    messaging.Notification = Notification
    messaging.Message = Message
    messaging.MulticastMessage = MulticastMessage
    messaging.send = MagicMock(return_value="message-id")
    messaging.send_each_for_multicast = MagicMock(
        return_value=SimpleNamespace(success_count=2, failure_count=1)
    )

    firebase_admin.credentials = credentials
    firebase_admin.messaging = messaging
    monkeypatch.setitem(sys.modules, "firebase_admin", firebase_admin)
    monkeypatch.setitem(sys.modules, "firebase_admin.credentials", credentials)
    monkeypatch.setitem(sys.modules, "firebase_admin.messaging", messaging)
    return firebase_admin, credentials, messaging


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _rows_result(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


def test_ensure_firebase_initializes_real_app(monkeypatch):
    firebase_admin, credentials, _ = _install_fake_firebase(monkeypatch, apps=[])
    monkeypatch.setattr(push_module.settings, "firebase_credentials_path", "/tmp/service.json")

    service = PushService()
    service._ensure_firebase_initialized()

    credentials.Certificate.assert_called_once_with("/tmp/service.json")
    firebase_admin.initialize_app.assert_called_once_with("credential")
    assert service._firebase_initialized is True
    assert service._is_mock_mode is False


def test_ensure_firebase_reuses_existing_app(monkeypatch):
    firebase_admin, credentials, _ = _install_fake_firebase(monkeypatch, apps=["app"])
    monkeypatch.setattr(push_module.settings, "firebase_credentials_path", "/tmp/service.json")

    service = PushService()
    service._ensure_firebase_initialized()

    credentials.Certificate.assert_not_called()
    firebase_admin.initialize_app.assert_not_called()
    assert service._is_mock_mode is False


@pytest.mark.asyncio
async def test_send_push_uses_firebase_message_in_real_mode(monkeypatch):
    _, _, messaging = _install_fake_firebase(monkeypatch)
    service = PushService()
    service._firebase_initialized = True
    service._is_mock_mode = False

    result = await service.send_push(
        token="token-1",
        title="완료",
        body="회의록 생성 완료",
        data={"meeting_id": "meeting-1"},
    )

    assert result is True
    message = messaging.send.call_args.args[0]
    assert message.notification.title == "완료"
    assert message.notification.body == "회의록 생성 완료"
    assert message.data == {"meeting_id": "meeting-1"}
    assert message.token == "token-1"


@pytest.mark.asyncio
async def test_send_push_returns_false_on_firebase_error(monkeypatch):
    _, _, messaging = _install_fake_firebase(monkeypatch)
    monkeypatch.setattr(push_module, "FirebaseError", RuntimeError)
    monkeypatch.setattr(push_module, "InvalidArgumentError", ValueError)
    messaging.send.side_effect = RuntimeError("fcm down")
    service = PushService()
    service._firebase_initialized = True
    service._is_mock_mode = False

    assert await service.send_push("token", "title", "body") is False


@pytest.mark.asyncio
async def test_send_push_mock_mode_logs_data_and_succeeds():
    service = PushService()
    service._firebase_initialized = True
    service._is_mock_mode = True

    with patch("backend.services.push_service.logger") as logger:
        result = await service.send_push("token-abcdef", "title", "body", data={"k": "v"})

    assert result is True
    assert logger.info.call_count == 2


@pytest.mark.asyncio
async def test_send_multicast_uses_firebase_response_counts(monkeypatch):
    _, _, messaging = _install_fake_firebase(monkeypatch)
    service = PushService()
    service._firebase_initialized = True
    service._is_mock_mode = False

    result = await service.send_multicast(
        tokens=["a", "b", "c"],
        title="알림",
        body="본문",
        data={"screen": "result"},
    )

    assert result == {"success_count": 2, "failure_count": 1, "invalid_tokens": []}
    message = messaging.send_each_for_multicast.call_args.args[0]
    assert message.tokens == ["a", "b", "c"]
    assert message.data == {"screen": "result"}


@pytest.mark.asyncio
async def test_send_multicast_empty_and_mock_mode_branches():
    service = PushService()
    service._firebase_initialized = True
    service._is_mock_mode = True

    empty = await service.send_multicast([], "title", "body")
    assert empty == {"success_count": 0, "failure_count": 0, "invalid_tokens": []}

    result = await service.send_multicast(["a", "b"], "title", "body")
    assert result == {"success_count": 2, "failure_count": 0, "invalid_tokens": []}


@pytest.mark.asyncio
async def test_register_device_rotates_to_existing_token_record():
    old_device = SimpleNamespace(id="old", is_active=True)
    token_device = SimpleNamespace(
        id="new",
        user_id="other",
        platform="ios",
        device_id="other-device",
        fcm_token="same-token",
        is_active=False,
    )
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar_result(old_device), _scalar_result(token_device)])

    await PushService().register_device(
        device_id="phone-1",
        fcm_token="same-token",
        db=db,
        user_id="user-1",
        platform="android",
    )

    assert old_device.is_active is False
    assert token_device.user_id == "user-1"
    assert token_device.platform == "android"
    assert token_device.device_id == "phone-1"
    assert token_device.is_active is True
    db.add.assert_not_called()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_device_creates_new_db_record_when_no_existing_token():
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result(None))
    db.commit = AsyncMock()

    await PushService().register_device(
        fcm_token="new-token",
        db=db,
        user_id="user-1",
        platform="ios",
    )

    added = db.add.call_args.args[0]
    assert added.user_id == "user-1"
    assert added.fcm_token == "new-token"
    assert added.platform == "ios"
    assert added.is_active is True
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_device_async_in_memory_mode():
    service = PushService()

    await service.register_device(device_id="device-1", fcm_token="token-1")

    assert service.get_all_devices() == {"device-1": "token-1"}


@pytest.mark.asyncio
async def test_register_device_rejects_incomplete_parameter_sets():
    with pytest.raises(ValueError, match="잘못된 파라미터 조합"):
        await PushService().register_device(fcm_token="token-only")


@pytest.mark.asyncio
async def test_unregister_device_by_user_device_commits_when_found():
    device = SimpleNamespace(
        user_id="user-1",
        device_id="phone-1",
        fcm_token="token-1234567890",
        is_active=True,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(device))

    result = await PushService().unregister_device(
        db=db,
        user_id="user-1",
        device_id="phone-1",
    )

    assert result is None
    assert device.is_active is False
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_unregister_device_by_user_device_is_idempotent_when_missing():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(None))

    result = await PushService().unregister_device(
        db=db,
        user_id="user-1",
        device_id="missing",
    )

    assert result is None
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_unregister_device_by_fcm_token_commits_when_found():
    device = SimpleNamespace(
        user_id="user-1",
        device_id="phone-1",
        fcm_token="token-1234567890",
        is_active=True,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(device))

    await PushService().unregister_device(db=db, fcm_token="token-1234567890")

    assert device.is_active is False
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_unregister_device_async_in_memory_mode():
    service = PushService()
    await service.register_device(device_id="device-1", fcm_token="token-1")

    assert await service.unregister_device(device_id="device-1") is True
    assert await service.unregister_device(device_id="device-1") is False


@pytest.mark.asyncio
async def test_unregister_device_rejects_empty_parameters():
    with pytest.raises(ValueError, match="잘못된 파라미터 조합"):
        await PushService().unregister_device()


@pytest.mark.asyncio
async def test_get_user_tokens_extracts_rows():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_rows_result([("token-a",), ("token-b",)]))

    assert await PushService().get_user_tokens(db, "user-1") == ["token-a", "token-b"]


@pytest.mark.asyncio
async def test_invalidate_token_delegates_to_unregister():
    service = PushService()
    db = AsyncMock()

    with patch.object(service, "unregister_device", AsyncMock()) as unregister:
        await service.invalidate_token(db, "token-a")

    unregister.assert_awaited_once_with(db=db, fcm_token="token-a")


@pytest.mark.asyncio
async def test_send_to_user_without_tokens_returns_empty_counts():
    service = PushService()

    with patch.object(service, "get_user_tokens", AsyncMock(return_value=[])):
        result = await service.send_to_user(
            AsyncMock(),
            user_id="user-1",
            meeting_id="meeting-1",
            title="title",
            body="body",
        )

    assert result == {"success_count": 0, "failure_count": 0, "invalid_tokens": []}


@pytest.mark.asyncio
async def test_send_to_user_preserves_existing_data_and_adds_meeting_id():
    service = PushService()
    payload = {"screen": "summary"}

    with (
        patch.object(service, "get_user_tokens", AsyncMock(return_value=["token-a"])),
        patch.object(
            service,
            "send_multicast",
            AsyncMock(return_value={"success_count": 1, "failure_count": 0, "invalid_tokens": []}),
        ) as multicast,
    ):
        result = await service.send_to_user(
            AsyncMock(),
            user_id="user-1",
            meeting_id="meeting-1",
            title="title",
            body="body",
            data=payload,
        )

    assert result["success_count"] == 1
    multicast.assert_awaited_once()
    assert multicast.await_args.kwargs["data"] == {
        "screen": "summary",
        "meeting_id": "meeting-1",
    }
    assert payload["meeting_id"] == "meeting-1"


def test_sync_device_wrappers_and_copy_semantics():
    service = PushService()
    service.register_device_sync("device-1", "token-1")

    devices = service.get_all_devices()
    devices["device-2"] = "token-2"

    assert service.get_all_devices() == {"device-1": "token-1"}
    assert service.unregister_device_sync("device-1") is True
    assert service.unregister_device_sync("device-1") is False


def test_get_push_service_creates_singleton_when_empty(monkeypatch):
    monkeypatch.setattr(push_module, "_push_service", None)

    first = push_module.get_push_service()
    second = push_module.get_push_service()

    assert first is second
