import importlib
import json
from unittest.mock import MagicMock, patch

import pytest

from backend.schemas.transcription import TaskStatus
from backend.workers.tasks.status_context import merge_existing_status_context


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.cache_ttl_seconds = 86400
    settings.diarization_result_ttl = 86400
    settings.minutes_result_ttl = 86400
    settings.summary_result_ttl = 86400
    settings.tone_result_ttl = 86400
    return settings


def test_merge_existing_status_context_preserves_access_metadata():
    existing = {
        "created_at": "2026-01-01T00:00:00+00:00",
        "user_id": "user-1",
        "is_guest": True,
        "guest_session_id": "guest-1",
        "stt_task_id": "stt-1",
        "diarization_task_id": "dia-1",
        "minutes_task_id": "min-1",
        "summary_task_id": "sum-1",
    }

    merged = merge_existing_status_context(
        json.dumps(existing),
        {"task_id": "task-1", "status": "processing"},
    )

    assert merged["created_at"] == "2026-01-01T00:00:00+00:00"
    assert merged["user_id"] == "user-1"
    assert merged["is_guest"] is True
    assert merged["guest_session_id"] == "guest-1"
    assert merged["stt_task_id"] == "stt-1"
    assert merged["diarization_task_id"] == "dia-1"
    assert merged["minutes_task_id"] == "min-1"
    assert merged["summary_task_id"] == "sum-1"


def test_merge_existing_status_context_ignores_malformed_existing_status():
    merged = merge_existing_status_context(
        "{not-json",
        {"task_id": "task-1", "status": "processing"},
    )

    assert merged == {"task_id": "task-1", "status": "processing"}


@pytest.mark.parametrize(
    ("module_name", "function_name", "call_args"),
    [
        ("backend.workers.tasks.transcription_task", "_update_task_status", ("task-1",)),
        ("backend.workers.tasks.diarization_task", "_update_task_status", ("task-1",)),
        ("backend.workers.tasks.minutes_task", "_update_task_status", ("task-1",)),
        ("backend.workers.tasks.summary_task", "_update_task_status", ("task-1",)),
        ("backend.workers.tasks.sentiment_task", "_update_task_status", ("task-1",)),
        ("backend.workers.tasks.tone_task", "_update_task_status", ("task-1",)),
        (
            "backend.workers.tasks.mind_map_task",
            "_update_mind_map_status",
            ("task-1", "summary-current"),
        ),
    ],
)
def test_worker_status_updates_preserve_in_flight_access_context(
    module_name: str,
    function_name: str,
    call_args: tuple[str, ...],
):
    module = importlib.import_module(module_name)
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps(
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "user_id": "user-1",
            "is_guest": False,
            "guest_session_id": "guest-1",
            "stt_task_id": "stt-1",
            "diarization_task_id": "dia-1",
            "minutes_task_id": "min-1",
            "summary_task_id": "sum-existing",
        }
    )

    with (
        patch.object(module, "_get_redis", return_value=mock_redis),
        patch.object(module, "settings", _settings()),
        patch.object(module, "publish_task_event_sync"),
    ):
        getattr(module, function_name)(*call_args, TaskStatus.processing, 0.5)

    stored = json.loads(mock_redis.setex.call_args.args[2])
    assert stored["created_at"] == "2026-01-01T00:00:00+00:00"
    assert stored["user_id"] == "user-1"
    assert stored["is_guest"] is False
    assert stored["guest_session_id"] == "guest-1"
    assert stored["stt_task_id"] == "stt-1"
    assert stored["diarization_task_id"] == "dia-1"
    assert stored["minutes_task_id"] == "min-1"

    if module_name.endswith("mind_map_task"):
        assert stored["summary_task_id"] == "summary-current"
    else:
        assert stored["summary_task_id"] == "sum-existing"
