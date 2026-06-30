"""
Cross-meeting promise radar API.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import (
    get_db_session,
    get_optional_current_user,
    require_task_access,
)
from backend.app.errors import internal_error, not_found
from backend.app.exceptions import VoiceNoteError
from backend.schemas.promise_radar import PromiseRadarResponse
from backend.services.promise_radar_service import PromiseRadarService

router = APIRouter(prefix="/promise-radar", tags=["promise-radar"])


def get_promise_radar_service() -> PromiseRadarService:
    return PromiseRadarService()


@router.get(
    "/{task_id}",
    response_model=PromiseRadarResponse,
    responses={404: {"description": "요약 작업 없음"}},
)
async def get_promise_radar(
    task_id: str,
    request: Request,
    limit: int = Query(default=30, ge=1, le=100, description="비교할 과거 요약 수"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseRadarResponse:
    """현재 회의의 약속/결정과 과거 회의의 후속 리스크를 비교합니다."""
    try:
        await require_task_access(request, db, task_id)
        return await svc.build_radar(
            session=db,
            task_id=task_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            limit=limit,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 레이더 생성 중 오류가 발생했습니다: {e}")


def _guest_session_id(request: Request) -> str | None:
    if getattr(request.state, "is_guest", False) is not True:
        return None
    value = getattr(request.state, "guest_session_id", None)
    return str(value) if value else None
