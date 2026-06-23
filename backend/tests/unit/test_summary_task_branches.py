"""Additional branch coverage for summary Celery task helpers and hooks."""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.schemas.summary import SummaryResult
from backend.workers.tasks import summary_task as summary_module


def _redis(active_count: int = 0):
    client = MagicMock()
    client.get.return_value = None
    client.setex.return_value = True
    pipe = MagicMock()
    pipe.execute.return_value = [0, active_count]
    client.pipeline.return_value = pipe
    client.scan_iter.return_value = []
    return client


def _completed_minutes(minutes_task_id: str = "minutes-1") -> dict:
    return {
        "task_id": minutes_task_id,
        "status": "completed",
        "segments": [{"speaker": "A", "text": "hello"}],
        "speakers": [],
        "created_at": "2026-01-02T03:04:05+00:00",
        "total_duration": 12.5,
        "diarization_task_id": "dia-1",
    }


def _summary_generator(summary_text: str = "요약"):
    generator = MagicMock()
    generator.return_value.generate_summary.return_value = SummaryResult(
        summary_text=summary_text,
        action_items=[],
        key_decisions=[],
        next_steps=[],
        sections={"main": summary_text},
    )
    return generator


def _settings():
    settings = MagicMock()
    settings.summary_result_ttl = 86400
    settings.max_concurrent_summaries = 2
    settings.llm_api_key = "sk-test"
    settings.llm_api_key = "sk-test"
    settings.llm_base_url = "https://api.openai.com/v1"
    settings.summary_model = "gpt-4o-mini"
    return settings


def test_summary_task_sends_push_on_completed_result():
    task_id = str(uuid.uuid4())
    minutes_task_id = str(uuid.uuid4())
    redis_client = _redis()
    redis_client.get.side_effect = lambda key: (
        json.dumps(_completed_minutes(minutes_task_id))
        if key == f"task:min:result:{minutes_task_id}"
        else None
    )

    with (
        patch.object(summary_module, "_get_redis", return_value=redis_client),
        patch.object(summary_module, "settings", _settings()),
        patch.object(summary_module, "SummaryGenerator", _summary_generator()),
        patch.object(summary_module, "_trigger_obsidian_auto_export") as auto_export,
        patch("backend.services.sync_service.persist_task_result"),
        patch("backend.app.workers.hooks.celery_push_hooks.fire_push_sync") as push,
    ):
        result = summary_module.summary_task(
            task_id=task_id,
            minutes_task_id=minutes_task_id,
            user_id="user-1",
        )

    assert result["status"] == "completed"
    push.assert_called_once_with(
        user_id="user-1",
        meeting_id=minutes_task_id,
        task_id=task_id,
        status="completed",
    )
    auto_export.assert_called_once_with(minutes_task_id)


def test_summary_task_sends_push_on_missing_minutes_failure():
    task_id = str(uuid.uuid4())
    minutes_task_id = str(uuid.uuid4())
    redis_client = _redis()
    redis_client.get.return_value = None

    with (
        patch.object(summary_module, "_get_redis", return_value=redis_client),
        patch.object(summary_module, "settings", _settings()),
        patch("backend.services.sync_service.persist_task_result"),
        patch("backend.app.workers.hooks.celery_push_hooks.fire_push_sync") as push,
    ):
        result = summary_module.summary_task(
            task_id=task_id,
            minutes_task_id=minutes_task_id,
            user_id="user-1",
        )

    assert result["status"] == "failed"
    push.assert_called_once()
    assert push.call_args.kwargs["status"] == "failed"
    assert minutes_task_id in push.call_args.kwargs["error_message"]


def test_summary_task_sends_push_on_generator_failure():
    task_id = str(uuid.uuid4())
    minutes_task_id = str(uuid.uuid4())
    redis_client = _redis()
    redis_client.get.side_effect = lambda key: (
        json.dumps(_completed_minutes(minutes_task_id))
        if key == f"task:min:result:{minutes_task_id}"
        else None
    )
    generator = _summary_generator()
    generator.return_value.generate_summary.side_effect = RuntimeError("llm failed")

    with (
        patch.object(summary_module, "_get_redis", return_value=redis_client),
        patch.object(summary_module, "settings", _settings()),
        patch.object(summary_module, "SummaryGenerator", generator),
        patch("backend.services.sync_service.persist_task_result"),
        patch("backend.app.workers.hooks.celery_push_hooks.fire_push_sync") as push,
    ):
        result = summary_module.summary_task(
            task_id=task_id,
            minutes_task_id=minutes_task_id,
            user_id="user-1",
        )

    assert result["status"] == "failed"
    assert result["error_message"] == "llm failed"
    push.assert_called_once()
    assert push.call_args.kwargs["error_message"] == "llm failed"


