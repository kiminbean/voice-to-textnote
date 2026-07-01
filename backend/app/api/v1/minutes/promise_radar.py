"""
Cross-meeting promise radar API.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import (
    get_db_session,
    get_optional_current_user,
    require_task_access,
)
from backend.app.errors import internal_error, not_found
from backend.app.exceptions import VoiceNoteError
from backend.db.auth_models import TeamMember
from backend.schemas.promise_radar import (
    PromiseAssigneeSuggestion,
    PromiseAutopilotResponse,
    PromiseCalendarExportResponse,
    PromiseLedgerEntryResponse,
    PromiseLedgerHistoryEntry,
    PromiseLedgerMergeRequest,
    PromiseLedgerMergeResponse,
    PromiseLedgerSplitRequest,
    PromiseLedgerSplitResponse,
    PromiseLedgerUpdateRequest,
    PromiseMatchExplanation,
    PromiseNextMeetingBriefing,
    PromiseNotificationDispatchResponse,
    PromiseRadarDashboard,
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
    team_id: str | None = Query(default=None, description="팀 약속 원장 조회 범위"),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> list[PromiseLedgerEntryResponse]:
    """현재 사용자/게스트 세션의 약속 원장을 조회합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        statuses = {item.strip().lower() for item in status or [] if item.strip()}
        return await svc.list_ledger_entries(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
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
    team_id: str | None = Query(default=None, description="팀 약속 브리핑 조회 범위"),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseNextMeetingBriefing:
    """다음 회의 전에 확인할 미해결 약속 브리핑을 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_next_meeting_briefing(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"다음 회의 브리핑 생성 중 오류가 발생했습니다: {e}")


@router.get("/dashboard", response_model=PromiseRadarDashboard)
async def get_promise_dashboard(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 대시보드 조회 범위"),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseRadarDashboard:
    """홈/대시보드에서 사용할 약속 원장 요약을 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_dashboard(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 대시보드 조회 중 오류가 발생했습니다: {e}")


@router.post("/ledger/notifications/due", response_model=PromiseNotificationDispatchResponse)
async def dispatch_due_promise_notifications(
    team_id: str | None = Query(default=None, description="팀 약속 알림 발송 범위"),
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseNotificationDispatchResponse:
    """기한 또는 리마인더 시각이 지난 약속을 실제 FCM 푸시로 발송합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.dispatch_due_notifications(
            db,
            owner_id=getattr(current_user, "id", None),
            team_id=scoped_team_id,
            limit=limit,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 푸시 알림 발송 중 오류가 발생했습니다: {e}")


@router.post("/autopilot/{task_id}", response_model=PromiseAutopilotResponse)
async def run_promise_autopilot(
    task_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    apply: bool = Query(default=True, description="신뢰도 기준을 넘은 상태 변경 자동 적용"),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseAutopilotResponse:
    """현재 회의 근거로 미해결 약속의 완료/지연/변경/취소 상태를 자동 판정합니다."""
    try:
        await require_task_access(request, db, task_id)
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.run_autopilot(
            db,
            task_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            apply=apply,
            limit=limit,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 자동 판정 중 오류가 발생했습니다: {e}")


@router.patch("/ledger/{entry_id}", response_model=PromiseLedgerEntryResponse)
async def update_promise_ledger_entry(
    entry_id: str,
    payload: PromiseLedgerUpdateRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 수정 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseLedgerEntryResponse:
    """약속 원장 항목의 상태/담당자/기한/확인 여부를 수정합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        await _validate_assigned_user_scope(
            db,
            current_user,
            scoped_team_id,
            payload.assigned_user_id,
        )
        return await svc.update_ledger_entry(
            db,
            entry_id,
            payload,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 원장 수정 중 오류가 발생했습니다: {e}")


@router.get("/ledger/{entry_id}/explain", response_model=PromiseMatchExplanation)
async def explain_promise_ledger_match(
    entry_id: str,
    request: Request,
    task_id: str | None = Query(default=None, description="비교할 현재 회의 요약 task_id"),
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseMatchExplanation:
    """약속 원장 항목이 현재 회의/원문 근거와 매칭된 이유를 설명합니다."""
    try:
        if task_id:
            await require_task_access(request, db, task_id)
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.explain_ledger_entry_match(
            db,
            entry_id,
            task_id=task_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 근거 설명 생성 중 오류가 발생했습니다: {e}")


@router.post("/ledger/{entry_id}/calendar", response_model=PromiseReminderCandidate)
async def create_promise_calendar_candidate(
    entry_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseReminderCandidate:
    """약속 원장 항목에서 내부 캘린더/알림 후보를 생성합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.create_calendar_candidate(
            db,
            entry_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 캘린더 후보 생성 중 오류가 발생했습니다: {e}")


@router.post("/ledger/{entry_id}/calendar/export", response_model=PromiseCalendarExportResponse)
async def export_promise_calendar_event(
    entry_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseCalendarExportResponse:
    """약속 원장 항목을 Google Calendar URL과 ICS 이벤트로 내보냅니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.export_calendar_event(
            db,
            entry_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 캘린더 내보내기 중 오류가 발생했습니다: {e}")


@router.get(
    "/ledger/{entry_id}/assignee-suggestions",
    response_model=list[PromiseAssigneeSuggestion],
)
async def suggest_promise_assignees(
    entry_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    limit: int = Query(default=5, ge=1, le=10),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> list[PromiseAssigneeSuggestion]:
    """약속 담당자 이름/과거 지정 이력으로 팀 사용자 후보를 추천합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.suggest_assignees(
            db,
            entry_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 담당자 추천 중 오류가 발생했습니다: {e}")


@router.post("/ledger/{entry_id}/action-item", response_model=PromiseTaskLinkResponse)
async def create_promise_action_item(
    entry_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseTaskLinkResponse:
    """약속 원장 항목을 앱 내부 할 일(ActionItem)로 전환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.create_action_item(
            db,
            entry_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 할 일 생성 중 오류가 발생했습니다: {e}")


@router.post("/ledger/{entry_id}/merge", response_model=PromiseLedgerMergeResponse)
async def merge_promise_ledger_entries(
    entry_id: str,
    payload: PromiseLedgerMergeRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseLedgerMergeResponse:
    """중복 또는 같은 의미의 약속 원장 항목을 하나로 병합합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.merge_ledger_entries(
            db,
            entry_id,
            payload,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 병합 중 오류가 발생했습니다: {e}")


@router.post("/ledger/{entry_id}/split", response_model=PromiseLedgerSplitResponse)
async def split_promise_ledger_entry(
    entry_id: str,
    payload: PromiseLedgerSplitRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseLedgerSplitResponse:
    """하나의 약속 원장 항목에서 별도 약속을 분리합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.split_ledger_entry(
            db,
            entry_id,
            payload,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 분리 중 오류가 발생했습니다: {e}")


@router.get("/ledger/{entry_id}/history", response_model=list[PromiseLedgerHistoryEntry])
async def list_promise_ledger_history(
    entry_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> list[PromiseLedgerHistoryEntry]:
    """약속 원장 항목의 수정/병합/분리/알림 발송 이력을 조회합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.list_ledger_history(
            db,
            entry_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 이력 조회 중 오류가 발생했습니다: {e}")


@router.get(
    "/{task_id}",
    response_model=PromiseRadarResponse,
    responses={404: {"description": "요약 작업 없음"}},
)
async def get_promise_radar(
    task_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 동기화 범위"),
    limit: int = Query(default=30, ge=1, le=100, description="비교할 과거 요약 수"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseRadarResponse:
    """현재 회의의 약속/결정과 과거 회의의 후속 리스크를 비교합니다."""
    try:
        await require_task_access(request, db, task_id)
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_radar(
            session=db,
            task_id=task_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
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


async def _accessible_team_id(
    db: AsyncSession,
    current_user,
    team_id: str | None,
) -> uuid.UUID | None:
    if not team_id:
        return None
    user_id = getattr(current_user, "id", None)
    if user_id is None:
        not_found("팀 약속 원장은 로그인 사용자만 조회할 수 있습니다")
    user_uuid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        not_found("올바른 팀 ID가 아닙니다")
    result = await db.execute(
        select(TeamMember.id).where(
            TeamMember.team_id == team_uuid,
            TeamMember.user_id == user_uuid,
        )
    )
    if result.scalar_one_or_none() is None:
        not_found("팀 약속 원장 접근 권한이 없습니다")
    return team_uuid


async def _validate_assigned_user_scope(
    db: AsyncSession,
    current_user,
    team_id: uuid.UUID | None,
    assigned_user_id: str | None,
) -> None:
    if not assigned_user_id:
        return
    requester_id = getattr(current_user, "id", None)
    if requester_id is None:
        not_found("약속 담당자 배정은 로그인 사용자만 사용할 수 있습니다")
    requester_uuid = requester_id if isinstance(requester_id, uuid.UUID) else uuid.UUID(str(requester_id))
    try:
        assigned_uuid = uuid.UUID(assigned_user_id)
    except ValueError:
        not_found("올바른 담당 사용자 ID가 아닙니다")
    if team_id is None:
        if assigned_uuid != requester_uuid:
            not_found("개인 약속은 본인에게만 배정할 수 있습니다")
        return
    result = await db.execute(
        select(TeamMember.id).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == assigned_uuid,
        )
    )
    if result.scalar_one_or_none() is None:
        not_found("담당 사용자가 해당 팀 멤버가 아닙니다")
