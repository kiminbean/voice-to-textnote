from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_redis_client
from backend.app.error_handlers import register_exception_handlers
from backend.app.exceptions import InternalServerError
from backend.schemas.sales_contact_brief import (
    SalesContactBriefResponse,
    SalesContactDeal,
    SalesContactIdentity,
    SalesNextStep,
)
from backend.services.sales_contact_brief_service import (
    SalesContactBriefSourceNotFoundError,
    SalesContactBriefValidationError,
)


@pytest.fixture
def app_client():
    from backend.app.api.v1.minutes.sales_contact_brief import (
        get_sales_contact_brief_service,
        router,
    )

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
    app.dependency_overrides[get_sales_contact_brief_service] = override_svc

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, redis_mock, svc_mock

    app.dependency_overrides.clear()


def make_response() -> SalesContactBriefResponse:
    return SalesContactBriefResponse(
        task_id="min-sales-001",
        contact=SalesContactIdentity(name="김민수", company="Acme", role="CTO"),
        deal=SalesContactDeal(stage="demo_requested", urgency="high"),
        customer_needs=["보안 감사 자동화"],
        pain_points=["수동 감사 시간"],
        objections=["견적 확인 필요"],
        next_steps=[SalesNextStep(task="데모 일정 확정", owner="영업", due="다음 주 화요일")],
        follow_up_message="요청하신 데모 일정을 확인드리겠습니다.",
        source_refs=[],
        created_at="2026-06-21T00:00:00+00:00",
    )


def test_get_sales_contact_brief_service_provider():
    from backend.app.api.v1.minutes.sales_contact_brief import get_sales_contact_brief_service
    from backend.services.sales_contact_brief_service import SalesContactBriefService

    assert isinstance(get_sales_contact_brief_service(), SalesContactBriefService)


def test_create_sales_contact_brief_success(app_client):
    client, _, svc = app_client
    svc.generate = AsyncMock(return_value=make_response())

    response = client.post("/api/v1/minutes/min-sales-001/sales-contact-brief", json={})

    assert response.status_code == 200
    assert response.json()["contact"]["company"] == "Acme"
    svc.generate.assert_awaited_once()


def test_get_sales_contact_brief_success(app_client):
    client, _, svc = app_client
    svc.get = AsyncMock(return_value=make_response())

    response = client.get("/api/v1/minutes/min-sales-001/sales-contact-brief")

    assert response.status_code == 200
    assert response.json()["next_steps"][0]["task"] == "데모 일정 확정"
    svc.get.assert_awaited_once()


def test_create_sales_contact_brief_missing_minutes_returns_404(app_client):
    client, _, svc = app_client
    svc.generate = AsyncMock(side_effect=SalesContactBriefSourceNotFoundError("회의록 없음"))

    response = client.post("/api/v1/minutes/missing/sales-contact-brief", json={})

    assert response.status_code == 404


def test_create_sales_contact_brief_malformed_ai_response_returns_422(app_client):
    client, _, svc = app_client
    svc.generate = AsyncMock(side_effect=SalesContactBriefValidationError("AI 응답 형식 오류"))

    response = client.post("/api/v1/minutes/min-sales-001/sales-contact-brief", json={})

    assert response.status_code == 422


def test_get_sales_contact_brief_missing_returns_404(app_client):
    client, _, svc = app_client
    svc.get = AsyncMock(side_effect=SalesContactBriefSourceNotFoundError("브리프 없음"))

    response = client.get("/api/v1/minutes/missing/sales-contact-brief")

    assert response.status_code == 404


def test_create_sales_contact_brief_passes_voice_note_error_through(app_client):
    client, _, svc = app_client
    svc.generate = AsyncMock(
        side_effect=InternalServerError(message="도메인 오류", error_code="TEST")
    )

    response = client.post("/api/v1/minutes/min-sales-001/sales-contact-brief", json={})

    assert response.status_code == 500
    assert response.json()["error_code"] == "TEST"


def test_create_sales_contact_brief_unexpected_error_returns_500(app_client):
    client, _, svc = app_client
    svc.generate = AsyncMock(side_effect=RuntimeError("boom"))

    response = client.post("/api/v1/minutes/min-sales-001/sales-contact-brief", json={})

    assert response.status_code == 500
