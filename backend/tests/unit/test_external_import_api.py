from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.error_handlers import register_exception_handlers
from backend.schemas.external_import import (
    DocumentImportResponse,
    ExternalImportSourceType,
    ExternalTextImportResponse,
)
from backend.services.external_import_service import ExternalImportValidationError


@pytest.fixture
def app_client():
    from backend.app.api.v1.minutes.external_import import (
        get_document_import_service,
        get_external_import_service,
        router,
    )

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    db_mock = AsyncMock()
    redis_mock = AsyncMock()
    svc_mock = AsyncMock()
    document_svc_mock = AsyncMock()

    async def override_db():
        yield db_mock

    async def override_redis():
        return redis_mock

    def override_svc():
        return svc_mock

    def override_document_svc():
        return document_svc_mock

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_redis_client] = override_redis
    app.dependency_overrides[get_external_import_service] = override_svc
    app.dependency_overrides[get_document_import_service] = override_document_svc

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, svc_mock, document_svc_mock

    app.dependency_overrides.clear()


def _response() -> ExternalTextImportResponse:
    return ExternalTextImportResponse(
        task_id="ext-001",
        status="completed",
        title="영상 요약",
        source_url="https://youtu.be/example123",
        source_type=ExternalImportSourceType.YOUTUBE,
        language="ko",
        result_url="/api/v1/minutes/ext-001",
        search_indexed=True,
    )


def test_get_external_import_service_provider():
    from backend.app.api.v1.minutes.external_import import get_external_import_service
    from backend.services.external_import_service import ExternalImportService

    assert isinstance(get_external_import_service(), ExternalImportService)


def test_import_external_text_success(app_client):
    client, svc, _ = app_client
    svc.import_text = AsyncMock(return_value=_response())

    response = client.post(
        "/api/v1/imports/external-text",
        json={
            "source_url": "https://youtu.be/example123",
            "title": "영상 요약",
            "content": "사용자가 보유한 영상 transcript를 가져옵니다.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "ext-001"
    assert body["source_type"] == "youtube"
    assert body["search_indexed"] is True
    svc.import_text.assert_awaited_once()


def test_import_external_text_validation_error_returns_422(app_client):
    client, svc, _ = app_client
    svc.import_text = AsyncMock(side_effect=ExternalImportValidationError("본문 없음"))

    response = client.post(
        "/api/v1/imports/external-text",
        json={
            "source_url": "https://example.com/post",
            "title": "외부 글",
            "content": "사용자가 보유한 긴 transcript 본문입니다.",
        },
    )

    assert response.status_code == 422


def test_import_external_text_rejects_too_short_content(app_client):
    client, _, _ = app_client

    response = client.post(
        "/api/v1/imports/external-text",
        json={
            "source_url": "https://example.com/post",
            "title": "외부 글",
            "content": "짧음",
        },
    )

    assert response.status_code == 422


def test_import_external_text_unexpected_error_returns_500(app_client):
    client, svc, _ = app_client
    svc.import_text = AsyncMock(side_effect=RuntimeError("boom"))

    response = client.post(
        "/api/v1/imports/external-text",
        json={
            "source_url": "https://example.com/post",
            "title": "외부 글",
            "content": "사용자가 보유한 긴 transcript 본문입니다.",
        },
    )

    assert response.status_code == 500


def test_get_document_import_service_provider():
    from backend.app.api.v1.minutes.external_import import get_document_import_service
    from backend.services.document_import_service import DocumentImportService

    assert isinstance(get_document_import_service(), DocumentImportService)


def test_import_document_success(app_client):
    client, _, document_svc = app_client
    document_svc.import_document = AsyncMock(
        return_value=DocumentImportResponse(
            task_id="ext-doc-001",
            status="completed",
            title="강의 슬라이드",
            source_url="https://local.voicetextnote/imports/documents/lecture.pdf",
            source_type=ExternalImportSourceType.DOCUMENT,
            language="ko",
            result_url="/api/v1/minutes/ext-doc-001",
            search_indexed=True,
            file_name="lecture.pdf",
            file_type="pdf",
            extracted_characters=42,
        )
    )

    response = client.post(
        "/api/v1/imports/document",
        files={"file": ("lecture.pdf", b"%PDF searchable text", "application/pdf")},
        data={"title": "강의 슬라이드", "language": "ko"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "ext-doc-001"
    assert body["source_type"] == "document"
    assert body["file_type"] == "pdf"
    assert body["extracted_characters"] == 42
    document_svc.import_document.assert_awaited_once()


def test_import_document_validation_error_returns_422(app_client):
    client, _, document_svc = app_client
    document_svc.import_document = AsyncMock(
        side_effect=ExternalImportValidationError("PDF 또는 DOCX 문서만 가져올 수 있습니다.")
    )

    response = client.post(
        "/api/v1/imports/document",
        files={"file": ("slides.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code == 422


def test_import_document_unexpected_error_returns_500(app_client):
    client, _, document_svc = app_client
    document_svc.import_document = AsyncMock(side_effect=RuntimeError("boom"))

    response = client.post(
        "/api/v1/imports/document",
        files={"file": ("lecture.pdf", b"%PDF searchable text", "application/pdf")},
    )

    assert response.status_code == 500
