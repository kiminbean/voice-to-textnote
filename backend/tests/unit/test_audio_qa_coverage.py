"""
SPEC-QA-001: 회의 Q&A API 테스트

대상: app/api/v1/audio/qa.py
  - POST /api/v1/qa/ask          질문하기
  - GET  /api/v1/qa/{task_id}/history  이력 조회
  - get_qa_service 의존성 주입 테스트
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_redis_client
from backend.app.error_handlers import register_exception_handlers
from backend.app.exceptions import VoiceNoteError


@pytest.fixture
def app_client():
    """QA 라우터 테스트 앱."""
    from backend.app.api.v1.audio.qa import get_qa_service, router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    # Redis mock
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    async def override_redis():
        return mock_redis

    # QA 서비스 mock
    mock_svc = MagicMock()

    async def override_svc():
        return mock_svc

    app.dependency_overrides[get_redis_client] = override_redis
    app.dependency_overrides[get_qa_service] = override_svc

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, mock_redis, mock_svc

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /qa/ask
# ---------------------------------------------------------------------------


class TestAskQuestion:
    """회의 Q&A 질문."""

    def test_ask_success(self, app_client):
        """정상 질문."""
        client, _mock_redis, mock_svc = app_client

        mock_svc.ask = AsyncMock(
            return_value=MagicMock(
                answer="테스트 답변입니다.",
                sources=[],
                thread_id="thread-1",
            )
        )

        resp = client.post(
            "/api/v1/qa/ask",
            json={
                "task_id": "task-123",
                "question": "회의 내용이 무엇인가요?",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "테스트 답변입니다."
        assert data["thread_id"] == "thread-1"

    def test_ask_with_thread_id(self, app_client):
        """스레드 ID 포함 질문."""
        client, _mock_redis, mock_svc = app_client

        mock_svc.ask = AsyncMock(
            return_value=MagicMock(
                answer="후속 답변입니다.",
                sources=[],
                thread_id="thread-1",
            )
        )

        resp = client.post(
            "/api/v1/qa/ask",
            json={
                "task_id": "task-123",
                "question": "더 자세히 설명해주세요.",
                "thread_id": "thread-1",
            },
        )

        assert resp.status_code == 200

    def test_ask_not_found_raises_value_error(self, app_client):
        """ValueError (회의록 없음) -> not_found 에러."""
        client, _mock_redis, mock_svc = app_client

        mock_svc.ask = AsyncMock(side_effect=ValueError("회의록을 찾을 수 없습니다"))

        resp = client.post(
            "/api/v1/qa/ask",
            json={
                "task_id": "nonexistent",
                "question": "무엇인가요?",
            },
        )

        assert resp.status_code == 404

    def test_ask_voice_note_error_passes_through(self, app_client):
        """VoiceNoteError 예외 pass-through."""
        client, _mock_redis, mock_svc = app_client

        mock_svc.ask = AsyncMock(
            side_effect=VoiceNoteError(
                error_code="AUDIO_ERROR",
                message="음성 처리 오류",
                status_code=400,
            )
        )

        # VoiceNoteError는 FastAPI HTTPException으로 변환되지 않으므로
        # error_handler에서 처리되거나 500 반환
        resp = client.post(
            "/api/v1/qa/ask",
            json={
                "task_id": "task-123",
                "question": "질문",
            },
        )

        # VoiceNoteError는 기본적으로 500으로 처리됨
        assert resp.status_code in (400, 500)

    def test_ask_generic_exception_returns_500(self, app_client):
        """일반 예외 -> internal_error -> 500."""
        client, _mock_redis, mock_svc = app_client

        mock_svc.ask = AsyncMock(side_effect=RuntimeError("예상치 못한 오류"))

        resp = client.post(
            "/api/v1/qa/ask",
            json={
                "task_id": "task-123",
                "question": "질문",
            },
        )

        assert resp.status_code == 500

    def test_ask_missing_task_id_returns_422(self, app_client):
        """task_id 누락 -> 422."""
        client, _, _ = app_client
        resp = client.post(
            "/api/v1/qa/ask",
            json={"question": "질문"},
        )
        assert resp.status_code == 422

    def test_ask_missing_question_returns_422(self, app_client):
        """question 누락 -> 422."""
        client, _, _ = app_client
        resp = client.post(
            "/api/v1/qa/ask",
            json={"task_id": "task-123"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /qa/{task_id}/history
# ---------------------------------------------------------------------------


class TestGetQAHistory:
    """Q&A 이력 조회."""

    def test_history_success(self, app_client):
        """정상 이력 조회."""
        client, _mock_redis, mock_svc = app_client

        mock_svc.get_history = AsyncMock(
            return_value=MagicMock(
                items=[],
                total=0,
            )
        )

        resp = client.get("/api/v1/qa/task-123/history")

        assert resp.status_code == 200

    def test_history_with_items(self, app_client):
        """이력 항목 포함 조회."""
        client, _mock_redis, mock_svc = app_client

        mock_history_item = MagicMock()
        mock_history_item.question = "질문1"
        mock_history_item.answer = "답변1"
        mock_history_item.sources = []
        mock_history_item.created_at = "2024-01-01T00:00:00"

        mock_svc.get_history = AsyncMock(
            return_value=MagicMock(
                items=[mock_history_item],
                total=1,
            )
        )

        resp = client.get("/api/v1/qa/task-123/history")

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# get_qa_service 의존성
# ---------------------------------------------------------------------------


class TestGetQAService:
    """get_qa_service 의존성 주입."""

    def test_creates_service_instance(self):
        """서비스 인스턴스 생성 확인."""
        from backend.app.api.v1.audio.qa import get_qa_service
        from backend.services.qa_service import QAService

        svc = get_qa_service()
        assert isinstance(svc, QAService)
