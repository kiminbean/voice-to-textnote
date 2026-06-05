"""
minutes.py 추가 테스트 (커버리지 개선)

대상 라인:
- Line 155-168: status가 processing/pending/failed인 경우
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.v1.minutes import router
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
# GET /minutes/{task_id} - 다양한 status 처리 (Lines 155-168)
# ---------------------------------------------------------------------------


class TestGetMinutesResultStatushandling:
    """다양한 task status에 대한 응답 테스트"""

    def test_returns_pending_response_when_status_pending(self, mock_redis):
        """status가 pending이면 진행 중 응답 반환"""
        import json

        app = make_app(mock_redis)
        client = TestClient(app)

        # 결과는 없지만 상태는 있는 경우
        mock_redis.get.return_value = None  # 결과 없음

        status_data = {
            "status": "pending",
            "diarization_task_id": "dia-123",
        }
        mock_redis.get.side_effect = lambda key: (
            None if "result" in key else json.dumps(status_data)
        )

        resp = client.get("/api/v1/minutes/test-task-id")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending"
        assert body["diarization_task_id"] == "dia-123"
        assert body["segments"] == []
        assert body["speakers"] == []

    def test_returns_processing_response_when_status_processing(self, mock_redis):
        """status가 processing이면 진행 중 응답 반환"""
        import json

        app = make_app(mock_redis)
        client = TestClient(app)

        status_data = {
            "status": "processing",
            "diarization_task_id": "dia-456",
        }
        mock_redis.get.side_effect = lambda key: (
            None if "result" in key else json.dumps(status_data)
        )

        resp = client.get("/api/v1/minutes/test-task-id")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "processing"

    def test_returns_failed_response_with_error_message(self, mock_redis):
        """status가 failed면 에러 메시지 포함"""
        import json

        app = make_app(mock_redis)
        client = TestClient(app)

        status_data = {
            "status": "failed",
            "error_message": "처리 중 오류 발생",
            "diarization_task_id": "",
        }
        mock_redis.get.side_effect = lambda key: (
            None if "result" in key else json.dumps(status_data)
        )

        resp = client.get("/api/v1/minutes/test-task-id")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert body["error_message"] == "처리 중 오류 발생"

    def test_returns_404_when_no_status_key(self, mock_redis):
        """status 키도 없으면 404"""
        app = make_app(mock_redis)
        client = TestClient(app)

        # 모든 키가 없음
        mock_redis.get.return_value = None

        resp = client.get("/api/v1/minutes/nonexistent-task")

        assert resp.status_code == 404
        assert "회의록 작업을 찾을 수 없습니다" in resp.json()["message"]