def test_safe_json_and_latest_completed_helpers_cover_invalid_and_sorted_entries():
    assert summary_module._safe_json_load_sync(None) is None
    assert summary_module._safe_json_load_sync("{bad") is None
    assert summary_module._safe_json_load_sync("[1, 2]") is None

    redis_client = MagicMock()
    redis_client.scan_iter.return_value = ["old", "failed", "other", "new"]
    payloads = {
        "old": {
            "minutes_task_id": "minutes-1",
            "status": "completed",
            "completed_at": "2026-01-01T00:00:00+00:00",
            "summary_text": "old",
        },
        "failed": {
            "minutes_task_id": "minutes-1",
            "status": "failed",
            "completed_at": "2026-01-03T00:00:00+00:00",
        },
        "other": {
            "minutes_task_id": "minutes-2",
            "status": "completed",
            "completed_at": "2026-01-04T00:00:00+00:00",
        },
        "new": {
            "minutes_task_id": "minutes-1",
            "status": "completed",
            "created_at": "2026-01-02T00:00:00+00:00",
            "summary_text": "new",
        },
    }
    redis_client.get.side_effect = lambda key: json.dumps(payloads[key])

    assert summary_module._find_latest_summary_sync(redis_client, "missing") is None
    latest = summary_module._find_latest_summary_sync(redis_client, "minutes-1")
    assert latest["summary_text"] == "new"

    redis_client.scan_iter.return_value = ["bad", "valid"]
    redis_client.get.side_effect = lambda key: {
        "bad": "{broken",
        "valid": json.dumps(
            {
                "mode": "lecture",
                "study_notes": "valid",
                "created_at": "2026-01-02T00:00:00+00:00",
            }
        ),
    }[key]

    study_pack = summary_module._find_latest_study_pack_sync(redis_client, "minutes-1")
    assert study_pack["study_notes"] == "valid"


def test_update_task_status_preserves_created_at_and_optional_fields():
    redis_client = _redis()
    redis_client.get.return_value = json.dumps({"created_at": "2026-01-01T00:00:00+00:00"})

    with (
        patch.object(summary_module, "_get_redis", return_value=redis_client),
        patch.object(summary_module, "settings", _settings()),
        patch.object(summary_module, "publish_task_event_sync") as publish,
    ):
        summary_module._update_task_status(
            "task-1",
            summary_module.TaskStatus.failed,
            0.5,
            message="halfway",
            error_message="broken",
        )

    _, _, payload = redis_client.setex.call_args.args
    status_data = json.loads(payload)
    assert status_data["created_at"] == "2026-01-01T00:00:00+00:00"
    assert status_data["message"] == "halfway"
    assert status_data["error_message"] == "broken"
    publish.assert_called_once()
    assert publish.call_args.args[2] == "failed"


def test_trigger_obsidian_auto_export_writes_note_with_related_results():
    minutes_task_id = "minutes-1"
    redis_client = MagicMock()
    redis_client.get.side_effect = lambda key: {
        f"task:min:result:{minutes_task_id}": json.dumps(_completed_minutes(minutes_task_id)),
        "task:sentiment:result:dia-1": json.dumps({"status": "failed"}),
        "task:tone:result:dia-1": json.dumps({"status": "completed", "tone": "formal"}),
        "summary-key": json.dumps(
            {
                "minutes_task_id": minutes_task_id,
                "status": "completed",
                "completed_at": "2026-01-03T00:00:00+00:00",
                "summary_text": "latest",
            }
        ),
        "sentiment-key": json.dumps(
            {
                "minutes_task_id": minutes_task_id,
                "status": "completed",
                "created_at": "2026-01-02T00:00:00+00:00",
                "sentiment": "positive",
            }
        ),
        "study-key": json.dumps(
            {
                "mode": "lecture",
                "study_notes": "학습 노트",
                "created_at": "2026-01-04T00:00:00+00:00",
            }
        ),
    }.get(key)
    redis_client.scan_iter.side_effect = [
        ["summary-key"],
        ["sentiment-key"],
        ["study-key"],
    ]
    service = MagicMock()
    service.validate_vault.return_value = {"valid": True}
    service.compute_file_path.return_value = "/vault/meeting.md"
    service.compose_note.return_value = "# note"
    service.atomic_write.return_value = True
    config = SimpleNamespace(
        auto_export=True,
        vault_path="/vault",
        folder_pattern="{date}",
        filename_pattern="{title}",
        frontmatter_custom={"source": "test"},
        conflict_policy="overwrite",
    )

    with (
        patch(
            "backend.app.api.v1.integrations.obsidian._get_config_from_db",
            return_value=config,
        ),
        patch("backend.services.obsidian_service.obsidian_service", service),
        patch("backend.workers.redis_client.get_worker_redis", return_value=redis_client),
    ):
        summary_module._trigger_obsidian_auto_export(minutes_task_id)

    service.compute_file_path.assert_called_once()
    service.compose_note.assert_called_once()
    compose_args = service.compose_note.call_args.args
    assert compose_args[2]["summary_text"] == "latest"
    assert compose_args[3]["sentiment"] == "positive"
    assert compose_args[4]["tone"] == "formal"
    assert service.compose_note.call_args.kwargs["study_pack_data"]["study_notes"] == "학습 노트"
    service.atomic_write.assert_called_once_with("/vault/meeting.md", "# note", exist_ok=True)


