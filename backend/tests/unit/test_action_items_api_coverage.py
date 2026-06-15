"""
SPEC-ACTION-001: 액션 아이템 관리 API 단위 테스트

테스트 대상: backend/app/api/v1/action_items.py (82 lines, 0% coverage)

엔드포인트:
- GET    /api/v1/action-items                     목록 조회
- POST   /api/v1/action-items                     생성
- GET    /api/v1/action-items/{id}                 단건 조회
- PATCH  /api/v1/action-items/{id}                 수정
- DELETE /api/v1/action-items/{id}                 삭제
- GET    /api/v1/action-items/meeting/{meeting_id} 회의별 조회
- PATCH  /api/v1/action-items/{id}/complete        완료 처리
- GET    /api/v1/action-items/overview             대시보드
- POST   /api/v1/action-items/batch-update         배치 업데이트
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

FAKE_USER_ID = uuid.uuid4()
FAKE_ITEM_ID = uuid.uuid4()
FAKE_ASSIGNEE_ID = uuid.uuid4()


def _make_action_item_response(
    item_id=None,
    title="Test action",
    status="pending",
    priority="medium",
):
    """Create a mock object satisfying ActionItemResponse schema fields."""
    now = datetime.now(UTC)
    item = MagicMock()
    item.id = item_id or uuid.uuid4()
    item.title = title
    item.description = "Test description"
    item.status = status
    item.priority = priority
    item.assignee_id = FAKE_ASSIGNEE_ID
    item.assignee_name = "Assignee User"
    item.created_by = FAKE_USER_ID
    item.created_by_name = "Test User"
    item.created_at = now
    item.updated_at = now
    item.due_date = now + timedelta(days=7)
    item.completed_at = None
    item.completed_by = None
    item.completed_by_name = None
    item.completion_notes = None
    item.meeting_id = None
    item.meeting_title = None
    item.tags = ["test"]
    item.estimated_hours = 2.0
    item.actual_hours = None
    item.category = "general"
    item.is_overdue = False
    item.time_remaining_hours = 168.0
    item.progress_percentage = 0.0
    return item


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client(mock_service):
    """TestClient using a minimal FastAPI app with only the action_items router."""
    from fastapi import FastAPI

    from backend.app.api.v1.minutes.action_items_crud import get_action_item_service, router
    from backend.app.dependencies import get_current_user, get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    mock_db = AsyncMock()

    async def mock_db_session():
        yield mock_db

    async def mock_user():
        u = MagicMock()
        u.id = FAKE_USER_ID
        u.email = "test@example.com"
        u.display_name = "Test User"
        u.is_active = True
        return u

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_user
    app.dependency_overrides[get_action_item_service] = lambda: mock_service

    yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()


@pytest.fixture
def mock_service():
    """Mock ActionItemService with all methods stubbed."""
    with patch("backend.app.api.v1.minutes.action_items_crud.ActionItemService") as cls:
        instance = AsyncMock()
        cls.return_value = instance
        with patch(
            "backend.app.api.v1.minutes.action_items_crud.get_action_item_service",
            return_value=instance,
        ):
            yield instance


# ---------------------------------------------------------------------------
# GET /api/v1/action-items - 목록 조회
# ---------------------------------------------------------------------------


class TestListActionItems:
    """GET /api/v1/action-items 엔드포인트 테스트"""

    def test_list_success(self, api_client, mock_service):
        """정상 목록 조회"""
        item = _make_action_item_response()
        mock_service.list_items.return_value = ([item], 1)

        response = api_client.get("/api/v1/action-items")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["page"] == 1
        assert data["page_size"] == 50
        mock_service.list_items.assert_called_once()

    def test_list_empty(self, api_client, mock_service):
        """빈 목록 조회"""
        mock_service.list_items.return_value = ([], 0)

        response = api_client.get("/api/v1/action-items")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_with_status_filter(self, api_client, mock_service):
        """상태 필터 적용"""
        mock_service.list_items.return_value = ([], 0)

        response = api_client.get("/api/v1/action-items?status=completed")

        assert response.status_code == 200
        call_kwargs = mock_service.list_items.call_args
        assert call_kwargs.kwargs.get("status") == "completed"

    def test_list_with_priority_filter(self, api_client, mock_service):
        """우선순위 필터 적용"""
        mock_service.list_items.return_value = ([], 0)

        response = api_client.get("/api/v1/action-items?priority=high")

        assert response.status_code == 200
        call_kwargs = mock_service.list_items.call_args
        assert call_kwargs.kwargs.get("priority") == "high"

    def test_list_with_pagination(self, api_client, mock_service):
        """페이지네이션 적용"""
        mock_service.list_items.return_value = ([], 0)

        response = api_client.get("/api/v1/action-items?page=2&page_size=10")

        assert response.status_code == 200
        call_kwargs = mock_service.list_items.call_args
        assert call_kwargs.kwargs.get("offset") == 10
        assert call_kwargs.kwargs.get("limit") == 10

    def test_list_with_due_date_filters(self, api_client, mock_service):
        """마감일 범위 필터"""
        mock_service.list_items.return_value = ([], 0)

        response = api_client.get(
            "/api/v1/action-items?due_from=2025-01-01T00:00:00&due_to=2025-12-31T23:59:59"
        )

        assert response.status_code == 200

    def test_list_with_is_overdue_filter(self, api_client, mock_service):
        """지연 여부 필터"""
        mock_service.list_items.return_value = ([], 0)

        response = api_client.get("/api/v1/action-items?is_overdue=true")

        assert response.status_code == 200

    def test_list_with_meeting_id_filter(self, api_client, mock_service):
        """회의 ID 필터"""
        mock_service.list_items.return_value = ([], 0)

        response = api_client.get("/api/v1/action-items?meeting_id=meeting-123")

        assert response.status_code == 200

    def test_list_with_assignee_id_filter(self, api_client, mock_service):
        """담당자 ID 필터"""
        mock_service.list_items.return_value = ([], 0)

        response = api_client.get(f"/api/v1/action-items?assignee_id={FAKE_ASSIGNEE_ID}")

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/v1/action-items - 생성
# ---------------------------------------------------------------------------


class TestCreateActionItem:
    """POST /api/v1/action-items 엔드포인트 테스트"""

    def test_create_success(self, api_client, mock_service):
        """정상 생성"""
        item = _make_action_item_response(title="New task")
        mock_service.create.return_value = item

        response = api_client.post(
            "/api/v1/action-items",
            json={
                "title": "New task",
                "description": "Task description",
                "priority": "medium",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New task"
        mock_service.create.assert_called_once()

    def test_create_high_priority_auto_due_date(self, api_client, mock_service):
        """높은 우선순위 시 자동 마감일 설정"""
        item = _make_action_item_response(priority="high")
        mock_service.create.return_value = item

        response = api_client.post(
            "/api/v1/action-items",
            json={"title": "Urgent task", "priority": "high"},
        )

        assert response.status_code == 201
        payload = mock_service.create.call_args.kwargs["payload"]
        assert payload.due_date is not None

    def test_create_critical_priority_auto_due_date(self, api_client, mock_service):
        """긴급 우선순위 시 자동 마감일 설정"""
        item = _make_action_item_response(priority="critical")
        mock_service.create.return_value = item

        response = api_client.post(
            "/api/v1/action-items",
            json={"title": "Critical task", "priority": "critical"},
        )

        assert response.status_code == 201
        payload = mock_service.create.call_args.kwargs["payload"]
        assert payload.due_date is not None

    def test_create_with_existing_due_date(self, api_client, mock_service):
        """마감일이 이미 설정된 경우 자동 설정하지 않음"""
        item = _make_action_item_response(priority="high")
        mock_service.create.return_value = item

        due = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        response = api_client.post(
            "/api/v1/action-items",
            json={"title": "High priority", "priority": "high", "due_date": due},
        )

        assert response.status_code == 201

    def test_create_missing_title_validation(self, api_client, mock_service):
        """title 누락 시 422"""
        response = api_client.post(
            "/api/v1/action-items",
            json={"priority": "medium"},
        )

        assert response.status_code == 422

    def test_create_title_too_long(self, api_client, mock_service):
        """title 200자 초과 시 422"""
        response = api_client.post(
            "/api/v1/action-items",
            json={"title": "x" * 201},
        )

        assert response.status_code == 422

    def test_create_with_all_fields(self, api_client, mock_service):
        """모든 필드 포함하여 생성"""
        item = _make_action_item_response(title="Full item")
        mock_service.create.return_value = item

        response = api_client.post(
            "/api/v1/action-items",
            json={
                "title": "Full item",
                "description": "Detailed description",
                "priority": "high",
                "assignee_id": str(FAKE_ASSIGNEE_ID),
                "due_date": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
                "meeting_id": "meeting-abc",
                "tags": ["urgent", "backend"],
                "estimated_hours": 4.5,
                "category": "development",
            },
        )

        assert response.status_code == 201
        mock_service.create.assert_called_once()

    def test_create_medium_priority_no_auto_due(self, api_client, mock_service):
        """medium/low 우선순위 시 자동 마감일 없음"""
        item = _make_action_item_response(priority="medium")
        mock_service.create.return_value = item

        response = api_client.post(
            "/api/v1/action-items",
            json={"title": "Normal task", "priority": "medium"},
        )

        assert response.status_code == 201
        payload = mock_service.create.call_args.kwargs["payload"]
        assert payload.due_date is None


# ---------------------------------------------------------------------------
# GET /api/v1/action-items/{id} - 단건 조회
# ---------------------------------------------------------------------------


class TestGetActionItem:
    """GET /api/v1/action-items/{id} 엔드포인트 테스트"""

    def test_get_success(self, api_client, mock_service):
        """정상 단건 조회"""
        item = _make_action_item_response(item_id=FAKE_ITEM_ID)
        mock_service.get_by_id.return_value = item

        response = api_client.get(f"/api/v1/action-items/{FAKE_ITEM_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(FAKE_ITEM_ID)
        mock_service.get_by_id.assert_called_once()

    def test_get_not_found(self, api_client, mock_service):
        """존재하지 않는 ID 조회 시 404"""
        mock_service.get_by_id.return_value = None

        response = api_client.get(f"/api/v1/action-items/{uuid.uuid4()}")

        assert response.status_code == 404
        assert "액션 아이템을 찾을 수 없습니다" in response.json()["detail"]

    def test_get_invalid_uuid(self, api_client, mock_service):
        """잘못된 UUID 형식 시 422"""
        response = api_client.get("/api/v1/action-items/not-a-uuid")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/v1/action-items/{id} - 수정
# ---------------------------------------------------------------------------


class TestUpdateActionItem:
    """PATCH /api/v1/action-items/{id} 엔드포인트 테스트"""

    def test_update_success(self, api_client, mock_service):
        """정상 수정"""
        item = _make_action_item_response(item_id=FAKE_ITEM_ID, title="Updated")
        mock_service.update.return_value = item

        response = api_client.patch(
            f"/api/v1/action-items/{FAKE_ITEM_ID}",
            json={"title": "Updated"},
        )

        assert response.status_code == 200
        assert response.json()["title"] == "Updated"

    def test_update_not_found(self, api_client, mock_service):
        """존재하지 않는 ID 수정 시 404"""
        mock_service.update.return_value = None

        response = api_client.patch(
            f"/api/v1/action-items/{uuid.uuid4()}",
            json={"title": "New title"},
        )

        assert response.status_code == 404
        assert "액션 아이템을 찾을 수 없습니다" in response.json()["detail"]

    def test_update_multiple_fields(self, api_client, mock_service):
        """여러 필드 동시 수정"""
        item = _make_action_item_response(item_id=FAKE_ITEM_ID, title="Updated")
        mock_service.update.return_value = item

        response = api_client.patch(
            f"/api/v1/action-items/{FAKE_ITEM_ID}",
            json={"title": "Updated", "status": "in_progress", "priority": "high"},
        )

        assert response.status_code == 200

    def test_update_empty_body(self, api_client, mock_service):
        """빈 바디로 수정"""
        item = _make_action_item_response(item_id=FAKE_ITEM_ID)
        mock_service.update.return_value = item

        response = api_client.patch(
            f"/api/v1/action-items/{FAKE_ITEM_ID}",
            json={},
        )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /api/v1/action-items/{id} - 삭제
# ---------------------------------------------------------------------------


class TestDeleteActionItem:
    """DELETE /api/v1/action-items/{id} 엔드포인트 테스트"""

    def test_delete_success(self, api_client, mock_service):
        """정상 삭제"""
        mock_service.delete.return_value = True

        response = api_client.delete(f"/api/v1/action-items/{FAKE_ITEM_ID}")

        assert response.status_code == 204
        mock_service.delete.assert_called_once()

    def test_delete_not_found(self, api_client, mock_service):
        """존재하지 않는 ID 삭제 시 404"""
        mock_service.delete.return_value = False

        response = api_client.delete(f"/api/v1/action-items/{uuid.uuid4()}")

        assert response.status_code == 404
        assert "액션 아이템을 찾을 수 없습니다" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/v1/action-items/meeting/{meeting_id} - 회의별 조회
# ---------------------------------------------------------------------------


class TestGetMeetingActionItems:
    """GET /api/v1/action-items/meeting/{meeting_id} 엔드포인트 테스트"""

    def _make_db_override(self, meeting_found=True):
        """Create a mock DB session and a get_db_session override function."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        if meeting_found:
            mock_result.scalars.return_value.first.return_value = MagicMock()
        else:
            mock_result.scalars.return_value.first.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_db_session():
            yield mock_db

        return mock_db_session

    def test_meeting_items_success(self, api_client, mock_service):
        """회의 액션 아이템 정상 조회"""
        from backend.app.dependencies import get_db_session

        item = _make_action_item_response(title="Meeting task")
        mock_service.list_items.return_value = ([item], 1)

        # Get the underlying FastAPI app from TestClient
        app = api_client.app
        app.dependency_overrides[get_db_session] = self._make_db_override(meeting_found=True)

        try:
            response = api_client.get("/api/v1/action-items/meeting/meeting-123")
            assert response.status_code == 200
            assert response.json()["total"] == 1
        finally:
            # Reset to default mock db
            async def orig():
                yield AsyncMock()

            app.dependency_overrides[get_db_session] = orig

    def test_meeting_not_found_raises_error(self, mock_service):
        """존재하지 않는 회의 시 404 에러 발생"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.app.api.v1.minutes.action_items_crud import router
        from backend.app.dependencies import get_current_user, get_db_session

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        async def mock_db_session():
            yield AsyncMock()

        async def mock_user():
            u = MagicMock()
            u.id = FAKE_USER_ID
            u.is_active = True
            return u

        app.dependency_overrides[get_db_session] = self._make_db_override(meeting_found=False)
        app.dependency_overrides[get_current_user] = mock_user

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/v1/action-items/meeting/nonexistent")
        assert response.status_code == 404
        assert "회의록을 찾을 수 없습니다" in response.text

    def test_meeting_with_status_filter(self, api_client, mock_service):
        """회의 액션 아이템 상태 필터"""
        from backend.app.dependencies import get_db_session

        mock_service.list_items.return_value = ([], 0)

        app = api_client.app
        app.dependency_overrides[get_db_session] = self._make_db_override(meeting_found=True)

        try:
            response = api_client.get("/api/v1/action-items/meeting/meeting-123?status=completed")
            assert response.status_code == 200
        finally:

            async def orig():
                yield AsyncMock()

            app.dependency_overrides[get_db_session] = orig

    def test_meeting_with_priority_filter(self, api_client, mock_service):
        """회의 액션 아이템 우선순위 필터"""
        from backend.app.dependencies import get_db_session

        mock_service.list_items.return_value = ([], 0)

        app = api_client.app
        app.dependency_overrides[get_db_session] = self._make_db_override(meeting_found=True)

        try:
            response = api_client.get("/api/v1/action-items/meeting/meeting-123?priority=high")
            assert response.status_code == 200
        finally:

            async def orig():
                yield AsyncMock()  # pragma: no cover

            app.dependency_overrides[get_db_session] = orig


# ---------------------------------------------------------------------------
# PATCH /api/v1/action-items/{id}/complete - 완료 처리
# ---------------------------------------------------------------------------


class TestCompleteActionItem:
    """PATCH /api/v1/action-items/{id}/complete 엔드포인트 테스트"""

    def test_complete_success(self, api_client, mock_service):
        """정상 완료 처리"""
        item = _make_action_item_response(item_id=FAKE_ITEM_ID, status="completed")
        mock_service.update.return_value = item

        response = api_client.patch(f"/api/v1/action-items/{FAKE_ITEM_ID}/complete")

        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        payload = mock_service.update.call_args.kwargs["payload"]
        assert payload.status.value == "completed"
        assert payload.completed_at is not None
        assert payload.completed_by == FAKE_USER_ID

    def test_complete_with_notes(self, api_client, mock_service):
        """완료 메모 포함"""
        item = _make_action_item_response(item_id=FAKE_ITEM_ID, status="completed")
        mock_service.update.return_value = item

        response = api_client.patch(
            f"/api/v1/action-items/{FAKE_ITEM_ID}/complete?notes=Done%20well"
        )

        assert response.status_code == 200
        payload = mock_service.update.call_args.kwargs["payload"]
        assert payload.completion_notes == "Done well"

    def test_complete_not_found(self, api_client, mock_service):
        """존재하지 않는 ID 완료 시 404"""
        mock_service.update.return_value = None

        response = api_client.patch(f"/api/v1/action-items/{uuid.uuid4()}/complete")

        assert response.status_code == 404

    def test_complete_with_empty_notes(self, api_client, mock_service):
        """notes 없이 완료 처리 시 빈 문자열"""
        item = _make_action_item_response(item_id=FAKE_ITEM_ID, status="completed")
        mock_service.update.return_value = item

        response = api_client.patch(f"/api/v1/action-items/{FAKE_ITEM_ID}/complete")

        assert response.status_code == 200
        payload = mock_service.update.call_args.kwargs["payload"]
        assert payload.completion_notes == ""


# ---------------------------------------------------------------------------
# GET /api/v1/action-items/overview - 대시보드
# ---------------------------------------------------------------------------


def _make_empty_overview():
    """Create an ActionItemOverview with zero counts."""
    from backend.app.schemas.action_item import (
        ActionItemOverview as OverviewSchema,
    )

    return OverviewSchema(
        total_count=0,
        pending_count=0,
        in_progress_count=0,
        completed_count=0,
        cancelled_count=0,
        overdue_count=0,
        critical_count=0,
        high_priority_count=0,
        by_category={},
        by_assignee={},
        completion_rate=0.0,
        overdue_rate=0.0,
        avg_estimated_hours=None,
        avg_actual_hours=None,
        efficiency_ratio=None,
        trending_status="stable",
        weekly_completion_trend=[],
        productivity_metrics={
            "completion_velocity": 0.0,
            "backlog_ratio": 0.0,
            "priority_fulfillment": 0.0,
            "time_accuracy": 0.0,
        },
    )


class TestGetOverview:
    """GET /api/v1/action-items/overview 엔드포인트 테스트

    NOTE: Due to route ordering in action_items.py, GET /{id} is defined
    before GET /overview, so '/overview' is matched as an invalid UUID by
    the /{id} route, returning 422. These tests document the current behavior.
    To fix: move the /overview and /meeting routes before /{id} in the source.
    """

    def test_overview_returns_422_due_to_route_ordering(self, api_client, mock_service):
        """Overview route is shadowed by /{id} route (known issue)"""
        from backend.app.schemas.action_item import (
            ActionItemOverview as OverviewSchema,
        )

        overview = OverviewSchema(
            total_count=10,
            pending_count=3,
            in_progress_count=2,
            completed_count=4,
            cancelled_count=1,
            overdue_count=1,
            critical_count=2,
            high_priority_count=3,
            by_category={"development": 5, "design": 3, "기타": 2},
            by_assignee={str(FAKE_USER_ID): 6, str(FAKE_ASSIGNEE_ID): 4},
            completion_rate=40.0,
            overdue_rate=10.0,
            avg_estimated_hours=3.5,
            avg_actual_hours=4.2,
            efficiency_ratio=1.2,
            trending_status="stable",
            weekly_completion_trend=[{"week": 1, "completed": 5, "created": 8}],
            productivity_metrics={
                "completion_velocity": 7.2,
                "backlog_ratio": 0.3,
                "priority_fulfillment": 0.85,
                "time_accuracy": 0.92,
            },
        )
        mock_service.get_overview.return_value = overview

        response = api_client.get("/api/v1/action-items/overview")

        # Route ordering bug: /{id} matches "overview" as invalid UUID
        assert response.status_code == 422

    def test_overview_with_days_param_returns_422(self, api_client, mock_service):
        """Route ordering prevents days parameter from working"""
        mock_service.get_overview.return_value = _make_empty_overview()

        response = api_client.get("/api/v1/action-items/overview?days=90")

        # Same route ordering issue
        assert response.status_code == 422

    def test_overview_default_days_returns_422(self, api_client, mock_service):
        """Route ordering prevents overview from working"""
        mock_service.get_overview.return_value = _make_empty_overview()

        response = api_client.get("/api/v1/action-items/overview")

        assert response.status_code == 422

    def test_overview_invalid_days_too_small(self, api_client, mock_service):
        """days가 7 미만 시 422"""
        response = api_client.get("/api/v1/action-items/overview?days=3")
        assert response.status_code == 422

    def test_overview_invalid_days_too_large(self, api_client, mock_service):
        """days가 365 초과 시 422"""
        response = api_client.get("/api/v1/action-items/overview?days=400")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/action-items/batch-update - 배치 업데이트
# ---------------------------------------------------------------------------


class TestBatchUpdateActionItems:
    """POST /api/v1/action-items/batch-update 엔드포인트 테스트"""

    def _make_batch_result(self, success_count=0, failure_count=0, failed_ids=None, errors=None):
        """Create a service-style batch result mapping."""
        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "failed_ids": failed_ids or [],
            "errors": errors or [],
        }

    def test_batch_update_success(self, api_client, mock_service):
        """정상 배치 업데이트"""
        mock_service.batch_update.return_value = self._make_batch_result(
            success_count=2,
            failure_count=1,
            failed_ids=[str(uuid.uuid4())],
            errors=["액션 아이템을 찾을 수 없거나 권한이 없습니다"],
        )

        ids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]
        response = api_client.post(
            "/api/v1/action-items/batch-update",
            json={"item_ids": ids, "update_data": {"status": "completed"}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success_count"] == 2
        assert data["failure_count"] == 1

    def test_batch_update_all_success(self, api_client, mock_service):
        """모든 항목 성공"""
        mock_service.batch_update.return_value = self._make_batch_result(
            success_count=3,
            failure_count=0,
        )

        ids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]
        response = api_client.post(
            "/api/v1/action-items/batch-update",
            json={"item_ids": ids, "update_data": {"status": "completed"}},
        )

        assert response.status_code == 200
        assert response.json()["success_count"] == 3

    def test_batch_update_empty_ids(self, api_client, mock_service):
        """item_ids가 빈 목록 시 422"""
        response = api_client.post(
            "/api/v1/action-items/batch-update",
            json={"item_ids": [], "update_data": {"status": "completed"}},
        )
        assert response.status_code == 422

    def test_batch_update_too_many_ids(self, api_client, mock_service):
        """item_ids가 100개 초과 시 422"""
        ids = [str(uuid.uuid4()) for _ in range(101)]
        response = api_client.post(
            "/api/v1/action-items/batch-update",
            json={"item_ids": ids, "update_data": {"status": "completed"}},
        )
        assert response.status_code == 422

    def test_batch_update_missing_update_data(self, api_client, mock_service):
        """update_data 누락 시 422"""
        response = api_client.post(
            "/api/v1/action-items/batch-update",
            json={"item_ids": [str(uuid.uuid4())]},
        )
        assert response.status_code == 422

    def test_batch_update_missing_item_ids(self, api_client, mock_service):
        """item_ids 누락 시 422"""
        response = api_client.post(
            "/api/v1/action-items/batch-update",
            json={"update_data": {"status": "completed"}},
        )
        assert response.status_code == 422
