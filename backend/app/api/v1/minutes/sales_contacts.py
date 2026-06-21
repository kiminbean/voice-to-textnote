"""Sales contact list API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session
from backend.app.errors import internal_error
from backend.schemas.sales_contact_brief import SalesContactListResponse
from backend.services.sales_contact_brief_service import SalesContactBriefService

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
