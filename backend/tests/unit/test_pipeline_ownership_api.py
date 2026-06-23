"""Account ownership propagation tests for pipeline entrypoints."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _request_with_user(user_id: uuid.UUID):
    return SimpleNamespace(state=SimpleNamespace(user_id=str(user_id)))


def _request_with_guest(session_id: str):
    return SimpleNamespace(
        state=SimpleNamespace(is_guest=True, guest_session_id=session_id)
    )


@pytest.mark.asyncio
async def test_create_minutes_passes_authenticated_user_to_worker():
    from backend.app.api.v1.minutes.minutes import create_minutes
    from backend.schemas.minutes import MinutesCreateRequest

    user_id = uuid.uuid4()
    redis = AsyncMock()
    redis.scard.return_value = 0
    redis.setex.return_value = True

    with patch("backend.workers.tasks.minutes_task.minutes_celery_task") as celery:
        response = await create_minutes(
            http_request=_request_with_user(user_id),
            request=MinutesCreateRequest(
                diarization_task_id="dia-owned-001",
                stt_task_id="stt-owned-001",
            ),
            redis_client=redis,
        )

    assert response["status"] == "pending"
    _, kwargs = celery.delay.call_args
    assert kwargs["user_id"] == str(user_id)
    assert kwargs["stt_task_id"] == "stt-owned-001"
    assert kwargs["is_guest"] is False
    assert kwargs["guest_session_id"] is None


@pytest.mark.asyncio
async def test_create_minutes_passes_guest_session_to_worker():
    from backend.app.api.v1.minutes.minutes import create_minutes
    from backend.schemas.minutes import MinutesCreateRequest

    redis = AsyncMock()
    redis.scard.return_value = 0
    redis.setex.return_value = True

    with patch("backend.workers.tasks.minutes_task.minutes_celery_task") as celery:
        await create_minutes(
            http_request=_request_with_guest("guest-session-001"),
            request=MinutesCreateRequest(diarization_task_id="dia-guest-001"),
            redis_client=redis,
        )

    _, kwargs = celery.delay.call_args
    assert kwargs["user_id"] is None
    assert kwargs["is_guest"] is True
    assert kwargs["guest_session_id"] == "guest-session-001"


@pytest.mark.asyncio
async def test_create_summary_passes_authenticated_user_to_worker():
    from backend.app.api.v1.minutes.summary import create_summary
    from backend.schemas.summary import SummaryCreateRequest

    user_id = uuid.uuid4()
    redis = AsyncMock()
    redis.scard.return_value = 0
    redis.setex.return_value = True

    with patch("backend.workers.tasks.summary_task.summary_celery_task") as celery:
        response = await create_summary(
            http_request=_request_with_user(user_id),
            request=SummaryCreateRequest(minutes_task_id="minutes-owned-001"),
            redis_client=redis,
        )

    assert response["status"] == "pending"
    _, kwargs = celery.delay.call_args
    assert kwargs["user_id"] == str(user_id)
    assert kwargs["minutes_task_id"] == "minutes-owned-001"
    assert kwargs["is_guest"] is False
    assert kwargs["guest_session_id"] is None
