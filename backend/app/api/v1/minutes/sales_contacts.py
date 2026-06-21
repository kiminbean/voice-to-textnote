"""Sales contact list API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
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
    page: int = Query(default=1, ge=1, description="Page number, starting at 1"),
    page_size: int = Query(default=20, ge=1, le=50, description="Items per page"),
    q: str | None = Query(default=None, min_length=2, description="Optional contact search"),
    db: AsyncSession = Depends(get_db_session),
    svc: SalesContactBriefService = Depends(get_sales_contact_service),
) -> SalesContactListResponse:
    """List persisted sales/customer follow-up briefs as lightweight CRM entries."""
    try:
        return await svc.list_contacts(db, page=page, page_size=page_size, query=q)
    except Exception as exc:
        internal_error(f"영업 연락처 목록 조회 중 오류가 발생했습니다: {exc}")


@router.patch("/sales-contacts/{artifact_task_id}/crm", response_model=SalesContactListItem)
async def update_sales_contact_crm(
    payload: SalesContactCrmUpdateRequest,
    artifact_task_id: str = Path(..., min_length=1),
    db: AsyncSession = Depends(get_db_session),
    svc: SalesContactBriefService = Depends(get_sales_contact_service),
) -> SalesContactListItem:
    """Update user-managed CRM fields for a generated sales/contact artifact."""
    try:
        return await svc.update_crm(db, artifact_task_id, payload)
    except SalesContactBriefSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        internal_error(f"영업 연락처 CRM 메모 저장 중 오류가 발생했습니다: {exc}")
