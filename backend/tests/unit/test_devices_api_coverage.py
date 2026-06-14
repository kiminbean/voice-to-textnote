import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.api.v1.auth.devices import (
    _get_push,
    is_valid_uuid,
    list_devices,
    register_device,
    unregister_device,
)
from backend.schemas.device import DeviceRegisterRequest


def _user(user_id: uuid.UUID | None = None):
    return SimpleNamespace(id=user_id or uuid.uuid4())


def test_get_push_returns_push_service_instance():
    service = _get_push()

    assert hasattr(service, "register_device")
    assert hasattr(service, "get_user_tokens")


def test_is_valid_uuid_accepts_valid_uuid_and_rejects_invalid_value():
    assert is_valid_uuid(str(uuid.uuid4())) is True
    assert is_valid_uuid("not-a-uuid") is False


@pytest.mark.asyncio
async def test_register_device_returns_created_device_response():
    current_user = _user()
    now = datetime.now(UTC)
    token_id = uuid.uuid4()
    device_token = SimpleNamespace(
        id=token_id,
        fcm_token="fcm-token-1",
        platform="ios",
        device_id="phone-1",
        created_at=now,
        updated_at=now,
    )
    query_result = MagicMock()
    query_result.scalar_one.return_value = device_token
    db = AsyncMock()
    db.execute.return_value = query_result
    push_service = SimpleNamespace(register_device=AsyncMock())
    req = DeviceRegisterRequest(
        fcm_token="fcm-token-1",
        platform="ios",
        device_id="phone-1",
    )

    with patch("backend.app.api.v1.auth.devices._get_push", return_value=push_service):
        response = await register_device(req=req, current_user=current_user, db=db)

    push_service.register_device.assert_awaited_once_with(
        device_id="phone-1",
        fcm_token="fcm-token-1",
        platform="ios",
        db=db,
        user_id=str(current_user.id),
    )
    assert response.id == token_id
    assert response.fcm_token == "fcm-token-1"
    assert response.platform == "ios"
    assert response.device_id == "phone-1"


@pytest.mark.asyncio
async def test_unregister_device_deactivates_requested_device_id():
    current_user = _user()
    db = AsyncMock()
    push_service = SimpleNamespace(
        unregister_device=AsyncMock(),
    )

    with patch("backend.app.api.v1.auth.devices._get_push", return_value=push_service):
        result = await unregister_device(
            device_id="phone-1",
            current_user=current_user,
            db=db,
        )

    assert result is None
    push_service.unregister_device.assert_awaited_once_with(
        db=db,
        user_id=str(current_user.id),
        device_id="phone-1",
    )


@pytest.mark.asyncio
async def test_unregister_device_no_active_tokens_is_idempotent():
    current_user = _user()
    db = AsyncMock()
    push_service = SimpleNamespace(
        unregister_device=AsyncMock(),
    )

    with patch("backend.app.api.v1.auth.devices._get_push", return_value=push_service):
        result = await unregister_device(
            device_id="phone-1",
            current_user=current_user,
            db=db,
        )

    assert result is None
    push_service.unregister_device.assert_awaited_once_with(
        db=db,
        user_id=str(current_user.id),
        device_id="phone-1",
    )


@pytest.mark.asyncio
async def test_list_devices_maps_active_device_tokens():
    current_user = _user()
    now = datetime.now(UTC)
    token_id = uuid.uuid4()
    device_token = SimpleNamespace(
        id=token_id,
        fcm_token="fcm-token-1",
        platform="android",
        device_id="pixel-1",
        created_at=now,
        updated_at=now,
    )

    scalars = MagicMock()
    scalars.all.return_value = [device_token]
    query_result = MagicMock()
    query_result.scalars.return_value = scalars
    db = AsyncMock()
    db.execute.return_value = query_result

    response = await list_devices(current_user=current_user, db=db)

    assert response.total == 1
    assert response.devices[0].id == token_id
    assert response.devices[0].fcm_token == "fcm-token-1"
    assert response.devices[0].platform == "android"
    assert response.devices[0].device_id == "pixel-1"
