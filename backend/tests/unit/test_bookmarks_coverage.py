"""
SPEC-BOOKMARK-001: 북마크 API 확장 엔드포인트 테스트

대상: app/api/v1/collaboration/bookmarks.py
  - POST /api/v1/bookmarks/bulk     대량 작업
  - POST /api/v1/bookmarks/cleanup   정리
  - POST /api/v1/bookmarks/export    내보내기

참고:
- BookmarkService는 서비스 레벨 mock으로 처리하고 라우터 계약을 검증한다.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_db_session
from backend.app.error_handlers import register_exception_handlers


@pytest.fixture
def app_client():
    """bookmarks 라우터 테스트 앱."""
    from backend.app.api.v1.collaboration.bookmarks import (
        get_bookmark_service,
        router,
    )

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    # DB 세션 mock
    mock_session = AsyncMock()

    async def override_db():
        yield mock_session

    # 사용자 mock
    mock_user = MagicMock()
    mock_user.id = "test-user-id"

    async def override_user():
        return mock_user

    # 서비스 mock
    mock_svc = MagicMock()

    async def override_svc():
        return mock_svc

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_bookmark_service] = override_svc

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, mock_session, mock_svc

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /bookmarks/bulk
# ---------------------------------------------------------------------------


class TestBulkBookmarkOperations:
    """대량 북마크 작업."""

    def test_bulk_delete_success(self, app_client):
        """대량 삭제 성공."""
        client, mock_session, mock_svc = app_client

        mock_svc.bulk_operation = AsyncMock(
            return_value={
                "processed_count": 3,
                "failed_count": 0,
                "errors": [],
            }
        )

        resp = client.post(
            "/api/v1/bookmarks/bulk",
            json={
                "operation": "delete",
                "bookmark_ids": [
                    "550e8400-e29b-41d4-a716-446655440001",
                    "550e8400-e29b-41d4-a716-446655440002",
                    "550e8400-e29b-41d4-a716-446655440003",
                ],
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["processed_count"] == 3

    def test_bulk_update_category(self, app_client):
        """대량 카테고리 업데이트."""
        client, mock_session, mock_svc = app_client

        mock_svc.bulk_operation = AsyncMock(
            return_value={
                "processed_count": 2,
                "failed_count": 0,
                "errors": [],
            }
        )

        resp = client.post(
            "/api/v1/bookmarks/bulk",
            json={
                "operation": "update_category",
                "bookmark_ids": [
                    "550e8400-e29b-41d4-a716-446655440001",
                    "550e8400-e29b-41d4-a716-446655440002",
                ],
                "data": {"category": "important"},
            },
        )

        assert resp.status_code == 200

    def test_bulk_missing_operation_returns_422(self, app_client):
        """operation 필드 누락 -> 422."""
        client, _, _ = app_client

        resp = client.post(
            "/api/v1/bookmarks/bulk",
            json={
                "bookmark_ids": [
                    "550e8400-e29b-41d4-a716-446655440001",
                ],
            },
        )
        assert resp.status_code == 422

    def test_bulk_empty_ids_returns_422(self, app_client):
        """빈 bookmark_ids -> 422 (min_length=1)."""
        client, _, _ = app_client

        resp = client.post(
            "/api/v1/bookmarks/bulk",
            json={
                "operation": "delete",
                "bookmark_ids": [],
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /bookmarks/cleanup
# ---------------------------------------------------------------------------


class TestBookmarkCleanup:
    """북마크 정리."""

    def test_cleanup_success(self, app_client):
        """정리 성공."""
        client, mock_session, mock_svc = app_client

        mock_svc.cleanup_bookmarks = AsyncMock(
            return_value={
                "total_count": 5,
                "deleted_count": 3,
                "archived_count": 2,
                "duplicate_count": 0,
                "empty_count": 0,
                "categories": {},
                "preview": [],
            }
        )

        resp = client.post(
            "/api/v1/bookmarks/cleanup",
            json={"older_than_days": 30},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 5

    def test_cleanup_dry_run(self, app_client):
        """dry_run 모드 (기본값)."""
        client, mock_session, mock_svc = app_client

        mock_svc.cleanup_bookmarks = AsyncMock(
            return_value={
                "total_count": 2,
                "deleted_count": 0,
                "archived_count": 0,
                "duplicate_count": 0,
                "empty_count": 0,
                "categories": {},
                "preview": [],
            }
        )

        resp = client.post(
            "/api/v1/bookmarks/cleanup",
            json={"older_than_days": 60, "dry_run": True},
        )

        assert resp.status_code == 200

    def test_cleanup_with_category_filter(self, app_client):
        """카테고리 필터 정리."""
        client, mock_session, mock_svc = app_client

        mock_svc.cleanup_bookmarks = AsyncMock(
            return_value={
                "total_count": 1,
                "deleted_count": 1,
                "archived_count": 0,
                "duplicate_count": 0,
                "empty_count": 0,
                "categories": {},
                "preview": [],
            }
        )

        resp = client.post(
            "/api/v1/bookmarks/cleanup",
            json={"older_than_days": 30, "category": "note"},
        )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /bookmarks/summary and /bookmarks/search
# ---------------------------------------------------------------------------


class TestBookmarkStaticGetRoutes:
    """동적 /{bookmark_id}보다 정적 GET 라우트가 먼저 매칭되어야 한다."""

    def test_summary_route_reaches_service(self, app_client):
        """summary 경로가 bookmark_id UUID 파싱으로 빠지지 않아야 함."""
        client, mock_session, mock_svc = app_client

        mock_svc.get_summary = AsyncMock(
            return_value={
                "total_count": 0,
                "category_counts": {},
                "priority_counts": {},
                "tag_counts": {},
                "recent_bookmarks": [],
            }
        )

        resp = client.get("/api/v1/bookmarks/summary?task_id=task-123")

        assert resp.status_code == 200
        assert resp.json()["total_count"] == 0
        mock_svc.get_summary.assert_awaited_once_with(
            mock_session,
            "test-user-id",
            "task-123",
        )

    def test_search_route_reaches_service(self, app_client):
        """search 경로가 bookmark_id UUID 파싱으로 빠지지 않아야 함."""
        client, mock_session, mock_svc = app_client

        mock_svc.search_bookmarks = AsyncMock(
            return_value={
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": 50,
                "total_pages": 0,
            }
        )

        resp = client.get("/api/v1/bookmarks/search?query=important&tags=urgent,review")

        assert resp.status_code == 200
        assert resp.json()["items"] == []
        mock_svc.search_bookmarks.assert_awaited_once()
        args = mock_svc.search_bookmarks.await_args.args
        assert args[0] is mock_session
        assert args[1] == "test-user-id"
        assert args[2].query == "important"
        assert args[2].tags == ["urgent", "review"]


# ---------------------------------------------------------------------------
# POST /bookmarks/export
# ---------------------------------------------------------------------------


class TestBookmarkExport:
    """북마크 내보내기."""

    def test_export_json_format(self, app_client):
        """JSON 형식 내보내기."""
        client, mock_session, mock_svc = app_client

        mock_svc.export_bookmarks = AsyncMock(
            return_value={
                "format": "json",
                "data": [],
                "count": 0,
            }
        )

        resp = client.post("/api/v1/bookmarks/export?format=json")

        assert resp.status_code == 200

    def test_export_with_task_id_filter(self, app_client):
        """task_id 필터 내보내기."""
        client, mock_session, mock_svc = app_client

        mock_svc.export_bookmarks = AsyncMock(
            return_value={
                "format": "csv",
                "data": [],
                "count": 0,
            }
        )

        resp = client.post("/api/v1/bookmarks/export?format=csv&task_id=task-123")

        assert resp.status_code == 200

    def test_export_csv_format(self, app_client):
        """CSV 형식 내보내기."""
        client, mock_session, mock_svc = app_client

        mock_svc.export_bookmarks = AsyncMock(
            return_value={
                "format": "csv",
                "data": "id,text\n1,test",
                "count": 1,
            }
        )

        resp = client.post("/api/v1/bookmarks/export?format=csv")

        assert resp.status_code == 200
