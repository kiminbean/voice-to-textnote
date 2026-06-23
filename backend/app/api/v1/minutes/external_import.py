"""External URL/text import API endpoints."""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_optional_current_user, get_redis_client
from backend.app.errors import internal_error, unprocessable
from backend.schemas.external_import import (
    DocumentImportResponse,
    ExternalTextImportRequest,
    ExternalTextImportResponse,
)
from backend.services.document_import_service import DocumentImportService
from backend.services.external_import_service import (
    ExternalImportService,
    ExternalImportValidationError,
)

router = APIRouter(prefix="/imports", tags=["imports"])


def get_external_import_service() -> ExternalImportService:
    """ExternalImportService dependency provider."""
    return ExternalImportService()


def get_document_import_service() -> DocumentImportService:
    """DocumentImportService dependency provider."""
    return DocumentImportService()


@router.post(
    "/external-text",
    response_model=ExternalTextImportResponse,
    responses={422: {"description": "가져오기 입력 검증 실패"}},
)
async def import_external_text(
    request: Request,
    payload: ExternalTextImportRequest,
    db: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    current_user=Depends(get_optional_current_user),
    svc: ExternalImportService = Depends(get_external_import_service),
) -> ExternalTextImportResponse:
    """Import user-provided URL transcript/text as a completed minutes artifact."""
    try:
        return await svc.import_text(
            payload,
            db,
            redis_client,
            owner_id=getattr(current_user, "id", None),
            is_guest=bool(getattr(request.state, "is_guest", False)),
            guest_session_id=getattr(request.state, "guest_session_id", None),
        )
    except ExternalImportValidationError as exc:
        unprocessable(str(exc))
    except Exception as exc:
        internal_error(f"외부 텍스트 가져오기 중 오류가 발생했습니다: {exc}")


@router.post(
    "/document",
    response_model=DocumentImportResponse,
    responses={422: {"description": "문서 가져오기 입력 또는 추출 실패"}},
)
async def import_document(
    request: Request,
    file: UploadFile = File(..., description="PDF 또는 DOCX 문서"),
    title: str | None = Form(default=None, description="가져올 노트 제목"),
    language: str = Form(default="ko", min_length=2, max_length=16, description="콘텐츠 언어"),
    db: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    current_user=Depends(get_optional_current_user),
    svc: DocumentImportService = Depends(get_document_import_service),
) -> DocumentImportResponse:
    """Import a user-owned PDF/DOCX/image document as searchable minutes-compatible content."""
    try:
        return await svc.import_document(
            filename=file.filename or "",
            content=await file.read(),
            title=title,
            language=language,
            db=db,
            redis_client=redis_client,
            owner_id=getattr(current_user, "id", None),
            is_guest=bool(getattr(request.state, "is_guest", False)),
            guest_session_id=getattr(request.state, "guest_session_id", None),
        )
    except ExternalImportValidationError as exc:
        unprocessable(str(exc))
    except Exception as exc:
        internal_error(f"문서 가져오기 중 오류가 발생했습니다: {exc}")
