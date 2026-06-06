"""
SPEC-ACTION-001: 액션 아이템 서비스 단위 테스트

테스트 대상: backend/services/action_item_service.py (181 lines, 0% coverage)

서비스 메서드:
- create()             액션 아이템 생성
- list_items()         목록 조회 (필터/페이징)
- get_by_id()          ID 조회
- update()             수정
- delete()             삭제
- get_overview()       개요 통계
- batch_update()       배치 업데이트
- extract_action_items_from_meeting()  회의록에서 액션 아이템 추출
- _calculate_weekly_completion_trend()  주간 추이 계산
- _calculate_productivity_metrics()     생산성 지표 계산
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Model and schema injection handled by backend/tests/unit/conftest.py
from backend.services.action_item_service import ActionItemService

# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = uuid.uuid4()
FAKE_ASSIGNEE_ID = uuid.uuid4()
FAKE_ITEM_ID = uuid.uuid4()


def _make_action_item_instance(**overrides):
    """Create a mock ActionItem instance for testing."""
    now = datetime.utcnow()
    defaults = {
        "id": FAKE_ITEM_ID,
        "title": "Test action item",
        "description": "Test description",
        "status": "pending",
        "priority": "medium",
        "assignee_id": FAKE_ASSIGNEE_ID,
        "created_by": FAKE_USER_ID,
        "due_date": now + timedelta(days=7),
        "meeting_id": None,
        "tags": ["test"],
        "estimated_hours": 2.0,
        "actual_hours": None,
        "category": "development",
        "completed_at": None,
        "completed_by": None,
        "completion_notes": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    instance = MagicMock()
    for k, v in defaults.items():
        setattr(instance, k, v)
    return instance


def _mock_db_result(items=None, first_val=None):
    """Build a mock DB result that supports .scalars().all() / .first() chaining."""
    scalars = MagicMock()
    if items is not None:
        scalars.all.return_value = items
    if first_val is not None:
        scalars.first.return_value = first_val
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


# ---------------------------------------------------------------------------
# create() 테스트
# ---------------------------------------------------------------------------


class TestCreate:
    """ActionItemService.create() 테스트"""

    @pytest.mark.asyncio
    async def test_create_success(self):
        """정상 생성"""
        from backend.app.schemas.action_item import ActionItemCreate, ActionItemPriority

        svc = ActionItemService()
        session = AsyncMock()

        mock_instance = _make_action_item_instance()

        with patch(
            "backend.services.action_item_service.ActionItemModel",
            return_value=mock_instance,
        ):
            result = await svc.create(
                session=session,
                user_id=FAKE_USER_ID,
                payload=ActionItemCreate(
                    title="New task",
                    description="Desc",
                    priority=ActionItemPriority.medium,
                ),
            )

        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once()
        assert result == mock_instance

    @pytest.mark.asyncio
    async def test_create_with_all_fields(self):
        """모든 필드 포함하여 생성"""
        from backend.app.schemas.action_item import ActionItemCreate, ActionItemPriority

        svc = ActionItemService()
        session = AsyncMock()

        mock_instance = _make_action_item_instance()

        with patch(
            "backend.services.action_item_service.ActionItemModel",
            return_value=mock_instance,
        ):
            result = await svc.create(
                session=session,
                user_id=FAKE_USER_ID,
                payload=ActionItemCreate(
                    title="Full task",
                    description="Detailed desc",
                    priority=ActionItemPriority.high,
                    assignee_id=FAKE_ASSIGNEE_ID,
                    due_date=datetime.utcnow() + timedelta(days=3),
                    meeting_id="meeting-123",
                    tags=["urgent", "backend"],
                    estimated_hours=4.0,
                    category="development",
                ),
            )

        assert result == mock_instance
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# list_items() 테스트
# ---------------------------------------------------------------------------


class TestListItems:
    """ActionItemService.list_items() 테스트"""

    @pytest.mark.asyncio
    async def test_list_basic(self):
        """기본 목록 조회"""
        svc = ActionItemService()
        session = AsyncMock()

        item = _make_action_item_instance()
        # Both count and data queries return the same items
        db_result = _mock_db_result(items=[item])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        items, total = await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
        )

        assert total == 1
        assert len(items) == 1
        assert items[0] == item

    @pytest.mark.asyncio
    async def test_list_empty(self):
        """빈 목록"""
        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        items, total = await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
        )

        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self):
        """상태 필터"""
        from backend.app.schemas.action_item import ActionItemStatus

        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        items, total = await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
            status=ActionItemStatus.completed,
        )

        assert session.execute.call_count == 2
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_with_priority_filter(self):
        """우선순위 필터"""
        from backend.app.schemas.action_item import ActionItemPriority

        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
            priority=ActionItemPriority.high,
        )

        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_assignee_filter(self):
        """담당자 필터"""
        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
            assignee_id=FAKE_ASSIGNEE_ID,
        )

        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_meeting_id_filter(self):
        """회의 ID 필터"""
        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
            meeting_id="meeting-123",
        )

        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_due_date_range(self):
        """마감일 범위 필터"""
        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        now = datetime.utcnow()
        await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
            due_from=now - timedelta(days=7),
            due_to=now + timedelta(days=7),
        )

        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_overdue_filter_true(self):
        """지연 항목만 필터"""
        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
            is_overdue=True,
        )

        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_overdue_filter_false(self):
        """지연되지 않은 항목 필터"""
        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
            is_overdue=False,
        )

        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_category_filter(self):
        """카테고리 필터"""
        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
            category="development",
        )

        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_tags_filter(self):
        """태그 필터"""
        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
            tags=["urgent", "backend"],
        )

        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_pagination(self):
        """페이징 적용"""
        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
            limit=10,
            offset=20,
        )

        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_all_filters_combined(self):
        """모든 필터 동시 적용"""
        from backend.app.schemas.action_item import ActionItemPriority, ActionItemStatus

        svc = ActionItemService()
        session = AsyncMock()

        db_result = _mock_db_result(items=[])
        session.execute = AsyncMock(side_effect=[db_result, db_result])

        now = datetime.utcnow()
        await svc.list_items(
            session=session,
            user_id=FAKE_USER_ID,
            status=ActionItemStatus.pending,
            priority=ActionItemPriority.high,
            assignee_id=FAKE_ASSIGNEE_ID,
            meeting_id="meeting-123",
            due_from=now - timedelta(days=7),
            due_to=now + timedelta(days=7),
            is_overdue=False,
            category="dev",
            tags=["urgent"],
            limit=10,
            offset=0,
        )

        assert session.execute.call_count == 2


# ---------------------------------------------------------------------------
# get_by_id() 테스트
# ---------------------------------------------------------------------------


class TestGetById:
    """ActionItemService.get_by_id() 테스트"""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self):
        """ID로 조회 성공"""
        svc = ActionItemService()
        session = AsyncMock()

        item = _make_action_item_instance()
        session.execute.return_value = _mock_db_result(first_val=item)

        result = await svc.get_by_id(session, FAKE_ITEM_ID, FAKE_USER_ID)

        assert result == item

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        """ID로 조회 실패 (없음)"""
        svc = ActionItemService()
        session = AsyncMock()

        # Build a result where scalars().first() returns None
        scalars = MagicMock()
        scalars.first.return_value = None
        mock_result = MagicMock()
        mock_result.scalars.return_value = scalars
        session.execute.return_value = mock_result

        result = await svc.get_by_id(session, uuid.uuid4(), FAKE_USER_ID)

        assert result is None


# ---------------------------------------------------------------------------
# update() 테스트
# ---------------------------------------------------------------------------


class TestUpdate:
    """ActionItemService.update() 테스트"""

    @pytest.mark.asyncio
    async def test_update_success(self):
        """정상 수정"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        existing = _make_action_item_instance()
        updated = _make_action_item_instance(title="Updated title")

        with patch.object(svc, "get_by_id", new_callable=AsyncMock, side_effect=[existing, updated]):
            result = await svc.update(
                session=session,
                item_id=FAKE_ITEM_ID,
                user_id=FAKE_USER_ID,
                payload=ActionItemUpdate(title="Updated title"),
            )

        assert result == updated
        session.execute.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        """존재하지 않는 아이템 수정 시 None 반환"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        with patch.object(svc, "get_by_id", new_callable=AsyncMock, return_value=None):
            result = await svc.update(
                session=session,
                item_id=uuid.uuid4(),
                user_id=FAKE_USER_ID,
                payload=ActionItemUpdate(title="New title"),
            )

        assert result is None
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_to_completed_sets_completed_at(self):
        """상태를 completed로 변경 시 completed_at, completed_by 자동 설정"""
        from backend.app.schemas.action_item import ActionItemStatus, ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        existing = _make_action_item_instance(status="in_progress")
        updated = _make_action_item_instance(status="completed")

        with patch.object(svc, "get_by_id", new_callable=AsyncMock, side_effect=[existing, updated]):
            result = await svc.update(
                session=session,
                item_id=FAKE_ITEM_ID,
                user_id=FAKE_USER_ID,
                payload=ActionItemUpdate(status=ActionItemStatus.completed),
            )

        assert result == updated
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self):
        """여러 필드 동시 수정"""
        from backend.app.schemas.action_item import ActionItemPriority, ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        existing = _make_action_item_instance()
        updated = _make_action_item_instance(title="Multi", priority="high")

        with patch.object(svc, "get_by_id", new_callable=AsyncMock, side_effect=[existing, updated]):
            result = await svc.update(
                session=session,
                item_id=FAKE_ITEM_ID,
                user_id=FAKE_USER_ID,
                payload=ActionItemUpdate(
                    title="Multi",
                    description="New desc",
                    priority=ActionItemPriority.high,
                    tags=["updated"],
                    category="testing",
                ),
            )

        assert result == updated

    @pytest.mark.asyncio
    async def test_update_already_completed_no_override(self):
        """이미 완료된 항목의 completed_at은 덮어쓰지 않음"""

        from backend.app.schemas.action_item import ActionItemStatus, ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        past_time = datetime(2025, 1, 1, tzinfo=UTC)
        existing = _make_action_item_instance(
            status="completed",
            completed_at=past_time,
        )
        updated = _make_action_item_instance(status="completed")

        with patch.object(svc, "get_by_id", new_callable=AsyncMock, side_effect=[existing, updated]):
            result = await svc.update(
                session=session,
                item_id=FAKE_ITEM_ID,
                user_id=FAKE_USER_ID,
                payload=ActionItemUpdate(status=ActionItemStatus.completed),
            )

        assert result == updated

    @pytest.mark.asyncio
    async def test_update_with_hours_fields(self):
        """estimated_hours, actual_hours 수정"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        existing = _make_action_item_instance()
        updated = _make_action_item_instance(estimated_hours=5.0, actual_hours=4.5)

        with patch.object(svc, "get_by_id", new_callable=AsyncMock, side_effect=[existing, updated]):
            result = await svc.update(
                session=session,
                item_id=FAKE_ITEM_ID,
                user_id=FAKE_USER_ID,
                payload=ActionItemUpdate(
                    estimated_hours=5.0,
                    actual_hours=4.5,
                ),
            )

        assert result == updated

    @pytest.mark.asyncio
    async def test_update_with_completion_notes(self):
        """completion_notes 수정"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        existing = _make_action_item_instance()
        updated = _make_action_item_instance(completion_notes="Done well")

        with patch.object(svc, "get_by_id", new_callable=AsyncMock, side_effect=[existing, updated]):
            result = await svc.update(
                session=session,
                item_id=FAKE_ITEM_ID,
                user_id=FAKE_USER_ID,
                payload=ActionItemUpdate(completion_notes="Done well"),
            )

        assert result == updated

    @pytest.mark.asyncio
    async def test_update_with_due_date(self):
        """due_date 수정"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        existing = _make_action_item_instance()
        new_due = datetime.utcnow() + timedelta(days=14)
        updated = _make_action_item_instance(due_date=new_due)

        with patch.object(svc, "get_by_id", new_callable=AsyncMock, side_effect=[existing, updated]):
            result = await svc.update(
                session=session,
                item_id=FAKE_ITEM_ID,
                user_id=FAKE_USER_ID,
                payload=ActionItemUpdate(due_date=new_due),
            )

        assert result == updated

    @pytest.mark.asyncio
    async def test_update_with_assignee(self):
        """assignee_id 수정"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        existing = _make_action_item_instance()
        new_assignee = uuid.uuid4()
        updated = _make_action_item_instance(assignee_id=new_assignee)

        with patch.object(svc, "get_by_id", new_callable=AsyncMock, side_effect=[existing, updated]):
            result = await svc.update(
                session=session,
                item_id=FAKE_ITEM_ID,
                user_id=FAKE_USER_ID,
                payload=ActionItemUpdate(assignee_id=new_assignee),
            )

        assert result == updated

    @pytest.mark.asyncio
    async def test_update_with_completed_by(self):
        """completed_by 수정"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        existing = _make_action_item_instance()
        completer = uuid.uuid4()
        updated = _make_action_item_instance(completed_by=completer)

        with patch.object(svc, "get_by_id", new_callable=AsyncMock, side_effect=[existing, updated]):
            result = await svc.update(
                session=session,
                item_id=FAKE_ITEM_ID,
                user_id=FAKE_USER_ID,
                payload=ActionItemUpdate(completed_by=completer),
            )

        assert result == updated