def test_trigger_obsidian_auto_export_skips_invalid_and_missing_inputs():
    minutes_task_id = "minutes-1"
    config = SimpleNamespace(auto_export=True, vault_path="/vault")
    service = MagicMock()
    service.validate_vault.return_value = {"valid": False}

    with (
        patch(
            "backend.app.api.v1.integrations.obsidian._get_config_from_db",
            return_value=config,
        ),
        patch("backend.services.obsidian_service.obsidian_service", service),
    ):
        summary_module._trigger_obsidian_auto_export(minutes_task_id)
    service.validate_vault.assert_called_once_with("/vault")

    service.reset_mock()
    service.validate_vault.return_value = {"valid": True}
    redis_client = MagicMock()
    redis_client.get.return_value = None
    with (
        patch(
            "backend.app.api.v1.integrations.obsidian._get_config_from_db",
            return_value=config,
        ),
        patch("backend.services.obsidian_service.obsidian_service", service),
        patch("backend.workers.redis_client.get_worker_redis", return_value=redis_client),
    ):
        summary_module._trigger_obsidian_auto_export(minutes_task_id)
    service.atomic_write.assert_not_called()


def test_trigger_obsidian_auto_export_skips_unparseable_minutes_and_missing_summary():
    minutes_task_id = "minutes-1"
    config = SimpleNamespace(auto_export=True, vault_path="/vault")
    service = MagicMock()
    service.validate_vault.return_value = {"valid": True}

    malformed_redis = MagicMock()
    malformed_redis.get.return_value = "{bad"
    with (
        patch(
            "backend.app.api.v1.integrations.obsidian._get_config_from_db",
            return_value=config,
        ),
        patch("backend.services.obsidian_service.obsidian_service", service),
        patch("backend.workers.redis_client.get_worker_redis", return_value=malformed_redis),
    ):
        summary_module._trigger_obsidian_auto_export(minutes_task_id)
    service.compute_file_path.assert_not_called()

    service.reset_mock()
    service.validate_vault.return_value = {"valid": True}
    no_summary_redis = MagicMock()
    no_summary_redis.get.side_effect = lambda key: (
        json.dumps(_completed_minutes(minutes_task_id))
        if key == f"task:min:result:{minutes_task_id}"
        else json.dumps({"status": "failed"})
        if key == "task:tone:result:dia-1"
        else None
    )
    no_summary_redis.scan_iter.return_value = []
    with (
        patch(
            "backend.app.api.v1.integrations.obsidian._get_config_from_db",
            return_value=config,
        ),
        patch("backend.services.obsidian_service.obsidian_service", service),
        patch("backend.workers.redis_client.get_worker_redis", return_value=no_summary_redis),
    ):
        summary_module._trigger_obsidian_auto_export(minutes_task_id)
    service.compute_file_path.assert_not_called()


def test_trigger_obsidian_auto_export_skips_existing_file_and_swallows_errors():
    minutes_task_id = "minutes-1"
    redis_client = MagicMock()
    redis_client.get.side_effect = lambda key: {
        f"task:min:result:{minutes_task_id}": json.dumps(_completed_minutes(minutes_task_id)),
        "summary-key": json.dumps(
            {
                "minutes_task_id": minutes_task_id,
                "status": "completed",
                "completed_at": "2026-01-03T00:00:00+00:00",
            }
        ),
    }.get(key)
    redis_client.scan_iter.return_value = ["summary-key"]
    service = MagicMock()
    service.validate_vault.return_value = {"valid": True}
    service.compute_file_path.return_value = "/vault/meeting.md"
    service.compose_note.return_value = "# note"
    service.atomic_write.return_value = False
    config = SimpleNamespace(
        auto_export=True,
        vault_path="/vault",
        folder_pattern="{date}",
        filename_pattern="{title}",
        frontmatter_custom={},
        conflict_policy="skip",
    )

    with (
        patch(
            "backend.app.api.v1.integrations.obsidian._get_config_from_db",
            return_value=config,
        ),
        patch("backend.services.obsidian_service.obsidian_service", service),
        patch("backend.workers.redis_client.get_worker_redis", return_value=redis_client),
    ):
        summary_module._trigger_obsidian_auto_export(minutes_task_id)
    service.atomic_write.assert_called_once_with("/vault/meeting.md", "# note", exist_ok=False)

    with patch(
        "backend.app.api.v1.integrations.obsidian._get_config_from_db",
        side_effect=RuntimeError("db unavailable"),
    ):
        summary_module._trigger_obsidian_auto_export(minutes_task_id)
