from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_redis_client
from backend.app.error_handlers import register_exception_handlers
from backend.app.exceptions import InternalServerError
from backend.schemas.study_pack import (
    StudyFlashcard,
    StudyKeyConcept,
    StudyPackResponse,
    StudyQuizQuestion,
)
from backend.services.study_pack_service import (
    StudyPackSourceNotFoundError,
    StudyPackValidationError,
)


@pytest.fixture
def app_client():
    from backend.app.api.v1.minutes.study_pack import get_study_pack_service, router

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
    app.dependency_overrides[get_study_pack_service] = override_svc

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, redis_mock, svc_mock

    app.dependency_overrides.clear()


def test_get_study_pack_service_provider():
    from backend.app.api.v1.minutes.study_pack import get_study_pack_service
    from backend.services.study_pack_service import StudyPackService

    assert isinstance(get_study_pack_service(), StudyPackService)


def make_response() -> StudyPackResponse:
    return StudyPackResponse(
        task_id="min-001",
        mode="lecture",
        language="ko",
        key_concepts=[StudyKeyConcept(term="광합성", explanation="빛 에너지 전환")],
        flashcards=[StudyFlashcard(front="광합성?", back="빛 에너지 전환")],
        quiz_questions=[
            StudyQuizQuestion(question="광합성?", answer="빛 에너지 전환", difficulty="easy")
        ],
        study_notes="광합성 핵심 노트",
        source_refs=[],
        created_at="2026-06-21T00:00:00+00:00",
    )


def test_create_study_pack_success(app_client):
    client, _, svc = app_client
    svc.generate = AsyncMock(return_value=make_response())

    response = client.post("/api/v1/minutes/min-001/study-pack", json={"mode": "lecture"})

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "min-001"
    assert body["mode"] == "lecture"
    assert body["flashcards"][0]["front"] == "광합성?"


def test_get_study_pack_success(app_client):
    client, _, svc = app_client
    svc.get = AsyncMock(return_value=make_response())

    response = client.get("/api/v1/minutes/min-001/study-pack?mode=interview")

    assert response.status_code == 200
    assert response.json()["study_notes"] == "광합성 핵심 노트"
    svc.get.assert_awaited_once()
    assert svc.get.await_args.kwargs["mode"] == "interview"


def test_create_study_pack_missing_minutes_returns_404(app_client):
    client, _, svc = app_client
    svc.generate = AsyncMock(side_effect=StudyPackSourceNotFoundError("회의록 없음"))

    response = client.post("/api/v1/minutes/missing/study-pack", json={})

    assert response.status_code == 404


def test_create_study_pack_malformed_ai_response_returns_422(app_client):
    client, _, svc = app_client
    svc.generate = AsyncMock(side_effect=StudyPackValidationError("AI 응답 형식 오류"))

    response = client.post("/api/v1/minutes/min-001/study-pack", json={})

    assert response.status_code == 422


def test_get_study_pack_missing_returns_404(app_client):
    client, _, svc = app_client
    svc.get = AsyncMock(side_effect=StudyPackSourceNotFoundError("학습팩 없음"))

    response = client.get("/api/v1/minutes/missing/study-pack")

    assert response.status_code == 404


def test_create_study_pack_passes_voice_note_error_through(app_client):
    client, _, svc = app_client
    svc.generate = AsyncMock(
        side_effect=InternalServerError(message="도메인 오류", error_code="TEST")
    )

    response = client.post("/api/v1/minutes/min-001/study-pack", json={})

    assert response.status_code == 500
    assert response.json()["error_code"] == "TEST"


def test_create_study_pack_unexpected_error_returns_500(app_client):
    client, _, svc = app_client
    svc.generate = AsyncMock(side_effect=RuntimeError("boom"))

    response = client.post("/api/v1/minutes/min-001/study-pack", json={})

    assert response.status_code == 500