# ---------------------------------------------------------------------------
# delete() 테스트
# ---------------------------------------------------------------------------


class TestDelete:
    """ActionItemService.delete() 테스트"""

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """정상 삭제"""
        svc = ActionItemService()
        session = AsyncMock()

        existing = _make_action_item_instance()
        with patch.object(svc, "get_by_id", new_callable=AsyncMock, return_value=existing):
            result = await svc.delete(session, FAKE_ITEM_ID, FAKE_USER_ID)

        assert result is True
        session.execute.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """존재하지 않는 아이템 삭제 시 False"""
        svc = ActionItemService()
        session = AsyncMock()

        with patch.object(svc, "get_by_id", new_callable=AsyncMock, return_value=None):
            result = await svc.delete(session, uuid.uuid4(), FAKE_USER_ID)

        assert result is False
        session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# get_overview() 테스트
# ---------------------------------------------------------------------------


class TestGetOverview:
    """ActionItemService.get_overview() 테스트"""

    @pytest.mark.asyncio
    async def test_overview_with_items(self):
        """아이템이 있는 경우 개요"""
        from backend.app.schemas.action_item import ActionItemPriority, ActionItemStatus

        svc = ActionItemService()
        session = AsyncMock()

        now = datetime.utcnow()
        items = [
            _make_action_item_instance(
                status=ActionItemStatus.pending,
                priority=ActionItemPriority.high,
                category="dev",
                assignee_id=FAKE_ASSIGNEE_ID,
                estimated_hours=3.0,
                actual_hours=4.0,
                due_date=now + timedelta(days=7),
            ),
            _make_action_item_instance(
                id=uuid.uuid4(),
                status=ActionItemStatus.completed,
                priority=ActionItemPriority.low,
                category="dev",
                assignee_id=FAKE_USER_ID,
                estimated_hours=2.0,
                actual_hours=1.5,
                completed_at=now,
            ),
            _make_action_item_instance(
                id=uuid.uuid4(),
                status=ActionItemStatus.in_progress,
                priority=ActionItemPriority.critical,
                category=None,
                assignee_id=None,
                estimated_hours=None,
                actual_hours=None,
                due_date=now - timedelta(days=1),  # overdue
            ),
        ]

        session.execute.return_value = _mock_db_result(items=items)

        result = await svc.get_overview(session, FAKE_USER_ID, days=30)

        assert result.total_count == 3
        assert result.pending_count == 1
        assert result.in_progress_count == 1
        assert result.completed_count == 1
        assert result.cancelled_count == 0
        assert result.critical_count == 1
        assert result.high_priority_count == 1
        assert result.overdue_count == 1  # in_progress + past due
        assert result.completion_rate == pytest.approx(33.3, rel=0.1)
        assert result.overdue_rate == pytest.approx(33.3, rel=0.1)
        assert "dev" in result.by_category
        assert len(result.weekly_completion_trend) == 4
        assert "completion_velocity" in result.productivity_metrics

    @pytest.mark.asyncio
    async def test_overview_empty(self):
        """아이템이 없는 경우 개요"""
        svc = ActionItemService()
        session = AsyncMock()

        session.execute.return_value = _mock_db_result(items=[])

        result = await svc.get_overview(session, FAKE_USER_ID, days=30)

        assert result.total_count == 0
        assert result.completion_rate == 0.0
        assert result.overdue_rate == 0.0
        assert result.avg_estimated_hours is None
        assert result.avg_actual_hours is None
        assert result.efficiency_ratio is None

    @pytest.mark.asyncio
    async def test_overview_custom_days(self):
        """커스텀 기간 개요"""
        svc = ActionItemService()
        session = AsyncMock()

        session.execute.return_value = _mock_db_result(items=[])

        result = await svc.get_overview(session, FAKE_USER_ID, days=90)

        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_overview_with_hours_stats(self):
        """시간 통계 포함 개요"""
        svc = ActionItemService()
        session = AsyncMock()

        items = [
            _make_action_item_instance(
                id=uuid.uuid4(),
                status="completed",
                estimated_hours=4.0,
                actual_hours=5.0,
            ),
            _make_action_item_instance(
                id=uuid.uuid4(),
                status="completed",
                estimated_hours=2.0,
                actual_hours=3.0,
            ),
        ]

        session.execute.return_value = _mock_db_result(items=items)

        result = await svc.get_overview(session, FAKE_USER_ID)

        assert result.avg_estimated_hours == 3.0
        assert result.avg_actual_hours == 4.0
        assert result.efficiency_ratio == pytest.approx(1.33, rel=0.01)


