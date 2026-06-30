"""Minutes and summary translation API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_request_context, require_task_access
from backend.app.errors import internal_error, not_found, unprocessable
from backend.app.exceptions import VoiceNoteError
from backend.schemas.translation import (
    TranslationCreateRequest,
    TranslationResponse,
    TranslationSourceType,
)
from backend.services.translation_service import (
    TranslationService,
    TranslationSourceNotFoundError,
    TranslationValidationError,
)

router = APIRouter(prefix="/minutes", tags=["translation"])


def get_translation_service() -> TranslationService:
    """TranslationService dependency provider."""
    return TranslationService()


@router.post(
    "/{task_id}/translation",
    response_model=TranslationResponse,
    responses={
        404: {"description": "회의록 또는 요약 없음"},
        422: {"description": "번역 소스 또는 응답 검증 실패"},
    },
)
async def create_translation(
    task_id: str,
    payload: TranslationCreateRequest,
    request = Depends(get_request_context),
    db: AsyncSession = Depends(get_db_session),
    svc: TranslationService = Depends(get_translation_service),
) -> TranslationResponse:
    """Generate a translation for a persisted minutes or summary result."""
    try:
        await require_task_access(request, db, task_id)
        return await svc.translate(
            task_id,
            db,
            target_language=payload.target_language,
            source_language=payload.source_language,
            source_type=payload.source_type,
            max_tokens=payload.max_tokens,
            force_refresh=payload.force_refresh,
        )
    except TranslationSourceNotFoundError as exc:
        not_found(str(exc))
    except TranslationValidationError as exc:
        unprocessable(str(exc))
    except VoiceNoteError:
        raise
    except Exception as exc:
        internal_error(f"번역 생성 중 오류가 발생했습니다: {exc}")


@router.get(
    "/{task_id}/translation",
    response_model=TranslationResponse,
    responses={404: {"description": "번역 결과 없음"}},
)
async def get_translation(
    task_id: str,
    request = Depends(get_request_context),
    target_language: str = Query(..., min_length=2, max_length=32),
    source_type: TranslationSourceType = Query(default=TranslationSourceType.AUTO),
    db: AsyncSession = Depends(get_db_session),
    svc: TranslationService = Depends(get_translation_service),
) -> TranslationResponse:
    """Load a cached translation."""
    try:
        await require_task_access(request, db, task_id)
        return await svc.get(
            task_id,
            db,
            target_language=target_language,
            source_type=source_type,
        )
    except TranslationSourceNotFoundError as exc:
        not_found(str(exc))
