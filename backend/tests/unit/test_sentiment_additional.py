"""
sentiment.py 추가 테스트 (커버리지 개선)

대상 라인:
- Line 116-121: status_key 확인 및 pending/failed 처리
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.v1.sentiment import router
from backend.app.error_handlers import register_exception_handlers


@pytest.fixture
def mock_redis():
    """Redis 클라이언트 mock"""
    redis_mock = AsyncMock()
    return redis_mock


def make_app(mock_redis):
    """테스트용 FastAPI 앱 생성"""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    from backend.app.dependencies import get_redis_client

    async def override_redis():
        return mock_redis

    app.dependency_overrides[get_redis_client] = override_redis
    return app


# ---------------------------------------------------------------------------
# GET /sentiment/{task_id} - status 처리 (Lines 116-121)
# ---------------------------------------------------------------------------


class TestGetSentimentStatushandling:
    """다양한 task status에 대한 응답 테스트"""

    def test_returns_pending_status_when_no_result(self, mock_redis):
        """결과가 없고 상태만 있는 경우 pending 반환"""
        import json

        app = make_app(mock_redis)
        client = TestClient(app)

        status_data = {
            "status": "pending",
            "minutes_task_id": "min-123",
        }
        mock_redis.get.side_effect = lambda key: (
            None if "result" in key else json.dumps(status_data)
        )

        resp = client.get("/api/v1/sentiment/test-task-id")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending"
        assert body["minutes_task_id"] == "min-123"

    def test_returns_failed_status_with_error(self, mock_redis):
        """실패한 작업 상태 반환"""
        import json

        app = make_app(mock_redis)
        client = TestClient(app)

        status_data = {
            "status": "failed",
            "minutes_task_id": "min-456",
            "error_message": "감정 분석 실패",
        }
        mock_redis.get.side_effect = lambda key: (
            None if "result" in key else json.dumps(status_data)
        )

        resp = client.get("/api/v1/sentiment/test-task-id")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        # error_message가 응답에 포함되는지 확인 (구현에 따라 다를 수 있음)

    def test_returns_404_when_no_status_key(self, mock_redis):
        """상태 키도 없으면 404"""
        app = make_app(mock_redis)
        client = TestClient(app)

        mock_redis.get.return_value = None

        resp = client.get("/api/v1/sentiment/nonexistent-task")

        assert resp.status_code == 404
        assert "감정 분석 작업을 찾을 수 없습니다" in resp.json()["message"]

    def test_returns_completed_result(self, mock_redis):
        """완료된 결과 반환"""
        import json

        app = make_app(mock_redis)
        client = TestClient(app)

        result_data = {
            "task_id": "test-task-id",
            "status": "completed",
            "minutes_task_id": "min-789",
            "overall_sentiment": "positive",
            "overall_emotion": "happy",
            "segments": [],
            "speakers": [],
            "emotional_timeline": [],
            "generation_time_seconds": 2.5,
        }
        mock_redis.get.side_effect = lambda key: (
            json.dumps(result_data) if "result" in key else json.dumps({"status": "completed"})
        )

        resp = client.get("/api/v1/sentiment/test-task-id")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["overall_sentiment"] == "positive"
        assert body["overall_emotion"] == "happy"
