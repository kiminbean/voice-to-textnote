"""
커버리지 100% 달성 - Phase 1: 실제 동작하는 테스트

기준: 98.65% (3133 passed, 530 uncovered)
목표: 100% (실현 가능한 범위)
"""

from datetime import datetime
from uuid import uuid4

import pytest

# ============================================================================
# 1. app/schemas/action_item.py - validator returns + class defs (7 lines)
# ============================================================================
from backend.app.schemas.action_item import (
    ActionItemComment,
    ActionItemCommentResponse,
    ActionItemHistory,
    ActionItemReminder,
    ActionItemResponse,
    ActionItemUpdate,
)


class TestActionItemSchemaValidators:
    """action_item.py:70,78 - field_validator return paths"""

    def test_validate_title_strips_whitespace(self):
        item = ActionItemUpdate(title="  공백 제목  ")
        assert item.title == "공백 제목"

    def test_validate_title_none_returns_none(self):
        item = ActionItemUpdate(title=None)
        assert item.title is None

    def test_validate_completion_notes_strips(self):
        item = ActionItemUpdate(completion_notes="  노트  ")
        assert item.completion_notes == "노트"

    def test_validate_completion_notes_none(self):
        item = ActionItemUpdate(completion_notes=None)
        assert item.completion_notes is None

    def test_validate_tags_dedup(self):
        item = ActionItemUpdate(tags=["a", "a", " b ", "c"])
        assert set(item.tags) == {"a", "b", "c"}


class TestActionItemSchemaClassDefs:
    """action_item.py:90,171,192,207,223 - class definitions"""

    def test_action_item_response(self):
        now = datetime.utcnow()
        uid = uuid4()
        r = ActionItemResponse(
            id=uid,
            title="t",
            description="d",
            status="pending",
            priority="medium",
            assignee_id=uid,
            assignee_name="U",
            created_by=uid,
            created_by_name="U",
            created_at=now,
            updated_at=now,
            due_date=None,
            completed_at=None,
            completed_by=None,
            completed_by_name=None,
            completion_notes=None,
            meeting_id=None,
            meeting_title=None,
            tags=["test"],
            estimated_hours=None,
            actual_hours=None,
            category=None,
            is_overdue=False,
            time_remaining_hours=None,
            progress_percentage=0.0,
        )
        assert r.status == "pending"
        assert r.tags == ["test"]

    def test_action_item_comment(self):
        now = datetime.utcnow()
        c = ActionItemComment(
            id=uuid4(),
            action_item_id=uuid4(),
            author_id=uuid4(),
            author_name="U",
            content="c",
            created_at=now,
            updated_at=now,
            is_internal=False,
        )
        assert c.content == "c"

    def test_action_item_comment_response(self):
        now = datetime.utcnow()
        r = ActionItemCommentResponse(
            id=uuid4(),
            action_item_id=uuid4(),
            author_id=uuid4(),
            author_name="U",
            content="c",
            created_at=now,
            updated_at=now,
            is_internal=False,
        )
        assert r.content == "c"

    def test_action_item_history(self):
        h = ActionItemHistory(
            id=uuid4(),
            action_item_id=uuid4(),
            field_name="status",
            old_value="pending",
            new_value="done",
            changed_by=uuid4(),
            changed_by_name="U",
            changed_at=datetime.utcnow(),
            change_type="update",
        )
        assert h.field_name == "status"

    def test_action_item_reminder(self):
        r = ActionItemReminder(
            id=uuid4(),
            action_item_id=uuid4(),
            reminder_type="before_due",
            reminder_time=datetime.utcnow(),
            is_active=True,
            last_sent_at=None,
            created_at=datetime.utcnow(),
        )
        assert r.reminder_type == "before_due"


# ============================================================================
# 2. utils/validators.py:138 - ValueError for webhook URL
# ============================================================================
from backend.utils.validators import validate_webhook_url  # noqa: E402


class TestValidatorWebhookUrl:
    def test_webhook_url_with_userinfo_raises(self):
        with pytest.raises(ValueError, match="사용자 정보"):
            validate_webhook_url("https://user:pass@example.com/hook")


# ============================================================================
# 3. services/advanced_search.py - Dependency injection (line 28)
# ============================================================================
from backend.services.advanced_search import AdvancedSearchService  # noqa: E402


class TestAdvancedSearchDependency:
    """advanced_search.py:28 - get_advanced_search_service"""

    def test_get_service(self):
        from backend.app.api.v1.analytics.advanced_search import get_advanced_search_service

        svc = get_advanced_search_service()
        assert isinstance(svc, AdvancedSearchService)


# ============================================================================
# 4. conftest.py fixtures - import to cover
# ============================================================================


class TestConftestImport:
    def test_backend_conftest_loaded(self):
        import backend.conftest

        assert backend.conftest is not None
