"""
SPEC-SENTIMENT-MINUTES: 회의 감정 분석 API 테스트

대상: app/api/v1/minutes/sentiment.py
  - POST /api/v1/sentiment (감정 분석 작업 요청)
  - GET  /api/v1/sentiment/{task_id}/status (상태 조회)
  - GET  /api/v1/sentiment/{task_id} (결과 조회)
  - DELETE /api/v1/sentiment/{task_id} (삭제)

참고: 이 모듈은 registry.py에 등록되지 않았으므로 독립 앱으로 테스트.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_redis_client
from backend.app.error_handlers import register_exception_handlers


@pytest.fixture
def app_client():
    """minutes/sentiment 라우터 테스트 앱."""
    from backend.app.api.v1.minutes.sentiment import router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    # Redis mock
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)

    async def override_redis():
        return mock_redis

    app.dependency_overrides[get_redis_client] = override_redis

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, mock_redis

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /sentiment
# ---------------------------------------------------------------------------


class TestCreateSentiment:
    """감정 분석 작업 요청."""

    def test_create_success(self, app_client):
        """정상 작업 등록."""
        client, mock_redis = app_client

        mock_task = MagicMock()
        with patch(
            "backend.workers.tasks.sentiment_task.sentiment_celery_task",
            mock_task,
        ):
            resp = client.post(
                "/api/v1/sentiment",
                json={"minutes_task_id": "test-minutes-123"},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert data["minutes_task_id"] == "test-minutes-123"
        assert "status_url" in data
        assert "result_url" in data

    def test_create_with_max_tokens(self, app_client):
        """max_tokens 포함 요청."""
        client, mock_redis = app_client

        mock_task = MagicMock()
        with patch(
            "backend.workers.tasks.sentiment_task.sentiment_celery_task",
            mock_task,
        ):
            resp = client.post(
                "/api/v1/sentiment",
                json={
                    "minutes_task_id": "test-minutes-456",
                    "max_tokens": 2048,
                },
            )

        assert resp.status_code == 202

    def test_create_missing_minutes_task_id_returns_422(self, app_client):
        """minutes_task_id 누락 -> 422."""
        client, _ = app_client
        resp = client.post("/api/v1/sentiment", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /sentiment/{task_id}/status
# ---------------------------------------------------------------------------


class TestGetSentimentStatus:
    """감정 분석 상태 조회."""

    def test_status_found(self, app_client):
        """상태 조회 성공."""
        client, mock_redis = app_client

        status_data = json.dumps({
            "task_id": "task-1",
            "status": "processing",
            "progress": 0.5,
            "message": "처리 중",
        })
        mock_redis.get = AsyncMock(return_value=status_data)

        resp = client.get("/api/v1/sentiment/task-1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-1"
        assert data["status"] == "processing"
        assert data["progress"] == 0.5

    def test_status_not_found(self, app_client):
        """작업 없음 -> 404."""
        client, mock_redis = app_client
        mock_redis.get = AsyncMock(return_value=None)

        resp = client.get("/api/v1/sentiment/nonexistent/status")
        assert resp.status_code == 404

    def test_status_with_error_message(self, app_client):
        """에러 메시지 포함 상태."""
        client, mock_redis = app_client

        status_data = json.dumps({
            "task_id": "task-err",
            "status": "failed",
            "progress": 0.0,
            "error_message": "처리 실패",
        })
        mock_redis.get = AsyncMock(return_value=status_data)

        resp = client.get("/api/v1/sentiment/task-err/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "처리 실패"


# ---------------------------------------------------------------------------
# GET /sentiment/{task_id}
# ---------------------------------------------------------------------------


class TestGetSentimentResult:
    """감정 분석 결과 전체 조회."""

    def test_result_with_full_data(self, app_client):
        """전체 결과 조회 성공."""
        client, mock_redis = app_client

        result_data = json.dumps({
            "task_id": "task-full",
            "status": "completed",
            "minutes_task_id": "minutes-1",
            "overall_sentiment": "positive",
            "overall_emotion": "joy",
            "segments": [],
            "speakers": [],
            "emotional_timeline": [],
            "generation_time_seconds": 2.5,
        })
        mock_redis.get = AsyncMock(return_value=result_data)

        resp = client.get("/api/v1/sentiment/task-full")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-full"
        assert data["overall_sentiment"] == "positive"

    def test_result_no_result_falls_back_to_status(self, app_client):
        """결과 없을 때 상태에서 폴백."""
        client, mock_redis = app_client

        async def mock_get(key):
            if "result" in key:
                return None
            # status 키
            return json.dumps({
                "task_id": "task-fallback",
                "status": "processing",
                "minutes_task_id": "minutes-2",
            })

        mock_redis.get = AsyncMock(side_effect=mock_get)

        resp = client.get("/api/v1/sentiment/task-fallback")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-fallback"
        assert data["status"] == "processing"

    def test_result_not_found(self, app_client):
        """결과와 상태 모두 없음 -> 404."""
        client, mock_redis = app_client
        mock_redis.get = AsyncMock(return_value=None)

        resp = client.get("/api/v1/sentiment/nonexistent")
        assert resp.status_code == 404

    def test_result_with_error_field(self, app_client):
        """error 필드 포함 결과 (error_message 폴백)."""
        client, mock_redis = app_client

        result_data = json.dumps({
            "task_id": "task-err-result",
            "status": "failed",
            "error": "분석 실패",
        })
        mock_redis.get = AsyncMock(return_value=result_data)

        resp = client.get("/api/v1/sentiment/task-err-result")
        assert resp.status_code == 200
        data = resp.json()
        assert data["error_message"] == "분석 실패"


# ---------------------------------------------------------------------------
# DELETE /sentiment/{task_id}
# ---------------------------------------------------------------------------


class TestDeleteSentiment:
    """감정 분석 작업 삭제."""

    def test_delete_success(self, app_client):
        """삭제 성공 -> 204."""
        client, mock_redis = app_client
        mock_redis.delete = AsyncMock(return_value=1)

        resp = client.delete("/api/v1/sentiment/task-to-delete")
        assert resp.status_code == 204
