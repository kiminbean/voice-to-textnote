from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_db_session
from backend.app.error_handlers import register_exception_handlers
from backend.app.exceptions import InternalServerError
from backend.schemas.translation import TranslationResponse
from backend.services.translation_service import (
    TranslationSourceNotFoundError,
    TranslationValidationError,
)


@pytest.fixture
def app_client():
    from backend.app.api.v1.minutes.translation import get_translation_service, router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    db_mock = AsyncMock()

    async def override_db():
        yield db_mock

    svc_mock = AsyncMock()

    async def override_svc():
        return svc_mock

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_translation_service] = override_svc

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, db_mock, svc_mock

    app.dependency_overrides.clear()


def make_response(cached: bool = False) -> TranslationResponse:
    return TranslationResponse(
        task_id="min-001",
        source_type="summary",
        source_language="ko",
        target_language="en",
        translated_text="Meeting summary",
        source_excerpt="회의 요약",
        cached=cached,
        created_at="2026-06-21T00:00:00+00:00",
    )


def test_get_translation_service_provider():
    from backend.app.api.v1.minutes.translation import get_translation_service
    from backend.services.translation_service import TranslationService

    assert isinstance(get_translation_service(), TranslationService)


def test_create_translation_success(app_client):
    client, _, svc = app_client
    svc.translate = AsyncMock(return_value=make_response())

    response = client.post(
        "/api/v1/minutes/min-001/translation",
        json={"target_language": "en", "source_language": "ko", "source_type": "summary"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["translated_text"] == "Meeting summary"
    svc.translate.assert_awaited_once()
    assert svc.translate.await_args.kwargs["source_type"] == "summary"


def test_get_translation_success(app_client):
    client, _, svc = app_client
    svc.get = AsyncMock(return_value=make_response(cached=True))

    response = client.get("/api/v1/minutes/min-001/translation?target_language=en")

    assert response.status_code == 200
    assert response.json()["cached"] is True
    svc.get.assert_awaited_once()


def test_create_translation_missing_source_returns_404(app_client):
    client, _, svc = app_client
    svc.translate = AsyncMock(side_effect=TranslationSourceNotFoundError("회의록 없음"))

    response = client.post("/api/v1/minutes/missing/translation", json={"target_language": "en"})

    assert response.status_code == 404


def test_create_translation_validation_error_returns_422(app_client):
    client, _, svc = app_client
    svc.translate = AsyncMock(side_effect=TranslationValidationError("소스 없음"))

    response = client.post("/api/v1/minutes/min-001/translation", json={"target_language": "en"})

    assert response.status_code == 422


def test_get_translation_missing_returns_404(app_client):
    client, _, svc = app_client
    svc.get = AsyncMock(side_effect=TranslationSourceNotFoundError("번역 없음"))

    response = client.get("/api/v1/minutes/missing/translation?target_language=en")

    assert response.status_code == 404


def test_create_translation_passes_voice_note_error_through(app_client):
    client, _, svc = app_client
    svc.translate = AsyncMock(
        side_effect=InternalServerError(message="도메인 오류", error_code="TEST")
    )

    response = client.post("/api/v1/minutes/min-001/translation", json={"target_language": "en"})

    assert response.status_code == 500
    assert response.json()["error_code"] == "TEST"


def test_create_translation_unexpected_error_returns_500(app_client):
    client, _, svc = app_client
    svc.translate = AsyncMock(side_effect=RuntimeError("boom"))

    response = client.post("/api/v1/minutes/min-001/translation", json={"target_language": "en"})

    assert response.status_code == 500
