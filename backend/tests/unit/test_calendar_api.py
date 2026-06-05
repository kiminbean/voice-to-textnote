"""
SPEC-CAL-001: 캘린더 통합 API 테스트
SPEC-REFACTOR-001: 에러 헬퍼 마이그레이션 검증
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.main import create_app

# ---------------------------------------------------------------------------
# 픽스처: conftest.py client 의존하지 않고 자체 격리 환경 구성
# ---------------------------------------------------------------------------


@pytest.fixture
def calendar_client():
    """
    캘린더 API 전용 TestClient.
    conftest.py의 무거운 client 픽스처(WhisperEngine, Celery 등) 없이
    Redis/DB만 mock하여 가볍게 동작.
    """
    app = create_app()

    # Redis Mock — setex 포함
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.setex = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=0)

    # DB 세션 Mock — .scalars().first() 가 None 반환하도록 구성
    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    app.dependency_overrides[get_redis_client] = lambda: mock_redis
    app.dependency_overrides[get_db_session] = lambda: mock_db

    with TestClient(app, raise_server_exceptions=True) as tc:
        yield tc, mock_redis, mock_db

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 샘플 회의 데이터
# ---------------------------------------------------------------------------

SAMPLE_MEETING_DATA = {
    "segments": [
        {
            "speaker": "김팀장",
            "text": "이번 프로젝트 할 일을 정리해보겠습니다.",
            "start": 0.0,
            "end": 120.0,
        },
        {
            "speaker": "이대리",
            "text": "네, action item부터 정리하겠습니다.",
            "start": 120.0,
            "end": 240.0,
        },
    ]
}


# ---------------------------------------------------------------------------
# 테스트 케이스
# ---------------------------------------------------------------------------


class TestCreateCalendarEvent:
    """POST /api/v1/calendar/events/{task_id}"""

    def test_no_meeting_data_returns_404(self, calendar_client):
        """회의록 데이터가 없으면 NotFoundError (404)"""
        client, _, _ = calendar_client

        response = client.post("/api/v1/calendar/events/missing_task?calendar_type=google")

        assert response.status_code == 404
        body = response.json()
        assert "error_code" in body
        assert body["error_code"] == "NOT_FOUND"
        assert "회의록" in body["message"]

    def test_invalid_calendar_type_returns_422(self, calendar_client):
        """지원하지 않는 캘린더 타입 — FastAPI Query validation으로 422"""
        client, _, _ = calendar_client

        response = client.post(
            "/api/v1/calendar/events/test_task?calendar_type=invalid_type",
        )

        # FastAPI Query(regex=...) 가 먼저 검증하거나, 비즈니스 로직에서 unprocessable()
        assert response.status_code == 422

    def test_success_with_meeting_data(self, calendar_client):
        """회의 데이터가 있으면 201 + 이벤트 생성"""
        client, mock_redis, _ = calendar_client

        # Redis에 회의 데이터 세팅
        mock_redis.get = AsyncMock(return_value=json.dumps(SAMPLE_MEETING_DATA))
        mock_redis.setex = AsyncMock(return_value=True)

        response = client.post("/api/v1/calendar/events/test_task?calendar_type=google")

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["event"]["calendar_type"] == "google"


class TestGetCalendarEvent:
    """GET /api/v1/calendar/events/{task_id}"""

    def test_not_found_returns_404(self, calendar_client):
        """존재하지 않는 이벤트 조회 — NotFoundError (404)"""
        client, _, _ = calendar_client

        response = client.get("/api/v1/calendar/events/nonexistent_task")

        assert response.status_code == 404
        body = response.json()
        assert body["error_code"] == "NOT_FOUND"

    def test_success_with_existing_event(self, calendar_client):
        """이벤트가 존재하면 200 + 이벤트 데이터"""
        client, mock_redis, _ = calendar_client

        # Redis에 캘린더 이벤트 데이터 세팅
        event_data = {
            "title": "회의록",
            "description": "테스트",
            "start_datetime": "2026-01-01T09:00:00",
            "end_datetime": "2026-01-01T10:00:00",
            "location": "온라인 미팅",
            "participants": ["김팀장"],
            "action_items": [],
            "duration_minutes": 60,
            "calendar_type": "google",
            "status": "confirmed",
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(event_data))

        response = client.get("/api/v1/calendar/events/existing_task")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["event"]["title"] == "회의록"


class TestDeleteCalendarEvent:
    """DELETE /api/v1/calendar/events/{task_id}"""

    def test_not_found_returns_404(self, calendar_client):
        """존재하지 않는 이벤트 삭제 — NotFoundError (404)"""
        client, _, _ = calendar_client

        # Redis delete 가 0 반환 (키 없음)
        response = client.delete("/api/v1/calendar/events/nonexistent_task")

        assert response.status_code == 404
        body = response.json()
        assert body["error_code"] == "NOT_FOUND"

    def test_success_deletes_event(self, calendar_client):
        """이벤트 삭제 성공 — 200"""
        client, mock_redis, _ = calendar_client

        # Redis delete 가 1 반환 (키 삭제됨)
        mock_redis.delete = AsyncMock(return_value=1)

        response = client.delete("/api/v1/calendar/events/existing_task")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True


class TestSupportedCalendars:
    """지원 캘린더 타입 상수 검증"""

    def test_supported_calendars(self):
        """google, outlook, apple 지원 확인"""
        from backend.app.api.v1.calendar import SUPPORTED_CALENDARS

        assert SUPPORTED_CALENDARS == {"google", "outlook", "apple"}
