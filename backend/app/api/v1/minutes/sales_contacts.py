"""Sales contact list API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session
from backend.app.errors import internal_error
from backend.schemas.sales_contact_brief import (
    SalesContactCrmUpdateRequest,
    SalesContactListItem,
    SalesContactListResponse,
)
from backend.services.sales_contact_brief_service import (
    SalesContactBriefService,
    SalesContactBriefSourceNotFoundError,
)

router = APIRouter(tags=["sales-contacts"])


def get_sales_contact_service() -> SalesContactBriefService:
    """SalesContactBriefService dependency provider for list endpoints."""
    return SalesContactBriefService()


@router.get("/sales-contacts", response_model=SalesContactListResponse)
async def list_sales_contacts(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number, starting at 1"),
    page_size: int = Query(default=20, ge=1, le=50, description="Items per page"),
    q: str | None = Query(default=None, min_length=2, description="Optional contact search"),
    db: AsyncSession = Depends(get_db_session),
    svc: SalesContactBriefService = Depends(get_sales_contact_service),
) -> SalesContactListResponse:
    """List persisted sales/customer follow-up briefs as lightweight CRM entries."""
    try:
        return await svc.list_contacts(
            db,
            page=page,
            page_size=page_size,
            query=q,
            owner_id=_request_owner_id(request),
            guest_session_id=_request_guest_session_id(request),
        )
    except Exception as exc:
        internal_error(f"영업 연락처 목록 조회 중 오류가 발생했습니다: {exc}")


@router.get("/sales-contacts/export.csv")
async def export_sales_contacts_csv(
    request: Request,
    q: str | None = Query(default=None, min_length=2, description="Optional contact search"),
    db: AsyncSession = Depends(get_db_session),
    svc: SalesContactBriefService = Depends(get_sales_contact_service),
) -> Response:
    """Export matching sales/customer follow-up entries as CRM-importable CSV."""
    try:
        csv_text = await svc.export_contacts_csv(
            db,
            query=q,
            owner_id=_request_owner_id(request),
            guest_session_id=_request_guest_session_id(request),
        )
    except Exception as exc:
        internal_error(f"영업 연락처 CSV 내보내기 중 오류가 발생했습니다: {exc}")
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sales-contacts.csv"'},
    )


@router.patch("/sales-contacts/{artifact_task_id}/crm", response_model=SalesContactListItem)
async def update_sales_contact_crm(
    request: Request,
    payload: SalesContactCrmUpdateRequest,
    artifact_task_id: str = Path(..., min_length=1),
    db: AsyncSession = Depends(get_db_session),
    svc: SalesContactBriefService = Depends(get_sales_contact_service),
) -> SalesContactListItem:
    """Update user-managed CRM fields for a generated sales/contact artifact."""
    try:
        return await svc.update_crm(
            db,
            artifact_task_id,
            payload,
            owner_id=_request_owner_id(request),
            guest_session_id=_request_guest_session_id(request),
        )
    except SalesContactBriefSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        internal_error(f"영업 연락처 CRM 메모 저장 중 오류가 발생했습니다: {exc}")


def _request_owner_id(request: Request) -> uuid.UUID | None:
    raw_user_id = getattr(request.state, "user_id", None)
    if not raw_user_id:
        return None
    try:
        return uuid.UUID(str(raw_user_id))
    except ValueError:
        return None


def _request_guest_session_id(request: Request) -> str | None:
    if getattr(request.state, "is_guest", False) is not True:
        return None
    guest_session_id = getattr(request.state, "guest_session_id", None)
    return str(guest_session_id) if guest_session_id else None
