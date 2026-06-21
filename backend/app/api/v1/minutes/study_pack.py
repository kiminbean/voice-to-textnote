"""Study Pack API endpoints."""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query

from backend.app.dependencies import get_redis_client
from backend.app.errors import internal_error, not_found, unprocessable
from backend.app.exceptions import VoiceNoteError
from backend.schemas.study_pack import StudyPackCreateRequest, StudyPackMode, StudyPackResponse
from backend.services.study_pack_service import (
    StudyPackService,
    StudyPackSourceNotFoundError,
    StudyPackValidationError,
)

router = APIRouter(prefix="/minutes", tags=["study-pack"])


def get_study_pack_service() -> StudyPackService:
    """StudyPackService dependency provider."""
    return StudyPackService()


@router.post(
    "/{task_id}/study-pack",
    response_model=StudyPackResponse,
    responses={
        404: {"description": "회의록 없음"},
        422: {"description": "학습팩 생성 응답 검증 실패"},
    },
)
async def create_study_pack(
    task_id: str,
    payload: StudyPackCreateRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: StudyPackService = Depends(get_study_pack_service),
) -> StudyPackResponse:
    """Generate a transcript-grounded study pack."""
    try:
        return await svc.generate(
            task_id,
            redis_client,
            mode=payload.mode,
            language=payload.language,
            max_tokens=payload.max_tokens,
            force_refresh=payload.force_refresh,
        )
    except StudyPackSourceNotFoundError as exc:
        not_found(str(exc))
    except StudyPackValidationError as exc:
        unprocessable(str(exc))
    except VoiceNoteError:
        raise
    except Exception as exc:
        internal_error(f"학습팩 생성 중 오류가 발생했습니다: {exc}")


@router.get(
    "/{task_id}/study-pack",
    response_model=StudyPackResponse,
    responses={404: {"description": "학습팩 없음"}},
)
async def get_study_pack(
    task_id: str,
    mode: StudyPackMode = Query(default=StudyPackMode.GENERAL),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: StudyPackService = Depends(get_study_pack_service),
) -> StudyPackResponse:
    """Load a cached study pack."""
    try:
        return await svc.get(task_id, redis_client, mode=mode)
    except StudyPackSourceNotFoundError as exc:
        not_found(str(exc))
