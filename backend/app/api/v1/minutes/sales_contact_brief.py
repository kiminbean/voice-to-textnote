"""Sales contact brief API endpoints."""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.errors import internal_error, not_found, unprocessable
from backend.app.exceptions import VoiceNoteError
from backend.schemas.sales_contact_brief import (
    SalesContactBriefCreateRequest,
    SalesContactBriefResponse,
)
from backend.services.sales_contact_brief_service import (
    SalesContactBriefService,
    SalesContactBriefSourceNotFoundError,
    SalesContactBriefValidationError,
)

router = APIRouter(prefix="/minutes", tags=["sales-contact-brief"])


def get_sales_contact_brief_service() -> SalesContactBriefService:
    """SalesContactBriefService dependency provider."""
    return SalesContactBriefService()


@router.post(
    "/{task_id}/sales-contact-brief",
    response_model=SalesContactBriefResponse,
    responses={
        404: {"description": "회의록 없음"},
        422: {"description": "영업 연락처 브리프 생성 응답 검증 실패"},
    },
)
async def create_sales_contact_brief(
    request: Request,
    task_id: str,
    payload: SalesContactBriefCreateRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
    svc: SalesContactBriefService = Depends(get_sales_contact_brief_service),
) -> SalesContactBriefResponse:
    """Generate a transcript-grounded sales/contact follow-up brief."""
    try:
        return await svc.generate(
            task_id,
            redis_client,
            language=payload.language,
            max_tokens=payload.max_tokens,
            force_refresh=payload.force_refresh,
            db_session=db,
            owner_id=getattr(request.state, "user_id", None),
            guest_session_id=(
                getattr(request.state, "guest_session_id", None)
                if getattr(request.state, "is_guest", False)
                else None
            ),
        )
    except SalesContactBriefSourceNotFoundError as exc:
        not_found(str(exc))
    except SalesContactBriefValidationError as exc:
        unprocessable(str(exc))
    except VoiceNoteError:
        raise
    except Exception as exc:
        internal_error(f"영업 연락처 브리프 생성 중 오류가 발생했습니다: {exc}")


@router.get(
    "/{task_id}/sales-contact-brief",
    response_model=SalesContactBriefResponse,
    responses={404: {"description": "영업 연락처 브리프 없음"}},
)
async def get_sales_contact_brief(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: SalesContactBriefService = Depends(get_sales_contact_brief_service),
) -> SalesContactBriefResponse:
    """Load a cached sales/contact follow-up brief."""
    try:
        return await svc.get(task_id, redis_client)
    except SalesContactBriefSourceNotFoundError as exc:
        not_found(str(exc))
