"""
Cross-meeting promise radar API.
"""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import (
    get_db_session,
    get_optional_current_user,
    require_task_access,
)
from backend.app.errors import forbidden, internal_error, not_found
from backend.app.exceptions import VoiceNoteError
from backend.db.auth_models import TeamMember
from backend.schemas.promise_radar import (
    PromiseAccuracyCase,
    PromiseAccuracyEvaluation,
    PromiseAccuracyReport,
    PromiseAssigneeSuggestion,
    PromiseAutomationPolicy,
    PromiseAutomationPolicyUpdateRequest,
    PromiseAutopilotAssessment,
    PromiseAutopilotConfirmRequest,
    PromiseAutopilotRejectRequest,
    PromiseAutopilotResponse,
    PromiseAutopilotReviewQueue,
    PromiseCalendarExportResponse,
    PromiseCommandCenter,
    PromiseConflictResolveRequest,
    PromiseDigest,
    PromiseDigestPreference,
    PromiseDigestPreferenceUpdateRequest,
    PromiseEvidenceComparison,
    PromiseEvidencePack,
    PromiseExternalExportRequest,
    PromiseExternalExportResponse,
    PromiseExternalTaskReconcileResponse,
    PromiseExternalTaskSyncRequest,
    PromiseExternalTaskSyncResponse,
    PromiseExternalTaskUpdateRequest,
    PromiseExtractionCase,
    PromiseExtractionRecallReport,
    PromiseGoogleTaskListResponse,
    PromiseLearningFeedbackRequest,
    PromiseLearningFeedbackResponse,
    PromiseLearningInsight,
    PromiseLearningProfile,
    PromiseLedgerEntryResponse,
    PromiseLedgerHistoryEntry,
    PromiseLedgerMergeRequest,
    PromiseLedgerMergeResponse,
    PromiseLedgerSplitRequest,
    PromiseLedgerSplitResponse,
    PromiseLedgerUpdateRequest,
    PromiseMatchExplanation,
    PromiseMeetingSeries,
    PromiseMeetingSeriesTimeline,
    PromiseNextMeetingBriefing,
    PromiseNotificationDispatchResponse,
    PromisePreMeetingBrief,
    PromiseRadarDashboard,
    PromiseRadarResponse,
    PromiseReminderCandidate,
    PromiseResponsibilityScore,
    PromiseResponsibilityTrend,
    PromiseTaskLinkResponse,
    PromiseTimelineResponse,
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


@router.get("/briefing/pre-meeting", response_model=PromisePreMeetingBrief)
async def get_pre_meeting_promise_brief(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 브리핑 조회 범위"),
    limit: int = Query(default=8, ge=1, le=30),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromisePreMeetingBrief:
    """녹음 시작 전 확인할 약속 3~8개와 질문을 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_pre_meeting_brief(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"회의 시작 전 약속 브리프 생성 중 오류가 발생했습니다: {e}")


@router.get("/digest", response_model=PromiseDigest)
async def get_promise_digest(
    request: Request,
    cadence: str = Query(default="daily", description="daily 또는 weekly"),
    team_id: str | None = Query(default=None, description="팀 약속 digest 조회 범위"),
    limit: int = Query(default=12, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseDigest:
    """개인/팀별 오늘 또는 이번 주 약속 요약을 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_digest(
            db,
            cadence=cadence,
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
        internal_error(f"약속 digest 생성 중 오류가 발생했습니다: {e}")


@router.get("/learning-profile", response_model=PromiseLearningProfile)
async def get_promise_learning_profile(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 학습 프로필 조회 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseLearningProfile:
    """사용자 수정 이력으로 계산한 Promise Radar 학습 프로필을 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.learning_profile(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 학습 프로필 조회 중 오류가 발생했습니다: {e}")


@router.get("/learning-insights", response_model=PromiseLearningInsight)
async def get_promise_learning_insights(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 학습 인사이트 조회 범위"),
    limit: int = Query(default=200, ge=10, le=500),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseLearningInsight:
    """사용자 피드백 기반의 운영 인사이트와 다음 조치 권장값을 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_learning_insights(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 학습 인사이트 조회 중 오류가 발생했습니다: {e}")


@router.get("/automation-policy", response_model=PromiseAutomationPolicy)
async def get_promise_automation_policy(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 자동화 정책 조회 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseAutomationPolicy:
    """팀/사용자별 Promise Radar 자동화 정책을 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.get_automation_policy(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 자동화 정책 조회 중 오류가 발생했습니다: {e}")


@router.put("/automation-policy", response_model=PromiseAutomationPolicy)
async def update_promise_automation_policy(
    payload: PromiseAutomationPolicyUpdateRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 자동화 정책 저장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseAutomationPolicy:
    """팀/사용자별 Promise Radar 자동화 정책을 저장합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        await _require_team_policy_admin(db, current_user, scoped_team_id)
        return await svc.update_automation_policy(
            db,
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
        internal_error(f"약속 자동화 정책 저장 중 오류가 발생했습니다: {e}")


@router.get("/digest-preference", response_model=PromiseDigestPreference)
async def get_promise_digest_preference(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 digest 설정 조회 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseDigestPreference:
    """예약 digest push 설정을 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.get_digest_preference(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 digest 설정 조회 중 오류가 발생했습니다: {e}")


@router.put("/digest-preference", response_model=PromiseDigestPreference)
async def update_promise_digest_preference(
    payload: PromiseDigestPreferenceUpdateRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 digest 설정 저장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseDigestPreference:
    """예약 digest push 설정을 저장합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.update_digest_preference(
            db,
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
        internal_error(f"약속 digest 설정 저장 중 오류가 발생했습니다: {e}")


@router.post("/accuracy/evaluate", response_model=PromiseAccuracyEvaluation)
async def evaluate_promise_accuracy(
    cases: list[PromiseAccuracyCase],
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseAccuracyEvaluation:
    """라벨링된 회의 fixture로 Promise Radar 자동 판정 정확도를 계산합니다."""
    return svc.evaluate_accuracy_cases(cases)


@router.get("/accuracy/report", response_model=PromiseAccuracyReport)
async def get_promise_accuracy_report(
    target_case_count: int = Query(default=100, ge=1, le=1000),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseAccuracyReport:
    """서버에 고정된 Promise Radar fixture 정확도와 실제 회의 label 수를 반환합니다."""
    try:
        backend_root = Path(__file__).resolve().parents[4]
        fixture = backend_root / "tests" / "fixtures" / "promise_radar_accuracy_cases.json"
        source_manifest = (
            backend_root / "tests" / "fixtures" / "promise_radar_real_meeting_sources.json"
        )
        raw_cases = json.loads(fixture.read_text(encoding="utf-8"))
        cases = [PromiseAccuracyCase(**item) for item in raw_cases]
        return svc.build_accuracy_report(
            cases,
            fixture_path=str(fixture),
            source_manifest_path=str(source_manifest) if source_manifest.exists() else None,
            target_case_count=target_case_count,
        )
    except FileNotFoundError as e:
        not_found(f"Promise Radar fixture 파일을 찾을 수 없습니다: {e}")
    except ValueError as e:
        not_found(str(e))
    except Exception as e:
        internal_error(f"Promise Radar 정확도 보고서 생성 중 오류가 발생했습니다: {e}")


@router.get("/accuracy/extraction-report", response_model=PromiseExtractionRecallReport)
async def get_promise_extraction_recall_report(
    target_case_count: int = Query(default=50, ge=1, le=1000),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseExtractionRecallReport:
    """약속 추출 false negative fixture recall을 반환합니다."""
    try:
        backend_root = Path(__file__).resolve().parents[4]
        fixture = backend_root / "tests" / "fixtures" / "promise_radar_extraction_cases.json"
        raw_cases = json.loads(fixture.read_text(encoding="utf-8"))
        cases = [PromiseExtractionCase(**item) for item in raw_cases]
        return svc.build_extraction_recall_report(
            cases,
            fixture_path=str(fixture),
            target_case_count=target_case_count,
        )
    except FileNotFoundError as e:
        not_found(f"Promise Radar extraction fixture 파일을 찾을 수 없습니다: {e}")
    except ValueError as e:
        not_found(str(e))
    except Exception as e:
        internal_error(f"Promise Radar extraction recall 보고서 생성 중 오류가 발생했습니다: {e}")


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


@router.get("/command-center", response_model=PromiseCommandCenter)
async def get_promise_command_center(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 운영 범위"),
    limit: int = Query(default=50, ge=1, le=200),
    target_case_count: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseCommandCenter:
    """Promise Radar 운영자 화면에 필요한 review/learning/sync/evidence 상태를 모읍니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_command_center(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
            target_case_count=target_case_count,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 Command Center 생성 중 오류가 발생했습니다: {e}")


@router.get("/responsibility-scores", response_model=list[PromiseResponsibilityScore])
async def get_promise_responsibility_scores(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 책임 점수 조회 범위"),
    limit: int = Query(default=100, ge=1, le=250),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> list[PromiseResponsibilityScore]:
    """담당자별 미해결/지연/기한초과 약속 책임 점수를 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_responsibility_scores(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 책임 점수 조회 중 오류가 발생했습니다: {e}")


@router.get("/responsibility-trends", response_model=list[PromiseResponsibilityTrend])
async def get_promise_responsibility_trends(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 책임 점수 추세 조회 범위"),
    limit: int = Query(default=250, ge=1, le=250),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> list[PromiseResponsibilityTrend]:
    """담당자별 책임 점수의 최근 추세를 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_responsibility_trends(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 책임 점수 추세 조회 중 오류가 발생했습니다: {e}")


@router.get("/meeting-series", response_model=list[PromiseMeetingSeries])
async def get_promise_meeting_series(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 반복회의 조회 범위"),
    limit: int = Query(default=100, ge=1, le=250),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> list[PromiseMeetingSeries]:
    """기존 약속 원장을 기반으로 반복회의 묶음과 확인 질문을 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_meeting_series(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"반복회의 약속 묶음 조회 중 오류가 발생했습니다: {e}")


@router.get("/meeting-series/{series_key}/timeline", response_model=PromiseMeetingSeriesTimeline)
async def get_promise_meeting_series_timeline(
    series_key: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 반복회의 timeline 조회 범위"),
    limit: int = Query(default=250, ge=1, le=250),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseMeetingSeriesTimeline:
    """반복회의 묶음 안에서 약속이 등장/지연/반복된 흐름을 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_meeting_series_timeline(
            db,
            series_key,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"반복회의 timeline 조회 중 오류가 발생했습니다: {e}")


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


@router.post("/ledger/notifications/digest", response_model=PromiseNotificationDispatchResponse)
async def dispatch_digest_promise_notifications(
    team_id: str | None = Query(default=None, description="팀 digest 알림 발송 범위"),
    cadence: str = Query(default="daily", description="daily 또는 weekly"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseNotificationDispatchResponse:
    """오늘/이번 주 확인할 약속 digest를 실제 FCM 푸시로 발송합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.dispatch_digest_notifications(
            db,
            cadence=cadence,
            owner_id=getattr(current_user, "id", None),
            team_id=scoped_team_id,
            limit=limit,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 digest 푸시 알림 발송 중 오류가 발생했습니다: {e}")


@router.post(
    "/briefing/pre-meeting/notifications",
    response_model=PromiseNotificationDispatchResponse,
)
async def dispatch_pre_meeting_brief_notifications(
    team_id: str | None = Query(default=None, description="팀 회의 전 브리프 발송 범위"),
    limit: int = Query(default=8, ge=1, le=30),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseNotificationDispatchResponse:
    """회의 전 확인할 약속 브리프를 실제 FCM 푸시로 발송합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.dispatch_pre_meeting_brief_notifications(
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
        internal_error(f"회의 전 약속 브리프 푸시 발송 중 오류가 발생했습니다: {e}")


@router.get("/autopilot/review-inbox", response_model=PromiseAutopilotReviewQueue)
async def get_promise_autopilot_review_inbox(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 Review Inbox 조회 범위"),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseAutopilotReviewQueue:
    """회의별 결과 화면과 독립된 전역 Autopilot Review Inbox를 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_autopilot_review_inbox(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 자동 판정 Review Inbox 조회 중 오류가 발생했습니다: {e}")


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


@router.post("/autopilot/{task_id}/preview", response_model=PromiseAutopilotResponse)
async def preview_promise_autopilot(
    task_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseAutopilotResponse:
    """상태를 바꾸지 않고 자동 판정 후보와 근거를 미리보기로 반환합니다."""
    try:
        await require_task_access(request, db, task_id)
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.run_autopilot(
            db,
            task_id,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            apply=False,
            limit=limit,
        )
    except ValueError as e:
        not_found(str(e))
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"약속 자동 판정 미리보기 중 오류가 발생했습니다: {e}")


@router.get("/autopilot/{task_id}/review-queue", response_model=PromiseAutopilotReviewQueue)
async def get_promise_autopilot_review_queue(
    task_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseAutopilotReviewQueue:
    """확정 대기 중인 자동 판정 후보를 한 화면에서 검토할 queue로 반환합니다."""
    try:
        await require_task_access(request, db, task_id)
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_autopilot_review_queue(
            db,
            task_id,
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
        internal_error(f"약속 자동 판정 review queue 생성 중 오류가 발생했습니다: {e}")


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


@router.get("/ledger/{entry_id}/evidence-pack", response_model=PromiseEvidencePack)
async def get_promise_latest_evidence_pack(
    entry_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseEvidencePack:
    """약속 원장 항목의 최신 Autopilot Evidence Pack을 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.latest_evidence_pack(
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
        internal_error(f"약속 Evidence Pack 조회 중 오류가 발생했습니다: {e}")


@router.get("/ledger/{entry_id}/evidence-comparison", response_model=PromiseEvidenceComparison)
async def compare_promise_evidence(
    entry_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseEvidenceComparison:
    """저장된 원장 근거와 최신 Evidence Pack을 비교합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.evidence_comparison(
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
        internal_error(f"약속 Evidence 비교 중 오류가 발생했습니다: {e}")


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


@router.post("/ledger/{entry_id}/autopilot-confirm", response_model=PromiseAutopilotAssessment)
async def confirm_promise_autopilot_assessment(
    entry_id: str,
    payload: PromiseAutopilotConfirmRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseAutopilotAssessment:
    """미리보기로 제안된 자동 판정을 사용자가 확인한 뒤 원장에 적용합니다."""
    try:
        await require_task_access(request, db, payload.task_id)
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.confirm_autopilot_assessment(
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
        internal_error(f"약속 자동 판정 확정 중 오류가 발생했습니다: {e}")


@router.post(
    "/ledger/{entry_id}/autopilot-reject",
    response_model=PromiseLearningFeedbackResponse,
)
async def reject_promise_autopilot_review_item(
    entry_id: str,
    payload: PromiseAutopilotRejectRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseLearningFeedbackResponse:
    """Review Queue 후보를 거절하고 다음 queue에서 제외되도록 저장합니다."""
    try:
        await require_task_access(request, db, payload.task_id)
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.reject_autopilot_review_item(
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
        internal_error(f"약속 자동 판정 거절 중 오류가 발생했습니다: {e}")


@router.post("/ledger/{entry_id}/resolve-conflict", response_model=PromiseLedgerEntryResponse)
async def resolve_promise_autopilot_conflict(
    entry_id: str,
    payload: PromiseConflictResolveRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseLedgerEntryResponse:
    """충돌 감지된 약속 판정을 사용자가 선택한 상태로 해결합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.resolve_autopilot_conflict(
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
        internal_error(f"약속 충돌 해결 중 오류가 발생했습니다: {e}")


@router.post("/ledger/{entry_id}/learning-feedback", response_model=PromiseLearningFeedbackResponse)
async def record_promise_learning_feedback(
    entry_id: str,
    payload: PromiseLearningFeedbackRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseLearningFeedbackResponse:
    """사용자의 자동 판정/담당자/병합/분리 수정 피드백을 학습 이벤트로 저장합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.record_learning_feedback(
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
        internal_error(f"약속 학습 피드백 저장 중 오류가 발생했습니다: {e}")


@router.get("/ledger/{entry_id}/timeline", response_model=PromiseTimelineResponse)
async def get_promise_ledger_timeline(
    entry_id: str,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseTimelineResponse:
    """약속의 감지/반복/지연/자동 판정/사용자 확정 흐름을 timeline으로 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_ledger_timeline(
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
        internal_error(f"약속 timeline 조회 중 오류가 발생했습니다: {e}")


@router.post("/ledger/{entry_id}/external-task", response_model=PromiseExternalExportResponse)
async def export_promise_external_task(
    entry_id: str,
    payload: PromiseExternalExportRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseExternalExportResponse:
    """약속을 Slack 업무 메시지로 내보냅니다. 기본값은 dry-run payload 생성입니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.export_external_task(
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
        internal_error(f"약속 외부 업무도구 연동 중 오류가 발생했습니다: {e}")


@router.post("/external-task/google-tasklists", response_model=PromiseGoogleTaskListResponse)
async def list_google_tasklists(
    payload: PromiseExternalExportRequest,
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseGoogleTaskListResponse:
    """Google Tasks OAuth token으로 tasklist 목록을 조회합니다."""
    try:
        return await svc.list_google_tasklists(payload)
    except ValueError as e:
        not_found(str(e))
    except Exception as e:
        internal_error(f"Google Tasks tasklist 조회 중 오류가 발생했습니다: {e}")


@router.get("/external-task/reconcile", response_model=PromiseExternalTaskReconcileResponse)
async def reconcile_promise_external_tasks(
    request: Request,
    team_id: str | None = Query(default=None, description="팀 외부 업무도구 재조정 범위"),
    limit: int = Query(default=100, ge=1, le=250),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseExternalTaskReconcileResponse:
    """Google Tasks와 Promise Ledger의 연결 상태와 재동기화 후보를 반환합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.build_external_task_reconcile_report(
            db,
            owner_id=getattr(current_user, "id", None),
            guest_session_id=_guest_session_id(request),
            team_id=scoped_team_id,
            limit=limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        internal_error(f"외부 업무도구 재조정 리포트 생성 중 오류가 발생했습니다: {e}")


@router.post(
    "/ledger/{entry_id}/external-task/sync",
    response_model=PromiseExternalTaskSyncResponse,
)
async def sync_promise_external_task(
    entry_id: str,
    payload: PromiseExternalTaskSyncRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseExternalTaskSyncResponse:
    """외부 업무도구 task 상태를 약속 원장으로 동기화합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.sync_external_task(
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
        internal_error(f"외부 업무도구 동기화 중 오류가 발생했습니다: {e}")


@router.post(
    "/ledger/{entry_id}/external-task/update",
    response_model=PromiseExternalTaskSyncResponse,
)
async def update_promise_external_task(
    entry_id: str,
    payload: PromiseExternalTaskUpdateRequest,
    request: Request,
    team_id: str | None = Query(default=None, description="팀 약속 원장 범위"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: PromiseRadarService = Depends(get_promise_radar_service),
) -> PromiseExternalTaskSyncResponse:
    """약속 원장의 현재 상태를 외부 업무도구 task로 반영합니다."""
    try:
        scoped_team_id = await _accessible_team_id(db, current_user, team_id)
        return await svc.update_external_task(
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
        internal_error(f"외부 업무도구 업데이트 중 오류가 발생했습니다: {e}")


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


async def _require_team_policy_admin(
    db: AsyncSession,
    current_user,
    team_id: uuid.UUID | None,
) -> None:
    if team_id is None:
        return
    user_id = getattr(current_user, "id", None)
    if user_id is None:
        forbidden("팀 자동화 정책 변경은 로그인 사용자가 필요합니다")
    user_uuid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
    result = await db.execute(
        select(TeamMember.role).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_uuid,
        )
    )
    role = result.scalar_one_or_none()
    if role != "admin":
        forbidden("팀 자동화 정책은 팀 관리자만 변경할 수 있습니다")


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
    requester_uuid = (
        requester_id if isinstance(requester_id, uuid.UUID) else uuid.UUID(str(requester_id))
    )
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
