from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_db_session
from backend.app.error_handlers import register_exception_handlers
from backend.schemas.sales_contact_brief import (
    SalesContactCrmUpdateRequest,
    SalesContactDeal,
    SalesContactIdentity,
    SalesContactListItem,
    SalesContactListResponse,
    SalesNextStep,
)
from backend.services.sales_contact_brief_service import SalesContactBriefSourceNotFoundError


@pytest.fixture
def app_client():
    from backend.app.api.v1.minutes.sales_contacts import get_sales_contact_service, router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    db_session = object()
    svc_mock = AsyncMock()

    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_sales_contact_service] = lambda: svc_mock

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, svc_mock, db_session

    app.dependency_overrides.clear()


def make_list_response() -> SalesContactListResponse:
    return SalesContactListResponse(
        items=[
            SalesContactListItem(
                artifact_task_id="sales-contact-brief:min-sales-001",
                source_task_id="min-sales-001",
                contact=SalesContactIdentity(name="김민수", company="Acme", role="CTO"),
                deal=SalesContactDeal(stage="demo_requested", urgency="high"),
                customer_needs=["보안 감사 자동화"],
                pain_points=["수동 감사 시간"],
                next_steps=[SalesNextStep(task="데모 일정 확정", owner="영업", due="화요일")],
                follow_up_message="데모 일정을 확인드리겠습니다.",
                crm_status="follow_up",
                crm_note="견적서 발송 후 금요일 재확인",
                crm_updated_at="2026-06-21T01:00:00+00:00",
                created_at="2026-06-21T00:00:00+00:00",
                completed_at="2026-06-21T00:00:00",
            )
        ],
        total=1,
        page=1,
        page_size=20,
    )


def test_get_sales_contact_service_provider():
    from backend.app.api.v1.minutes.sales_contacts import get_sales_contact_service
    from backend.services.sales_contact_brief_service import SalesContactBriefService

    assert isinstance(get_sales_contact_service(), SalesContactBriefService)


def test_list_sales_contacts_success(app_client):
    client, svc, db_session = app_client
    svc.list_contacts = AsyncMock(return_value=make_list_response())

    response = client.get("/api/v1/sales-contacts", params={"q": "Acme"})

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["contact"]["company"] == "Acme"
    assert body["items"][0]["source_task_id"] == "min-sales-001"
    assert body["items"][0]["crm_status"] == "follow_up"
    assert body["items"][0]["crm_note"] == "견적서 발송 후 금요일 재확인"
    svc.list_contacts.assert_awaited_once_with(
        db_session,
        page=1,
        page_size=20,
        query="Acme",
    )


def test_list_sales_contacts_validates_page_size(app_client):
    client, _, _ = app_client

    response = client.get("/api/v1/sales-contacts", params={"page_size": 100})

    assert response.status_code == 422


def test_list_sales_contacts_unexpected_error_returns_500(app_client):
    client, svc, _ = app_client
    svc.list_contacts = AsyncMock(side_effect=RuntimeError("boom"))

    response = client.get("/api/v1/sales-contacts")

    assert response.status_code == 500


def test_update_sales_contact_crm_success(app_client):
    client, svc, db_session = app_client
    updated = make_list_response().items[0]
    svc.update_crm = AsyncMock(return_value=updated)

    response = client.patch(
        "/api/v1/sales-contacts/sales-contact-brief:min-sales-001/crm",
        json={"status": "follow_up", "note": "금요일 오전 재연락"},
    )

    assert response.status_code == 200
    assert response.json()["crm_note"] == "견적서 발송 후 금요일 재확인"
    svc.update_crm.assert_awaited_once()
    args = svc.update_crm.await_args.args
    assert args[0] is db_session
    assert args[1] == "sales-contact-brief:min-sales-001"
    assert isinstance(args[2], SalesContactCrmUpdateRequest)
    assert args[2].status == "follow_up"
    assert args[2].note == "금요일 오전 재연락"


def test_update_sales_contact_crm_validates_note_length(app_client):
    client, _, _ = app_client

    response = client.patch(
        "/api/v1/sales-contacts/sales-contact-brief:min-sales-001/crm",
        json={"status": "follow_up", "note": "x" * 2001},
    )

    assert response.status_code == 422


def test_update_sales_contact_crm_missing_returns_404(app_client):
    client, svc, _ = app_client
    svc.update_crm = AsyncMock(
        side_effect=SalesContactBriefSourceNotFoundError("영업 연락처를 찾을 수 없습니다.")
    )

    response = client.patch(
        "/api/v1/sales-contacts/sales-contact-brief:min-sales-404/crm",
        json={"status": "follow_up", "note": "금요일 오전 재연락"},
    )

    assert response.status_code == 404


def test_update_sales_contact_crm_unexpected_error_returns_500(app_client):
    client, svc, _ = app_client
    svc.update_crm = AsyncMock(side_effect=RuntimeError("db unavailable"))

    response = client.patch(
        "/api/v1/sales-contacts/sales-contact-brief:min-sales-001/crm",
        json={"status": "follow_up", "note": "금요일 오전 재연락"},
    )

    assert response.status_code == 500
