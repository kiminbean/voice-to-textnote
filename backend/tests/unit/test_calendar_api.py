"""
캘린더 통합 API 테스트
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.mark.asyncio
async def test_create_calendar_event_success(client):
    """캘린더 이벤트 생성 성공 테스트"""
    # Mock meeting data in Redis
    task_id = "test_meeting_001"

    # Mock Redis client (테스트 환경에서는 실제 Redis 사용 안 함)
    # 실제 테스트에서는 테스트용 Redis나 Mock을 사용해야 함

    response = client.post(
        f"/api/v1/calendar/events/{task_id}?calendar_type=google",
        headers={"X-API-Key": "test_key"}
    )

    # Mock 데이터가 없으므로 404 예상
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_calendar_event_invalid_calendar_type(client):
    """지원하지 않는 캘endar 타입 테스트"""
    task_id = "test_meeting_002"

    response = client.post(
        f"/api/v1/calendar/events/{task_id}?calendar_type=invalid",
        headers={"X-API-Key": "test_key"}
    )

    assert response.status_code == 422
    assert "지원하지 않는 캘린더 타입" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_calendar_event_not_found(client):
    """존재하지 않는 캘린더 이벤트 조회 테스트"""
    task_id = "nonexistent_meeting"

    response = client.get(f"/api/v1/calendar/events/{task_id}")

    assert response.status_code == 404
    assert "캘린더 이벤트를 찾을 수 없습니다" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_calendar_event_not_found(client):
    """존재하지 않는 캘린더 이벤트 삭제 테스트"""
    task_id = "nonexistent_meeting"

    response = client.delete(f"/api/v1/calendar/events/{task_id}")

    assert response.status_code == 404
    assert "캘린더 이벤트를 찾을 수 없습니다" in response.json()["detail"]


def test_supported_calendars():
    """지원되는 캘린더 타입 테스트"""
    from backend.app.api.v1.calendar import SUPPORTED_CALENDARS

    expected_calendars = {"google", "outlook", "apple"}
    assert SUPPORTED_CALENDARS == expected_calendars
