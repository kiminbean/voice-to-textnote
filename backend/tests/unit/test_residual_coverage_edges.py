"""Residual single-line coverage edges for providers, mappers, and reprs."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace


def test_smart_summary_dependency_returns_service():
    from backend.app.api.v1.minutes.smart_summary import get_smart_summary_service
    from backend.services.smart_summary_service import SmartSummaryService

    assert isinstance(get_smart_summary_service(), SmartSummaryService)


def test_sentiment_mapping_returns_dict_unchanged():
    from backend.app.api.v1.analytics.sentiment import _sentiment_mapping

    payload = {"speaker_name": "Alice", "overall_score": 0.4}

    assert _sentiment_mapping(payload) is payload


def test_completed_action_item_response_has_full_progress():
    from backend.app.api.v1.minutes.action_items_crud import _to_action_item_response
    from backend.app.schemas.action_item import ActionItemPriority, ActionItemStatus

    now = datetime.now(UTC)
    action_item = SimpleNamespace(
        id=uuid.uuid4(),
        title="완료 항목",
        description=None,
        status=ActionItemStatus.completed.value,
        priority=ActionItemPriority.medium.value,
        assignee_id=None,
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        due_date=now,
        completed_at=now,
        completed_by=None,
        completion_notes=None,
        meeting_id=None,
        tags=[],
        estimated_hours=None,
        actual_hours=None,
        category=None,
    )

    response = _to_action_item_response(action_item)

    assert response.progress_percentage == 100.0
    assert response.is_overdue is False
    assert response.time_remaining_hours is None


def test_in_progress_action_item_response_has_half_progress():
    from backend.app.api.v1.minutes.action_items_crud import _to_action_item_response
    from backend.app.schemas.action_item import ActionItemPriority, ActionItemStatus

    now = datetime.now(UTC)
    action_item = SimpleNamespace(
        id=uuid.uuid4(),
        title="진행 항목",
        description=None,
        status=ActionItemStatus.in_progress.value,
        priority=ActionItemPriority.high.value,
        assignee_id=None,
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        due_date=None,
        completed_at=None,
        completed_by=None,
        completion_notes=None,
        meeting_id=None,
        tags=[],
        estimated_hours=None,
        actual_hours=None,
        category=None,
    )

    response = _to_action_item_response(action_item)

    assert response.progress_percentage == 50.0


def test_database_model_repr_methods_include_key_fields():
    from backend.db.collab_models import CollabSession
    from backend.db.device_token_models import DeviceToken
    from backend.db.obsidian_models import ObsidianConfig

    obsidian_config = ObsidianConfig()
    obsidian_config.id = 1
    obsidian_config.vault_name = "Vault"
    assert "Vault" in repr(obsidian_config)

    device = DeviceToken()
    device.id = uuid.uuid4()
    device.user_id = uuid.uuid4()
    device.platform = "ios"
    device.is_active = True
    assert "ios" in repr(device)

    session = CollabSession()
    session.id = uuid.uuid4()
    session.task_id = "task-1"
    assert "task-1" in repr(session)
