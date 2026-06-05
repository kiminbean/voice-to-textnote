"""
SPEC-QA-001: 회의 Q&A API 엔드포인트 테스트

대상: app/api/v1/qa.py
  - POST /api/v1/qa/ask (ask_question)
  - GET  /api/v1/qa/{task_id}/history (get_qa_history)
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_redis_client
from backend.app.error_handlers import register_exception_handlers
from backend.schemas.qa import MeetingAskResponse, QAHistoryItem, QAHistoryResponse, QASource


@pytest.fixture
def app_client():
    from backend.app.api.v1.audio.qa import get_qa_service, router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    redis_mock = AsyncMock()

    async def override_redis():
        return redis_mock

    svc_mock = AsyncMock()

    async def override_svc():
        return svc_mock

    app.dependency_overrides[get_redis_client] = override_redis
    app.dependency_overrides[get_qa_service] = override_svc

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, redis_mock, svc_mock

    app.dependency_overrides.clear()


class TestAskQuestion:
    def test_successful_ask(self, app_client):
        client, _, mock_svc = app_client
        mock_response = MeetingAskResponse(
            answer="분기 매출이 15% 증가했습니다.",
            sources=[QASource(segment_index=0, speaker="김철수", text="매출 증가")],
            thread_id="thread-123",
        )
        mock_svc.ask = AsyncMock(return_value=mock_response)

        resp = client.post(
            "/api/v1/qa/ask",
            json={
                "task_id": "task-001",
                "question": "매출 증가율은?",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "매출" in body["answer"]
        assert body["thread_id"] == "thread-123"
        assert len(body["sources"]) == 1

    def test_ask_with_thread_id(self, app_client):
        client, _, mock_svc = app_client
        mock_response = MeetingAskResponse(
            answer="답변입니다.",
            sources=[],
            thread_id="existing-thread",
        )
        mock_svc.ask = AsyncMock(return_value=mock_response)

        resp = client.post(
            "/api/v1/qa/ask",
            json={
                "task_id": "task-001",
                "question": "질문",
                "thread_id": "existing-thread",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["thread_id"] == "existing-thread"

    def test_ask_no_minutes_returns_404(self, app_client):
        client, _, mock_svc = app_client
        mock_svc.ask = AsyncMock(side_effect=ValueError("회의록을 찾을 수 없습니다"))

        resp = client.post(
            "/api/v1/qa/ask",
            json={"task_id": "missing-task", "question": "질문"},
        )

        assert resp.status_code == 404

    def test_ask_empty_content_returns_404(self, app_client):
        client, _, mock_svc = app_client
        mock_svc.ask = AsyncMock(side_effect=ValueError("회의록 내용이 비어 있습니다"))

        resp = client.post(
            "/api/v1/qa/ask",
            json={"task_id": "empty-task", "question": "질문"},
        )

        assert resp.status_code == 404

    def test_ask_internal_error_returns_500(self, app_client):
        client, _, mock_svc = app_client
        mock_svc.ask = AsyncMock(side_effect=RuntimeError("OpenAI 장애"))

        resp = client.post(
            "/api/v1/qa/ask",
            json={"task_id": "task-001", "question": "질문"},
        )

        assert resp.status_code == 500


class TestGetQAHistory:
    async def _async_iter(self, items):
        for item in items:
            yield item

    def test_empty_history(self, app_client):
        client, _, mock_svc = app_client
        mock_svc.get_history = AsyncMock(return_value=QAHistoryResponse(items=[], total=0))

        resp = client.get("/api/v1/qa/task-001/history")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_history_with_items(self, app_client):
        client, _, mock_svc = app_client

        history = QAHistoryResponse(
            items=[
                QAHistoryItem(
                    question="질문1",
                    answer="답변1",
                    sources=[],
                    created_at="2026-01-01T10:00:00",
                ),
                QAHistoryItem(
                    question="질문2",
                    answer="답변2",
                    sources=[],
                    created_at="2026-01-01T11:00:00",
                ),
            ],
            total=2,
        )
        mock_svc.get_history = AsyncMock(return_value=history)

        resp = client.get("/api/v1/qa/task-001/history")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["items"][0]["question"] == "질문1"
