"""External URL/text import API endpoints."""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.errors import internal_error, unprocessable
from backend.schemas.external_import import ExternalTextImportRequest, ExternalTextImportResponse
from backend.services.external_import_service import (
    ExternalImportService,
    ExternalImportValidationError,
)

router = APIRouter(prefix="/imports", tags=["imports"])


def get_external_import_service() -> ExternalImportService:
    """ExternalImportService dependency provider."""
    return ExternalImportService()


@router.post(
    "/external-text",
    response_model=ExternalTextImportResponse,
    responses={422: {"description": "가져오기 입력 검증 실패"}},
)
async def import_external_text(
    payload: ExternalTextImportRequest,
    db: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: ExternalImportService = Depends(get_external_import_service),
) -> ExternalTextImportResponse:
    """Import user-provided URL transcript/text as a completed minutes artifact."""
    try:
        return await svc.import_text(payload, db, redis_client)
    except ExternalImportValidationError as exc:
        unprocessable(str(exc))
    except Exception as exc:
        internal_error(f"외부 텍스트 가져오기 중 오류가 발생했습니다: {exc}")
