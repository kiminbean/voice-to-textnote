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
from backend.schemas.promise_radar import (
    PromiseLedgerEntryResponse,
    PromiseLedgerUpdateRequest,
    PromiseNextMeetingBriefing,
    PromiseRadarResponse,
    PromiseReminderCandidate,
    PromiseTaskLinkResponse,
)
from backend.services.promise_radar_service import PromiseRadarService

router = APIRouter(prefix="/promise-radar", tags=["promise-radar"])


def get_promise_radar_service() -> PromiseRadarService:
    return PromiseRadarService()


@router.get("/ledger", response_model=list[PromiseLedgerEntryResponse])
async def list_promise_ledger(
    request: Request,
    status: list[str] | None = Query(default=None, description="필터링할 약속 상태"),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> list[PromiseLedgerEntryResponse]:
    """현재 사용자/게스트 세션의 약속 원장을 조회합니다."""
    try:
        statuses = {item.strip().lower() for item in status or [] if item.strip()}
        return await svc.list_ledger_entries(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            statuses=statuses or None,
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 원장 조회 중 오류가 발생했습니다: {e}")


@router.get("/briefing/next", response_model=PromiseNextMeetingBriefing)
async def get_next_meeting_briefing(
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseNextMeetingBriefing:
    """다음 회의 전에 확인할 미해결 약속 브리핑을 반환합니다."""
    try:
        return await svc.build_next_meeting_briefing(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"다음 회의 브리핑 생성 중 오류가 발생했습니다: {e}")


@router.patch("/ledger/{entry_id}", response_model=PromiseLedgerEntryResponse)
async def update_promise_ledger_entry(
    entry_id: str,
    payload: PromiseLedgerUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseLedgerEntryResponse:
    """약속 원장 항목의 상태/담당자/기한/확인 여부를 수정합니다."""
    try:
        return await svc.update_ledger_entry(
            db,
            entry_id,
            payload,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 원장 수정 중 오류가 발생했습니다: {e}")


@router.post("/ledger/{entry_id}/calendar", response_model=PromiseReminderCandidate)
async def create_promise_calendar_candidate(
    entry_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseReminderCandidate:
    """약속 원장 항목에서 내부 캘린더/알림 후보를 생성합니다."""
    try:
        return await svc.create_calendar_candidate(
            db,
            entry_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 캘린더 후보 생성 중 오류가 발생했습니다: {e}")


@router.post("/ledger/{entry_id}/action-item", response_model=PromiseTaskLinkResponse)
async def create_promise_action_item(
    entry_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseTaskLinkResponse:
    """약속 원장 항목을 앱 내부 할 일(ActionItem)로 전환합니다."""
    try:
        return await svc.create_action_item(
            db,
            entry_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 할 일 생성 중 오류가 발생했습니다: {e}")


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
