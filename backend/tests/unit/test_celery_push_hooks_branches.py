"""Branch coverage for Celery push notification hooks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.workers.hooks import celery_push_hooks as hooks


def test_fire_push_async_dispatches_completed_and_failed_statuses():
    with patch.object(hooks, "on_pipeline_success", AsyncMock(return_value=True)) as success:
        hooks._fire_push_async("user-1", "meeting-1", "task-1", "completed")
    success.assert_awaited_once_with(
        user_id="user-1",
        meeting_id="meeting-1",
        task_id="task-1",
    )

    with patch.object(hooks, "on_pipeline_failure", AsyncMock(return_value=True)) as failure:
        hooks._fire_push_async("user-1", "meeting-1", "task-1", "failed", "bad")
    failure.assert_awaited_once_with(
        user_id="user-1",
        meeting_id="meeting-1",
        task_id="task-1",
        error_message="bad",
    )


def test_fire_push_async_and_sync_swallow_hook_errors():
    with (
        patch.object(hooks, "on_pipeline_success", AsyncMock(side_effect=RuntimeError("boom"))),
        patch.object(hooks, "logger") as logger,
    ):
        hooks._fire_push_async("user-1", "meeting-1", "task-1", "completed")
    logger.error.assert_called_once()

    with (
        patch.object(hooks, "_fire_push_async", side_effect=RuntimeError("boom")),
        patch.object(hooks, "logger") as logger,
    ):
        hooks.fire_push_sync("user-1", "meeting-1", "task-1", "completed")
    logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_success_sends_completion_push_and_handles_no_db():
    assert await hooks.on_pipeline_success("user-1", "meeting-1", "task-1") is False

    push_service = MagicMock()
    push_service.send_to_user = AsyncMock(return_value={"success_count": 2, "failure_count": 0})
    with patch("backend.services.push_service.get_push_service", return_value=push_service):
        result = await hooks.on_pipeline_success(
            "user-1",
            "meeting-1",
            "task-1",
            db_session=MagicMock(),
        )

    assert result is True
    push_service.send_to_user.assert_awaited_once()
    kwargs = push_service.send_to_user.await_args.kwargs
    assert kwargs["title"] == "회의록 처리 완료"
    assert kwargs["data"] == {"task_id": "task-1", "type": "pipeline_complete"}


@pytest.mark.asyncio
async def test_pipeline_success_returns_false_when_push_service_fails_or_has_no_success():
    push_service = MagicMock()
    push_service.send_to_user = AsyncMock(return_value={"success_count": 0, "failure_count": 1})
    with patch("backend.services.push_service.get_push_service", return_value=push_service):
        assert (
            await hooks.on_pipeline_success("user-1", "meeting-1", "task-1", db_session=MagicMock())
            is False
        )

    push_service.send_to_user = AsyncMock(side_effect=RuntimeError("fcm down"))
    with patch("backend.services.push_service.get_push_service", return_value=push_service):
        assert (
            await hooks.on_pipeline_success("user-1", "meeting-1", "task-1", db_session=MagicMock())
            is False
        )


@pytest.mark.asyncio
async def test_pipeline_failure_sends_failure_push_and_handles_no_db():
    assert await hooks.on_pipeline_failure("user-1", "meeting-1", "task-1") is False

    push_service = MagicMock()
    push_service.send_to_user = AsyncMock(return_value={"success_count": 1, "failure_count": 0})
    long_error = "x" * 250
    with patch("backend.services.push_service.get_push_service", return_value=push_service):
        result = await hooks.on_pipeline_failure(
            "user-1",
            "meeting-1",
            "task-1",
            error_message=long_error,
            db_session=MagicMock(),
        )

    assert result is True
    kwargs = push_service.send_to_user.await_args.kwargs
    assert kwargs["title"] == "회의록 처리 실패"
    assert kwargs["body"].endswith("x" * 50)
    assert kwargs["data"]["type"] == "pipeline_failed"
    assert kwargs["data"]["error"] == "x" * 200


@pytest.mark.asyncio
async def test_pipeline_failure_returns_false_when_push_service_fails_or_has_no_success():
    push_service = MagicMock()
    push_service.send_to_user = AsyncMock(return_value={"success_count": 0, "failure_count": 1})
    with patch("backend.services.push_service.get_push_service", return_value=push_service):
        assert (
            await hooks.on_pipeline_failure("user-1", "meeting-1", "task-1", db_session=MagicMock())
            is False
        )

    push_service.send_to_user = AsyncMock(side_effect=RuntimeError("fcm down"))
    with patch("backend.services.push_service.get_push_service", return_value=push_service):
        assert (
            await hooks.on_pipeline_failure("user-1", "meeting-1", "task-1", db_session=MagicMock())
            is False
        )


def test_get_push_hook_summary_contains_context():
    assert hooks.get_push_hook_summary("user-1", "meeting-1", "task-1", "completed") == {
        "user_id": "user-1",
        "meeting_id": "meeting-1",
        "task_id": "task-1",
        "status": "completed",
        "hook_version": "1.0.0",
    }