# ---------------------------------------------------------------------------
# batch_update() 테스트
# ---------------------------------------------------------------------------


class TestBatchUpdate:
    """ActionItemService.batch_update() 테스트"""

    @pytest.mark.asyncio
    async def test_batch_update_all_success(self):
        """모든 아이템 업데이트 성공"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        item1 = _make_action_item_instance(id=uuid.uuid4())
        item2 = _make_action_item_instance(id=uuid.uuid4())

        with patch.object(svc, "update", new_callable=AsyncMock, side_effect=[item1, item2]):
            result = await svc.batch_update(
                session=session,
                user_id=FAKE_USER_ID,
                item_ids=[item1.id, item2.id],
                update_data=ActionItemUpdate(title="Updated"),
            )

        assert result["success_count"] == 2
        assert result["failure_count"] == 0
        assert result["failed_ids"] == []
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_batch_update_partial_failure(self):
        """일부 아이템 업데이트 실패"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        item1_id = uuid.uuid4()
        item2_id = uuid.uuid4()

        with patch.object(
            svc, "update", new_callable=AsyncMock,
            side_effect=[_make_action_item_instance(id=item1_id), None],
        ):
            result = await svc.batch_update(
                session=session,
                user_id=FAKE_USER_ID,
                item_ids=[item1_id, item2_id],
                update_data=ActionItemUpdate(title="Updated"),
            )

        assert result["success_count"] == 1
        assert result["failure_count"] == 1
        assert item2_id in result["failed_ids"]
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_batch_update_with_exception(self):
        """업데이트 중 예외 발생"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        item1_id = uuid.uuid4()
        item2_id = uuid.uuid4()

        with patch.object(
            svc, "update", new_callable=AsyncMock,
            side_effect=[_make_action_item_instance(id=item1_id), RuntimeError("DB error")],
        ):
            result = await svc.batch_update(
                session=session,
                user_id=FAKE_USER_ID,
                item_ids=[item1_id, item2_id],
                update_data=ActionItemUpdate(title="Updated"),
            )

        assert result["success_count"] == 1
        assert result["failure_count"] == 1
        assert item2_id in result["failed_ids"]
        assert len(result["errors"]) == 1
        assert "DB error" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_batch_update_empty_list(self):
        """빈 아이템 목록"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        result = await svc.batch_update(
            session=session,
            user_id=FAKE_USER_ID,
            item_ids=[],
            update_data=ActionItemUpdate(title="Updated"),
        )

        assert result["success_count"] == 0
        assert result["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_batch_update_all_fail(self):
        """모든 아이템 업데이트 실패"""
        from backend.app.schemas.action_item import ActionItemUpdate

        svc = ActionItemService()
        session = AsyncMock()

        id1 = uuid.uuid4()
        id2 = uuid.uuid4()

        with patch.object(
            svc, "update", new_callable=AsyncMock, side_effect=[None, None],
        ):
            result = await svc.batch_update(
                session=session,
                user_id=FAKE_USER_ID,
                item_ids=[id1, id2],
                update_data=ActionItemUpdate(title="Updated"),
            )

        assert result["success_count"] == 0
        assert result["failure_count"] == 2
        assert len(result["failed_ids"]) == 2


# ---------------------------------------------------------------------------
# extract_action_items_from_meeting() 테스트
# ---------------------------------------------------------------------------


class TestExtractActionItemsFromMeeting:
    """ActionItemService.extract_action_items_from_meeting() 테스트"""

    @pytest.mark.asyncio
    async def test_extract_success(self):
        """키워드 포함 회의록에서 액션 아이템 추출"""
        svc = ActionItemService()
        session = AsyncMock()

        mock_meeting = MagicMock()
        mock_meeting.result_data = {
            "segments": [
                {"text": "김대리가 내일까지 보고서를 작성해 주세요"},
                {"text": "박과장이 이번 주에 검토해야 할 사항입니다"},
                {"text": "이건 일반 발언입니다"},
            ]
        }

        session.execute.return_value = _mock_db_result(first_val=mock_meeting)

        result = await svc.extract_action_items_from_meeting(
            session=session,
            meeting_id="meeting-123",
        )

        assert len(result) == 2  # Only 2 segments contain action keywords

    @pytest.mark.asyncio
    async def test_extract_no_meeting(self):
        """회의록이 없는 경우 빈 목록"""
        svc = ActionItemService()
        session = AsyncMock()

        session.execute.return_value = _mock_db_result(first_val=None)

        result = await svc.extract_action_items_from_meeting(
            session=session,
            meeting_id="nonexistent",
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_no_result_data(self):
        """result_data가 없는 경우 빈 목록"""
        svc = ActionItemService()
        session = AsyncMock()

        mock_meeting = MagicMock()
        mock_meeting.result_data = None

        session.execute.return_value = _mock_db_result(first_val=mock_meeting)

        result = await svc.extract_action_items_from_meeting(
            session=session,
            meeting_id="meeting-123",
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_no_action_keywords(self):
        """액션 키워드가 없는 회의록"""
        svc = ActionItemService()
        session = AsyncMock()

        mock_meeting = MagicMock()
        mock_meeting.result_data = {
            "segments": [
                {"text": "오늘 날씨가 좋네요"},
                {"text": "다들 수고하셨습니다"},
            ]
        }

        session.execute.return_value = _mock_db_result(first_val=mock_meeting)

        result = await svc.extract_action_items_from_meeting(
            session=session,
            meeting_id="meeting-123",
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_empty_segments(self):
        """빈 segments"""
        svc = ActionItemService()
        session = AsyncMock()

        mock_meeting = MagicMock()
        mock_meeting.result_data = {"segments": []}

        session.execute.return_value = _mock_db_result(first_val=mock_meeting)

        result = await svc.extract_action_items_from_meeting(
            session=session,
            meeting_id="meeting-123",
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_segment_without_text(self):
        """text 필드가 없는 segment 무시"""
        svc = ActionItemService()
        session = AsyncMock()

        mock_meeting = MagicMock()
        mock_meeting.result_data = {
            "segments": [
                {"no_text_field": "value"},
                {"text": ""},
                {"text": None},
            ]
        }

        session.execute.return_value = _mock_db_result(first_val=mock_meeting)

        result = await svc.extract_action_items_from_meeting(
            session=session,
            meeting_id="meeting-123",
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_multiple_action_keywords(self):
        """여러 액션 키워드가 포함된 단일 segment"""
        svc = ActionItemService()
        session = AsyncMock()

        mock_meeting = MagicMock()
        mock_meeting.result_data = {
            "segments": [
                {"text": "이번 주에 진행할 할 일을 확인해 보겠습니다"},
            ]
        }

        session.execute.return_value = _mock_db_result(first_val=mock_meeting)

        result = await svc.extract_action_items_from_meeting(
            session=session,
            meeting_id="meeting-123",
        )

        assert len(result) == 1
        assert "할 일" in result[0].title or "진행" in result[0].title


# ---------------------------------------------------------------------------
# _calculate_weekly_completion_trend() 테스트
# ---------------------------------------------------------------------------


class TestCalculateWeeklyCompletionTrend:
    """ActionItemService._calculate_weekly_completion_trend() 테스트"""

    def test_trend_returns_list(self):
        """추이 데이터 리스트 반환"""
        svc = ActionItemService()
        result = svc._calculate_weekly_completion_trend([])

        assert isinstance(result, list)
        assert len(result) == 4
        assert all("week" in item for item in result)
        assert all("completed" in item for item in result)
        assert all("created" in item for item in result)


# ---------------------------------------------------------------------------
# _calculate_productivity_metrics() 테스트
# ---------------------------------------------------------------------------


class TestCalculateProductivityMetrics:
    """ActionItemService._calculate_productivity_metrics() 테스트"""

    def test_metrics_returns_dict(self):
        """생산성 지표 딕셔너리 반환"""
        svc = ActionItemService()
        result = svc._calculate_productivity_metrics([])

        assert isinstance(result, dict)
        assert "completion_velocity" in result
        assert "backlog_ratio" in result
        assert "priority_fulfillment" in result
        assert "time_accuracy" in result
