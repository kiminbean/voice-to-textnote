"""
Cross-meeting promise radar service.

The first implementation is intentionally deterministic: it compares persisted
summary action_items/key_decisions across a user's previous meetings before any
LLM embellishment. That keeps the feature useful even when the model provider is
temporarily unavailable.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.metrics import (
    record_promise_radar_autopilot,
    record_promise_radar_build,
    record_promise_radar_external_sync,
    record_promise_radar_notification,
    record_promise_radar_review_queue,
)
from backend.db.auth_models import MeetingOwnership, TeamMember, User
from backend.db.device_token_models import DeviceToken
from backend.db.models import ActionItem, TaskResult
from backend.db.promise_ledger_models import PromiseLedgerEntry, PromiseLedgerEvent
from backend.ml.zai_client import AsyncZAIClient, structured_json_completion_options
from backend.schemas.promise_radar import (
    PromiseAccuracyCase,
    PromiseAccuracyEvaluation,
    PromiseAccuracyReport,
    PromiseAssigneeSuggestion,
    PromiseAutomationPolicy,
    PromiseAutomationPolicyUpdateRequest,
    PromiseAutopilotAssessment,
    PromiseAutopilotConfirmRequest,
    PromiseAutopilotQuarantineSummary,
    PromiseAutopilotRejectRequest,
    PromiseAutopilotResponse,
    PromiseAutopilotReviewItem,
    PromiseAutopilotReviewQueue,
    PromiseAutopilotShadowSummary,
    PromiseAutopilotUndoRequest,
    PromiseAutopilotUndoResponse,
    PromiseCalendarExportResponse,
    PromiseCommandCenter,
    PromiseCommandCenterAction,
    PromiseCommandCenterFocusItem,
    PromiseConflictResolveRequest,
    PromiseDigest,
    PromiseDigestPreference,
    PromiseDigestPreferenceUpdateRequest,
    PromiseEvidenceAuditSummary,
    PromiseEvidenceComparison,
    PromiseEvidencePack,
    PromiseEvidencePermissionSummary,
    PromiseEvidenceRoomLinkRequest,
    PromiseEvidenceRoomLinkResponse,
    PromiseEvidenceRoomSummary,
    PromiseExternalExportRequest,
    PromiseExternalExportResponse,
    PromiseExternalTaskReconcileItem,
    PromiseExternalTaskReconcileResponse,
    PromiseExternalTaskSyncRequest,
    PromiseExternalTaskSyncResponse,
    PromiseExternalTaskUpdateRequest,
    PromiseExtractionCase,
    PromiseExtractionRecallEvaluation,
    PromiseExtractionRecallReport,
    PromiseGoogleTaskList,
    PromiseGoogleTaskListResponse,
    PromiseGoogleTasksOAuthGuide,
    PromiseGoogleTasksOAuthStartRequest,
    PromiseGoogleTasksOAuthStartResponse,
    PromiseLearningFeedbackRequest,
    PromiseLearningFeedbackResponse,
    PromiseLearningInsight,
    PromiseLearningProfile,
    PromiseLearningTelemetryReport,
    PromiseLearningTelemetrySegment,
    PromiseLedgerEntryResponse,
    PromiseLedgerHistoryEntry,
    PromiseLedgerMergeRequest,
    PromiseLedgerMergeResponse,
    PromiseLedgerSplitRequest,
    PromiseLedgerSplitResponse,
    PromiseLedgerUpdateRequest,
    PromiseLiveCoachPrompt,
    PromiseLiveCoachSummary,
    PromiseMatchExplanation,
    PromiseMeetingRecipePolicy,
    PromiseMeetingSeries,
    PromiseMeetingSeriesTimeline,
    PromiseMeetingSeriesTimelineItem,
    PromiseMemoryGraph,
    PromiseMemoryGraphEdge,
    PromiseMemoryGraphNode,
    PromiseNextMeetingBriefing,
    PromiseNotificationDispatchResponse,
    PromiseOwnerAlias,
    PromisePreMeetingBrief,
    PromiseQualityScore,
    PromiseRadarCarryOver,
    PromiseRadarChainLink,
    PromiseRadarDashboard,
    PromiseRadarDecisionDrift,
    PromiseRadarEvidence,
    PromiseRadarOwnerRisk,
    PromiseRadarPromise,
    PromiseRadarPromiseChain,
    PromiseRadarResponse,
    PromiseReminderCandidate,
    PromiseResponsibilityScore,
    PromiseResponsibilityTrend,
    PromiseResponsibilityTrendPoint,
    PromiseTaskLinkResponse,
    PromiseTeamScorecard,
    PromiseTimelineItem,
    PromiseTimelineResponse,
)
from backend.services.push_service import PushService, get_push_service

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
_STOPWORDS = {
    "그리고",
    "그래서",
    "이번",
    "다음",
    "회의",
    "진행",
    "하기",
    "관련",
    "대한",
    "대해",
    "것",
    "수",
    "및",
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
}
_SYNONYM_MAP = {
    "qa": "검증",
    "테스트": "검증",
    "검수": "검증",
    "체크": "확인",
    "확인": "확인",
    "점검": "확인",
    "마무리": "완료",
    "완료": "완료",
    "종료": "완료",
    "작성": "작성",
    "초안": "작성",
    "정리": "작성",
    "릴리즈": "배포",
    "릴리스": "배포",
    "배포": "배포",
    "서버": "백엔드",
    "백엔드": "백엔드",
    "api": "api",
    "url": "url",
    "주소": "url",
    "도메인": "url",
    "ip": "url",
    "푸시": "알림",
    "알림": "알림",
}
_KOREAN_TOKEN_SUFFIXES = (
    "까지",
    "부터",
    "에서",
    "에게",
    "으로",
    "로",
    "을",
    "를",
    "은",
    "는",
    "이",
    "가",
    "님",
)
_WEEKDAY_TO_INDEX = {
    "월": 0,
    "화": 1,
    "수": 2,
    "목": 3,
    "금": 4,
    "토": 5,
    "일": 6,
}

_OPEN_LEDGER_STATUSES = {"open", "delegated", "blocked", "delayed", "changed"}
_CLOSED_LEDGER_STATUSES = {"completed", "dismissed"}
_VALID_LEDGER_STATUSES = _OPEN_LEDGER_STATUSES | _CLOSED_LEDGER_STATUSES
_AUTOPILOT_APPLY_THRESHOLD = 0.68
_EVIDENCE_LOCK_MIN_SIMILARITY = 0.24
_EVIDENCE_LOCK_MIN_FACTORS = 2
_EVIDENCE_LOCK_MIN_TOKENS = 4
_EVIDENCE_LOCK_MIN_CHARS = 18
_AUTOMATION_POLICY_MODES = {"safe_auto", "preview_only", "completed_only", "manual_only"}
_AUTOMATION_POLICY_DEFAULT_ALLOWED = {"completed", "delayed", "changed", "dismissed"}
_AUTOPILOT_MARKERS = {
    "completed": (
        "완료",
        "끝냈",
        "끝났",
        "처리",
        "해결",
        "반영했",
        "반영 완료",
        "배포했",
        "done",
        "completed",
        "finished",
        "resolved",
        "approved",
        "approve",
        "adopted",
        "adopt",
        "accepted",
        "확인했",
        "확인 완료",
        "pass",
        "so ordered",
        "all in favor",
        "place it on file",
    ),
    "delayed": (
        "아직",
        "못 했",
        "못했",
        "지연",
        "미뤘",
        "연기",
        "다음 회의",
        "다음 주로",
        "blocked",
        "delayed",
        "later",
        "postpone",
    ),
    "changed": (
        "변경",
        "바꾸",
        "로 전환",
        "으로 전환",
        "대신",
        "재조정",
        "범위 조정",
        "우선순위 변경",
        "changed",
        "rescheduled",
        "add item",
        "new format",
        "accountable",
    ),
    "dismissed": (
        "취소",
        "중단",
        "폐기",
        "안 하기로",
        "필요 없",
        "보류 해제",
        "drop",
        "cancel",
        "dismiss",
    ),
}
_QUALITY_COMPLETION_TERMS = (
    "완료 기준",
    "검증",
    "테스트",
    "확인",
    "배포",
    "리뷰",
    "공유",
    "전달",
    "측정",
)
_QUALITY_ACTION_TERMS = (
    "작성",
    "확인",
    "수정",
    "배포",
    "테스트",
    "검증",
    "공유",
    "연결",
    "적용",
    "정리",
    "마무리",
    "완료",
)


@dataclass(frozen=True)
class _ExtractedPromise:
    text: str
    owner: str | None
    due_date: str | None
    priority: str
    source_task_id: str
    source_created_at: str
    evidence: str
    confidence: float = 0.72

    def to_schema(self) -> PromiseRadarPromise:
        return PromiseRadarPromise(
            text=self.text,
            owner=self.owner,
            due_date=self.due_date,
            priority=self.priority,
            source_task_id=self.source_task_id,
            source_created_at=self.source_created_at,
            evidence=self.evidence,
            confidence=self.confidence,
        )


@dataclass(frozen=True)
class _SemanticPromise:
    """LLM-normalized promise metadata used to improve ledger matching."""

    text: str
    canonical_text: str
    owner: str | None = None
    due_date: str | None = None
    confidence: float = 0.0


class PromiseRadarService:
    """Builds a cross-meeting promise/decision continuity brief."""

    async def build_radar(
        self,
        session: AsyncSession,
        task_id: str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 30,
    ) -> PromiseRadarResponse:
        current = await self._get_record(session, task_id)
        if current is None:
            record_promise_radar_build("not_found", 0)
            raise ValueError("회의 요약을 찾을 수 없습니다")

        if (
            owner_id is None
            and not guest_session_id
            and team_id is None
            and current.is_guest
            and current.guest_session_id
        ):
            guest_session_id = current.guest_session_id

        previous = await self._load_previous_summaries(
            session=session,
            current=current,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        response = self.analyze_records(current, previous)
        semantic_promises, semantic_status = await self._semantic_promises(current)
        response.semantic_enrichment_status = semantic_status

        if owner_id is not None or guest_session_id or team_id is not None:
            ledger_entries = await self._sync_ledger(
                session=session,
                current=current,
                response=response,
                owner_id=owner_id,
                guest_session_id=guest_session_id,
                team_id=team_id,
                semantic_promises=semantic_promises,
            )
            response.ledger_entries = ledger_entries
            response.next_meeting_briefing = self._build_next_meeting_briefing(ledger_entries)
            await session.commit()

        record_promise_radar_build(
            "success",
            len(response.ledger_entries or response.current_promises),
        )
        return response

    async def list_ledger_entries(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        statuses: set[str] | None = None,
        limit: int = 50,
    ) -> list[PromiseLedgerEntryResponse]:
        """List scoped ledger entries for the current user or guest session."""
        entries = await self._list_ledger_entry_models(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            statuses=statuses,
            limit=limit,
        )
        return [self._entry_to_response(entry) for entry in entries]

    async def _list_ledger_entry_models(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        statuses: set[str] | None = None,
        limit: int = 100,
    ) -> list[PromiseLedgerEntry]:
        stmt = select(PromiseLedgerEntry).where(
            self._ledger_scope_condition(owner_id, guest_session_id, team_id=team_id)
        )
        if statuses:
            stmt = stmt.where(PromiseLedgerEntry.status.in_(statuses))
        stmt = stmt.order_by(
            PromiseLedgerEntry.risk_level.desc(),
            PromiseLedgerEntry.due_at.is_(None),
            PromiseLedgerEntry.due_at.asc(),
            PromiseLedgerEntry.last_seen_at.desc(),
        ).limit(max(1, min(limit, 250)))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def build_next_meeting_briefing(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 30,
    ) -> PromiseNextMeetingBriefing:
        """Build a pre-meeting brief from unresolved ledger entries."""
        entries = await self.list_ledger_entries(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            statuses=_OPEN_LEDGER_STATUSES,
            limit=limit,
        )
        briefing = self._build_next_meeting_briefing(entries)
        briefing.responsibility_scores = await self.build_responsibility_scores(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        briefing.meeting_series = await self.build_meeting_series(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        return briefing

    async def update_ledger_entry(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseLedgerUpdateRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseLedgerEntryResponse:
        """Apply a user correction to a ledger item."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")

        old_value = self._ledger_snapshot(entry)

        if payload.text is not None:
            text = payload.text.strip()
            if text:
                entry.text = text
                entry.canonical_text = text
                entry.canonical_key = self._canonical_key(text)
        if payload.status is not None:
            status = payload.status.strip().lower()
            if status not in _VALID_LEDGER_STATUSES:
                raise ValueError("지원하지 않는 약속 상태입니다")
            entry.status = status
            entry.completed_at = (
                datetime.now(UTC).replace(tzinfo=None) if status == "completed" else None
            )

        if payload.owner is not None:
            entry.owner_name = payload.owner.strip() or None
        if payload.priority is not None:
            entry.priority = payload.priority.strip().lower() or entry.priority
        if payload.team_id is not None:
            requested_team_id = self._coerce_uuid(payload.team_id)
            scoped_team_id = self._coerce_uuid(team_id)
            if requested_team_id != scoped_team_id:
                raise ValueError("검증된 팀 범위와 요청 팀 ID가 일치하지 않습니다")
            entry.team_id = requested_team_id
        if payload.assigned_user_id is not None:
            entry.assigned_user_id = self._coerce_uuid(payload.assigned_user_id)
        if payload.due_date is not None:
            entry.due_date_text = payload.due_date.strip() or None
            entry.due_at = payload.due_at or self._parse_due_at(
                entry.due_date_text, entry.last_seen_at
            )
            entry.notification_sent_at = None
        elif payload.due_at is not None:
            entry.due_at = payload.due_at.replace(tzinfo=None)
            entry.notification_sent_at = None
        if payload.reminder_at is not None:
            entry.reminder_at = payload.reminder_at.replace(tzinfo=None)
            entry.notification_sent_at = None
        if payload.user_confirmed is not None:
            entry.user_confirmed = payload.user_confirmed
        if payload.dismissed_reason is not None:
            entry.dismissed_reason = payload.dismissed_reason.strip() or None

        entry.risk_level = self._ledger_risk_level(entry.priority, entry.due_at, entry.occurrences)
        entry.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._record_ledger_event(
            session,
            entry,
            "updated",
            old_value=old_value,
            new_value=self._ledger_snapshot(entry),
            actor_user_id=owner_id,
        )
        await session.commit()
        await session.refresh(entry)
        return self._entry_to_response(entry)

    async def create_calendar_candidate(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseReminderCandidate:
        """Persist an internal calendar/reminder candidate for one promise."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")

        candidate = self._reminder_candidate(self._entry_to_response(entry))
        entry.calendar_event = candidate.calendar_event
        entry.reminder_at = candidate.reminder_at
        entry.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._record_ledger_event(
            session,
            entry,
            "calendar_candidate_created",
            new_value=candidate.model_dump(mode="json"),
            actor_user_id=owner_id,
        )
        await session.commit()
        await session.refresh(entry)
        return self._reminder_candidate(self._entry_to_response(entry))

    async def create_action_item(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseTaskLinkResponse:
        """Convert a promise ledger entry into an internal ActionItem."""
        owner_uuid = self._coerce_uuid(owner_id)
        if owner_uuid is None:
            raise ValueError("로그인 사용자만 약속을 할 일로 전환할 수 있습니다")

        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_uuid,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")

        if entry.action_item_id is not None:
            existing = await session.execute(
                select(ActionItem).where(ActionItem.id == entry.action_item_id)
            )
            action_item = existing.scalar_one_or_none()
            if action_item is not None:
                return PromiseTaskLinkResponse(
                    ledger_entry_id=str(entry.id),
                    action_item_id=str(action_item.id),
                    title=action_item.title,
                    status=action_item.status,
                )

        now = datetime.now(UTC).replace(tzinfo=None)
        action_item = ActionItem(
            title=entry.text[:200],
            description=self._calendar_description(self._entry_to_response(entry)),
            assignee_id=None,
            priority=self._action_item_priority(entry.priority, entry.risk_level),
            status="pending",
            created_by=owner_uuid,
            due_date=entry.due_at,
            meeting_id=entry.last_source_task_id,
            tags=["promise-radar", entry.risk_level],
            category="promise-radar",
            created_at=now,
            updated_at=now,
        )
        session.add(action_item)
        await session.flush()

        entry.action_item_id = action_item.id
        entry.user_confirmed = True
        entry.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._record_ledger_event(
            session,
            entry,
            "action_item_created",
            new_value={
                "action_item_id": str(action_item.id),
                "title": action_item.title,
                "status": action_item.status,
            },
            actor_user_id=owner_uuid,
        )
        await session.commit()
        await session.refresh(action_item)
        await session.refresh(entry)
        return PromiseTaskLinkResponse(
            ledger_entry_id=str(entry.id),
            action_item_id=str(action_item.id),
            title=action_item.title,
            status=action_item.status,
        )

    async def merge_ledger_entries(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseLedgerMergeRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseLedgerMergeResponse:
        """Merge duplicate promise ledger entries into a target entry."""
        target = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if target is None:
            raise ValueError("병합 대상 약속 원장 항목을 찾을 수 없습니다")

        source_ids = {
            source_id
            for source_id in (self._coerce_uuid(item) for item in payload.source_entry_ids)
            if source_id is not None and source_id != target.id
        }
        if not source_ids:
            raise ValueError("병합할 원본 약속 원장 항목을 선택해야 합니다")

        result = await session.execute(
            select(PromiseLedgerEntry).where(
                PromiseLedgerEntry.id.in_(source_ids),
                self._ledger_scope_condition(owner_id, guest_session_id, team_id=team_id),
            )
        )
        sources = list(result.scalars().all())
        if not sources:
            raise ValueError("병합할 원본 약속 원장 항목을 찾을 수 없습니다")

        old_target = self._ledger_snapshot(target)
        now = datetime.now(UTC).replace(tzinfo=None)
        merged_ids: list[str] = []
        for source in sources:
            merged_ids.append(str(source.id))
            target.occurrences += max(1, source.occurrences)
            target.first_seen_at = min(target.first_seen_at, source.first_seen_at)
            target.last_seen_at = max(target.last_seen_at, source.last_seen_at)
            target.confidence = max(target.confidence, source.confidence)
            target.evidence = self._merge_evidence(target.evidence or [], source.evidence or [])
            target.due_at = target.due_at or source.due_at
            target.due_date_text = target.due_date_text or source.due_date_text
            target.owner_name = target.owner_name or source.owner_name
            target.assigned_user_id = target.assigned_user_id or source.assigned_user_id
            target.calendar_event = target.calendar_event or source.calendar_event
            target.action_item_id = target.action_item_id or source.action_item_id

            old_source = self._ledger_snapshot(source)
            source.status = "dismissed"
            source.dismissed_reason = f"merged_into:{target.id}"
            source.updated_at = now
            self._record_ledger_event(
                session,
                source,
                "merged_away",
                old_value=old_source,
                new_value={"merged_into": str(target.id)},
                note=payload.note,
                actor_user_id=owner_id,
            )

        target.risk_level = self._ledger_risk_level(
            target.priority, target.due_at, target.occurrences
        )
        target.updated_at = now
        self._record_ledger_event(
            session,
            target,
            "merged",
            old_value=old_target,
            new_value={**self._ledger_snapshot(target), "merged_entry_ids": merged_ids},
            note=payload.note,
            actor_user_id=owner_id,
        )
        await session.commit()
        await session.refresh(target)
        return PromiseLedgerMergeResponse(
            target=self._entry_to_response(target),
            merged_entry_ids=merged_ids,
        )

    async def split_ledger_entry(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseLedgerSplitRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseLedgerSplitResponse:
        """Split a mixed promise ledger entry into a new tracked entry."""
        original = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if original is None:
            raise ValueError("분리할 약속 원장 항목을 찾을 수 없습니다")

        text = payload.text.strip()
        if not text:
            raise ValueError("분리할 약속 내용을 입력해야 합니다")

        now = datetime.now(UTC).replace(tzinfo=None)
        evidence = self._split_evidence(original.evidence or [], payload.evidence_indices)
        due_text = payload.due_date.strip() if payload.due_date else None
        due_at = (
            payload.due_at.replace(tzinfo=None)
            if payload.due_at
            else self._parse_due_at(
                due_text,
                original.last_seen_at,
            )
        )
        created = PromiseLedgerEntry(
            owner_id=original.owner_id,
            guest_session_id=original.guest_session_id,
            team_id=original.team_id,
            assigned_user_id=original.assigned_user_id,
            source_task_id=original.source_task_id,
            last_source_task_id=original.last_source_task_id,
            canonical_key=self._canonical_key(text),
            canonical_text=text,
            text=text,
            owner_name=payload.owner.strip() if payload.owner else original.owner_name,
            speaker_label=original.speaker_label,
            speaker_profile_id=original.speaker_profile_id,
            status="open",
            priority=(payload.priority or original.priority or "medium").strip().lower(),
            risk_level="low",
            confidence=original.confidence,
            due_date_text=due_text,
            due_at=due_at,
            occurrences=1,
            first_seen_at=original.last_seen_at,
            last_seen_at=original.last_seen_at,
            evidence=evidence,
            user_confirmed=True,
            created_at=now,
            updated_at=now,
        )
        created.risk_level = self._ledger_risk_level(
            created.priority,
            created.due_at,
            created.occurrences,
        )
        session.add(created)
        await session.flush()

        original.updated_at = now
        self._record_ledger_event(
            session,
            original,
            "split",
            new_value={"created_entry_id": str(created.id), "text": created.text},
            note=payload.note,
            actor_user_id=owner_id,
        )
        self._record_ledger_event(
            session,
            created,
            "split_created",
            new_value=self._ledger_snapshot(created),
            note=payload.note,
            actor_user_id=owner_id,
        )
        await session.commit()
        await session.refresh(original)
        await session.refresh(created)
        return PromiseLedgerSplitResponse(
            original=self._entry_to_response(original),
            created=self._entry_to_response(created),
        )

    async def list_ledger_history(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 30,
    ) -> list[PromiseLedgerHistoryEntry]:
        """Return chronological audit events for a scoped ledger entry."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(PromiseLedgerEvent.ledger_entry_id == entry.id)
            .order_by(PromiseLedgerEvent.created_at.desc())
            .limit(max(1, min(limit, 100)))
        )
        return [self._event_to_response(item) for item in result.scalars().all()]

    async def build_dashboard(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 50,
    ) -> PromiseRadarDashboard:
        """Build the Home/dashboard promise obligation summary."""
        entries = await self.list_ledger_entries(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            statuses=_OPEN_LEDGER_STATUSES,
            limit=limit,
        )
        now = datetime.now(UTC).replace(tzinfo=None)
        urgent = sorted(
            entries,
            key=lambda entry: (
                entry.risk_level != "high",
                entry.due_at is None,
                entry.due_at or now + timedelta(days=365),
                -entry.occurrences,
            ),
        )
        recent = await self._recent_history(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        responsibility_scores = await self.build_responsibility_scores(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        meeting_series = await self.build_meeting_series(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        return PromiseRadarDashboard(
            open_count=len(entries),
            high_risk_count=sum(1 for entry in entries if entry.risk_level == "high"),
            overdue_count=sum(1 for entry in entries if entry.due_at and entry.due_at < now),
            due_soon_count=sum(
                1
                for entry in entries
                if entry.due_at and now <= entry.due_at <= now + timedelta(days=3)
            ),
            blocked_count=sum(1 for entry in entries if entry.status == "blocked"),
            unconfirmed_count=sum(1 for entry in entries if not entry.user_confirmed),
            owner_hotspots=self._owner_risks_from_entries(entries)[:6],
            urgent_promises=urgent[:8],
            recent_changes=recent,
            responsibility_scores=responsibility_scores[:6],
            meeting_series=meeting_series[:6],
        )

    async def build_responsibility_scores(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 100,
    ) -> list[PromiseResponsibilityScore]:
        """Score owners by unresolved, delayed, overdue, and unconfirmed promises."""
        entries = await self._list_ledger_entry_models(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        now = datetime.now(UTC).replace(tzinfo=None)
        buckets: dict[tuple[str, str | None], dict[str, Any]] = {}
        for entry in entries:
            owner = entry.owner_name or entry.speaker_label or "미지정"
            assigned_user_id = str(entry.assigned_user_id) if entry.assigned_user_id else None
            bucket = buckets.setdefault(
                (owner, assigned_user_id),
                {
                    "open": 0,
                    "completed": 0,
                    "delayed": 0,
                    "blocked": 0,
                    "overdue": 0,
                    "unconfirmed": 0,
                    "recurring": 0,
                    "total": 0,
                },
            )
            bucket["total"] += 1
            if entry.status == "completed":
                bucket["completed"] += 1
            if entry.status in _OPEN_LEDGER_STATUSES:
                bucket["open"] += 1
            if entry.status in {"delayed", "changed"}:
                bucket["delayed"] += 1
            if entry.status == "blocked":
                bucket["blocked"] += 1
            if entry.status in _OPEN_LEDGER_STATUSES and entry.due_at and entry.due_at < now:
                bucket["overdue"] += 1
            if entry.status in _OPEN_LEDGER_STATUSES and not entry.user_confirmed:
                bucket["unconfirmed"] += 1
            if entry.occurrences >= 2:
                bucket["recurring"] += 1

        scores: list[PromiseResponsibilityScore] = []
        for (owner, assigned_user_id), values in buckets.items():
            total = max(1, int(values["total"]))
            completion_rate = int(values["completed"]) / total
            score = min(
                100,
                max(
                    0,
                    int(values["open"]) * 10
                    + int(values["delayed"]) * 14
                    + int(values["blocked"]) * 18
                    + int(values["overdue"]) * 25
                    + int(values["unconfirmed"]) * 7
                    + int(values["recurring"]) * 10
                    - int(values["completed"]) * 4,
                ),
            )
            if score >= 80:
                risk_level = "critical"
            elif score >= 55:
                risk_level = "high"
            elif score >= 30:
                risk_level = "medium"
            else:
                risk_level = "low"
            reasons: list[str] = []
            if values["overdue"]:
                reasons.append(f"기한 초과 {values['overdue']}개")
            if values["blocked"]:
                reasons.append(f"차단 {values['blocked']}개")
            if values["delayed"]:
                reasons.append(f"지연/변경 {values['delayed']}개")
            if values["recurring"]:
                reasons.append(f"반복 약속 {values['recurring']}개")
            if values["unconfirmed"]:
                reasons.append(f"확정 필요 {values['unconfirmed']}개")
            if not reasons:
                reasons.append("현재 위험 신호 낮음")
            scores.append(
                PromiseResponsibilityScore(
                    owner=owner,
                    assigned_user_id=assigned_user_id,
                    score=score,
                    risk_level=risk_level,
                    open_count=int(values["open"]),
                    completed_count=int(values["completed"]),
                    delayed_count=int(values["delayed"]),
                    blocked_count=int(values["blocked"]),
                    overdue_count=int(values["overdue"]),
                    unconfirmed_count=int(values["unconfirmed"]),
                    recurring_count=int(values["recurring"]),
                    completion_rate=round(completion_rate, 3),
                    reasons=reasons[:4],
                )
            )
        return sorted(scores, key=lambda item: item.score, reverse=True)

    async def build_learning_insights(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 200,
    ) -> PromiseLearningInsight:
        """Summarize learning-loop feedback into operator actions."""
        profile = await self.learning_profile(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        events = await self._scoped_events(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        feedback_count = sum(
            1
            for event in events
            if event.event_type
            in {
                "learning_feedback",
                "autopilot_review_rejected",
                "autopilot_confirmed",
                "autopilot_applied",
                "updated",
            }
        )
        status_attention = [
            status
            for status, count in sorted(
                profile.status_false_positive_count.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            if count > 0
        ]
        status_sample_counts = {
            status: profile.status_false_positive_count.get(status, 0)
            + profile.status_confirmed_count.get(status, 0)
            for status in sorted(
                set(profile.status_false_positive_count)
                | set(profile.status_confirmed_count)
                | {"completed", "delayed", "changed", "dismissed"}
            )
        }
        status_false_positive_rate = {
            status: round(
                profile.status_false_positive_count.get(status, 0) / sample_count,
                3,
            )
            for status, sample_count in status_sample_counts.items()
            if sample_count > 0
        }
        recommended_policy = "safe_auto"
        if profile.false_positive_count >= max(3, profile.confirmed_count + 1):
            recommended_policy = "preview_only"
        elif profile.assignee_correction_count >= 3:
            recommended_policy = "preview_only"
        elif any(status in {"delayed", "changed", "dismissed"} for status in status_attention):
            recommended_policy = "completed_only"

        insights = [
            f"현재 자동 적용 기준은 {round(profile.autopilot_threshold * 100)}%입니다.",
            f"확정 {profile.confirmed_count}건, 오판/거절 {profile.false_positive_count}건이 반영됐습니다.",
        ]
        if profile.assignee_correction_count:
            insights.append(f"담당자 보정 {profile.assignee_correction_count}건이 감지됐습니다.")
        if status_attention:
            insights.append(f"주의 상태: {', '.join(status_attention[:4])}")
        if not profile.owner_aliases:
            insights.append("아직 충분한 담당자 alias graph가 없습니다.")
        else:
            insights.append(f"담당자 alias graph {len(profile.owner_aliases)}개가 활성화됐습니다.")

        next_actions: list[str] = []
        if recommended_policy == "preview_only":
            next_actions.append("자동 적용보다 Review Inbox 확정을 우선하세요.")
        if profile.assignee_correction_count:
            next_actions.append("반복 보정된 담당자 이름을 팀 alias로 고정하세요.")
        if status_attention:
            next_actions.append("주의 상태의 threshold를 낮추지 말고 evidence pack을 확인하세요.")
        if not next_actions:
            next_actions.append("현재 정책을 유지하고 확정/거절 피드백을 계속 누적하세요.")

        scope_breakdown = {
            "feedback": feedback_count,
            "status_samples": sum(status_sample_counts.values()),
            "owner_aliases": len(profile.owner_aliases),
            "assignee_corrections": profile.assignee_correction_count,
        }
        scope_recommendations: list[str] = []
        if team_id:
            scope_breakdown["team_scope"] = 1
            scope_recommendations.append("팀 alias graph와 상태별 threshold를 함께 고정하세요.")
        elif owner_id:
            scope_breakdown["owner_scope"] = 1
            scope_recommendations.append(
                "개인 확정/거절 데이터를 충분히 누적한 뒤 팀 정책으로 승격하세요."
            )
        elif guest_session_id:
            scope_breakdown["guest_scope"] = 1
            scope_recommendations.append(
                "게스트 범위 학습은 자동 적용보다 preview-only로 유지하세요."
            )
        if sum(status_sample_counts.values()) < 10:
            scope_recommendations.append(
                "상태별 샘플이 10건 미만이면 자동 적용 기준을 낮추지 마세요."
            )
        if not scope_recommendations:
            scope_recommendations.append("현재 scope의 상태별 학습 기준을 유지하세요.")

        return PromiseLearningInsight(
            scope=profile.scope,
            autopilot_threshold=profile.autopilot_threshold,
            status_thresholds=profile.status_thresholds,
            status_sample_counts=status_sample_counts,
            status_false_positive_rate=status_false_positive_rate,
            feedback_count=feedback_count,
            false_positive_count=profile.false_positive_count,
            confirmed_count=profile.confirmed_count,
            assignee_correction_count=profile.assignee_correction_count,
            alias_graph_size=len(profile.owner_aliases),
            scope_breakdown=scope_breakdown,
            scope_recommendations=scope_recommendations[:4],
            evidence_lock_enabled=profile.evidence_lock_enabled,
            status_attention=status_attention[:6],
            recommended_policy=recommended_policy,
            insights=insights[:6],
            next_actions=next_actions[:5],
        )

    async def build_learning_telemetry_report(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 500,
    ) -> PromiseLearningTelemetryReport:
        """Aggregate privacy-safe production learning telemetry from ledger events."""
        events = await self._scoped_events(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        status_buckets: dict[str, Counter[str]] = {}
        owner_buckets: dict[str, Counter[str]] = {}
        locale_buckets: dict[str, Counter[str]] = {}
        shape_buckets: dict[str, Counter[str]] = {}
        feedback_count = 0

        for event in events:
            value = event.new_value if isinstance(event.new_value, dict) else {}
            event_type = event.event_type or "unknown"
            if event_type in {
                "learning_feedback",
                "autopilot_review_rejected",
                "autopilot_confirmed",
                "autopilot_applied",
                "autopilot_undone",
            }:
                feedback_count += 1

            status = self._telemetry_status(value, event_type)
            self._telemetry_mark(status_buckets, status, event_type, value)

            owner_key = self._telemetry_owner_key(value)
            if owner_key:
                self._telemetry_mark(owner_buckets, owner_key, event_type, value)

            locale = self._telemetry_locale(value)
            self._telemetry_mark(locale_buckets, locale, event_type, value)

            payload_shape = str(value.get("payload_shape") or event_type or "unknown")
            self._telemetry_mark(shape_buckets, payload_shape, event_type, value)

        status_segments = self._telemetry_segments("status", status_buckets)
        owner_segments = self._telemetry_segments("owner", owner_buckets)
        locale_segments = self._telemetry_segments("locale", locale_buckets)
        payload_shape_segments = self._telemetry_segments("payload_shape", shape_buckets)
        recommendations: list[str] = []
        weak_statuses = [
            item.value
            for item in status_segments
            if item.sample_count >= 2 and item.false_positive_rate >= 0.34
        ]
        if weak_statuses:
            recommendations.append(
                f"오판율이 높은 상태({', '.join(weak_statuses[:4])})는 preview-only로 유지하세요."
            )
        if not owner_segments:
            recommendations.append(
                "담당자 보정 telemetry가 부족합니다. Review Queue에서 owner 수정 데이터를 누적하세요."
            )
        if any(item.value == "ko" and item.false_positive_count for item in locale_segments):
            recommendations.append(
                "한국어 회의 오판 샘플을 별도 accuracy/extraction fixture로 승격하세요."
            )
        if not recommendations:
            recommendations.append(
                "현재 production telemetry 기준으로 즉시 격리할 고위험 패턴은 없습니다."
            )

        return PromiseLearningTelemetryReport(
            generated_at=datetime.now(UTC).replace(tzinfo=None),
            scope=self._scope_label(owner_id, guest_session_id, team_id),
            event_count=len(events),
            feedback_event_count=feedback_count,
            status_segments=status_segments,
            owner_segments=owner_segments,
            locale_segments=locale_segments,
            payload_shape_segments=payload_shape_segments,
            recommendations=recommendations[:5],
        )

    async def build_responsibility_trends(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 250,
    ) -> list[PromiseResponsibilityTrend]:
        """Build owner responsibility score trends from ledger first/last seen dates."""
        entries = await self._list_ledger_entry_models(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        if not entries:
            return []
        current_scores = {
            (item.owner, item.assigned_user_id): item
            for item in await self.build_responsibility_scores(
                session,
                owner_id=owner_id,
                guest_session_id=guest_session_id,
                team_id=team_id,
                limit=limit,
            )
        }
        now = datetime.now(UTC).replace(tzinfo=None)
        buckets: dict[tuple[str, str | None], dict[str, dict[str, int]]] = {}
        for entry in entries:
            owner = entry.owner_name or entry.speaker_label or "미지정"
            assigned_user_id = str(entry.assigned_user_id) if entry.assigned_user_id else None
            period = (entry.last_seen_at or entry.first_seen_at or now).date().isoformat()
            values = buckets.setdefault((owner, assigned_user_id), {}).setdefault(
                period,
                {
                    "open": 0,
                    "completed": 0,
                    "delayed": 0,
                    "blocked": 0,
                    "overdue": 0,
                    "unconfirmed": 0,
                    "recurring": 0,
                },
            )
            if entry.status == "completed":
                values["completed"] += 1
            if entry.status in _OPEN_LEDGER_STATUSES:
                values["open"] += 1
            if entry.status in {"delayed", "changed"}:
                values["delayed"] += 1
            if entry.status == "blocked":
                values["blocked"] += 1
            if entry.status in _OPEN_LEDGER_STATUSES and entry.due_at and entry.due_at < now:
                values["overdue"] += 1
            if entry.status in _OPEN_LEDGER_STATUSES and not entry.user_confirmed:
                values["unconfirmed"] += 1
            if entry.occurrences >= 2:
                values["recurring"] += 1

        trends: list[PromiseResponsibilityTrend] = []
        for key, periods in buckets.items():
            owner, assigned_user_id = key
            points = [
                PromiseResponsibilityTrendPoint(
                    period_start=period,
                    score=self._responsibility_score_from_counts(values),
                    open_count=values["open"],
                    completed_count=values["completed"],
                    delayed_count=values["delayed"],
                    blocked_count=values["blocked"],
                    overdue_count=values["overdue"],
                    unconfirmed_count=values["unconfirmed"],
                    recurring_count=values["recurring"],
                )
                for period, values in sorted(periods.items())
            ]
            if len(points) >= 2 and points[-1].score > points[0].score + 5:
                direction = "worsening"
            elif len(points) >= 2 and points[-1].score < points[0].score - 5:
                direction = "improving"
            else:
                direction = "stable"
            current = current_scores.get(key)
            current_score = current.score if current else points[-1].score
            risk_level = (
                current.risk_level if current else self._responsibility_risk_level(current_score)
            )
            trends.append(
                PromiseResponsibilityTrend(
                    owner=owner,
                    assigned_user_id=assigned_user_id,
                    current_score=current_score,
                    risk_level=risk_level,
                    direction=direction,
                    points=points[-12:],
                )
            )
        return sorted(trends, key=lambda item: item.current_score, reverse=True)

    async def build_meeting_series(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 100,
    ) -> list[PromiseMeetingSeries]:
        """Infer recurring meeting groups from ledger source meetings and titles."""
        entries = await self._list_ledger_entry_models(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            statuses=_OPEN_LEDGER_STATUSES,
            limit=limit,
        )
        if not entries:
            return []
        titles = await self._meeting_titles_for_entries(session, entries)
        now = datetime.now(UTC).replace(tzinfo=None)
        buckets: dict[str, dict[str, Any]] = {}
        for entry in entries:
            source_id = entry.last_source_task_id or entry.source_task_id
            title = titles.get(source_id) or self._fallback_series_title(entry)
            series_key = self._meeting_series_key(title)
            bucket = buckets.setdefault(
                series_key,
                {
                    "title": title,
                    "task_ids": set(),
                    "first_seen_at": entry.first_seen_at,
                    "last_seen_at": entry.last_seen_at,
                    "latest_task_id": source_id,
                    "open": 0,
                    "overdue": 0,
                    "high_risk": 0,
                    "owners": set(),
                    "questions": [],
                },
            )
            bucket["task_ids"].add(source_id)
            if entry.first_seen_at < bucket["first_seen_at"]:
                bucket["first_seen_at"] = entry.first_seen_at
            if entry.last_seen_at > bucket["last_seen_at"]:
                bucket["last_seen_at"] = entry.last_seen_at
                bucket["latest_task_id"] = source_id
            bucket["open"] += 1
            if entry.due_at and entry.due_at < now:
                bucket["overdue"] += 1
            if entry.risk_level == "high":
                bucket["high_risk"] += 1
            owner = entry.owner_name or entry.speaker_label
            if owner:
                bucket["owners"].add(owner)
            if len(bucket["questions"]) < 3:
                owner_prefix = f"{owner}님의 " if owner else ""
                bucket["questions"].append(
                    f"{owner_prefix}'{entry.text}' 진행 상태를 확인했습니까?"
                )

        series: list[PromiseMeetingSeries] = []
        for series_key, values in buckets.items():
            task_ids = values["task_ids"]
            if len(task_ids) < 2 and int(values["open"]) < 2:
                continue
            series.append(
                PromiseMeetingSeries(
                    series_key=series_key,
                    title=str(values["title"]),
                    meeting_count=max(1, len(task_ids)),
                    first_seen_at=values["first_seen_at"],
                    last_seen_at=values["last_seen_at"],
                    latest_task_id=str(values["latest_task_id"]),
                    open_count=int(values["open"]),
                    overdue_count=int(values["overdue"]),
                    high_risk_count=int(values["high_risk"]),
                    owners=sorted(values["owners"])[:5],
                    next_questions=list(values["questions"])[:3],
                )
            )
        return sorted(
            series,
            key=lambda item: (item.overdue_count, item.high_risk_count, item.open_count),
            reverse=True,
        )

    async def build_meeting_series_timeline(
        self,
        session: AsyncSession,
        series_key: str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 250,
    ) -> PromiseMeetingSeriesTimeline:
        """Return a recurring meeting series timeline with grouped promises."""
        entries = await self._list_ledger_entry_models(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        if not entries:
            return PromiseMeetingSeriesTimeline(
                series_key=series_key, title=series_key, meeting_count=0
            )
        titles = await self._meeting_titles_for_entries(session, entries)
        now = datetime.now(UTC).replace(tzinfo=None)
        buckets: dict[str, dict[str, Any]] = {}
        selected_title = series_key
        normalized_target = self._meeting_series_key(series_key)
        for entry in entries:
            response_entry = self._entry_to_response(entry)
            source_points = [
                (entry.source_task_id, entry.first_seen_at),
                (entry.last_source_task_id, entry.last_seen_at),
            ]
            seen_source_ids: set[str] = set()
            for raw_source_id, seen_at in source_points:
                source_id = str(raw_source_id or "")
                if not source_id or source_id in seen_source_ids:
                    continue
                seen_source_ids.add(source_id)
                title = titles.get(source_id) or self._fallback_series_title(entry)
                key = self._meeting_series_key(title)
                if key != normalized_target and series_key != key:
                    continue
                selected_title = title
                bucket = buckets.setdefault(
                    source_id,
                    {
                        "title": title,
                        "seen_at": seen_at,
                        "open": 0,
                        "overdue": 0,
                        "high_risk": 0,
                        "owners": set(),
                        "promises": [],
                        "questions": [],
                    },
                )
                if seen_at > bucket["seen_at"]:
                    bucket["seen_at"] = seen_at
                if entry.status in _OPEN_LEDGER_STATUSES:
                    bucket["open"] += 1
                if entry.status in _OPEN_LEDGER_STATUSES and entry.due_at and entry.due_at < now:
                    bucket["overdue"] += 1
                if entry.risk_level == "high":
                    bucket["high_risk"] += 1
                owner = entry.owner_name or entry.speaker_label
                if owner:
                    bucket["owners"].add(owner)
                if len(bucket["promises"]) < 8:
                    bucket["promises"].append(response_entry)
                if len(bucket["questions"]) < 3:
                    bucket["questions"].append(self._briefing_checkpoint(response_entry))

        items = [
            PromiseMeetingSeriesTimelineItem(
                series_key=normalized_target,
                task_id=task_id,
                title=str(values["title"]),
                seen_at=values["seen_at"],
                open_count=int(values["open"]),
                overdue_count=int(values["overdue"]),
                high_risk_count=int(values["high_risk"]),
                owners=sorted(values["owners"])[:6],
                promises=values["promises"],
                questions=list(values["questions"])[:3],
            )
            for task_id, values in sorted(
                buckets.items(), key=lambda item: item[1]["seen_at"], reverse=True
            )
        ]
        return PromiseMeetingSeriesTimeline(
            series_key=normalized_target,
            title=selected_title,
            meeting_count=len(items),
            first_seen_at=min((item.seen_at for item in items), default=None),
            last_seen_at=max((item.seen_at for item in items), default=None),
            items=items,
        )

    async def build_autopilot_review_inbox(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 50,
    ) -> PromiseAutopilotReviewQueue:
        """Build a global Review Inbox from persisted Autopilot assessment events."""
        events = await self._scoped_events(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=max(limit * 4, 50),
        )
        pending: list[tuple[PromiseLedgerEvent, PromiseAutopilotAssessment]] = []
        seen: set[tuple[str, str]] = set()
        for event in events:
            if event.event_type not in {"autopilot_assessed", "autopilot_applied"}:
                continue
            value = event.new_value if isinstance(event.new_value, dict) else {}
            autopilot = value.get("autopilot")
            if not isinstance(autopilot, dict):
                continue
            try:
                assessment = PromiseAutopilotAssessment(**autopilot)
            except Exception:
                continue
            key = (assessment.ledger_entry_id, assessment.suggested_status)
            if key in seen:
                continue
            seen.add(key)
            if (
                assessment.conflict_detected
                or assessment.requires_confirmation
                or assessment.suggested_status != assessment.previous_status
            ):
                pending.append((event, assessment))
            if len(pending) >= limit:
                break

        if not pending:
            return PromiseAutopilotReviewQueue(
                task_id="review-inbox",
                queue_count=0,
                actionable_count=0,
                conflict_count=0,
                items=[],
            )
        entry_ids = [
            entry_id
            for _, assessment in pending
            if (entry_id := self._coerce_uuid(assessment.ledger_entry_id)) is not None
        ]
        result = await session.execute(
            select(PromiseLedgerEntry).where(PromiseLedgerEntry.id.in_(entry_ids))
        )
        entries_by_id = {str(entry.id): entry for entry in result.scalars().all()}
        items: list[PromiseAutopilotReviewItem] = []
        for event, assessment in pending:
            entry = entries_by_id.get(assessment.ledger_entry_id)
            if entry is None or entry.status not in _OPEN_LEDGER_STATUSES:
                continue
            items.append(
                PromiseAutopilotReviewItem(
                    ledger_entry=self._entry_to_response(entry),
                    assessment=assessment,
                    queued_at=event.created_at,
                    decision_required=(
                        assessment.conflict_detected
                        or assessment.suggested_status != assessment.previous_status
                    ),
                )
            )
        return PromiseAutopilotReviewQueue(
            task_id="review-inbox",
            queue_count=len(items),
            actionable_count=sum(
                1
                for item in items
                if not item.assessment.conflict_detected
                and item.assessment.suggested_status != item.assessment.previous_status
            ),
            conflict_count=sum(1 for item in items if item.assessment.conflict_detected),
            items=items,
        )

    async def build_command_center(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 50,
        target_case_count: int = 560,
    ) -> PromiseCommandCenter:
        """Build one operational Promise Radar view for review, learning, and sync."""
        dashboard = await self.build_dashboard(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        review_queue = await self.build_autopilot_review_inbox(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        learning_insight = await self.build_learning_insights(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=max(limit, 200),
        )
        learning_telemetry = await self.build_learning_telemetry_report(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=max(limit, 500),
        )
        digest = await self.build_digest(
            session,
            cadence="daily",
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=min(max(limit, 12), 50),
        )
        pre_meeting_brief = await self.build_pre_meeting_brief(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=8,
        )
        live_coach = self._build_live_coach_summary(pre_meeting_brief)
        external_reconcile = await self.build_external_task_reconcile_report(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=min(max(limit, 25), 100),
        )
        accuracy_report = self._default_accuracy_report(target_case_count=target_case_count)
        extraction_recall = self._default_extraction_recall_report(target_case_count=50)
        evidence_audit = self._evidence_audit_summary(review_queue)
        memory_graph = self._memory_graph_summary(dashboard, learning_insight)
        shadow_mode = self._autopilot_shadow_summary(review_queue, learning_insight)
        evidence_permissions = self._evidence_permission_summary(
            review_queue,
            evidence_audit,
            scope=self._scope_label(owner_id, guest_session_id, team_id),
        )
        evidence_room = self._evidence_room_summary(
            review_queue,
            evidence_permissions,
            scope=self._scope_label(owner_id, guest_session_id, team_id),
        )
        team_scorecard = self._team_scorecard_summary(dashboard)
        autopilot_quarantine = await self.build_autopilot_quarantine_summary(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=max(limit, 200),
        )
        meeting_recipe = self._meeting_recipe_policy(
            dashboard=dashboard,
            learning_insight=learning_insight,
            evidence_permissions=evidence_permissions,
        )
        focus_items = self._command_center_focus_items(
            dashboard=dashboard,
            review_queue=review_queue,
            learning_insight=learning_insight,
            learning_telemetry=learning_telemetry,
            digest=digest,
            external_reconcile=external_reconcile,
            accuracy_report=accuracy_report,
            extraction_recall=extraction_recall,
            evidence_audit=evidence_audit,
            memory_graph=memory_graph,
            shadow_mode=shadow_mode,
            evidence_permissions=evidence_permissions,
            evidence_room=evidence_room,
            team_scorecard=team_scorecard,
            autopilot_quarantine=autopilot_quarantine,
            live_coach=live_coach,
        )
        actions = self._command_center_actions(
            review_queue=review_queue,
            external_reconcile=external_reconcile,
            accuracy_report=accuracy_report,
            extraction_recall=extraction_recall,
            evidence_permissions=evidence_permissions,
            evidence_room=evidence_room,
            autopilot_quarantine=autopilot_quarantine,
            live_coach=live_coach,
        )
        return PromiseCommandCenter(
            generated_at=datetime.now(UTC).replace(tzinfo=None),
            dashboard=dashboard,
            review_queue=review_queue,
            learning_insight=learning_insight,
            learning_telemetry=learning_telemetry,
            digest=digest,
            pre_meeting_brief=pre_meeting_brief,
            live_coach=live_coach,
            external_reconcile=external_reconcile,
            accuracy_report=accuracy_report,
            extraction_recall=extraction_recall,
            evidence_audit=evidence_audit,
            memory_graph=memory_graph,
            shadow_mode=shadow_mode,
            evidence_permissions=evidence_permissions,
            evidence_room=evidence_room,
            team_scorecard=team_scorecard,
            autopilot_quarantine=autopilot_quarantine,
            meeting_recipe=meeting_recipe,
            google_tasks_oauth=self._google_tasks_oauth_guide(),
            actions=actions,
            focus_items=focus_items,
        )

    async def build_external_task_reconcile_report(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 100,
    ) -> PromiseExternalTaskReconcileResponse:
        """Report linked Google Tasks that need explicit sync/update review."""
        entries = await self._list_ledger_entry_models(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        items: list[PromiseExternalTaskReconcileItem] = []
        for entry in entries:
            metadata = self._google_task_metadata(entry)
            external_id = metadata.get("external_id")
            if not external_id:
                continue
            ledger_status = "completed" if entry.status == "completed" else "needsAction"
            external_status = metadata.get("external_status")
            needs_sync = (
                external_status in {"completed", "needsAction"} and external_status != ledger_status
            )
            direction = "none"
            issue = None
            if needs_sync:
                direction = (
                    "pull_from_external" if external_status == "completed" else "push_to_external"
                )
                issue = "Google Tasks 상태와 Promise Ledger 상태가 다릅니다."
            elif external_status is None:
                issue = "OAuth 토큰으로 Google Tasks 최신 상태 확인이 필요합니다."
            items.append(
                PromiseExternalTaskReconcileItem(
                    ledger_entry=self._entry_to_response(entry),
                    provider="google_tasks",
                    tasklist=metadata.get("tasklist") or "@default",
                    external_id=external_id,
                    external_url=metadata.get("external_url"),
                    ledger_status=ledger_status,
                    external_status=external_status,
                    needs_sync=needs_sync,
                    direction=direction,
                    issue=issue,
                    sync_contract=self._external_sync_contract(
                        entry,
                        provider="google_tasks",
                        tasklist=metadata.get("tasklist") or "@default",
                        external_id=external_id,
                    ),
                )
            )
        return PromiseExternalTaskReconcileResponse(
            provider="google_tasks",
            checked_count=len(entries),
            linked_count=len(items),
            needs_sync_count=sum(1 for item in items if item.needs_sync),
            requires_oauth=True,
            items=items,
        )

    async def dispatch_due_notifications(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        team_id: UUID | str | None = None,
        now: datetime | None = None,
        limit: int = 25,
        push_service: PushService | None = None,
        allow_global: bool = False,
    ) -> PromiseNotificationDispatchResponse:
        """Send FCM notifications for due or reminder-ready promises."""
        owner_uuid = self._coerce_uuid(owner_id)
        team_uuid = self._coerce_uuid(team_id)
        if owner_uuid is None and team_uuid is None and not allow_global:
            raise ValueError("로그인 사용자 또는 팀 범위가 필요합니다")

        moment = (now or datetime.now(UTC)).replace(tzinfo=None)
        if team_uuid is not None:
            scope_condition = PromiseLedgerEntry.team_id == team_uuid
        elif owner_uuid is not None:
            scope_condition = PromiseLedgerEntry.owner_id == owner_uuid
        else:
            scope_condition = PromiseLedgerEntry.id.is_not(None)
        result = await session.execute(
            select(PromiseLedgerEntry)
            .where(
                scope_condition,
                PromiseLedgerEntry.status.in_(_OPEN_LEDGER_STATUSES),
                PromiseLedgerEntry.notification_sent_at.is_(None),
                or_(
                    PromiseLedgerEntry.reminder_at <= moment,
                    PromiseLedgerEntry.due_at <= moment,
                ),
            )
            .order_by(PromiseLedgerEntry.due_at.is_(None), PromiseLedgerEntry.due_at.asc())
            .limit(max(1, min(limit, 100)))
        )
        entries = list(result.scalars().all())
        push = push_service or get_push_service()
        sent_count = 0
        failure_count = 0
        invalid_tokens: list[str] = []
        notified_ids: list[str] = []
        for entry in entries:
            target_user_id = entry.assigned_user_id or entry.owner_id or owner_uuid
            if target_user_id is None:
                continue
            tokens_result = await session.execute(
                select(DeviceToken.fcm_token)
                .where(DeviceToken.user_id == str(target_user_id))
                .where(DeviceToken.is_active)
            )
            tokens = [row[0] for row in tokens_result.all()]
            if not tokens:
                continue
            response = await push.send_multicast(
                tokens=tokens,
                title="약속 기한 확인",
                body=self._notification_body(entry),
                data={
                    "type": "promise_radar",
                    "ledger_entry_id": str(entry.id),
                    "meeting_id": entry.last_source_task_id,
                },
            )
            sent_count += int(response.get("success_count") or 0)
            failure_count += int(response.get("failure_count") or 0)
            invalid = [str(token) for token in response.get("invalid_tokens") or []]
            invalid_tokens.extend(invalid)
            for invalid_token in invalid:
                await push.invalidate_token(session, invalid_token)
            if int(response.get("success_count") or 0) > 0:
                entry.notification_sent_at = moment
                entry.updated_at = moment
                notified_ids.append(str(entry.id))
                self._record_ledger_event(
                    session,
                    entry,
                    "notification_sent",
                    new_value={"sent_at": moment.isoformat()},
                    actor_user_id=owner_uuid,
                )
        await session.commit()
        record_promise_radar_notification(
            "due",
            sent=sent_count,
            failed=failure_count,
        )
        return PromiseNotificationDispatchResponse(
            considered_count=len(entries),
            sent_count=sent_count,
            failure_count=failure_count,
            invalid_tokens=invalid_tokens,
            notified_entry_ids=notified_ids,
        )

    async def dispatch_digest_notifications(
        self,
        session: AsyncSession,
        *,
        cadence: str = "daily",
        owner_id: UUID | str | None = None,
        team_id: UUID | str | None = None,
        now: datetime | None = None,
        limit: int = 50,
        push_service: PushService | None = None,
        allow_global: bool = False,
        require_enabled_preference: bool = False,
    ) -> PromiseNotificationDispatchResponse:
        """Send daily/weekly Promise Digest pushes grouped by responsible user."""
        normalized = cadence.lower().strip()
        if normalized not in {"daily", "weekly"}:
            raise ValueError("지원하지 않는 digest 주기입니다")
        owner_uuid = self._coerce_uuid(owner_id)
        team_uuid = self._coerce_uuid(team_id)
        if owner_uuid is None and team_uuid is None and not allow_global:
            raise ValueError("로그인 사용자 또는 팀 범위가 필요합니다")

        moment = (now or datetime.now(UTC)).replace(tzinfo=None)
        if team_uuid is not None:
            scope_condition = PromiseLedgerEntry.team_id == team_uuid
        elif owner_uuid is not None:
            scope_condition = PromiseLedgerEntry.owner_id == owner_uuid
        else:
            scope_condition = PromiseLedgerEntry.id.is_not(None)
        result = await session.execute(
            select(PromiseLedgerEntry)
            .where(
                scope_condition,
                PromiseLedgerEntry.status.in_(_OPEN_LEDGER_STATUSES),
            )
            .order_by(
                PromiseLedgerEntry.risk_level.desc(),
                PromiseLedgerEntry.due_at.is_(None),
                PromiseLedgerEntry.due_at.asc(),
            )
            .limit(max(1, min(limit, 200)))
        )
        entries = list(result.scalars().all())
        grouped: dict[UUID, list[PromiseLedgerEntry]] = {}
        for entry in entries:
            target_user_id = entry.assigned_user_id or entry.owner_id or owner_uuid
            if target_user_id is None:
                continue
            grouped.setdefault(target_user_id, []).append(entry)

        push = push_service or get_push_service()
        sent_count = 0
        failure_count = 0
        invalid_tokens: list[str] = []
        notified_ids: list[str] = []
        for target_user_id, user_entries in grouped.items():
            if require_enabled_preference and not await self._digest_preference_enabled_for_target(
                session,
                target_user_id,
                cadence=normalized,
                moment=moment,
            ):
                continue
            if await self._digest_already_sent(
                session,
                target_user_id,
                cadence=normalized,
                moment=moment,
            ):
                continue
            tokens_result = await session.execute(
                select(DeviceToken.fcm_token)
                .where(DeviceToken.user_id == str(target_user_id))
                .where(DeviceToken.is_active)
            )
            tokens = [row[0] for row in tokens_result.all()]
            if not tokens:
                continue
            overdue = [entry for entry in user_entries if entry.due_at and entry.due_at < moment]
            horizon = moment + (timedelta(days=1) if normalized == "daily" else timedelta(days=7))
            due_soon = [
                entry
                for entry in user_entries
                if entry.due_at and moment <= entry.due_at <= horizon
            ]
            high_risk = [entry for entry in user_entries if entry.risk_level == "high"]
            title = "오늘의 약속 레이더" if normalized == "daily" else "이번 주 약속 레이더"
            body = (
                f"열린 약속 {len(user_entries)}개 · "
                f"기한 초과 {len(overdue)}개 · "
                f"확인 필요 {len(due_soon)}개 · "
                f"고위험 {len(high_risk)}개"
            )
            response = await push.send_multicast(
                tokens=tokens,
                title=title,
                body=body,
                data={
                    "type": "promise_radar_digest",
                    "cadence": normalized,
                    "entry_count": str(len(user_entries)),
                },
            )
            sent_count += int(response.get("success_count") or 0)
            failure_count += int(response.get("failure_count") or 0)
            invalid = [str(token) for token in response.get("invalid_tokens") or []]
            invalid_tokens.extend(invalid)
            for invalid_token in invalid:
                await push.invalidate_token(session, invalid_token)
            if int(response.get("success_count") or 0) > 0:
                anchor = user_entries[0]
                notified_ids.extend(str(entry.id) for entry in user_entries[:5])
                self._record_ledger_event(
                    session,
                    anchor,
                    "digest_notification_sent",
                    new_value={
                        "sent_at": moment.isoformat(),
                        "cadence": normalized,
                        "entry_count": len(user_entries),
                        "overdue_count": len(overdue),
                        "due_soon_count": len(due_soon),
                        "high_risk_count": len(high_risk),
                    },
                    actor_user_id=target_user_id,
                )
        await session.commit()
        record_promise_radar_notification(
            "digest",
            sent=sent_count,
            failed=failure_count,
        )
        return PromiseNotificationDispatchResponse(
            considered_count=len(entries),
            sent_count=sent_count,
            failure_count=failure_count,
            invalid_tokens=invalid_tokens,
            notified_entry_ids=notified_ids,
        )

    async def dispatch_pre_meeting_brief_notifications(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        team_id: UUID | str | None = None,
        now: datetime | None = None,
        limit: int = 8,
        push_service: PushService | None = None,
        allow_global: bool = False,
    ) -> PromiseNotificationDispatchResponse:
        """Send a pre-meeting Promise Brief push without consuming due-push state."""
        owner_uuid = self._coerce_uuid(owner_id)
        team_uuid = self._coerce_uuid(team_id)
        if owner_uuid is None and team_uuid is None and not allow_global:
            raise ValueError("로그인 사용자 또는 팀 범위가 필요합니다")

        moment = (now or datetime.now(UTC)).replace(tzinfo=None)
        if team_uuid is not None:
            scope_condition = PromiseLedgerEntry.team_id == team_uuid
        elif owner_uuid is not None:
            scope_condition = PromiseLedgerEntry.owner_id == owner_uuid
        else:
            scope_condition = PromiseLedgerEntry.id.is_not(None)
        result = await session.execute(
            select(PromiseLedgerEntry)
            .where(
                scope_condition,
                PromiseLedgerEntry.status.in_(_OPEN_LEDGER_STATUSES),
            )
            .order_by(
                PromiseLedgerEntry.risk_level.desc(),
                PromiseLedgerEntry.due_at.is_(None),
                PromiseLedgerEntry.due_at.asc(),
                PromiseLedgerEntry.last_seen_at.desc(),
            )
            .limit(max(1, min(limit, 50)))
        )
        entries = list(result.scalars().all())
        grouped: dict[UUID, list[PromiseLedgerEntry]] = {}
        for entry in entries:
            target_user_id = entry.assigned_user_id or entry.owner_id or owner_uuid
            if target_user_id is None:
                continue
            grouped.setdefault(target_user_id, []).append(entry)

        push = push_service or get_push_service()
        sent_count = 0
        failure_count = 0
        invalid_tokens: list[str] = []
        notified_ids: list[str] = []
        for target_user_id, user_entries in grouped.items():
            if await self._pre_meeting_brief_already_sent(
                session,
                target_user_id,
                moment=moment,
            ):
                continue
            tokens_result = await session.execute(
                select(DeviceToken.fcm_token)
                .where(DeviceToken.user_id == str(target_user_id))
                .where(DeviceToken.is_active)
            )
            tokens = [row[0] for row in tokens_result.all()]
            if not tokens:
                continue
            overdue = [entry for entry in user_entries if entry.due_at and entry.due_at < moment]
            high_risk = [entry for entry in user_entries if entry.risk_level == "high"]
            body = (
                f"회의 전 확인할 약속 {len(user_entries)}개 · "
                f"기한 초과 {len(overdue)}개 · 고위험 {len(high_risk)}개"
            )
            response = await push.send_multicast(
                tokens=tokens,
                title="회의 전 약속 브리프",
                body=body,
                data={
                    "type": "promise_radar_pre_meeting_brief",
                    "entry_count": str(len(user_entries)),
                    "overdue_count": str(len(overdue)),
                    "high_risk_count": str(len(high_risk)),
                },
            )
            sent_count += int(response.get("success_count") or 0)
            failure_count += int(response.get("failure_count") or 0)
            invalid = [str(token) for token in response.get("invalid_tokens") or []]
            invalid_tokens.extend(invalid)
            for invalid_token in invalid:
                await push.invalidate_token(session, invalid_token)
            if int(response.get("success_count") or 0) > 0:
                anchor = user_entries[0]
                notified_ids.extend(str(entry.id) for entry in user_entries)
                self._record_ledger_event(
                    session,
                    anchor,
                    "pre_meeting_brief_sent",
                    new_value={
                        "sent_at": moment.isoformat(),
                        "entry_count": len(user_entries),
                        "overdue_count": len(overdue),
                        "high_risk_count": len(high_risk),
                    },
                    actor_user_id=target_user_id,
                )
        await session.commit()
        record_promise_radar_notification(
            "pre_meeting_brief",
            sent=sent_count,
            failed=failure_count,
        )
        return PromiseNotificationDispatchResponse(
            considered_count=len(entries),
            sent_count=sent_count,
            failure_count=failure_count,
            invalid_tokens=invalid_tokens,
            notified_entry_ids=notified_ids,
        )

    async def run_autopilot(
        self,
        session: AsyncSession,
        task_id: str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        apply: bool = True,
        limit: int = 50,
    ) -> PromiseAutopilotResponse:
        """Assess unresolved promises against the current meeting and optionally apply status."""
        current = await self._get_record(session, task_id)
        if current is None:
            raise ValueError("회의 요약을 찾을 수 없습니다")

        result = await session.execute(
            select(PromiseLedgerEntry)
            .where(
                self._ledger_scope_condition(owner_id, guest_session_id, team_id=team_id),
                PromiseLedgerEntry.status.in_(_OPEN_LEDGER_STATUSES),
            )
            .order_by(PromiseLedgerEntry.risk_level.desc(), PromiseLedgerEntry.last_seen_at.desc())
            .limit(max(1, min(limit, 100)))
        )
        entries = list(result.scalars().all())
        records = await self._load_evidence_records(session, current)
        candidates = self._current_evidence_candidates(current, records)
        learning_profile = await self.learning_profile(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        automation_policy = await self.get_automation_policy(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        now = datetime.now(UTC).replace(tzinfo=None)
        assessments: list[PromiseAutopilotAssessment] = []
        applied_count = 0

        for entry in entries:
            assessment = self._autopilot_assessment(entry, current, candidates, now)
            threshold = self._status_threshold(learning_profile, assessment.suggested_status)
            assessment.threshold = threshold
            assessment.evidence_locked = self._has_locked_evidence(assessment)
            if apply and self._should_apply_autopilot(
                assessment,
                entry=entry,
                threshold=threshold,
                evidence_lock_enabled=learning_profile.evidence_lock_enabled,
                policy=automation_policy,
            ):
                old_value = self._ledger_snapshot(entry)
                entry.status = assessment.suggested_status
                if assessment.suggested_status == "completed":
                    entry.completed_at = now
                elif assessment.suggested_status == "dismissed":
                    entry.completed_at = None
                    entry.dismissed_reason = "autopilot"
                else:
                    entry.completed_at = None
                if assessment.suggested_status in {"blocked", "delayed"}:
                    entry.risk_level = "high"
                else:
                    entry.risk_level = self._ledger_risk_level(
                        entry.priority,
                        entry.due_at,
                        entry.occurrences,
                    )
                entry.updated_at = now
                assessment.applied = True
                applied_count += 1
                self._record_ledger_event(
                    session,
                    entry,
                    "autopilot_applied",
                    old_value=old_value,
                    new_value={
                        **self._ledger_snapshot(entry),
                        "autopilot": assessment.model_dump(mode="json"),
                        "evidence_pack": (
                            assessment.evidence_pack.model_dump(mode="json")
                            if assessment.evidence_pack
                            else None
                        ),
                    },
                    actor_user_id=owner_id,
                )
            elif apply and assessment.confidence >= 0.55:
                self._record_ledger_event(
                    session,
                    entry,
                    "autopilot_assessed",
                    new_value=assessment.model_dump(mode="json"),
                    actor_user_id=owner_id,
                )
            assessments.append(assessment)

        if apply:
            await session.commit()
        mode = "apply" if apply else "preview"
        for assessment in assessments:
            record_promise_radar_autopilot(
                mode=mode,
                suggested_status=assessment.suggested_status,
                applied=assessment.applied,
            )
        return PromiseAutopilotResponse(
            task_id=task_id,
            autopilot_threshold=learning_profile.autopilot_threshold,
            status_thresholds=learning_profile.status_thresholds,
            evidence_lock_enforced=learning_profile.evidence_lock_enabled,
            preview_mode=not apply,
            assessed_count=len(assessments),
            applied_count=applied_count,
            assessments=assessments,
        )

    async def build_autopilot_review_queue(
        self,
        session: AsyncSession,
        task_id: str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 50,
    ) -> PromiseAutopilotReviewQueue:
        """Build a pending-review queue for Autopilot decisions without mutating entries."""
        preview = await self.run_autopilot(
            session,
            task_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            apply=False,
            limit=limit,
        )
        candidate_assessments = [
            assessment
            for assessment in preview.assessments
            if assessment.conflict_detected
            or assessment.suggested_status != assessment.previous_status
            or assessment.confidence >= max(0.55, assessment.threshold)
        ]
        rejected_keys = await self._rejected_review_keys(
            session,
            task_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        candidate_assessments = [
            assessment
            for assessment in candidate_assessments
            if (
                assessment.ledger_entry_id,
                assessment.suggested_status,
            )
            not in rejected_keys
        ]
        if not candidate_assessments:
            record_promise_radar_review_queue(0)
            return PromiseAutopilotReviewQueue(
                task_id=task_id,
                queue_count=0,
                actionable_count=0,
                conflict_count=0,
                items=[],
            )

        entry_ids = [
            entry_id
            for assessment in candidate_assessments
            if (entry_id := self._coerce_uuid(assessment.ledger_entry_id)) is not None
        ]
        result = await session.execute(
            select(PromiseLedgerEntry).where(PromiseLedgerEntry.id.in_(entry_ids))
        )
        entries_by_id = {str(entry.id): entry for entry in result.scalars().all()}
        queued_at = datetime.now(UTC).replace(tzinfo=None)
        items: list[PromiseAutopilotReviewItem] = []
        for assessment in candidate_assessments:
            entry = entries_by_id.get(assessment.ledger_entry_id)
            if entry is None:
                continue
            decision_required = (
                assessment.conflict_detected
                or assessment.suggested_status != assessment.previous_status
            )
            items.append(
                PromiseAutopilotReviewItem(
                    ledger_entry=self._entry_to_response(entry),
                    assessment=assessment,
                    queued_at=queued_at,
                    decision_required=decision_required,
                )
            )
        record_promise_radar_review_queue(len(items))
        return PromiseAutopilotReviewQueue(
            task_id=task_id,
            queue_count=len(items),
            actionable_count=sum(
                1
                for item in items
                if not item.assessment.conflict_detected
                and item.assessment.suggested_status != item.assessment.previous_status
            ),
            conflict_count=sum(1 for item in items if item.assessment.conflict_detected),
            items=items,
        )

    async def reject_autopilot_review_item(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseAutopilotRejectRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseLearningFeedbackResponse:
        """Persist a Review Queue rejection and feed it into the learning loop."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        self._record_ledger_event(
            session,
            entry,
            "autopilot_review_rejected",
            new_value={
                "task_id": payload.task_id,
                "suggested_status": payload.suggested_status,
                "previous_status": entry.status,
            },
            note=payload.note,
            actor_user_id=owner_id,
        )
        await session.flush()
        return await self.record_learning_feedback(
            session,
            entry_id,
            PromiseLearningFeedbackRequest(
                expected_status=entry.status,
                predicted_status=payload.suggested_status,
                correction_type="autopilot",
                note=payload.note or "Review Queue에서 자동 판정을 거절했습니다.",
            ),
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )

    async def confirm_autopilot_assessment(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseAutopilotConfirmRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseAutopilotAssessment:
        """Apply a previewed Autopilot assessment only after user confirmation."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        current = await self._get_record(session, payload.task_id)
        if current is None:
            raise ValueError("회의 요약을 찾을 수 없습니다")
        records = await self._load_evidence_records(session, current)
        candidates = self._current_evidence_candidates(current, records)
        now = datetime.now(UTC).replace(tzinfo=None)
        learning_profile = await self.learning_profile(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        assessment = self._autopilot_assessment(entry, current, candidates, now)
        assessment.threshold = self._status_threshold(learning_profile, assessment.suggested_status)
        assessment.evidence_locked = self._has_locked_evidence(assessment)
        if payload.suggested_status and payload.suggested_status != assessment.suggested_status:
            raise ValueError("현재 회의 근거와 요청한 자동 판정 상태가 일치하지 않습니다")
        if assessment.conflict_detected:
            raise ValueError(assessment.conflict_reason or "충돌하는 약속 상태 신호가 있습니다")
        if assessment.suggested_status == assessment.previous_status:
            raise ValueError("확정할 상태 변경이 없습니다")

        old_value = self._ledger_snapshot(entry)
        entry.status = assessment.suggested_status
        entry.user_confirmed = True
        if assessment.suggested_status == "completed":
            entry.completed_at = now
        elif assessment.suggested_status == "dismissed":
            entry.completed_at = None
            entry.dismissed_reason = "autopilot_confirmed"
        else:
            entry.completed_at = None
        if assessment.suggested_status in {"blocked", "delayed"}:
            entry.risk_level = "high"
        else:
            entry.risk_level = self._ledger_risk_level(
                entry.priority,
                entry.due_at,
                entry.occurrences,
            )
        entry.updated_at = now
        assessment.applied = True
        assessment.requires_confirmation = False
        self._record_ledger_event(
            session,
            entry,
            "autopilot_confirmed",
            old_value=old_value,
            new_value={
                **self._ledger_snapshot(entry),
                "autopilot": assessment.model_dump(mode="json"),
                "evidence_pack": (
                    assessment.evidence_pack.model_dump(mode="json")
                    if assessment.evidence_pack
                    else None
                ),
            },
            note=payload.note,
            actor_user_id=owner_id,
        )
        await session.commit()
        return assessment

    async def undo_autopilot_decision(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseAutopilotUndoRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseAutopilotUndoResponse:
        """Revert the latest applied/confirmed Autopilot decision and optionally quarantine it."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(
                PromiseLedgerEvent.ledger_entry_id == entry.id,
                PromiseLedgerEvent.event_type.in_(["autopilot_applied", "autopilot_confirmed"]),
            )
            .order_by(PromiseLedgerEvent.created_at.desc())
            .limit(1)
        )
        event = result.scalar_one_or_none()
        if event is None or not isinstance(event.old_value, dict):
            raise ValueError("되돌릴 자동 판정 이력이 없습니다")

        current_snapshot = self._ledger_snapshot(entry)
        suggested_status = (
            event.new_value.get("autopilot", {}).get("suggested_status")
            if isinstance(event.new_value, dict)
            and isinstance(event.new_value.get("autopilot"), dict)
            else current_snapshot.get("status")
        )
        self._apply_ledger_snapshot(entry, event.old_value)
        entry.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._record_ledger_event(
            session,
            entry,
            "autopilot_undone",
            old_value=current_snapshot,
            new_value={
                **self._ledger_snapshot(entry),
                "reverted_event_id": str(event.id),
                "suggested_status": suggested_status,
                "quarantined": payload.quarantine,
            },
            note=payload.reason or "사용자가 자동 판정을 되돌렸습니다.",
            actor_user_id=owner_id,
        )
        await session.flush()
        if payload.quarantine:
            self._record_ledger_event(
                session,
                entry,
                "autopilot_quarantined",
                new_value={
                    "reverted_event_id": str(event.id),
                    "suggested_status": suggested_status,
                    "previous_status": current_snapshot.get("status"),
                },
                note=payload.reason or "Undo 후 같은 자동 판정 패턴을 격리했습니다.",
                actor_user_id=owner_id,
            )
        await session.commit()
        await session.refresh(entry)
        return PromiseAutopilotUndoResponse(
            ledger_entry=self._entry_to_response(entry),
            reverted_event_id=str(event.id),
            quarantined=payload.quarantine,
            message="자동 판정을 이전 상태로 되돌렸습니다.",
        )

    async def build_autopilot_quarantine_summary(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 200,
    ) -> PromiseAutopilotQuarantineSummary:
        """Summarize rejected/undone Autopilot patterns that should remain in review."""
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(
                self._event_scope_condition(owner_id, guest_session_id, team_id=team_id),
                PromiseLedgerEvent.event_type.in_(
                    [
                        "autopilot_review_rejected",
                        "autopilot_undone",
                        "autopilot_quarantined",
                    ]
                ),
            )
            .order_by(PromiseLedgerEvent.created_at.desc())
            .limit(max(1, min(limit, 500)))
        )
        statuses: Counter[str] = Counter()
        affected_entries: list[str] = []
        rejected_count = 0
        quarantined_count = 0
        for event in result.scalars().all():
            value = event.new_value if isinstance(event.new_value, dict) else {}
            status = str(value.get("suggested_status") or value.get("predicted_status") or "")
            if status:
                statuses[status] += 1
            entry_id_text = str(event.ledger_entry_id)
            if entry_id_text not in affected_entries:
                affected_entries.append(entry_id_text)
            if event.event_type == "autopilot_review_rejected":
                rejected_count += 1
            else:
                quarantined_count += 1
        notes = ["격리된 자동 판정은 같은 회의/entry/status 후보로 즉시 재등장하지 않습니다."]
        if statuses:
            notes.append(f"주의 상태: {', '.join(status for status, _ in statuses.most_common(4))}")
        return PromiseAutopilotQuarantineSummary(
            quarantined_count=quarantined_count,
            rejected_count=rejected_count,
            affected_statuses=dict(statuses),
            affected_entries=affected_entries[:20],
            notes=notes,
        )

    async def build_live_coach_summary(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 8,
    ) -> PromiseLiveCoachSummary:
        """Build live meeting prompts from unresolved promises."""
        brief = await self.build_pre_meeting_brief(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        return self._build_live_coach_summary(brief)

    async def build_evidence_room_summary(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 50,
    ) -> PromiseEvidenceRoomSummary:
        """Summarize privacy-safe evidence sharing readiness."""
        review_queue = await self.build_autopilot_review_inbox(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        evidence_audit = self._evidence_audit_summary(review_queue)
        evidence_permissions = self._evidence_permission_summary(
            review_queue,
            evidence_audit,
            scope=self._scope_label(owner_id, guest_session_id, team_id),
        )
        return self._evidence_room_summary(
            review_queue,
            evidence_permissions,
            scope=self._scope_label(owner_id, guest_session_id, team_id),
        )

    async def create_evidence_room_link(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseEvidenceRoomLinkRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseEvidenceRoomLinkResponse:
        """Create a short-lived redacted evidence payload for external review."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")

        redacted: list[dict[str, Any]] = []
        redaction_applied = False
        for raw in entry.evidence or []:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            if not payload.include_transcript_quotes and "transcript" in item:
                item["transcript"] = "[redacted]"
                redaction_applied = True
            if not payload.include_speaker_labels and "speaker_label" in item:
                item["speaker_label"] = "[redacted]"
                redaction_applied = True
            if not payload.include_timestamps:
                for key in ("start_seconds", "end_seconds"):
                    if key in item:
                        item.pop(key, None)
                        redaction_applied = True
            redacted.append(item)
            if len(redacted) >= 5:
                break

        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=payload.ttl_hours)
        token_preview = secrets.token_urlsafe(18)[:16]
        self._record_ledger_event(
            session,
            entry,
            "evidence_room_link_created",
            new_value={
                "ttl_hours": payload.ttl_hours,
                "expires_at": expires_at.isoformat(),
                "evidence_count": len(redacted),
                "redaction_applied": redaction_applied,
                "include_transcript_quotes": payload.include_transcript_quotes,
                "include_timestamps": payload.include_timestamps,
                "include_speaker_labels": payload.include_speaker_labels,
            },
            note=payload.reason or "Evidence Room redacted link created.",
            actor_user_id=owner_id,
        )
        await session.commit()
        return PromiseEvidenceRoomLinkResponse(
            ledger_entry_id=str(entry.id),
            share_token_preview=token_preview,
            expires_at=expires_at,
            redaction_applied=redaction_applied,
            evidence_count=len(redacted),
            redacted_evidence=redacted,
            policy_notes=[
                "원본 transcript/speaker label은 기본적으로 redaction됩니다.",
                "공유 링크는 짧은 TTL로만 사용하고 토큰 원문은 서버 로그에 남기지 않습니다.",
            ],
        )

    async def build_meeting_recipe_policy(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseMeetingRecipePolicy:
        """Infer the active meeting recipe policy from current Promise Radar state."""
        dashboard = await self.build_dashboard(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=50,
        )
        learning_insight = await self.build_learning_insights(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=200,
        )
        evidence_room = await self.build_evidence_room_summary(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=50,
        )
        evidence_permissions = PromiseEvidencePermissionSummary(
            scope=evidence_room.scope,
            export_allowed=evidence_room.blocked_count == 0,
            redaction_required=evidence_room.redaction_required_count > 0,
            contains_speaker_data=evidence_room.redaction_required_count > 0,
            contains_timestamp_data=evidence_room.redaction_required_count > 0,
            allowed_evidence_count=evidence_room.share_ready_count,
            blocked_export_count=evidence_room.blocked_count,
            policy_notes=evidence_room.policy_notes,
        )
        return self._meeting_recipe_policy(
            dashboard=dashboard,
            learning_insight=learning_insight,
            evidence_permissions=evidence_permissions,
        )

    def build_google_tasks_oauth_start(
        self,
        payload: PromiseGoogleTasksOAuthStartRequest,
    ) -> PromiseGoogleTasksOAuthStartResponse:
        """Build a Google Tasks OAuth URL for native app handoff."""
        client_ids = [
            item.strip() for item in str(settings.google_client_id or "").split(",") if item.strip()
        ]
        client_id = client_ids[0] if client_ids else ""
        redirect_uri = payload.redirect_uri or "com.voicetextnote.app:/oauth2redirect/google-tasks"
        state = payload.state or secrets.token_urlsafe(24)
        scopes = ["https://www.googleapis.com/auth/tasks"]
        missing_setup: list[str] = []
        if not client_id:
            missing_setup.append("GOOGLE_CLIENT_ID")
        params: dict[str, str] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "state": state,
            "prompt": payload.prompt,
        }
        if payload.code_challenge:
            params["code_challenge"] = payload.code_challenge
            params["code_challenge_method"] = payload.code_challenge_method
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params, safe=":/")
        return PromiseGoogleTasksOAuthStartResponse(
            ready=not missing_setup,
            auth_url=auth_url,
            state=state,
            redirect_uri=redirect_uri,
            scopes=scopes,
            missing_setup=missing_setup,
            token_handling=(
                "authorization code만 앱에서 백엔드로 전달하고 access token은 "
                "요청 처리 중에만 사용합니다."
            ),
        )

    async def resolve_autopilot_conflict(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseConflictResolveRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseLedgerEntryResponse:
        """Resolve a conflicting Autopilot assessment with an explicit user decision."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        status = payload.status.strip().lower()
        if status not in _VALID_LEDGER_STATUSES:
            raise ValueError("지원하지 않는 약속 상태입니다")

        now = datetime.now(UTC).replace(tzinfo=None)
        old_value = self._ledger_snapshot(entry)
        entry.status = status
        entry.user_confirmed = True
        if status == "completed":
            entry.completed_at = now
            entry.dismissed_reason = None
        elif status == "dismissed":
            entry.completed_at = None
            entry.dismissed_reason = payload.note or "conflict_resolved"
        else:
            entry.completed_at = None
            if status != "dismissed":
                entry.dismissed_reason = None
        if status in {"blocked", "delayed"}:
            entry.risk_level = "high"
        else:
            entry.risk_level = self._ledger_risk_level(
                entry.priority,
                entry.due_at,
                entry.occurrences,
            )
        entry.updated_at = now
        self._record_ledger_event(
            session,
            entry,
            "conflict_resolved",
            old_value=old_value,
            new_value={
                **self._ledger_snapshot(entry),
                "resolution": status,
            },
            note=payload.note,
            actor_user_id=owner_id,
        )
        await session.commit()
        await session.refresh(entry)
        return self._entry_to_response(entry)

    async def explain_ledger_entry_match(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        *,
        task_id: str | None = None,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseMatchExplanation:
        """Explain why one ledger entry matches the current meeting or its stored evidence."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")

        if task_id:
            current = await self._get_record(session, task_id)
            if current is None:
                raise ValueError("회의 요약을 찾을 수 없습니다")
            records = await self._load_evidence_records(session, current)
            candidates = self._current_evidence_candidates(current, records)
            return self._explain_entry_against_candidates(entry, candidates)

        evidence = []
        for item in entry.evidence or []:
            if isinstance(item, dict):
                evidence.append(PromiseRadarEvidence(**item))
        matched = evidence[0].transcript if evidence else entry.text
        similarity = self._promise_similarity(entry.text, matched, entry.owner_name, None)
        return PromiseMatchExplanation(
            ledger_entry_id=str(entry.id),
            matched_task_id=entry.last_source_task_id,
            matched_text=matched,
            similarity=round(similarity, 3),
            overlap_terms=sorted(set(self._tokens(entry.text)) & set(self._tokens(matched)))[:8],
            confidence_factors=self._confidence_factors(entry, similarity, evidence),
            rationale=self._match_rationale(entry, similarity, matched),
            evidence=evidence[:3],
        )

    async def latest_evidence_pack(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseEvidencePack:
        """Return the latest immutable Evidence Pack stored on ledger events."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(PromiseLedgerEvent.ledger_entry_id == entry.id)
            .where(
                PromiseLedgerEvent.event_type.in_(
                    ["autopilot_applied", "autopilot_confirmed", "autopilot_assessed"]
                )
            )
            .order_by(PromiseLedgerEvent.created_at.desc())
            .limit(20)
        )
        for event in result.scalars().all():
            value = event.new_value if isinstance(event.new_value, dict) else {}
            pack = value.get("evidence_pack")
            if isinstance(pack, dict):
                return PromiseEvidencePack(**pack)
            autopilot = value.get("autopilot")
            if isinstance(autopilot, dict) and isinstance(autopilot.get("evidence_pack"), dict):
                return PromiseEvidencePack(**autopilot["evidence_pack"])
        raise ValueError("저장된 Evidence Pack이 없습니다")

    async def evidence_comparison(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseEvidenceComparison:
        """Compare original ledger evidence with the latest Autopilot Evidence Pack."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        previous_evidence = [
            PromiseRadarEvidence(**item) for item in entry.evidence or [] if isinstance(item, dict)
        ]
        try:
            pack = await self.latest_evidence_pack(
                session,
                entry_id,
                owner_id=owner_id,
                guest_session_id=guest_session_id,
                team_id=team_id,
            )
        except ValueError:
            pack = None
        previous_text = previous_evidence[0].transcript if previous_evidence else entry.text
        current_text = pack.matched_text if pack else None
        previous_similarity = round(
            self._promise_similarity(entry.text, previous_text, entry.owner_name, None),
            3,
        )
        current_similarity = pack.similarity if pack else None
        shared_terms = sorted(
            set(self._tokens(previous_text)) & set(self._tokens(current_text or ""))
        )[:10]
        delta = (
            round(current_similarity - previous_similarity, 3)
            if current_similarity is not None
            else None
        )
        summary = (
            "현재 자동 판정 근거가 기존 원장 근거보다 강합니다."
            if delta is not None and delta >= 0
            else "기존 원장 근거와 현재 자동 판정 근거의 차이를 확인해야 합니다."
        )
        return PromiseEvidenceComparison(
            ledger_entry_id=str(entry.id),
            previous_text=previous_text,
            current_text=current_text,
            previous_similarity=previous_similarity,
            current_similarity=current_similarity,
            similarity_delta=delta,
            shared_terms=shared_terms,
            previous_evidence=previous_evidence[:3],
            current_pack=pack,
            summary=summary,
        )

    async def export_calendar_event(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseCalendarExportResponse:
        """Build a concrete calendar handoff payload for Google Calendar and ICS import."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")

        response = self._entry_to_response(entry)
        candidate = self._reminder_candidate(response)
        start = response.due_at or response.reminder_at or datetime.now(UTC).replace(tzinfo=None)
        end = start + timedelta(minutes=30)
        title = candidate.title
        description = self._calendar_description(response)
        uid = f"promise-{response.id}@voice-to-textnote"
        ics_content = self._ics_content(
            uid=uid,
            title=title,
            description=description,
            start=start,
            end=end,
            promise_id=response.id,
        )
        google_url = self._google_calendar_url(title, description, start, end)
        entry.calendar_event = {
            **(candidate.calendar_event or {}),
            "uid": uid,
            "google_calendar_url": google_url,
            "ics_filename": f"promise-{response.id}.ics",
        }
        entry.reminder_at = candidate.reminder_at
        entry.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._record_ledger_event(
            session,
            entry,
            "calendar_export_created",
            new_value=entry.calendar_event,
            actor_user_id=owner_id,
        )
        await session.commit()
        await session.refresh(entry)
        return PromiseCalendarExportResponse(
            ledger_entry_id=response.id,
            title=title,
            due_at=start,
            ics_filename=f"promise-{response.id}.ics",
            ics_content=ics_content,
            google_calendar_url=google_url,
            calendar_event=entry.calendar_event,
        )

    async def suggest_assignees(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 5,
    ) -> list[PromiseAssigneeSuggestion]:
        """Suggest a concrete app user for a promise owner/speaker."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        return await self._assignee_suggestions(session, entry, limit=limit)

    async def record_learning_feedback(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseLearningFeedbackRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseLearningFeedbackResponse:
        """Record user feedback so later Autopilot runs can adapt thresholds."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")

        value = {
            "correction_type": payload.correction_type,
            "expected_status": payload.expected_status,
            "predicted_status": payload.predicted_status,
            "expected_assigned_user_id": payload.expected_assigned_user_id,
            "expected_owner": payload.expected_owner,
            "current_status": entry.status,
            "current_assigned_user_id": (
                str(entry.assigned_user_id) if entry.assigned_user_id else None
            ),
            "current_owner": entry.owner_name,
        }
        self._record_ledger_event(
            session,
            entry,
            "learning_feedback",
            new_value=value,
            note=payload.note,
            actor_user_id=owner_id,
        )
        await session.commit()
        profile = await self.learning_profile(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        return PromiseLearningFeedbackResponse(
            ledger_entry_id=str(entry.id),
            recorded=True,
            learning_profile=profile,
        )

    async def learning_profile(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 200,
    ) -> PromiseLearningProfile:
        """Build a scoped learning profile from user corrections and confirmations."""
        events = await self._scoped_events(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        false_positive = 0
        confirmed = 0
        status_false_positive: dict[str, int] = {}
        status_confirmed: dict[str, int] = {}
        assignee_corrections = 0
        aliases: dict[str, str] = {}
        for event in events:
            event_type = event.event_type
            old = event.old_value or {}
            new = event.new_value or {}
            if event_type == "learning_feedback":
                expected_status = self._clean_optional(new.get("expected_status"))
                current_status = self._clean_optional(new.get("current_status"))
                predicted_status = (
                    self._clean_optional(new.get("predicted_status")) or current_status
                )
                if expected_status and predicted_status and expected_status != predicted_status:
                    false_positive += 1
                    status_false_positive[predicted_status] = (
                        status_false_positive.get(predicted_status, 0) + 1
                    )
                if new.get("expected_assigned_user_id") or new.get("expected_owner"):
                    assignee_corrections += 1
                if new.get("expected_owner") and new.get("current_owner"):
                    aliases[str(new["current_owner"])] = str(new["expected_owner"])
                continue
            if event_type == "updated":
                old_status = self._clean_optional(old.get("status"))
                new_status = self._clean_optional(new.get("status"))
                if old_status in _CLOSED_LEDGER_STATUSES | {"delayed"} and new_status in {
                    "open",
                    "blocked",
                    "changed",
                }:
                    false_positive += 1
                    if old_status:
                        status_false_positive[old_status] = (
                            status_false_positive.get(old_status, 0) + 1
                        )
                elif new.get("user_confirmed") is True:
                    confirmed += 1
                    if new_status:
                        status_confirmed[new_status] = status_confirmed.get(new_status, 0) + 1
                if old.get("assigned_user_id") != new.get("assigned_user_id"):
                    assignee_corrections += 1
                if old.get("owner") and new.get("owner") and old.get("owner") != new.get("owner"):
                    aliases[str(old["owner"])] = str(new["owner"])
            elif event_type in {"autopilot_applied", "autopilot_confirmed"}:
                confirmed += 1
                suggested = None
                if isinstance(new.get("autopilot"), dict):
                    suggested = self._clean_optional(new["autopilot"].get("suggested_status"))
                if suggested:
                    status_confirmed[suggested] = status_confirmed.get(suggested, 0) + 1

        adjustment = min(0.15, false_positive * 0.03) - min(0.06, confirmed * 0.01)
        threshold = max(0.62, min(0.86, _AUTOPILOT_APPLY_THRESHOLD + adjustment))
        status_thresholds = {
            status: self._status_specific_threshold(
                status_false_positive.get(status, 0),
                status_confirmed.get(status, 0),
            )
            for status in ("completed", "delayed", "changed", "dismissed")
        }
        owner_aliases = await self._owner_alias_graph(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            event_aliases=aliases,
        )
        return PromiseLearningProfile(
            scope=self._scope_label(owner_id, guest_session_id, team_id),
            autopilot_threshold=round(threshold, 3),
            status_thresholds=status_thresholds,
            false_positive_count=false_positive,
            confirmed_count=confirmed,
            status_false_positive_count=status_false_positive,
            status_confirmed_count=status_confirmed,
            assignee_correction_count=assignee_corrections,
            evidence_lock_enabled=True,
            learned_owner_aliases=aliases,
            owner_aliases=owner_aliases,
        )

    async def get_automation_policy(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseAutomationPolicy:
        """Return the latest scoped automation policy, falling back to conservative defaults."""
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(
                self._event_scope_condition(owner_id, guest_session_id, team_id=team_id),
                PromiseLedgerEvent.event_type == "automation_policy_updated",
            )
            .order_by(PromiseLedgerEvent.created_at.desc())
            .limit(1)
        )
        event = result.scalar_one_or_none()
        value = event.new_value if event and isinstance(event.new_value, dict) else {}
        return self._automation_policy_from_value(
            value,
            scope=self._scope_label(owner_id, guest_session_id, team_id),
            updated_at=event.created_at if event else None,
        )

    async def update_automation_policy(
        self,
        session: AsyncSession,
        payload: PromiseAutomationPolicyUpdateRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseAutomationPolicy:
        """Persist a scoped automation policy as an auditable ledger event."""
        policy = self._automation_policy_from_value(
            payload.model_dump(mode="json"),
            scope=self._scope_label(owner_id, guest_session_id, team_id),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        result = await session.execute(
            select(PromiseLedgerEntry)
            .where(self._ledger_scope_condition(owner_id, guest_session_id, team_id=team_id))
            .order_by(PromiseLedgerEntry.updated_at.desc())
            .limit(1)
        )
        anchor = result.scalar_one_or_none()
        if anchor is None:
            raise ValueError("정책을 저장할 약속 원장 항목이 필요합니다")
        self._record_ledger_event(
            session,
            anchor,
            "automation_policy_updated",
            new_value=policy.model_dump(mode="json"),
            actor_user_id=owner_id,
        )
        await session.commit()
        return policy

    async def get_digest_preference(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseDigestPreference:
        """Return the latest scoped scheduled digest preference."""
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(
                self._event_scope_condition(owner_id, guest_session_id, team_id=team_id),
                PromiseLedgerEvent.event_type == "digest_preference_updated",
            )
            .order_by(PromiseLedgerEvent.created_at.desc())
            .limit(1)
        )
        event = result.scalar_one_or_none()
        value = event.new_value if event and isinstance(event.new_value, dict) else {}
        return self._digest_preference_from_value(
            value,
            scope=self._scope_label(owner_id, guest_session_id, team_id),
            updated_at=event.created_at if event else None,
        )

    async def update_digest_preference(
        self,
        session: AsyncSession,
        payload: PromiseDigestPreferenceUpdateRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseDigestPreference:
        """Persist scheduled digest preference as an auditable ledger event."""
        preference = self._digest_preference_from_value(
            payload.model_dump(mode="json"),
            scope=self._scope_label(owner_id, guest_session_id, team_id),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        result = await session.execute(
            select(PromiseLedgerEntry)
            .where(self._ledger_scope_condition(owner_id, guest_session_id, team_id=team_id))
            .order_by(PromiseLedgerEntry.updated_at.desc())
            .limit(1)
        )
        anchor = result.scalar_one_or_none()
        if anchor is None:
            raise ValueError("Digest 설정을 저장할 약속 원장 항목이 필요합니다")
        self._record_ledger_event(
            session,
            anchor,
            "digest_preference_updated",
            new_value=preference.model_dump(mode="json"),
            actor_user_id=owner_id,
        )
        await session.commit()
        return preference

    async def build_ledger_timeline(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 50,
    ) -> PromiseTimelineResponse:
        """Return a user-readable lifecycle timeline for one promise."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(PromiseLedgerEvent.ledger_entry_id == entry.id)
            .order_by(PromiseLedgerEvent.created_at.asc())
            .limit(max(1, min(limit, 100)))
        )
        events = list(result.scalars().all())
        items = [self._timeline_item(event) for event in events]
        if not items:
            items.append(
                PromiseTimelineItem(
                    id=str(entry.id),
                    event_type="detected",
                    label="약속이 처음 감지됐습니다.",
                    created_at=entry.first_seen_at,
                    status_after=entry.status,
                    source_task_id=entry.source_task_id,
                )
            )
        return PromiseTimelineResponse(
            ledger_entry_id=str(entry.id),
            current_status=entry.status,
            items=items,
        )

    async def build_pre_meeting_brief(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 8,
    ) -> PromisePreMeetingBrief:
        """Build a compact brief to show before starting a new recording."""
        briefing = await self.build_next_meeting_briefing(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            limit=limit,
        )
        readiness = max(
            0,
            100
            - briefing.high_risk_count * 18
            - briefing.overdue_count * 14
            - briefing.due_soon_count * 6,
        )
        summary = (
            "바로 시작해도 좋습니다."
            if not briefing.promises
            else f"회의 전 확인할 약속 {len(briefing.promises[:limit])}개가 있습니다."
        )
        return PromisePreMeetingBrief(
            title="회의 시작 전 약속 브리프",
            readiness_score=readiness,
            summary=summary,
            promises=briefing.promises[:limit],
            questions=briefing.questions[:limit],
            checkpoints=[self._briefing_checkpoint(entry) for entry in briefing.promises[:limit]],
        )

    async def build_digest(
        self,
        session: AsyncSession,
        *,
        cadence: str = "daily",
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
        limit: int = 12,
    ) -> PromiseDigest:
        """Build a daily/weekly unresolved promise digest."""
        normalized = cadence.lower().strip()
        if normalized not in {"daily", "weekly"}:
            raise ValueError("지원하지 않는 digest 주기입니다")
        entries = await self.list_ledger_entries(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            statuses=_OPEN_LEDGER_STATUSES,
            limit=limit,
        )
        now = datetime.now(UTC).replace(tzinfo=None)
        horizon = now + (timedelta(days=1) if normalized == "daily" else timedelta(days=7))
        due_soon = [entry for entry in entries if entry.due_at and now <= entry.due_at <= horizon]
        overdue = [entry for entry in entries if entry.due_at and entry.due_at < now]
        high_risk = [entry for entry in entries if entry.risk_level == "high"]
        lines = [
            f"열린 약속 {len(entries)}개",
            f"기한 초과 {len(overdue)}개",
            f"{'오늘' if normalized == 'daily' else '이번 주'} 확인 {len(due_soon)}개",
            f"고위험 {len(high_risk)}개",
        ]
        for entry in sorted(
            entries,
            key=lambda item: (
                item.risk_level != "high",
                item.due_at is None,
                item.due_at or now + timedelta(days=365),
            ),
        )[:5]:
            lines.append(f"- {entry.owner or '미지정'}: {entry.text}")
        return PromiseDigest(
            cadence=normalized,
            title="오늘의 약속 레이더" if normalized == "daily" else "이번 주 약속 레이더",
            generated_at=now,
            open_count=len(entries),
            overdue_count=len(overdue),
            due_soon_count=len(due_soon),
            high_risk_count=len(high_risk),
            lines=lines,
            promises=entries[:limit],
        )

    async def export_external_task(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseExternalExportRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseExternalExportResponse:
        """Export one promise to an external work tool."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        provider = payload.provider.strip().lower()
        response_entry = self._entry_to_response(entry)
        if provider == "google_tasks":
            return await self._export_google_task(
                session,
                entry,
                response_entry,
                payload,
                actor_user_id=owner_id,
            )
        if provider != "slack":
            raise ValueError("현재 외부 업무도구 연동은 Slack 또는 Google Tasks만 지원합니다")
        slack_payload = self._slack_payload(response_entry)
        webhook_url = os.environ.get("PROMISE_RADAR_SLACK_WEBHOOK_URL", "").strip()
        sent = False
        message = "Slack payload가 생성됐습니다."
        if not payload.dry_run:
            if not webhook_url:
                raise ValueError("PROMISE_RADAR_SLACK_WEBHOOK_URL이 설정되어 있지 않습니다")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=slack_payload)
                response.raise_for_status()
            sent = True
            message = "Slack으로 약속을 전송했습니다."
            self._record_ledger_event(
                session,
                entry,
                "external_exported",
                new_value={"provider": provider, "sent": True},
                actor_user_id=owner_id,
            )
            await session.commit()
            record_promise_radar_external_sync("slack", "export", outcome="sent")
        elif provider == "slack":
            record_promise_radar_external_sync("slack", "export", outcome="dry_run")
        return PromiseExternalExportResponse(
            ledger_entry_id=str(entry.id),
            provider=provider,
            sent=sent,
            payload=slack_payload,
            message=message,
        )

    async def list_google_tasklists(
        self,
        payload: PromiseExternalExportRequest,
    ) -> PromiseGoogleTaskListResponse:
        """List Google Tasks tasklists using a user-granted OAuth access token."""
        token = (payload.access_token or "").strip()
        if not token:
            raise ValueError("Google Tasks tasklist 조회에는 OAuth access token이 필요합니다")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://tasks.googleapis.com/tasks/v1/users/@me/lists",
                headers={"Authorization": f"Bearer {token}"},
                params={"maxResults": 100},
            )
            response.raise_for_status()
        tasklists = [
            PromiseGoogleTaskList(
                id=str(item.get("id") or ""),
                title=str(item.get("title") or "Untitled"),
                updated=item.get("updated"),
            )
            for item in response.json().get("items", [])
            if item.get("id")
        ]
        return PromiseGoogleTaskListResponse(tasklists=tasklists)

    async def sync_external_task(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseExternalTaskSyncRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseExternalTaskSyncResponse:
        """Sync one external work-tool task state back to the Promise Ledger."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        provider = payload.provider.strip().lower()
        if provider != "google_tasks":
            raise ValueError("현재 동기화는 Google Tasks만 지원합니다")
        token = (payload.access_token or "").strip()
        if not token:
            raise ValueError("Google Tasks 동기화에는 OAuth access token이 필요합니다")
        metadata = self._google_task_metadata(entry)
        tasklist = payload.tasklist.strip() or metadata.get("tasklist") or "@default"
        external_id = (payload.external_id or metadata.get("external_id") or "").strip()
        if not external_id:
            raise ValueError("동기화할 Google Tasks task id가 없습니다")
        endpoint = (
            f"https://tasks.googleapis.com/tasks/v1/lists/{quote(tasklist, safe='@')}"
            f"/tasks/{quote(external_id, safe='')}"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                endpoint,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
        task = response.json()
        old_value = self._ledger_snapshot(entry)
        google_status = str(task.get("status") or "")
        if google_status == "completed" and entry.status != "completed":
            moment = datetime.now(UTC).replace(tzinfo=None)
            entry.status = "completed"
            entry.completed_at = moment
            entry.user_confirmed = True
            entry.updated_at = moment
        self._record_ledger_event(
            session,
            entry,
            "external_task_synced",
            old_value=old_value,
            new_value={
                **self._ledger_snapshot(entry),
                "provider": "google_tasks",
                "external_id": external_id,
                "tasklist": tasklist,
                "external_status": google_status,
            },
            actor_user_id=owner_id,
        )
        await session.commit()
        record_promise_radar_external_sync("google_tasks", "sync", outcome="synced")
        return PromiseExternalTaskSyncResponse(
            ledger_entry_id=str(entry.id),
            provider="google_tasks",
            synced=True,
            status=google_status,
            message="Google Tasks 상태를 동기화했습니다.",
            sync_contract=self._external_sync_contract(
                entry,
                provider="google_tasks",
                tasklist=tasklist,
                external_id=external_id,
            ),
        )

    async def update_external_task(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        payload: PromiseExternalTaskUpdateRequest,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
        team_id: UUID | str | None = None,
    ) -> PromiseExternalTaskSyncResponse:
        """Push a Promise Ledger state change to an exported external task."""
        entry = await self._get_scoped_ledger_entry(
            session,
            entry_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
        )
        if entry is None:
            raise ValueError("약속 원장 항목을 찾을 수 없습니다")
        provider = payload.provider.strip().lower()
        if provider != "google_tasks":
            raise ValueError("현재 외부 task 업데이트는 Google Tasks만 지원합니다")
        token = (payload.access_token or "").strip()
        if not token:
            raise ValueError("Google Tasks 업데이트에는 OAuth access token이 필요합니다")
        metadata = self._google_task_metadata(entry)
        tasklist = payload.tasklist.strip() or metadata.get("tasklist") or "@default"
        external_id = (payload.external_id or metadata.get("external_id") or "").strip()
        if not external_id:
            raise ValueError("업데이트할 Google Tasks task id가 없습니다")
        status = (
            payload.status or ("completed" if entry.status == "completed" else "needsAction")
        ).strip()
        if status not in {"completed", "needsAction"}:
            raise ValueError("Google Tasks 상태는 completed 또는 needsAction만 지원합니다")
        body: dict[str, Any] = {"status": status}
        if payload.title:
            body["title"] = payload.title
        if status == "completed":
            body["completed"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        endpoint = (
            f"https://tasks.googleapis.com/tasks/v1/lists/{quote(tasklist, safe='@')}"
            f"/tasks/{quote(external_id, safe='')}"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                endpoint,
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
            response.raise_for_status()
        task = response.json()
        entry.calendar_event = {
            **(entry.calendar_event or {}),
            "external_tasks": {
                **((entry.calendar_event or {}).get("external_tasks") or {}),
                "google_tasks": {
                    **metadata,
                    "external_id": external_id,
                    "tasklist": tasklist,
                    "external_url": metadata.get("external_url") or task.get("selfLink"),
                    "external_status": str(task.get("status") or status),
                    "source_task_id": entry.last_source_task_id or entry.source_task_id,
                    "canonical_key": entry.canonical_key,
                    "idempotency_key": self._external_idempotency_key(
                        entry,
                        provider="google_tasks",
                    ),
                    "synced_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
                },
            },
        }
        self._record_ledger_event(
            session,
            entry,
            "external_task_updated",
            new_value={
                "provider": "google_tasks",
                "external_id": external_id,
                "tasklist": tasklist,
                "external_status": str(task.get("status") or status),
            },
            actor_user_id=owner_id,
        )
        await session.commit()
        record_promise_radar_external_sync("google_tasks", "update", outcome="synced")
        return PromiseExternalTaskSyncResponse(
            ledger_entry_id=str(entry.id),
            provider="google_tasks",
            synced=True,
            status=str(task.get("status") or status),
            message="Promise Ledger 상태를 Google Tasks에 반영했습니다.",
            sync_contract=self._external_sync_contract(
                entry,
                provider="google_tasks",
                tasklist=tasklist,
                external_id=external_id,
            ),
        )

    async def _export_google_task(
        self,
        session: AsyncSession,
        entry: PromiseLedgerEntry,
        response_entry: PromiseLedgerEntryResponse,
        payload: PromiseExternalExportRequest,
        *,
        actor_user_id: UUID | str | None,
    ) -> PromiseExternalExportResponse:
        task_payload = self._google_tasks_payload(response_entry)
        tasklist = payload.tasklist.strip() or "@default"
        endpoint = f"https://tasks.googleapis.com/tasks/v1/lists/{quote(tasklist, safe='@')}/tasks"
        query: dict[str, str] = {}
        if payload.parent_task_id:
            query["parent"] = payload.parent_task_id
        if payload.previous_task_id:
            query["previous"] = payload.previous_task_id
        sent = False
        message = "Google Tasks payload가 생성됐습니다."
        external_id = None
        external_url = None
        if not payload.dry_run:
            token = (payload.access_token or "").strip()
            if not token:
                raise ValueError("Google Tasks 전송에는 OAuth access token이 필요합니다")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    endpoint,
                    params=query or None,
                    headers={"Authorization": f"Bearer {token}"},
                    json=task_payload,
                )
                response.raise_for_status()
            result = response.json()
            sent = True
            external_id = str(result.get("id")) if result.get("id") else None
            external_url = result.get("selfLink")
            message = "Google Tasks로 약속을 전송했습니다."
            entry.calendar_event = {
                **(entry.calendar_event or {}),
                "external_tasks": {
                    **((entry.calendar_event or {}).get("external_tasks") or {}),
                    "google_tasks": {
                        "external_id": external_id,
                        "tasklist": tasklist,
                        "external_url": external_url,
                        "source_task_id": entry.last_source_task_id or entry.source_task_id,
                        "canonical_key": entry.canonical_key,
                        "idempotency_key": self._external_idempotency_key(
                            entry,
                            provider="google_tasks",
                        ),
                        "synced_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
                    },
                },
            }
            self._record_ledger_event(
                session,
                entry,
                "external_exported",
                new_value={
                    "provider": "google_tasks",
                    "sent": True,
                    "external_id": external_id,
                    "tasklist": tasklist,
                },
                actor_user_id=actor_user_id,
            )
            await session.commit()
            record_promise_radar_external_sync("google_tasks", "export", outcome="sent")
        else:
            record_promise_radar_external_sync("google_tasks", "export", outcome="dry_run")
        return PromiseExternalExportResponse(
            ledger_entry_id=str(entry.id),
            provider="google_tasks",
            sent=sent,
            payload={
                "endpoint": endpoint,
                "query": query,
                "task": task_payload,
                "sync_contract": self._external_sync_contract(
                    entry,
                    provider="google_tasks",
                    tasklist=tasklist,
                    external_id=external_id,
                ),
            },
            message=message,
            external_id=external_id,
            external_url=external_url,
        )

    def evaluate_accuracy_cases(
        self,
        cases: list[PromiseAccuracyCase],
    ) -> PromiseAccuracyEvaluation:
        """Evaluate Autopilot status predictions against labeled fixture cases."""
        now = datetime.now(UTC).replace(tzinfo=None)
        correct = 0
        predicted_by_status: dict[str, int] = {}
        correct_by_status: dict[str, int] = {}
        bucket_totals: dict[str, int] = {}
        bucket_correct: dict[str, int] = {}
        failures: list[dict[str, Any]] = []
        for case in cases:
            entry = PromiseLedgerEntry(
                source_task_id=f"{case.id}-source",
                last_source_task_id=f"{case.id}-source",
                canonical_key=self._canonical_key(case.entry_text),
                canonical_text=case.entry_text,
                text=case.entry_text,
                owner_name=case.owner,
                status="open",
                priority="medium",
                risk_level="low",
                confidence=0.8,
                due_at=case.due_at,
                occurrences=1,
                first_seen_at=now,
                last_seen_at=now,
            )
            current = TaskResult(
                task_id=f"{case.id}-current",
                task_type="summary",
                status="completed",
                result_data={"summary_text": case.current_text},
                created_at=now,
                completed_at=now,
            )
            assessment = self._autopilot_assessment(
                entry,
                current,
                [
                    (
                        case.current_text,
                        {
                            "source_task_id": current.task_id,
                            "meeting_link": f"/results/{current.task_id}",
                            "transcript": case.current_text,
                        },
                    )
                ],
                now,
            )
            predicted = assessment.suggested_status
            expected = case.expected_status
            bucket = self._confidence_bucket(assessment.confidence)
            bucket_totals[bucket] = bucket_totals.get(bucket, 0) + 1
            predicted_by_status[predicted] = predicted_by_status.get(predicted, 0) + 1
            if predicted == expected:
                correct += 1
                correct_by_status[predicted] = correct_by_status.get(predicted, 0) + 1
                bucket_correct[bucket] = bucket_correct.get(bucket, 0) + 1
            else:
                failures.append(
                    {
                        "id": case.id,
                        "expected": expected,
                        "predicted": predicted,
                        "confidence": assessment.confidence,
                        "reason": assessment.reason,
                    }
                )
        precision = {
            status: round(correct_by_status.get(status, 0) / count, 3)
            for status, count in predicted_by_status.items()
            if count
        }
        confidence_buckets = {
            bucket: {
                "case_count": count,
                "correct_count": bucket_correct.get(bucket, 0),
                "accuracy": round(bucket_correct.get(bucket, 0) / count, 3),
            }
            for bucket, count in sorted(bucket_totals.items())
            if count
        }
        return PromiseAccuracyEvaluation(
            case_count=len(cases),
            correct_count=correct,
            accuracy=round(correct / len(cases), 3) if cases else 0.0,
            status_precision=precision,
            confidence_buckets=confidence_buckets,
            failures=failures,
        )

    def build_accuracy_report(
        self,
        cases: list[PromiseAccuracyCase],
        *,
        fixture_path: str,
        source_manifest_path: str | None = None,
        target_case_count: int = 560,
    ) -> PromiseAccuracyReport:
        """Build an operator-facing accuracy report from fixture labels."""
        evaluation = self.evaluate_accuracy_cases(cases)
        status_counts = Counter(case.expected_status for case in cases)
        source_counts: Counter[str] = Counter()
        source_quality = self._accuracy_source_quality(source_manifest_path)
        source_prefixes, source_case_ids = self._accuracy_source_lookup(source_manifest_path)
        real_meeting_case_count = 0
        for case in cases:
            if case.id.startswith("real-"):
                real_meeting_case_count += 1
                source_id = self._accuracy_case_source_id(
                    case.id,
                    source_prefixes=source_prefixes,
                    source_case_ids=source_case_ids,
                )
                if source_id:
                    source_counts[source_id] += 1
                    continue
            parts = case.id.split("-")
            if case.id.startswith("real-v10-") and len(parts) >= 3:
                source_counts[parts[2]] += 1
            elif case.id.startswith("real-") and len(parts) >= 2:
                source_counts[parts[1]] += 1
            else:
                source_counts["synthetic"] += 1
        manifest_label_count = sum(
            int(item.get("golden_case_count") or 0)
            for item in source_quality.values()
            if isinstance(item, dict)
        )
        coverage = {
            "owner": self._ratio(sum(1 for case in cases if case.owner), len(cases)),
            "due_at": self._ratio(sum(1 for case in cases if case.due_at), len(cases)),
            "source_metadata": self._ratio(
                sum(1 for case in cases if case.source_id or case.id.startswith("real-")),
                len(cases),
            ),
            "real_meeting_target": self._ratio(real_meeting_case_count, target_case_count),
            "manifest_case_match": (
                1.0
                if manifest_label_count == real_meeting_case_count
                else self._ratio(
                    min(manifest_label_count, real_meeting_case_count),
                    max(manifest_label_count, real_meeting_case_count, 1),
                )
            ),
        }
        quality_warnings: list[str] = []
        if real_meeting_case_count < target_case_count:
            quality_warnings.append(
                f"실제 회의 label이 목표보다 부족합니다: {real_meeting_case_count}/{target_case_count}"
            )
        if manifest_label_count and manifest_label_count != real_meeting_case_count:
            quality_warnings.append(
                f"Manifest golden_case_count 합계({manifest_label_count})와 실제 fixture label 수({real_meeting_case_count})가 다릅니다."
            )
        for source_id, quality in source_quality.items():
            if quality.get("candidate_only"):
                continue
            missing = [
                key
                for key in ("url", "license", "verified_with", "rebuild_commands")
                if not quality.get(key)
            ]
            if missing:
                quality_warnings.append(
                    f"{source_id} source manifest 필수 항목 누락: {', '.join(missing)}"
                )
            if "creative commons" not in str(quality.get("license", "")).lower():
                quality_warnings.append(
                    f"{source_id} license가 Creative Commons로 확인되지 않았습니다."
                )
            if not quality.get("subtitle_cache"):
                quality_warnings.append(f"{source_id} subtitle_cache 경로가 없습니다.")
            if not quality.get("representative_audio_clip"):
                quality_warnings.append(f"{source_id} 대표 음성 clip 경로가 없습니다.")
        return PromiseAccuracyReport(
            generated_at=datetime.now(UTC).replace(tzinfo=None),
            fixture_path=fixture_path,
            source_manifest_path=source_manifest_path,
            evaluation=evaluation,
            status_counts=dict(status_counts),
            source_counts=dict(source_counts),
            coverage=coverage,
            source_quality=source_quality,
            quality_warnings=quality_warnings,
            real_meeting_case_count=real_meeting_case_count,
            target_case_count=target_case_count,
            below_target=real_meeting_case_count < target_case_count,
        )

    def _default_accuracy_report(self, *, target_case_count: int = 560) -> PromiseAccuracyReport:
        backend_root = Path(__file__).resolve().parents[1]
        fixture_path = backend_root / "tests" / "fixtures" / "promise_radar_accuracy_cases.json"
        source_manifest_path = (
            backend_root / "tests" / "fixtures" / "promise_radar_real_meeting_sources.json"
        )
        cases = [
            PromiseAccuracyCase(**item)
            for item in json.loads(fixture_path.read_text(encoding="utf-8"))
        ]
        return self.build_accuracy_report(
            cases,
            fixture_path=str(fixture_path.relative_to(backend_root.parent)),
            source_manifest_path=str(source_manifest_path.relative_to(backend_root.parent)),
            target_case_count=target_case_count,
        )

    def evaluate_extraction_cases(
        self,
        cases: list[PromiseExtractionCase],
    ) -> PromiseExtractionRecallEvaluation:
        """Evaluate promise extraction recall before autopilot status scoring."""
        expected_count = 0
        extracted_count = 0
        matched_count = 0
        failures: list[dict[str, Any]] = []
        for case in cases:
            record = TaskResult(
                task_id=f"{case.id}-summary",
                task_type="summary",
                status="completed",
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                result_data=case.result_data,
            )
            extracted = self._extract_promises(record)
            extracted_texts = [item.text for item in extracted]
            extracted_count += len(extracted_texts)
            unmatched: list[str] = []
            for expected in case.expected_promises:
                expected_count += 1
                if any(
                    self._extraction_text_matches(expected, actual) for actual in extracted_texts
                ):
                    matched_count += 1
                else:
                    unmatched.append(expected)
            if unmatched:
                failures.append(
                    {
                        "id": case.id,
                        "source_id": case.source_id,
                        "unmatched": unmatched,
                        "extracted": extracted_texts,
                    }
                )
        return PromiseExtractionRecallEvaluation(
            case_count=len(cases),
            expected_count=expected_count,
            extracted_count=extracted_count,
            matched_count=matched_count,
            recall=round(matched_count / expected_count, 3) if expected_count else 0.0,
            failures=failures,
        )

    def build_extraction_recall_report(
        self,
        cases: list[PromiseExtractionCase],
        *,
        fixture_path: str,
        target_case_count: int = 50,
    ) -> PromiseExtractionRecallReport:
        """Build false-negative recall report from extraction fixture labels."""
        evaluation = self.evaluate_extraction_cases(cases)
        real_meeting_case_count = sum(1 for case in cases if case.id.startswith("extract-real-"))
        return PromiseExtractionRecallReport(
            generated_at=datetime.now(UTC).replace(tzinfo=None),
            fixture_path=fixture_path,
            evaluation=evaluation,
            real_meeting_case_count=real_meeting_case_count,
            target_case_count=target_case_count,
            below_target=real_meeting_case_count < target_case_count,
        )

    def _default_extraction_recall_report(
        self, *, target_case_count: int = 50
    ) -> PromiseExtractionRecallReport:
        backend_root = Path(__file__).resolve().parents[1]
        fixture_path = backend_root / "tests" / "fixtures" / "promise_radar_extraction_cases.json"
        cases = [
            PromiseExtractionCase(**item)
            for item in json.loads(fixture_path.read_text(encoding="utf-8"))
        ]
        return self.build_extraction_recall_report(
            cases,
            fixture_path=str(fixture_path.relative_to(backend_root.parent)),
            target_case_count=target_case_count,
        )

    def _evidence_audit_summary(
        self,
        review_queue: PromiseAutopilotReviewQueue,
    ) -> PromiseEvidenceAuditSummary:
        locked_count = 0
        weak_evidence_count = 0
        missing_timestamp_count = 0
        missing_speaker_count = 0
        marker_hit_count = 0
        similarities: list[float] = []
        for item in review_queue.items:
            assessment = item.assessment
            pack = assessment.evidence_pack
            if assessment.evidence_locked:
                locked_count += 1
            else:
                weak_evidence_count += 1
            if pack is not None:
                similarities.append(pack.similarity)
                marker_hit_count += len(pack.marker_hits)
                evidence_items = pack.evidence
            else:
                similarities.append(assessment.explanation.similarity)
                evidence_items = assessment.explanation.evidence
            if not evidence_items:
                missing_timestamp_count += 1
                missing_speaker_count += 1
                continue
            if not any(
                evidence.start_seconds is not None and evidence.end_seconds is not None
                for evidence in evidence_items
            ):
                missing_timestamp_count += 1
            if not any(
                evidence.speaker or evidence.speaker_label or evidence.speaker_profile_id
                for evidence in evidence_items
            ):
                missing_speaker_count += 1

        notes: list[str] = []
        if weak_evidence_count:
            notes.append("Evidence Lock이 약한 자동 판정은 일괄 확정 전에 근거를 확인하세요.")
        if missing_timestamp_count:
            notes.append("일부 근거에 timestamp가 없어 회의 원문 위치 재현성이 낮습니다.")
        if missing_speaker_count:
            notes.append("일부 근거에 화자 정보가 없어 담당자 자동 지정 신뢰도가 낮습니다.")
        if not notes:
            notes.append("검토 대기 항목의 evidence 품질이 안정적입니다.")
        average_similarity = (
            round(sum(similarities) / len(similarities), 3) if similarities else 0.0
        )
        return PromiseEvidenceAuditSummary(
            locked_count=locked_count,
            weak_evidence_count=weak_evidence_count,
            missing_timestamp_count=missing_timestamp_count,
            missing_speaker_count=missing_speaker_count,
            marker_hit_count=marker_hit_count,
            average_similarity=average_similarity,
            notes=notes,
        )

    def _memory_graph_summary(
        self,
        dashboard: PromiseRadarDashboard,
        learning_insight: PromiseLearningInsight,
    ) -> PromiseMemoryGraph:
        nodes: list[PromiseMemoryGraphNode] = []
        edges: list[PromiseMemoryGraphEdge] = []
        seen_nodes: set[str] = set()
        seen_edges: set[tuple[str, str, str]] = set()

        def add_node(
            node_id: str,
            *,
            label: str,
            kind: str,
            weight: int = 1,
            status: str | None = None,
            risk_level: str | None = None,
        ) -> None:
            if node_id in seen_nodes:
                return
            seen_nodes.add(node_id)
            nodes.append(
                PromiseMemoryGraphNode(
                    id=node_id,
                    label=label,
                    kind=kind,
                    weight=max(0, weight),
                    status=status,
                    risk_level=risk_level,
                )
            )

        def add_edge(
            source: str,
            target: str,
            relationship: str,
            *,
            weight: int = 1,
        ) -> None:
            key = (source, target, relationship)
            if key in seen_edges:
                return
            seen_edges.add(key)
            edges.append(
                PromiseMemoryGraphEdge(
                    source=source,
                    target=target,
                    relationship=relationship,
                    weight=max(0, weight),
                )
            )

        for hotspot in dashboard.owner_hotspots[:8]:
            owner_id = f"owner:{hotspot.owner or 'UNKNOWN'}"
            add_node(
                owner_id,
                label=hotspot.owner or "UNKNOWN",
                kind="owner",
                weight=hotspot.risk_score,
                risk_level="high" if hotspot.risk_score >= 70 else "medium",
            )

        changed_cluster_count = 0
        delayed_cluster_count = 0
        for promise in dashboard.urgent_promises[:10]:
            promise_id = f"promise:{promise.id}"
            add_node(
                promise_id,
                label=promise.text,
                kind="promise",
                weight=promise.occurrences,
                status=promise.status,
                risk_level=promise.risk_level,
            )
            status_id = f"status:{promise.status}"
            add_node(
                status_id,
                label=promise.status,
                kind="status",
                weight=1,
                status=promise.status,
            )
            add_edge(promise_id, status_id, "has_status")
            if promise.owner:
                owner_id = f"owner:{promise.owner}"
                add_node(owner_id, label=promise.owner, kind="owner")
                add_edge(owner_id, promise_id, "owns")
            if promise.status == "changed":
                changed_cluster_count += 1
            if promise.status in {"blocked", "delayed"} or promise.due_at is not None:
                delayed_cluster_count += int(promise.status in {"blocked", "delayed"})

        for series in dashboard.meeting_series[:6]:
            series_id = f"series:{series.series_key}"
            add_node(
                series_id,
                label=series.title,
                kind="series",
                weight=series.meeting_count,
                risk_level=(
                    "high"
                    if series.high_risk_count
                    else "medium"
                    if series.overdue_count
                    else "low"
                ),
            )
            if series.overdue_count:
                delayed_cluster_count += 1
            for owner in series.owners[:4]:
                owner_id = f"owner:{owner}"
                add_node(owner_id, label=owner, kind="owner")
                add_edge(series_id, owner_id, "mentions_owner", weight=series.meeting_count)

        narrative: list[str] = []
        if dashboard.meeting_series:
            narrative.append(
                f"반복 회의 {len(dashboard.meeting_series)}개에서 미해결 약속 흐름을 추적합니다."
            )
        if delayed_cluster_count:
            narrative.append(
                f"지연/차단 cluster {delayed_cluster_count}개가 다음 회의 확인 대상입니다."
            )
        if changed_cluster_count:
            narrative.append(
                f"변경 cluster {changed_cluster_count}개는 분리/병합 확인이 필요합니다."
            )
        if learning_insight.alias_graph_size:
            narrative.append(
                f"화자/담당자 alias {learning_insight.alias_graph_size}개를 owner node에 연결했습니다."
            )
        if not narrative:
            narrative.append("현재 표시할 고위험 promise memory cluster가 없습니다.")

        return PromiseMemoryGraph(
            node_count=len(nodes),
            edge_count=len(edges),
            recurring_series_count=len(dashboard.meeting_series),
            changed_cluster_count=changed_cluster_count,
            delayed_cluster_count=delayed_cluster_count,
            owner_alias_count=learning_insight.alias_graph_size,
            nodes=nodes,
            edges=edges,
            narrative=narrative,
        )

    def _autopilot_shadow_summary(
        self,
        review_queue: PromiseAutopilotReviewQueue,
        learning_insight: PromiseLearningInsight,
    ) -> PromiseAutopilotShadowSummary:
        distribution: Counter[str] = Counter()
        confidence_sum = 0.0
        would_apply_count = 0
        blocked_by_evidence_count = 0
        for item in review_queue.items:
            assessment = item.assessment
            distribution[assessment.suggested_status] += 1
            confidence_sum += assessment.confidence
            status_changed = assessment.suggested_status != assessment.previous_status
            threshold = learning_insight.status_thresholds.get(
                assessment.suggested_status,
                assessment.threshold,
            )
            if (
                status_changed
                and not assessment.conflict_detected
                and assessment.evidence_locked
                and assessment.confidence >= threshold
            ):
                would_apply_count += 1
            elif (
                status_changed
                and not assessment.conflict_detected
                and not assessment.evidence_locked
            ):
                blocked_by_evidence_count += 1

        notes: list[str] = []
        if review_queue.conflict_count:
            notes.append("충돌 신호는 Shadow Mode에서만 보관하고 자동 적용하지 않습니다.")
        if blocked_by_evidence_count:
            notes.append("Evidence Lock 미충족 후보는 사용자 확정 전 상태 변경을 막았습니다.")
        if learning_insight.status_attention:
            notes.append(
                "오판이 많은 상태는 status별 threshold를 분리해 보수적으로 시뮬레이션합니다."
            )
        if not notes:
            notes.append("현재 Shadow Mode 후보는 보수 정책 안에서 안정적입니다.")

        average_confidence = (
            round(confidence_sum / review_queue.queue_count, 3) if review_queue.queue_count else 0.0
        )
        return PromiseAutopilotShadowSummary(
            candidate_count=review_queue.queue_count,
            would_apply_count=would_apply_count,
            preview_only_count=max(0, review_queue.actionable_count - would_apply_count),
            blocked_by_evidence_count=blocked_by_evidence_count,
            conflict_count=review_queue.conflict_count,
            status_distribution=dict(distribution),
            average_confidence=average_confidence,
            learning_value=(
                "사용자 확정/거절 결과를 다음 status별 threshold와 담당자 alias 학습에 반영합니다."
            ),
            notes=notes,
        )

    def _evidence_permission_summary(
        self,
        review_queue: PromiseAutopilotReviewQueue,
        evidence_audit: PromiseEvidenceAuditSummary,
        *,
        scope: str,
    ) -> PromiseEvidencePermissionSummary:
        contains_speaker_data = False
        contains_timestamp_data = False
        for item in review_queue.items:
            pack = item.assessment.evidence_pack
            evidence_items = (
                pack.evidence if pack is not None else item.assessment.explanation.evidence
            )
            for evidence in evidence_items:
                if evidence.speaker or evidence.speaker_label or evidence.speaker_profile_id:
                    contains_speaker_data = True
                if evidence.start_seconds is not None or evidence.end_seconds is not None:
                    contains_timestamp_data = True

        blocked_export_count = (
            evidence_audit.weak_evidence_count
            + evidence_audit.missing_timestamp_count
            + evidence_audit.missing_speaker_count
        )
        redaction_required = contains_speaker_data or contains_timestamp_data
        policy_notes: list[str] = []
        if redaction_required:
            policy_notes.append("외부 공유 전 speaker/timestamp 식별자는 최소화 또는 마스킹하세요.")
        if blocked_export_count:
            policy_notes.append(
                "근거가 약하거나 위치 재현성이 낮은 후보는 Evidence Pack export를 막습니다."
            )
        if not policy_notes:
            policy_notes.append("현재 Evidence Pack은 export 전 privacy gate를 통과했습니다.")

        return PromiseEvidencePermissionSummary(
            scope=scope,
            export_allowed=blocked_export_count == 0,
            redaction_required=redaction_required,
            contains_speaker_data=contains_speaker_data,
            contains_timestamp_data=contains_timestamp_data,
            allowed_evidence_count=evidence_audit.locked_count,
            blocked_export_count=blocked_export_count,
            policy_notes=policy_notes,
        )

    def _team_scorecard_summary(
        self,
        dashboard: PromiseRadarDashboard,
    ) -> PromiseTeamScorecard:
        scores = dashboard.responsibility_scores
        weakest = min(scores, key=lambda item: item.score, default=None)
        strongest = max(scores, key=lambda item: item.score, default=None)
        base_risk = (
            dashboard.high_risk_count * 22
            + dashboard.overdue_count * 18
            + dashboard.blocked_count * 16
            + dashboard.unconfirmed_count * 8
            + min(dashboard.open_count * 3, 18)
        )
        if weakest is not None and weakest.score < 50:
            base_risk += 10
        risk_score = max(0, min(100, base_risk))

        recommendations: list[str] = []
        if dashboard.overdue_count:
            recommendations.append("기한 초과 약속은 다음 회의 첫 안건으로 올리세요.")
        if dashboard.high_risk_count:
            recommendations.append("고위험 약속은 담당자와 기한을 사용자 확정 상태로 고정하세요.")
        if weakest is not None and weakest.score < 70:
            recommendations.append(f"{weakest.owner}의 지연/미확정 약속을 분리 검토하세요.")
        if not recommendations:
            recommendations.append("팀 약속 부하가 안정적입니다. 주간 digest로 유지 관리하세요.")

        return PromiseTeamScorecard(
            risk_score=risk_score,
            owner_count=len(scores),
            open_count=dashboard.open_count,
            overdue_count=dashboard.overdue_count,
            high_risk_count=dashboard.high_risk_count,
            recurring_series_count=len(dashboard.meeting_series),
            weakest_owner=weakest.owner if weakest is not None else None,
            strongest_owner=strongest.owner if strongest is not None else None,
            recommendations=recommendations,
        )

    def _google_tasks_oauth_guide(self) -> PromiseGoogleTasksOAuthGuide:
        required_env = ["GOOGLE_CLIENT_ID"]
        missing_setup = [name for name in required_env if not getattr(settings, name.lower(), "")]
        return PromiseGoogleTasksOAuthGuide(
            auth_url_hint=(
                "https://accounts.google.com/o/oauth2/v2/auth?"
                "scope=https%3A//www.googleapis.com/auth/tasks&"
                "response_type=code&access_type=offline&prompt=consent"
            ),
            production_ready=not missing_setup,
            missing_setup=missing_setup,
            required_backend_env=required_env,
            verification_steps=[
                "Google Cloud OAuth consent screen에서 Tasks scope가 승인됐는지 확인합니다.",
                "Android/iOS OAuth client id가 현재 release bundle id/package와 일치하는지 확인합니다.",
                "실기기에서 계정 선택 후 tasklist 조회 API가 200을 반환하는지 확인합니다.",
            ],
            steps=[
                "앱에서 Google Tasks scope 승인을 시작합니다.",
                "사용자가 Google 계정을 선택하고 Tasks 접근을 승인합니다.",
                "앱은 authorization code를 백엔드로 전달하고 access token을 교환합니다.",
                "tasklist를 선택한 뒤 Promise Ledger 항목을 Google Tasks로 전송합니다.",
                "이후 reconcile/sync/update API로 외부 상태와 원장 상태를 맞춥니다.",
            ],
            token_handling=(
                "access token은 요청 시에만 사용하고 로그/evidence에 저장하지 않습니다. "
                "장기 동기화가 필요하면 refresh token은 암호화 저장소에만 보관해야 합니다."
            ),
            security_notes=[
                "요청 scope는 Google Tasks 단일 scope로 제한합니다.",
                "state/nonce 검증으로 OAuth callback 위조를 막아야 합니다.",
                "팀 공유 task 전송은 담당자/팀 권한 확인 후 수행합니다.",
            ],
        )

    def _build_live_coach_summary(
        self,
        brief: PromisePreMeetingBrief,
    ) -> PromiseLiveCoachSummary:
        prompts: list[PromiseLiveCoachPrompt] = []
        moment = datetime.now(UTC).replace(tzinfo=None)
        for entry in brief.promises[:5]:
            severity = "high" if entry.risk_level == "high" else "warning"
            if entry.due_at and entry.due_at > moment:
                severity = "info" if entry.risk_level != "high" else "warning"
            owner = entry.owner or "담당자 미정"
            prompts.append(
                PromiseLiveCoachPrompt(
                    key=f"promise:{entry.id}",
                    label="약속 확인",
                    prompt=f"{owner}에게 '{entry.text}' 상태와 다음 기한을 확인하세요.",
                    severity=severity,
                    owner=entry.owner,
                    due_at=entry.due_at,
                    ledger_entry_id=entry.id,
                )
            )
        for index, checkpoint in enumerate(brief.checkpoints[:3]):
            prompts.append(
                PromiseLiveCoachPrompt(
                    key=f"checkpoint:{index}",
                    label="체크포인트",
                    prompt=checkpoint,
                    severity="warning",
                )
            )
        for index, question in enumerate(brief.questions[:2]):
            prompts.append(
                PromiseLiveCoachPrompt(
                    key=f"question:{index}",
                    label="질문",
                    prompt=question,
                    severity="info",
                )
            )
        notes = [
            "녹음 시작 전과 회의 중간에 Live Coach prompt를 확인하면 약속 누락을 줄일 수 있습니다."
        ]
        if not prompts:
            notes.append("현재 회의 중 확인할 미해결 약속 prompt가 없습니다.")
        return PromiseLiveCoachSummary(
            generated_at=moment,
            readiness_score=brief.readiness_score,
            prompt_count=len(prompts),
            prompts=prompts[:8],
            notes=notes,
        )

    def _evidence_room_summary(
        self,
        review_queue: PromiseAutopilotReviewQueue,
        evidence_permissions: PromiseEvidencePermissionSummary,
        *,
        scope: str,
    ) -> PromiseEvidenceRoomSummary:
        share_ready = evidence_permissions.allowed_evidence_count
        redaction_required = (
            evidence_permissions.allowed_evidence_count
            if evidence_permissions.redaction_required
            else 0
        )
        blocked = evidence_permissions.blocked_export_count
        policy_notes = list(evidence_permissions.policy_notes)
        if review_queue.conflict_count:
            policy_notes.append(
                "충돌 후보는 Evidence Room 공유 전 사용자가 상태를 먼저 확정해야 합니다."
            )
        if not policy_notes:
            policy_notes.append(
                "공유 가능한 Evidence Pack은 짧은 TTL과 redaction 정책으로 생성됩니다."
            )
        return PromiseEvidenceRoomSummary(
            scope=scope,
            share_ready_count=share_ready,
            redaction_required_count=redaction_required,
            blocked_count=blocked,
            default_ttl_hours=72,
            policy_notes=policy_notes[:4],
        )

    def _meeting_recipe_policy(
        self,
        *,
        dashboard: PromiseRadarDashboard,
        learning_insight: PromiseLearningInsight,
        evidence_permissions: PromiseEvidencePermissionSummary,
    ) -> PromiseMeetingRecipePolicy:
        recipe_key = "team_sync"
        label = "Team Sync"
        high_risk_keywords = ["blocker", "blocked", "지연", "리스크", "결정 필요"]
        recommended_integrations = ["Google Tasks"]
        if dashboard.high_risk_count >= 3 or not evidence_permissions.export_allowed:
            recipe_key = "risk_review"
            label = "Risk Review"
            high_risk_keywords.extend(["법무", "비용", "계약", "보안", "품질"])
            recommended_integrations = ["Google Tasks", "Calendar"]
        elif learning_insight.recommended_policy == "manual_only":
            recipe_key = "strict_review"
            label = "Strict Review"
            high_risk_keywords.extend(["승인", "확정", "취소"])
        return PromiseMeetingRecipePolicy(
            recipe_key=recipe_key,
            label=label,
            owner_required=True,
            due_date_required=True,
            default_autopilot_mode=learning_insight.recommended_policy,
            high_risk_keywords=high_risk_keywords,
            prompt_templates=[
                "담당자, 기한, 완료 기준을 한 문장으로 다시 확인하세요.",
                "이 약속이 다음 회의 전까지 완료되지 않으면 어떤 위험이 생기는지 확인하세요.",
                "자동 판정이 근거를 충분히 갖췄는지 Evidence Pack을 확인하세요.",
            ],
            recommended_integrations=recommended_integrations,
        )

    def _command_center_actions(
        self,
        *,
        review_queue: PromiseAutopilotReviewQueue,
        external_reconcile: PromiseExternalTaskReconcileResponse,
        accuracy_report: PromiseAccuracyReport,
        extraction_recall: PromiseExtractionRecallReport,
        evidence_permissions: PromiseEvidencePermissionSummary,
        evidence_room: PromiseEvidenceRoomSummary,
        autopilot_quarantine: PromiseAutopilotQuarantineSummary,
        live_coach: PromiseLiveCoachSummary,
    ) -> list[PromiseCommandCenterAction]:
        """Expose only existing review/report/sync routes as operator actions."""
        actions = [
            PromiseCommandCenterAction(
                key="open_review_queue",
                label="확정 대기 약속 검토",
                method="GET",
                route="/promise-review-inbox",
                enabled=review_queue.queue_count > 0,
                reason=(
                    f"{review_queue.queue_count}개 후보가 대기 중입니다."
                    if review_queue.queue_count
                    else "현재 검토할 자동 판정 후보가 없습니다."
                ),
            ),
            PromiseCommandCenterAction(
                key="refresh_external_reconcile",
                label="Google Tasks 동기화 점검",
                method="GET",
                route="/api/v1/promise-radar/external-task/reconcile",
                enabled=external_reconcile.linked_count > 0,
                reason=(
                    f"{external_reconcile.needs_sync_count}개 항목 재확인이 필요합니다."
                    if external_reconcile.needs_sync_count
                    else "연결된 Google Tasks 항목이 없거나 최신 상태입니다."
                ),
            ),
            PromiseCommandCenterAction(
                key="open_accuracy_report",
                label="상태 판정 정확도 보고서",
                method="GET",
                route="/api/v1/promise-radar/accuracy/report",
                enabled=True,
                reason=(f"실제 회의 label {accuracy_report.real_meeting_case_count}건 기준입니다."),
            ),
            PromiseCommandCenterAction(
                key="open_extraction_recall_report",
                label="약속 추출 누락 보고서",
                method="GET",
                route="/api/v1/promise-radar/accuracy/extraction-report",
                enabled=True,
                reason=(
                    f"Recall {round(extraction_recall.evaluation.recall * 100)}%, "
                    f"{extraction_recall.evaluation.matched_count}/"
                    f"{extraction_recall.evaluation.expected_count} matched"
                ),
            ),
            PromiseCommandCenterAction(
                key="review_evidence_permissions",
                label="Evidence 공유 권한 확인",
                method="GET",
                route="/promise-review-inbox",
                enabled=evidence_permissions.blocked_export_count > 0,
                requires_confirmation=True,
                reason=(
                    "speaker/timestamp redaction 확인이 필요합니다."
                    if evidence_permissions.blocked_export_count
                    else "현재 evidence export 차단 항목이 없습니다."
                ),
            ),
            PromiseCommandCenterAction(
                key="open_learning_telemetry",
                label="학습 telemetry 점검",
                method="GET",
                route="/api/v1/promise-radar/telemetry/learning",
                enabled=True,
                reason="상태/담당자/언어별 오판율을 확인합니다.",
            ),
            PromiseCommandCenterAction(
                key="open_live_coach",
                label="Live Promise Coach",
                method="GET",
                route="/api/v1/promise-radar/live-coach",
                enabled=live_coach.prompt_count > 0,
                reason=(
                    f"회의 중 확인 prompt {live_coach.prompt_count}개가 준비됐습니다."
                    if live_coach.prompt_count
                    else "현재 회의 중 확인할 prompt가 없습니다."
                ),
            ),
            PromiseCommandCenterAction(
                key="open_evidence_room",
                label="Evidence Room 공유",
                method="GET",
                route="/api/v1/promise-radar/evidence-room",
                enabled=evidence_room.share_ready_count > 0,
                requires_confirmation=True,
                reason=(
                    f"공유 가능 {evidence_room.share_ready_count}개, 차단 {evidence_room.blocked_count}개"
                ),
            ),
            PromiseCommandCenterAction(
                key="open_meeting_recipe",
                label="회의 레시피 정책",
                method="GET",
                route="/api/v1/promise-radar/meeting-recipe",
                enabled=True,
                reason="회의 유형별 owner/due/evidence 정책을 적용합니다.",
            ),
            PromiseCommandCenterAction(
                key="review_autopilot_quarantine",
                label="Autopilot 격리 패턴",
                method="GET",
                route="/api/v1/promise-radar/autopilot/quarantine",
                enabled=autopilot_quarantine.quarantined_count > 0,
                reason=(
                    f"격리/되돌림 패턴 {autopilot_quarantine.quarantined_count}개"
                    if autopilot_quarantine.quarantined_count
                    else "현재 격리된 Autopilot 패턴이 없습니다."
                ),
            ),
            PromiseCommandCenterAction(
                key="start_google_tasks_oauth",
                label="Google Tasks OAuth 시작",
                method="POST",
                route="/api/v1/promise-radar/external-task/google-oauth/start",
                enabled=bool(str(settings.google_client_id or "").strip()),
                requires_confirmation=True,
                reason="앱에서 Tasks scope 승인 URL을 생성합니다.",
            ),
        ]
        return actions

    def _command_center_focus_items(
        self,
        *,
        dashboard: PromiseRadarDashboard,
        review_queue: PromiseAutopilotReviewQueue,
        learning_insight: PromiseLearningInsight,
        learning_telemetry: PromiseLearningTelemetryReport,
        digest: PromiseDigest,
        external_reconcile: PromiseExternalTaskReconcileResponse,
        accuracy_report: PromiseAccuracyReport,
        extraction_recall: PromiseExtractionRecallReport,
        evidence_audit: PromiseEvidenceAuditSummary,
        memory_graph: PromiseMemoryGraph,
        shadow_mode: PromiseAutopilotShadowSummary,
        evidence_permissions: PromiseEvidencePermissionSummary,
        evidence_room: PromiseEvidenceRoomSummary,
        team_scorecard: PromiseTeamScorecard,
        autopilot_quarantine: PromiseAutopilotQuarantineSummary,
        live_coach: PromiseLiveCoachSummary,
    ) -> list[PromiseCommandCenterFocusItem]:
        items: list[PromiseCommandCenterFocusItem] = []
        if review_queue.conflict_count:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="conflicts",
                    label="충돌 약속 해결",
                    severity="critical",
                    count=review_queue.conflict_count,
                    action="완료/지연/변경/분리 중 하나로 명시적으로 결정하세요.",
                    route="/promise-review-inbox",
                )
            )
        if review_queue.actionable_count:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="review_queue",
                    label="자동 판정 확정 대기",
                    severity="high",
                    count=review_queue.actionable_count,
                    action="Evidence Pack을 확인하고 맞음/아님을 확정하세요.",
                    route="/promise-review-inbox",
                )
            )
        if digest.overdue_count:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="overdue",
                    label="기한 초과 약속",
                    severity="high",
                    count=digest.overdue_count,
                    action="오늘 회의 전 담당자와 상태를 확인하세요.",
                )
            )
        if dashboard.high_risk_count:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="high_risk",
                    label="고위험 약속",
                    severity="warning",
                    count=dashboard.high_risk_count,
                    action="회의 전 Promise Brief에 포함해 진행상황을 확인하세요.",
                )
            )
        if external_reconcile.requires_oauth:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="google_tasks_oauth",
                    label="Google Tasks OAuth 필요",
                    severity="warning",
                    count=max(1, external_reconcile.linked_count),
                    action="Tasks scope 승인을 완료해야 실제 tasklist 조회/전송이 가능합니다.",
                )
            )
        elif external_reconcile.needs_sync_count:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="external_sync",
                    label="외부 업무도구 동기화 필요",
                    severity="warning",
                    count=external_reconcile.needs_sync_count,
                    action="Google Tasks 상태와 Promise Ledger 상태를 재동기화하세요.",
                )
            )
        if learning_insight.status_attention:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="learning_attention",
                    label="학습 루프 주의 상태",
                    severity="warning",
                    count=len(learning_insight.status_attention),
                    action="주의 상태의 threshold를 낮추지 말고 확정/거절 데이터를 누적하세요.",
                )
            )
        high_false_positive_segments = [
            segment
            for segment in learning_telemetry.status_segments
            if segment.sample_count >= 2 and segment.false_positive_rate >= 0.34
        ]
        if high_false_positive_segments:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="learning_telemetry",
                    label="Telemetry 오판 패턴",
                    severity="warning",
                    count=len(high_false_positive_segments),
                    action="오판율이 높은 상태는 preview-only로 유지하고 fixture로 승격하세요.",
                    route="/api/v1/promise-radar/telemetry/learning",
                )
            )
        if autopilot_quarantine.quarantined_count:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="autopilot_quarantine",
                    label="Autopilot 격리",
                    severity="warning",
                    count=autopilot_quarantine.quarantined_count,
                    action="되돌린 자동 판정 패턴은 근거가 보강될 때까지 검토함에 유지하세요.",
                    route="/api/v1/promise-radar/autopilot/quarantine",
                )
            )
        if evidence_audit.weak_evidence_count:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="weak_evidence",
                    label="약한 근거",
                    severity="warning",
                    count=evidence_audit.weak_evidence_count,
                    action="자동 상태 변경 전에 발화/화자/timestamp 근거를 확인하세요.",
                )
            )
        if shadow_mode.blocked_by_evidence_count or shadow_mode.conflict_count:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="shadow_mode",
                    label="Shadow Mode 보류",
                    severity="warning",
                    count=shadow_mode.blocked_by_evidence_count + shadow_mode.conflict_count,
                    action="자동 적용 후보를 확정하기 전에 충돌/근거 잠금 상태를 확인하세요.",
                    route="/promise-review-inbox",
                )
            )
        if not evidence_permissions.export_allowed:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="evidence_permission",
                    label="Evidence 공유 제한",
                    severity="warning",
                    count=evidence_permissions.blocked_export_count,
                    action="근거 export 전 speaker/timestamp redaction과 Evidence Lock을 확인하세요.",
                )
            )
        if evidence_room.blocked_count:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="evidence_room",
                    label="Evidence Room 차단",
                    severity="warning",
                    count=evidence_room.blocked_count,
                    action="외부 공유 전 transcript/speaker/timestamp redaction과 근거 강도를 확인하세요.",
                    route="/api/v1/promise-radar/evidence-room",
                )
            )
        if live_coach.prompt_count:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="live_coach",
                    label="회의 중 확인 prompt",
                    severity="info",
                    count=live_coach.prompt_count,
                    action="녹음 중 담당자/기한/완료 기준을 바로 확인하세요.",
                    route="/api/v1/promise-radar/live-coach",
                )
            )
        if team_scorecard.risk_score >= 70:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="team_scorecard",
                    label="팀 약속 위험도 높음",
                    severity="high",
                    count=team_scorecard.risk_score,
                    action="책임자별 지연/고위험 약속을 Command Center에서 재배정하세요.",
                )
            )
        if memory_graph.delayed_cluster_count or memory_graph.changed_cluster_count:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="memory_graph",
                    label="Promise Memory cluster",
                    severity="info",
                    count=memory_graph.delayed_cluster_count + memory_graph.changed_cluster_count,
                    action="반복 회의와 owner node를 따라 지연/변경 흐름을 확인하세요.",
                )
            )
        if accuracy_report.below_target or accuracy_report.quality_warnings:
            items.append(
                PromiseCommandCenterFocusItem(
                    key="accuracy_quality",
                    label="정확도 세트 품질 점검",
                    severity="info",
                    count=len(accuracy_report.quality_warnings),
                    action="실제 회의 label과 source manifest 품질 경고를 확인하세요.",
                )
            )
        if extraction_recall.below_target or extraction_recall.evaluation.recall < 0.95:
            missed = (
                extraction_recall.evaluation.expected_count
                - extraction_recall.evaluation.matched_count
            )
            items.append(
                PromiseCommandCenterFocusItem(
                    key="extraction_recall",
                    label="약속 추출 누락 점검",
                    severity="warning" if missed else "info",
                    count=max(missed, len(extraction_recall.evaluation.failures)),
                    action="False negative fixture에서 빠진 약속을 확인하고 추출 규칙을 보강하세요.",
                )
            )
        return items[:10]

    def _accuracy_source_quality(
        self,
        source_manifest_path: str | None,
    ) -> dict[str, dict[str, Any]]:
        if not source_manifest_path:
            return {}
        path = Path(source_manifest_path)
        if not path.exists():
            return {}
        raw_sources = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw_sources, list):
            return {}
        quality: dict[str, dict[str, Any]] = {}
        for item in raw_sources:
            if not isinstance(item, dict):
                continue
            source_id = str(item.get("source_id") or "unknown")
            rebuild_commands = item.get("rebuild_commands")
            segments = item.get("segments")
            segment_count = len(segments) if isinstance(segments, list) else 0
            golden_case_count = int(item.get("golden_case_count") or 0)
            if golden_case_count == 0 and isinstance(segments, list):
                for segment in segments:
                    if not isinstance(segment, dict):
                        continue
                    if "golden_case_count" in segment:
                        golden_case_count += int(segment.get("golden_case_count") or 0)
                    else:
                        golden_ids = segment.get("golden_case_ids")
                        if isinstance(golden_ids, list):
                            golden_case_count += len(golden_ids)
            quality[source_id] = {
                "title": item.get("title"),
                "url": item.get("url"),
                "license": item.get("license"),
                "verified_with": item.get("verified_with"),
                "subtitle_cache": item.get("subtitle_cache"),
                "representative_audio_clip": item.get("representative_audio_clip"),
                "golden_case_count": golden_case_count,
                "golden_case_id_prefix": item.get("golden_case_id_prefix"),
                "candidate_only": bool(item.get("candidate_only")),
                "rebuild_commands": rebuild_commands if isinstance(rebuild_commands, list) else [],
                "segment_count": segment_count,
            }
        return quality

    def _accuracy_source_lookup(
        self,
        source_manifest_path: str | None,
    ) -> tuple[dict[str, str], dict[str, str]]:
        if not source_manifest_path:
            return {}, {}
        path = Path(source_manifest_path)
        if not path.exists():
            return {}, {}
        raw_sources = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw_sources, list):
            return {}, {}
        prefixes: dict[str, str] = {}
        case_ids: dict[str, str] = {}
        for item in raw_sources:
            if not isinstance(item, dict):
                continue
            source_id = str(item.get("source_id") or "unknown")
            prefix = item.get("golden_case_id_prefix")
            if isinstance(prefix, str) and prefix:
                prefixes[prefix] = source_id
            segments = item.get("segments")
            if not isinstance(segments, list):
                continue
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                for case_id in segment.get("golden_case_ids") or []:
                    if isinstance(case_id, str):
                        case_ids[case_id] = source_id
        return prefixes, case_ids

    def _accuracy_case_source_id(
        self,
        case_id: str,
        *,
        source_prefixes: dict[str, str],
        source_case_ids: dict[str, str],
    ) -> str | None:
        if case_id in source_case_ids:
            return source_case_ids[case_id]
        for prefix, source_id in source_prefixes.items():
            if case_id.startswith(prefix):
                return source_id
        return None

    def _confidence_bucket(self, confidence: float) -> str:
        clipped = max(0.0, min(1.0, confidence))
        start = min(0.9, int(clipped * 10) / 10)
        end = 1.0 if start >= 0.9 else start + 0.09
        return f"{start:.1f}-{end:.2f}"

    def _ratio(self, numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(max(0.0, min(1.0, numerator / denominator)), 3)

    def analyze_records(
        self,
        current: TaskResult,
        previous_records: list[TaskResult],
    ) -> PromiseRadarResponse:
        """Analyze current summary against previous summary records."""
        now = datetime.now(UTC).isoformat()
        current_promises = self._extract_promises(current)
        previous_promises = [
            promise for record in previous_records for promise in self._extract_promises(record)
        ]
        current_decisions = self._extract_decisions(current)
        previous_decisions = [
            (record, decision)
            for record in previous_records
            for decision in self._extract_decisions(record)
        ]

        carried = self._match_carried_promises(current_promises, previous_promises)
        stale = self._find_stale_promises(previous_promises, current_promises, current)
        drifts = self._find_decision_drifts(current, current_decisions, previous_decisions)
        all_promises = [*previous_promises, *current_promises]
        chains = self._build_promise_chains(all_promises, current.task_id)
        owner_risks = self._build_owner_risks(chains, stale, carried)
        questions = self._build_follow_up_questions(stale, drifts, chains)
        risk_score = self._risk_score(stale, carried, drifts, chains, owner_risks)
        high_risk_count = sum(1 for chain in chains if chain.risk_level == "high") + sum(
            1 for owner in owner_risks if owner.risk_score >= 70
        )

        headline = self._headline(
            current_count=len(current_promises),
            stale_count=len(stale),
            drift_count=len(drifts),
            risk_score=risk_score,
        )

        return PromiseRadarResponse(
            task_id=current.task_id,
            generated_at=now,
            headline=headline,
            risk_score=risk_score,
            analyzed_meetings=len(previous_records) + 1,
            current_promises=[promise.to_schema() for promise in current_promises[:8]],
            carried_over_promises=carried[:6],
            stale_promises=[promise.to_schema() for promise in stale[:8]],
            decision_drifts=drifts[:6],
            promise_chains=chains[:8],
            owner_risks=owner_risks[:8],
            high_risk_count=high_risk_count,
            follow_up_questions=questions[:8],
        )

    async def _sync_ledger(
        self,
        *,
        session: AsyncSession,
        current: TaskResult,
        response: PromiseRadarResponse,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
        team_id: UUID | str | None,
        semantic_promises: list[_SemanticPromise],
    ) -> list[PromiseLedgerEntryResponse]:
        evidence_records = await self._load_evidence_records(session, current)
        team_uuid = self._coerce_uuid(team_id)
        new_entries: list[PromiseLedgerEntry] = []
        for promise in response.current_promises:
            semantic = self._match_semantic_promise(promise, semantic_promises)
            canonical_text = semantic.canonical_text if semantic else promise.text
            canonical_key = self._canonical_key(canonical_text)
            evidence = self._evidence_for_promise(promise, evidence_records)
            first_seen = self._parse_datetime(promise.source_created_at) or datetime.now(
                UTC
            ).replace(tzinfo=None)
            due_text = semantic.due_date if semantic and semantic.due_date else promise.due_date
            due_at = self._parse_due_at(due_text, first_seen)

            existing = await self._find_open_ledger_entry(
                session,
                canonical_key,
                canonical_text,
                owner_id=owner_id,
                guest_session_id=guest_session_id,
                team_id=team_id,
            )
            if existing is None:
                session.add(
                    entry := PromiseLedgerEntry(
                        owner_id=self._coerce_uuid(owner_id),
                        guest_session_id=guest_session_id,
                        team_id=team_uuid,
                        source_task_id=promise.source_task_id,
                        last_source_task_id=promise.source_task_id,
                        canonical_key=canonical_key,
                        canonical_text=canonical_text,
                        text=promise.text,
                        semantic_summary=semantic.canonical_text if semantic else None,
                        owner_name=(
                            semantic.owner if semantic and semantic.owner else promise.owner
                        ),
                        speaker_label=evidence[0].get("speaker_label") if evidence else None,
                        speaker_profile_id=self._coerce_uuid(
                            evidence[0].get("speaker_profile_id") if evidence else None
                        ),
                        status="open",
                        priority=promise.priority,
                        risk_level=self._ledger_risk_level(promise.priority, due_at, 1),
                        confidence=max(
                            promise.confidence, semantic.confidence if semantic else 0.0
                        ),
                        due_date_text=due_text,
                        due_at=due_at,
                        occurrences=1,
                        first_seen_at=first_seen,
                        last_seen_at=first_seen,
                        evidence=evidence,
                    )
                )
                new_entries.append(entry)
                continue

            if existing.last_source_task_id != promise.source_task_id:
                existing.occurrences += 1
            existing.last_source_task_id = promise.source_task_id
            existing.canonical_text = canonical_text
            existing.text = promise.text
            existing.semantic_summary = (
                semantic.canonical_text if semantic else existing.semantic_summary
            )
            if not existing.user_confirmed:
                existing.owner_name = (
                    semantic.owner if semantic and semantic.owner else promise.owner
                )
            existing.priority = promise.priority
            existing.confidence = max(
                existing.confidence,
                promise.confidence,
                semantic.confidence if semantic else 0.0,
            )
            existing.due_date_text = due_text or existing.due_date_text
            existing.due_at = due_at or existing.due_at
            existing.last_seen_at = max(existing.last_seen_at, first_seen)
            existing.risk_level = self._ledger_risk_level(
                existing.priority,
                existing.due_at,
                existing.occurrences,
            )
            existing.evidence = self._merge_evidence(existing.evidence or [], evidence)
            if evidence:
                existing.speaker_label = existing.speaker_label or evidence[0].get("speaker_label")
                existing.speaker_profile_id = existing.speaker_profile_id or self._coerce_uuid(
                    evidence[0].get("speaker_profile_id")
                )
            existing.updated_at = datetime.now(UTC).replace(tzinfo=None)

        await session.flush()
        for entry in new_entries:
            self._record_ledger_event(
                session,
                entry,
                "detected",
                new_value=self._ledger_snapshot(entry),
                actor_user_id=owner_id,
            )
        return await self.list_ledger_entries(
            session,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
            team_id=team_id,
            statuses=_OPEN_LEDGER_STATUSES,
            limit=30,
        )

    async def _semantic_promises(self, current: TaskResult) -> tuple[list[_SemanticPromise], str]:
        promises = self._extract_promises(current)
        if not promises:
            return [], "deterministic"
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return [], "zai_unavailable"
        if not settings.llm_api_key:
            return [], "zai_unavailable"

        client = AsyncZAIClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout_seconds=45.0,
        )
        payload = [
            {
                "text": promise.text,
                "owner": promise.owner,
                "due_date": promise.due_date,
                "priority": promise.priority,
            }
            for promise in promises[:12]
        ]
        try:
            response = await client.chat.completions.create(
                model=settings.summary_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Normalize meeting promises into stable JSON. "
                            'Return only {"promises": [...]} with fields '
                            "text, canonical_text, owner, due_date, confidence."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps({"promises": payload}, ensure_ascii=False),
                    },
                ],
                max_tokens=1200,
                **structured_json_completion_options(settings.summary_model, settings.llm_base_url),
            )
            content = response.choices[0].message.content if response.choices else None
            if not content:
                return [], "zai_failed"
            data = json.loads(content)
            normalized = []
            for item in data.get("promises", []):
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text") or "").strip()
                canonical = str(item.get("canonical_text") or text).strip()
                if not text or not canonical:
                    continue
                normalized.append(
                    _SemanticPromise(
                        text=text,
                        canonical_text=canonical,
                        owner=self._clean_optional(item.get("owner")),
                        due_date=self._clean_optional(item.get("due_date")),
                        confidence=float(item.get("confidence") or 0.8),
                    )
                )
            return normalized, "zai_applied" if normalized else "zai_failed"
        except Exception:
            return [], "zai_failed"

    async def _load_evidence_records(
        self,
        session: AsyncSession,
        current: TaskResult,
    ) -> list[TaskResult]:
        task_ids = {current.task_id}
        for source in (current.input_metadata, current.result_data):
            if not isinstance(source, dict):
                continue
            for key in ("source_task_id", "minutes_task_id", "diarization_task_id", "stt_task_id"):
                value = source.get(key)
                if value:
                    task_ids.add(str(value))
            nested = source.get("summary_content")
            if isinstance(nested, dict):
                for key in (
                    "source_task_id",
                    "minutes_task_id",
                    "diarization_task_id",
                    "stt_task_id",
                ):
                    value = nested.get(key)
                    if value:
                        task_ids.add(str(value))

        result = await session.execute(select(TaskResult).where(TaskResult.task_id.in_(task_ids)))
        records = {record.task_id: record for record in result.scalars().all()}
        records[current.task_id] = current
        return list(records.values())

    def _evidence_for_promise(
        self,
        promise: PromiseRadarPromise,
        records: list[TaskResult],
    ) -> list[dict[str, Any]]:
        candidates: list[tuple[float, dict[str, Any]]] = []
        for record in records:
            data = self._result_data(record)
            for segment in data.get("segments") or []:
                if not isinstance(segment, dict):
                    continue
                text = str(segment.get("text") or "").strip()
                if not text:
                    continue
                score = max(
                    self._similarity(promise.text, text), 1.0 if promise.text in text else 0.0
                )
                if score <= 0:
                    continue
                speaker = (
                    segment.get("identified_speaker_name")
                    or segment.get("speaker_name")
                    or segment.get("speaker")
                    or segment.get("speaker_id")
                )
                candidates.append(
                    (
                        score,
                        {
                            "source_task_id": record.task_id,
                            "meeting_link": f"/results/{record.task_id}",
                            "transcript": text,
                            "speaker": str(speaker) if speaker else None,
                            "speaker_label": self._clean_optional(
                                segment.get("speaker_id") or segment.get("speaker_label")
                            ),
                            "speaker_profile_id": self._clean_optional(
                                segment.get("identified_speaker_profile_id")
                            ),
                            "voiceprint_similarity": segment.get("voiceprint_similarity"),
                            "start_seconds": segment.get("start"),
                            "end_seconds": segment.get("end"),
                        },
                    )
                )
        candidates.sort(key=lambda item: item[0], reverse=True)
        if candidates:
            return [item[1] for item in candidates[:3]]
        return [
            {
                "source_task_id": promise.source_task_id,
                "meeting_link": f"/results/{promise.source_task_id}",
                "transcript": promise.evidence or promise.text,
                "speaker": promise.owner,
                "speaker_label": None,
                "speaker_profile_id": None,
                "voiceprint_similarity": None,
                "start_seconds": None,
                "end_seconds": None,
            }
        ]

    def _build_next_meeting_briefing(
        self,
        entries: list[PromiseLedgerEntryResponse],
    ) -> PromiseNextMeetingBriefing:
        now = datetime.now(UTC).replace(tzinfo=None)
        high_risk = [
            entry for entry in entries if entry.risk_level == "high" or entry.status == "blocked"
        ]
        overdue = [entry for entry in entries if entry.due_at is not None and entry.due_at < now]
        due_soon = [
            entry
            for entry in entries
            if entry.due_at is not None and now <= entry.due_at <= now + timedelta(days=3)
        ]
        owner_hotspots = self._owner_risks_from_entries(entries)
        questions = [
            self._briefing_question(entry)
            for entry in sorted(
                entries,
                key=lambda item: (
                    item.risk_level != "high",
                    item.due_at is None,
                    item.due_at or now,
                ),
            )[:8]
        ]
        reminders = [self._reminder_candidate(entry) for entry in entries[:8]]
        return PromiseNextMeetingBriefing(
            title="다음 회의 전 확인할 약속",
            high_risk_count=len(high_risk),
            overdue_count=len(overdue),
            due_soon_count=len(due_soon),
            owner_hotspots=owner_hotspots[:6],
            promises=entries[:12],
            questions=questions,
            reminder_candidates=reminders,
        )

    def _ledger_scope_condition(
        self,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
        *,
        team_id: UUID | str | None = None,
    ):
        team_uuid = self._coerce_uuid(team_id)
        if team_uuid is not None:
            return PromiseLedgerEntry.team_id == team_uuid
        owner_uuid = self._coerce_uuid(owner_id)
        if owner_uuid is not None:
            return PromiseLedgerEntry.owner_id == owner_uuid
        if guest_session_id:
            return PromiseLedgerEntry.guest_session_id == guest_session_id
        return PromiseLedgerEntry.id.is_(None)

    def _event_scope_condition(
        self,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
        *,
        team_id: UUID | str | None = None,
    ):
        team_uuid = self._coerce_uuid(team_id)
        if team_uuid is not None:
            return PromiseLedgerEvent.team_id == team_uuid
        owner_uuid = self._coerce_uuid(owner_id)
        if owner_uuid is not None:
            return PromiseLedgerEvent.owner_id == owner_uuid
        if guest_session_id:
            return PromiseLedgerEvent.guest_session_id == guest_session_id
        return PromiseLedgerEvent.id.is_(None)

    async def _get_scoped_ledger_entry(
        self,
        session: AsyncSession,
        entry_id: UUID | str,
        *,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
        team_id: UUID | str | None = None,
    ) -> PromiseLedgerEntry | None:
        entry_uuid = self._coerce_uuid(entry_id)
        if entry_uuid is None:
            return None
        result = await session.execute(
            select(PromiseLedgerEntry).where(
                PromiseLedgerEntry.id == entry_uuid,
                self._ledger_scope_condition(owner_id, guest_session_id, team_id=team_id),
            )
        )
        return result.scalar_one_or_none()

    def _current_evidence_candidates(
        self,
        current: TaskResult,
        records: list[TaskResult],
    ) -> list[tuple[str, dict[str, Any]]]:
        candidates: list[tuple[str, dict[str, Any]]] = []
        for record in records:
            data = self._result_data(record)
            for segment in data.get("segments") or []:
                if not isinstance(segment, dict):
                    continue
                text = str(segment.get("text") or "").strip()
                if not text:
                    continue
                candidates.append(
                    (
                        text,
                        {
                            "source_task_id": record.task_id,
                            "meeting_link": f"/results/{record.task_id}",
                            "transcript": text,
                            "speaker": self._clean_optional(
                                segment.get("identified_speaker_name")
                                or segment.get("speaker_name")
                                or segment.get("speaker")
                            ),
                            "speaker_label": self._clean_optional(
                                segment.get("speaker_id") or segment.get("speaker_label")
                            ),
                            "speaker_profile_id": self._clean_optional(
                                segment.get("identified_speaker_profile_id")
                            ),
                            "voiceprint_similarity": segment.get("voiceprint_similarity"),
                            "start_seconds": segment.get("start"),
                            "end_seconds": segment.get("end"),
                        },
                    )
                )

        data = self._result_data(current)
        for key in ("summary_text", "summary", "markdown"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(
                    (
                        value.strip(),
                        {
                            "source_task_id": current.task_id,
                            "meeting_link": f"/results/{current.task_id}",
                            "transcript": value.strip(),
                        },
                    )
                )
        for item in data.get("action_items") or []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("task") or item.get("title") or "").strip()
            if text:
                candidates.append(
                    (
                        text,
                        {
                            "source_task_id": current.task_id,
                            "meeting_link": f"/results/{current.task_id}",
                            "transcript": text,
                        },
                    )
                )
        for key in ("key_decisions", "next_steps"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    text = str(item).strip()
                    if text:
                        candidates.append(
                            (
                                text,
                                {
                                    "source_task_id": current.task_id,
                                    "meeting_link": f"/results/{current.task_id}",
                                    "transcript": text,
                                },
                            )
                        )
        return candidates

    def _autopilot_assessment(
        self,
        entry: PromiseLedgerEntry,
        current: TaskResult,
        candidates: list[tuple[str, dict[str, Any]]],
        now: datetime,
    ) -> PromiseAutopilotAssessment:
        explanation = self._explain_entry_against_candidates(entry, candidates)
        matched_text = explanation.matched_text or ""
        status = entry.status
        reason = "현재 회의에서 상태 변경을 확정할 근거가 부족합니다."
        marker_confidence = 0.0
        selected_marker_hits: list[str] = []
        conflict = self._status_conflict(matched_text)

        if conflict is not None:
            reason = conflict
        elif explanation.similarity >= 0.18 or (
            explanation.similarity >= 0.15
            and any(self._marker_hits(matched_text, status) for status in _AUTOPILOT_MARKERS)
        ):
            for candidate_status in ("dismissed", "completed", "changed", "delayed"):
                marker_hits = self._marker_hits(matched_text, candidate_status)
                if not marker_hits:
                    continue
                if candidate_status == "completed" and self._looks_future_intent(matched_text):
                    continue
                if candidate_status == "delayed" and self._looks_future_intent(matched_text):
                    if not any(
                        marker in " ".join(marker_hits)
                        for marker in ("못", "지연", "미뤘", "연기", "delayed", "later", "postpone")
                    ):
                        continue
                status = candidate_status
                selected_marker_hits = marker_hits
                marker_confidence = min(0.28, 0.14 + len(marker_hits) * 0.04)
                reason = self._autopilot_reason(candidate_status, marker_hits, matched_text)
                break

        if (
            conflict is None
            and status == entry.status
            and entry.due_at is not None
            and entry.due_at < now
        ):
            status = "delayed"
            marker_confidence = max(marker_confidence, 0.2)
            reason = "기한이 지났지만 완료 또는 취소 근거가 없어 지연 약속으로 판정했습니다."

        evidence_bonus = 0.06 if explanation.evidence else 0.0
        confidence = min(
            1.0,
            explanation.similarity * 0.66
            + marker_confidence
            + evidence_bonus
            + min(entry.confidence, 1.0) * 0.08,
        )
        if status == entry.status and marker_confidence == 0:
            confidence = min(confidence, 0.54)

        assessment = PromiseAutopilotAssessment(
            ledger_entry_id=str(entry.id),
            previous_status=entry.status,
            suggested_status=status,
            confidence=round(confidence, 3),
            reason=reason,
            explanation=explanation,
            conflict_detected=conflict is not None,
            conflict_reason=conflict,
        )
        assessment.evidence_pack = self._evidence_pack(
            entry,
            current,
            assessment,
            marker_hits=selected_marker_hits,
            captured_at=now,
        )
        return assessment

    def _should_apply_autopilot(
        self,
        assessment: PromiseAutopilotAssessment,
        *,
        entry: PromiseLedgerEntry | None = None,
        threshold: float = _AUTOPILOT_APPLY_THRESHOLD,
        evidence_lock_enabled: bool = True,
        policy: PromiseAutomationPolicy | None = None,
    ) -> bool:
        if assessment.conflict_detected:
            return False
        if policy is not None:
            if policy.mode in {"preview_only", "manual_only"}:
                return False
            if policy.mode == "completed_only" and assessment.suggested_status != "completed":
                return False
            if (
                policy.allowed_auto_statuses
                and assessment.suggested_status not in policy.allowed_auto_statuses
            ):
                return False
            if (
                policy.high_risk_requires_review
                and entry is not None
                and entry.risk_level == "high"
            ):
                return False
        if evidence_lock_enabled and not self._has_locked_evidence(assessment):
            return False
        return (
            assessment.suggested_status != assessment.previous_status
            and assessment.confidence >= threshold
        )

    def _status_threshold(
        self,
        profile: PromiseLearningProfile,
        status: str,
    ) -> float:
        return profile.status_thresholds.get(status, profile.autopilot_threshold)

    def _status_specific_threshold(self, false_positive: int, confirmed: int) -> float:
        adjustment = min(0.18, false_positive * 0.045) - min(0.05, confirmed * 0.008)
        return round(max(0.62, min(0.9, _AUTOPILOT_APPLY_THRESHOLD + adjustment)), 3)

    def _status_conflict(self, text: str) -> str | None:
        if not text:
            return None
        hits = {
            status: self._marker_hits(text, status)
            for status in ("completed", "delayed", "changed", "dismissed")
        }
        active = {status: markers for status, markers in hits.items() if markers}
        if "completed" in active and ("delayed" in active or "dismissed" in active):
            labels = ", ".join(
                f"{status}:{'/'.join(markers[:2])}" for status, markers in active.items()
            )
            return f"상태 신호가 충돌합니다. 자동 적용하지 않습니다: {labels}"
        return None

    def _evidence_pack(
        self,
        entry: PromiseLedgerEntry,
        current: TaskResult,
        assessment: PromiseAutopilotAssessment,
        *,
        marker_hits: list[str],
        captured_at: datetime,
    ) -> PromiseEvidencePack:
        explanation = assessment.explanation
        return PromiseEvidencePack(
            ledger_entry_id=str(entry.id),
            source_task_id=explanation.matched_task_id or current.task_id,
            matched_text=explanation.matched_text,
            similarity=explanation.similarity,
            marker_hits=marker_hits,
            confidence_factors=explanation.confidence_factors,
            evidence=explanation.evidence,
            captured_at=captured_at,
        )

    def _has_locked_evidence(self, assessment: PromiseAutopilotAssessment) -> bool:
        explanation = assessment.explanation
        matched_text = (explanation.matched_text or "").strip()
        matched_tokens = self._tokens(matched_text)
        evidence_pack = assessment.evidence_pack
        marker_hits = evidence_pack.marker_hits if evidence_pack else []
        status_change = assessment.suggested_status != assessment.previous_status
        status_needs_marker = status_change and assessment.suggested_status in {
            "completed",
            "delayed",
            "changed",
            "dismissed",
        }
        return (
            bool(matched_text)
            and len(matched_text) >= _EVIDENCE_LOCK_MIN_CHARS
            and len(matched_tokens) >= _EVIDENCE_LOCK_MIN_TOKENS
            and explanation.similarity >= _EVIDENCE_LOCK_MIN_SIMILARITY
            and bool(explanation.evidence)
            and len(explanation.confidence_factors) >= _EVIDENCE_LOCK_MIN_FACTORS
            and (not status_needs_marker or bool(marker_hits))
        )

    def _explain_entry_against_candidates(
        self,
        entry: PromiseLedgerEntry,
        candidates: list[tuple[str, dict[str, Any]]],
    ) -> PromiseMatchExplanation:
        best_text = ""
        best_payload: dict[str, Any] = {}
        best_score = 0.0
        for text, payload in candidates:
            score = self._promise_similarity(
                entry.text, text, entry.owner_name, payload.get("speaker")
            )
            if score > best_score:
                best_text = text
                best_payload = payload
                best_score = score

        evidence = []
        if best_payload:
            evidence.append(PromiseRadarEvidence(**best_payload))
        if not evidence:
            for item in entry.evidence or []:
                if isinstance(item, dict):
                    evidence.append(PromiseRadarEvidence(**item))
                    if len(evidence) >= 3:
                        break

        overlap = sorted(set(self._tokens(entry.text)) & set(self._tokens(best_text)))[:8]
        return PromiseMatchExplanation(
            ledger_entry_id=str(entry.id),
            matched_task_id=best_payload.get("source_task_id") or entry.last_source_task_id,
            matched_text=best_text or (evidence[0].transcript if evidence else None),
            similarity=round(best_score, 3),
            overlap_terms=overlap,
            confidence_factors=self._confidence_factors(entry, best_score, evidence),
            rationale=self._match_rationale(entry, best_score, best_text),
            evidence=evidence[:3],
        )

    def _confidence_factors(
        self,
        entry: PromiseLedgerEntry,
        similarity: float,
        evidence: list[PromiseRadarEvidence],
    ) -> list[str]:
        factors: list[str] = []
        if similarity >= 0.65:
            factors.append("약속 내용의 의미 유사도가 높습니다.")
        elif similarity >= 0.35:
            factors.append("약속 내용의 핵심 단어가 일부 겹칩니다.")
        if entry.owner_name:
            factors.append("원장에 담당자 이름이 있습니다.")
        if entry.due_at:
            factors.append("기한 정보가 있어 상태 위험도를 계산할 수 있습니다.")
        if evidence:
            factors.append("회의 원문 근거가 연결되어 있습니다.")
        if entry.occurrences >= 2:
            factors.append(f"{entry.occurrences}회 이상 반복 추적된 약속입니다.")
        return factors

    def _match_rationale(
        self,
        entry: PromiseLedgerEntry,
        similarity: float,
        matched_text: str,
    ) -> str:
        if similarity >= 0.65:
            return "현재 회의 발화가 원장 약속과 강하게 일치합니다."
        if similarity >= 0.35:
            return "현재 회의 발화가 원장 약속과 일부 유사합니다."
        if matched_text:
            return "현재 회의에서 약한 관련 신호만 발견했습니다."
        return "현재 회의에서 직접 관련 발화를 찾지 못했습니다."

    def _marker_hits(self, text: str, category: str) -> list[str]:
        lowered = text.lower()
        return [marker for marker in _AUTOPILOT_MARKERS[category] if marker.lower() in lowered]

    def _looks_future_intent(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            marker in lowered
            for marker in (
                "하겠습니다",
                "하겠",
                "할 예정",
                "해야",
                "진행하겠습니다",
                "will",
                "todo",
                "next",
            )
        )

    def _autopilot_reason(
        self,
        status: str,
        marker_hits: list[str],
        matched_text: str,
    ) -> str:
        markers = ", ".join(marker_hits[:3])
        if status == "completed":
            return f"현재 회의 근거에서 완료 신호({markers})가 확인됐습니다."
        if status == "delayed":
            return f"현재 회의 근거에서 지연 신호({markers})가 확인됐습니다."
        if status == "changed":
            return f"현재 회의 근거에서 범위/기한 변경 신호({markers})가 확인됐습니다."
        if status == "dismissed":
            return f"현재 회의 근거에서 취소/폐기 신호({markers})가 확인됐습니다."
        return f"현재 회의 근거를 확인했습니다: {matched_text[:80]}"

    async def _find_open_ledger_entry(
        self,
        session: AsyncSession,
        canonical_key: str,
        canonical_text: str,
        *,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
        team_id: UUID | str | None = None,
    ) -> PromiseLedgerEntry | None:
        scoped = self._ledger_scope_condition(owner_id, guest_session_id, team_id=team_id)
        exact_result = await session.execute(
            select(PromiseLedgerEntry)
            .where(
                scoped,
                PromiseLedgerEntry.canonical_key == canonical_key,
                PromiseLedgerEntry.status.in_(_OPEN_LEDGER_STATUSES),
            )
            .order_by(PromiseLedgerEntry.last_seen_at.desc())
            .limit(1)
        )
        exact = exact_result.scalar_one_or_none()
        if exact is not None:
            return exact

        result = await session.execute(
            select(PromiseLedgerEntry)
            .where(
                scoped,
                PromiseLedgerEntry.status.in_(_OPEN_LEDGER_STATUSES),
            )
            .order_by(PromiseLedgerEntry.last_seen_at.desc())
            .limit(30)
        )
        best: PromiseLedgerEntry | None = None
        best_score = 0.0
        for entry in result.scalars().all():
            score = self._promise_similarity(canonical_text, entry.canonical_text)
            if score > best_score:
                best = entry
                best_score = score
        return best if best is not None and best_score >= 0.74 else None

    def _entry_to_response(self, entry: PromiseLedgerEntry) -> PromiseLedgerEntryResponse:
        evidence = []
        for item in entry.evidence or []:
            if isinstance(item, dict):
                evidence.append(PromiseRadarEvidence(**item))
        identity_confidence, identity_factors = self._identity_confidence(entry, evidence)
        return PromiseLedgerEntryResponse(
            id=str(entry.id),
            canonical_key=entry.canonical_key,
            canonical_text=entry.canonical_text,
            text=entry.text,
            owner=entry.owner_name,
            team_id=str(entry.team_id) if entry.team_id else None,
            assigned_user_id=str(entry.assigned_user_id) if entry.assigned_user_id else None,
            speaker_label=entry.speaker_label,
            speaker_profile_id=str(entry.speaker_profile_id) if entry.speaker_profile_id else None,
            status=entry.status,
            priority=entry.priority,
            risk_level=entry.risk_level,
            confidence=entry.confidence,
            due_date=entry.due_date_text,
            due_at=entry.due_at,
            reminder_at=entry.reminder_at,
            notification_sent_at=entry.notification_sent_at,
            occurrences=entry.occurrences,
            first_seen_at=entry.first_seen_at,
            last_seen_at=entry.last_seen_at,
            evidence=evidence,
            user_confirmed=entry.user_confirmed,
            semantic_summary=entry.semantic_summary,
            calendar_event=entry.calendar_event,
            action_item_id=str(entry.action_item_id) if entry.action_item_id else None,
            dismissed_reason=entry.dismissed_reason,
            quality=self._quality_score(entry),
            identity_confidence=identity_confidence,
            identity_confidence_factors=identity_factors,
        )

    def _telemetry_status(self, value: dict[str, Any], event_type: str) -> str:
        autopilot = value.get("autopilot") if isinstance(value.get("autopilot"), dict) else {}
        return str(
            value.get("predicted_status")
            or value.get("suggested_status")
            or value.get("current_status")
            or autopilot.get("suggested_status")
            or event_type
            or "unknown"
        ).strip()

    def _telemetry_owner_key(self, value: dict[str, Any]) -> str | None:
        expected = self._clean_optional(value.get("expected_owner"))
        current = self._clean_optional(value.get("current_owner") or value.get("owner"))
        if expected and current and self._owner_key(expected) != self._owner_key(current):
            return "owner_corrected"
        if expected or current:
            return "owner_confirmed"
        expected_user = self._clean_optional(value.get("expected_assigned_user_id"))
        current_user = self._clean_optional(value.get("assigned_user_id"))
        if expected_user and current_user and expected_user != current_user:
            return "assigned_user_corrected"
        return None

    def _telemetry_locale(self, value: dict[str, Any]) -> str:
        text = " ".join(
            str(value.get(key) or "")
            for key in (
                "note",
                "reason",
                "current_text",
                "matched_text",
                "expected_owner",
                "current_owner",
            )
        )
        autopilot = value.get("autopilot") if isinstance(value.get("autopilot"), dict) else {}
        if autopilot:
            text = f"{text} {autopilot.get('reason') or ''}"
        if re.search(r"[가-힣]", text):
            return "ko"
        if re.search(r"[A-Za-z]", text):
            return "en"
        return "unknown"

    def _telemetry_mark(
        self,
        buckets: dict[str, Counter[str]],
        key: str,
        event_type: str,
        value: dict[str, Any],
    ) -> None:
        normalized = key or "unknown"
        bucket = buckets.setdefault(normalized, Counter())
        bucket["sample"] += 1
        if event_type in {"autopilot_confirmed", "autopilot_applied"}:
            bucket["confirmed"] += 1
        if event_type in {"learning_feedback", "autopilot_review_rejected", "autopilot_undone"}:
            bucket["false_positive"] += 1
        if value.get("expected_owner") or value.get("expected_assigned_user_id"):
            bucket["correction"] += 1

    def _telemetry_segments(
        self,
        dimension: str,
        buckets: dict[str, Counter[str]],
    ) -> list[PromiseLearningTelemetrySegment]:
        segments: list[PromiseLearningTelemetrySegment] = []
        for value, counts in sorted(
            buckets.items(),
            key=lambda item: (item[1]["false_positive"], item[1]["sample"]),
            reverse=True,
        ):
            sample_count = int(counts["sample"])
            confirmed_count = int(counts["confirmed"])
            false_positive_count = int(counts["false_positive"])
            correction_count = int(counts["correction"])
            notes: list[str] = []
            if sample_count and false_positive_count / sample_count >= 0.34:
                notes.append("preview-only 권장")
            if correction_count:
                notes.append("사용자 보정 반영됨")
            segments.append(
                PromiseLearningTelemetrySegment(
                    dimension=dimension,
                    value=value,
                    sample_count=sample_count,
                    confirmed_count=confirmed_count,
                    false_positive_count=false_positive_count,
                    correction_count=correction_count,
                    precision=round(confirmed_count / sample_count, 3) if sample_count else 0.0,
                    false_positive_rate=round(false_positive_count / sample_count, 3)
                    if sample_count
                    else 0.0,
                    notes=notes,
                )
            )
        return segments[:12]

    def _event_to_response(self, event: PromiseLedgerEvent) -> PromiseLedgerHistoryEntry:
        return PromiseLedgerHistoryEntry(
            id=str(event.id),
            ledger_entry_id=str(event.ledger_entry_id),
            event_type=event.event_type,
            actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
            old_value=event.old_value,
            new_value=event.new_value,
            note=event.note,
            created_at=event.created_at,
        )

    def _timeline_item(self, event: PromiseLedgerEvent) -> PromiseTimelineItem:
        old = event.old_value or {}
        new = event.new_value or {}
        label_by_type = {
            "created": "약속이 처음 감지됐습니다.",
            "updated": "약속이 수정됐습니다.",
            "autopilot_applied": "자동 판정이 적용됐습니다.",
            "autopilot_assessed": "자동 판정이 검토됐습니다.",
            "learning_feedback": "사용자 피드백이 학습에 반영됐습니다.",
            "merged": "중복 약속이 병합됐습니다.",
            "merged_away": "다른 약속으로 병합됐습니다.",
            "split": "약속이 분리됐습니다.",
            "split_created": "분리된 약속이 생성됐습니다.",
            "calendar_created": "캘린더 후보가 생성됐습니다.",
            "calendar_exported": "캘린더 내보내기가 생성됐습니다.",
            "action_item_created": "앱 내부 할 일이 생성됐습니다.",
            "notification_sent": "기한 알림이 발송됐습니다.",
            "external_exported": "외부 업무도구로 전송됐습니다.",
        }
        autopilot = new.get("autopilot") if isinstance(new.get("autopilot"), dict) else {}
        status_before = old.get("status") or new.get("current_status")
        status_after = new.get("status") or new.get("expected_status")
        confidence = autopilot.get("confidence") or new.get("confidence")
        source_task_id = (
            new.get("source_task_id")
            or new.get("last_source_task_id")
            or old.get("source_task_id")
            or old.get("last_source_task_id")
        )
        return PromiseTimelineItem(
            id=str(event.id),
            event_type=event.event_type,
            label=label_by_type.get(event.event_type, "약속 이력이 기록됐습니다."),
            created_at=event.created_at,
            actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
            status_before=str(status_before) if status_before else None,
            status_after=str(status_after) if status_after else None,
            confidence=float(confidence) if confidence is not None else None,
            source_task_id=str(source_task_id) if source_task_id else None,
            note=event.note,
        )

    async def _scoped_events(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
        team_id: UUID | str | None,
        limit: int = 200,
    ) -> list[PromiseLedgerEvent]:
        team_uuid = self._coerce_uuid(team_id)
        owner_uuid = self._coerce_uuid(owner_id)
        stmt = select(PromiseLedgerEvent)
        if team_uuid is not None:
            stmt = stmt.where(PromiseLedgerEvent.team_id == team_uuid)
        elif owner_uuid is not None:
            stmt = stmt.where(PromiseLedgerEvent.owner_id == owner_uuid)
        elif guest_session_id:
            stmt = stmt.where(PromiseLedgerEvent.guest_session_id == guest_session_id)
        else:
            return []
        stmt = stmt.order_by(PromiseLedgerEvent.created_at.desc()).limit(max(1, min(limit, 500)))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _owner_alias_graph(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
        team_id: UUID | str | None,
        event_aliases: dict[str, str],
        limit: int = 200,
    ) -> list[PromiseOwnerAlias]:
        scoped = self._ledger_scope_condition(owner_id, guest_session_id, team_id=team_id)
        result = await session.execute(
            select(PromiseLedgerEntry)
            .where(scoped)
            .order_by(PromiseLedgerEntry.last_seen_at.desc())
            .limit(max(1, min(limit, 300)))
        )
        grouped: dict[tuple[str, str, str | None, str | None, str | None], int] = {}

        def add_alias(
            alias: str | None,
            canonical_owner: str | None,
            *,
            speaker_label: str | None = None,
            speaker_profile_id: str | None = None,
            assigned_user_id: UUID | str | None = None,
        ) -> None:
            clean_alias = self._clean_optional(alias)
            clean_owner = self._clean_optional(canonical_owner)
            if not clean_alias or not clean_owner:
                return
            key = (
                clean_alias,
                clean_owner,
                speaker_label,
                speaker_profile_id,
                str(assigned_user_id) if assigned_user_id else None,
            )
            grouped[key] = grouped.get(key, 0) + 1

        for entry in result.scalars().all():
            add_alias(entry.owner_name, entry.owner_name, assigned_user_id=entry.assigned_user_id)
            add_alias(
                entry.speaker_label,
                entry.owner_name,
                speaker_label=entry.speaker_label,
                speaker_profile_id=str(entry.speaker_profile_id)
                if entry.speaker_profile_id
                else None,
                assigned_user_id=entry.assigned_user_id,
            )
            add_alias(
                str(entry.speaker_profile_id) if entry.speaker_profile_id else None,
                entry.owner_name,
                speaker_label=entry.speaker_label,
                speaker_profile_id=str(entry.speaker_profile_id)
                if entry.speaker_profile_id
                else None,
                assigned_user_id=entry.assigned_user_id,
            )
            for item in entry.evidence or []:
                if isinstance(item, dict):
                    add_alias(
                        item.get("speaker"),
                        entry.owner_name,
                        assigned_user_id=entry.assigned_user_id,
                    )
                    add_alias(
                        item.get("speaker_label"),
                        entry.owner_name,
                        speaker_label=item.get("speaker_label"),
                        speaker_profile_id=item.get("speaker_profile_id"),
                        assigned_user_id=entry.assigned_user_id,
                    )

        for alias, canonical in event_aliases.items():
            add_alias(alias, canonical)

        aliases = [
            PromiseOwnerAlias(
                alias=alias,
                canonical_owner=canonical,
                speaker_label=speaker_label,
                speaker_profile_id=speaker_profile_id,
                assigned_user_id=assigned_user_id,
                confidence=min(0.97, 0.65 + count * 0.08),
                source_count=count,
            )
            for (
                alias,
                canonical,
                speaker_label,
                speaker_profile_id,
                assigned_user_id,
            ), count in grouped.items()
        ]
        aliases.sort(key=lambda item: (item.confidence, item.source_count), reverse=True)
        return aliases[:50]

    def _scope_label(
        self,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
        team_id: UUID | str | None,
    ) -> str:
        if team_id:
            return f"team:{team_id}"
        if owner_id:
            return f"owner:{owner_id}"
        if guest_session_id:
            return f"guest:{guest_session_id}"
        return "none"

    def _automation_policy_from_value(
        self,
        value: dict[str, Any],
        *,
        scope: str,
        updated_at: datetime | None,
    ) -> PromiseAutomationPolicy:
        mode = str(value.get("mode") or "safe_auto").strip().lower()
        if mode not in _AUTOMATION_POLICY_MODES:
            mode = "safe_auto"
        raw_statuses = value.get("allowed_auto_statuses")
        statuses = [
            str(status).strip().lower()
            for status in (raw_statuses if isinstance(raw_statuses, list) else [])
            if str(status).strip().lower() in _AUTOMATION_POLICY_DEFAULT_ALLOWED
        ]
        if not statuses and mode in {"safe_auto", "completed_only"}:
            statuses = (
                ["completed"]
                if mode == "completed_only"
                else sorted(_AUTOMATION_POLICY_DEFAULT_ALLOWED)
            )
        return PromiseAutomationPolicy(
            scope=scope,
            mode=mode,
            allowed_auto_statuses=statuses,
            high_risk_requires_review=bool(value.get("high_risk_requires_review", True)),
            assignee_change_requires_review=bool(
                value.get("assignee_change_requires_review", True)
            ),
            conflict_requires_review=bool(value.get("conflict_requires_review", True)),
            updated_at=updated_at,
        )

    def _digest_preference_from_value(
        self,
        value: dict[str, Any],
        *,
        scope: str,
        updated_at: datetime | None,
    ) -> PromiseDigestPreference:
        cadence = str(value.get("cadence") or "daily").strip().lower()
        if cadence not in {"daily", "weekly"}:
            cadence = "daily"
        return PromiseDigestPreference(
            scope=scope,
            enabled=bool(value.get("enabled", False)),
            cadence=cadence,
            local_time=self._hhmm(value.get("local_time"), default="08:30"),
            timezone=str(value.get("timezone") or "Asia/Seoul").strip() or "Asia/Seoul",
            quiet_hours_start=self._optional_hhmm(value.get("quiet_hours_start"), "22:00"),
            quiet_hours_end=self._optional_hhmm(value.get("quiet_hours_end"), "07:00"),
            updated_at=updated_at,
        )

    def _hhmm(self, value: Any, *, default: str) -> str:
        text = str(value or default).strip()
        if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", text):
            return text
        return default

    def _responsibility_score_from_counts(self, values: dict[str, int]) -> int:
        return min(
            100,
            max(
                0,
                int(values.get("open", 0)) * 10
                + int(values.get("delayed", 0)) * 14
                + int(values.get("blocked", 0)) * 18
                + int(values.get("overdue", 0)) * 25
                + int(values.get("unconfirmed", 0)) * 7
                + int(values.get("recurring", 0)) * 10
                - int(values.get("completed", 0)) * 4,
            ),
        )

    def _responsibility_risk_level(self, score: int) -> str:
        if score >= 80:
            return "critical"
        if score >= 55:
            return "high"
        if score >= 30:
            return "medium"
        return "low"

    def _optional_hhmm(self, value: Any, default: str | None) -> str | None:
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return None
        if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", text):
            return text
        return default

    async def _recent_history(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
        team_id: UUID | str | None,
        limit: int = 12,
    ) -> list[PromiseLedgerHistoryEntry]:
        team_uuid = self._coerce_uuid(team_id)
        owner_uuid = self._coerce_uuid(owner_id)
        stmt = select(PromiseLedgerEvent)
        if team_uuid is not None:
            stmt = stmt.where(PromiseLedgerEvent.team_id == team_uuid)
        elif owner_uuid is not None:
            stmt = stmt.where(PromiseLedgerEvent.owner_id == owner_uuid)
        elif guest_session_id:
            stmt = stmt.where(PromiseLedgerEvent.guest_session_id == guest_session_id)
        else:
            return []
        stmt = stmt.order_by(PromiseLedgerEvent.created_at.desc()).limit(max(1, min(limit, 50)))
        result = await session.execute(stmt)
        return [self._event_to_response(item) for item in result.scalars().all()]

    async def _digest_already_sent(
        self,
        session: AsyncSession,
        target_user_id: UUID,
        *,
        cadence: str,
        moment: datetime,
    ) -> bool:
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(
                PromiseLedgerEvent.actor_user_id == target_user_id,
                PromiseLedgerEvent.event_type == "digest_notification_sent",
            )
            .order_by(PromiseLedgerEvent.created_at.desc())
            .limit(50)
        )
        for event in result.scalars().all():
            if not isinstance(event.new_value, dict):
                continue
            if event.new_value.get("cadence") != cadence:
                continue
            if self._event_matches_local_day(event, moment):
                return True
        return False

    async def _pre_meeting_brief_already_sent(
        self,
        session: AsyncSession,
        target_user_id: UUID,
        *,
        moment: datetime,
    ) -> bool:
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(
                PromiseLedgerEvent.actor_user_id == target_user_id,
                PromiseLedgerEvent.event_type == "pre_meeting_brief_sent",
            )
            .order_by(PromiseLedgerEvent.created_at.desc())
            .limit(50)
        )
        return any(self._event_matches_local_day(event, moment) for event in result.scalars().all())

    def _event_matches_local_day(
        self,
        event: PromiseLedgerEvent,
        moment: datetime,
    ) -> bool:
        value = event.new_value if isinstance(event.new_value, dict) else {}
        sent_at = value.get("sent_at")
        if isinstance(sent_at, str):
            try:
                return datetime.fromisoformat(sent_at).date() == moment.date()
            except ValueError:
                pass
        return event.created_at.date() == moment.date()

    async def _digest_preference_enabled_for_target(
        self,
        session: AsyncSession,
        target_user_id: UUID,
        *,
        cadence: str,
        moment: datetime,
    ) -> bool:
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(
                PromiseLedgerEvent.actor_user_id == target_user_id,
                PromiseLedgerEvent.event_type == "digest_preference_updated",
            )
            .order_by(PromiseLedgerEvent.created_at.desc())
            .limit(1)
        )
        event = result.scalar_one_or_none()
        if event is None or not isinstance(event.new_value, dict):
            return False
        preference = self._digest_preference_from_value(
            event.new_value,
            scope=f"owner:{target_user_id}",
            updated_at=event.created_at,
        )
        return (
            preference.enabled
            and preference.cadence == cadence
            and self._digest_preference_due_now(preference, moment)
        )

    def _digest_preference_due_now(
        self,
        preference: PromiseDigestPreference,
        moment: datetime,
    ) -> bool:
        try:
            timezone = ZoneInfo(preference.timezone)
        except ZoneInfoNotFoundError:
            timezone = ZoneInfo("Asia/Seoul")
        aware = moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
        local = aware.astimezone(timezone)
        if self._in_quiet_hours(
            local,
            preference.quiet_hours_start,
            preference.quiet_hours_end,
        ):
            return False
        hour, minute = [int(part) for part in preference.local_time.split(":", maxsplit=1)]
        scheduled = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return 0 <= (local - scheduled).total_seconds() < 3600

    def _in_quiet_hours(
        self,
        local: datetime,
        start: str | None,
        end: str | None,
    ) -> bool:
        if not start or not end:
            return False
        start_minutes = self._hhmm_to_minutes(start)
        end_minutes = self._hhmm_to_minutes(end)
        now_minutes = local.hour * 60 + local.minute
        if start_minutes == end_minutes:
            return False
        if start_minutes < end_minutes:
            return start_minutes <= now_minutes < end_minutes
        return now_minutes >= start_minutes or now_minutes < end_minutes

    def _hhmm_to_minutes(self, value: str) -> int:
        hour, minute = [int(part) for part in value.split(":", maxsplit=1)]
        return hour * 60 + minute

    async def _rejected_review_keys(
        self,
        session: AsyncSession,
        task_id: str,
        *,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
        team_id: UUID | str | None,
    ) -> set[tuple[str, str]]:
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(
                self._event_scope_condition(owner_id, guest_session_id, team_id=team_id),
                PromiseLedgerEvent.event_type.in_(
                    [
                        "autopilot_review_rejected",
                        "autopilot_undone",
                        "autopilot_quarantined",
                    ]
                ),
            )
            .order_by(PromiseLedgerEvent.created_at.desc())
            .limit(500)
        )
        rejected: set[tuple[str, str]] = set()
        for event in result.scalars().all():
            value = event.new_value if isinstance(event.new_value, dict) else {}
            if value.get("task_id") and value.get("task_id") != task_id:
                continue
            status = str(value.get("suggested_status") or "").strip()
            if status:
                rejected.add((str(event.ledger_entry_id), status))
        return rejected

    def _record_ledger_event(
        self,
        session: AsyncSession,
        entry: PromiseLedgerEntry,
        event_type: str,
        *,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        note: str | None = None,
        actor_user_id: UUID | str | None = None,
    ) -> None:
        session.add(
            PromiseLedgerEvent(
                ledger_entry_id=entry.id,
                owner_id=entry.owner_id,
                guest_session_id=entry.guest_session_id,
                team_id=entry.team_id,
                actor_user_id=self._coerce_uuid(actor_user_id),
                event_type=event_type,
                old_value=old_value,
                new_value=new_value,
                note=note.strip() if note else None,
            )
        )

    def _ledger_snapshot(self, entry: PromiseLedgerEntry) -> dict[str, Any]:
        return {
            "id": str(entry.id),
            "text": entry.text,
            "canonical_key": entry.canonical_key,
            "canonical_text": entry.canonical_text,
            "owner": entry.owner_name,
            "owner_name": entry.owner_name,
            "team_id": str(entry.team_id) if entry.team_id else None,
            "assigned_user_id": str(entry.assigned_user_id) if entry.assigned_user_id else None,
            "status": entry.status,
            "priority": entry.priority,
            "risk_level": entry.risk_level,
            "confidence": entry.confidence,
            "due_date": entry.due_date_text,
            "due_at": entry.due_at.isoformat() if entry.due_at else None,
            "reminder_at": entry.reminder_at.isoformat() if entry.reminder_at else None,
            "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
            "notification_sent_at": (
                entry.notification_sent_at.isoformat() if entry.notification_sent_at else None
            ),
            "occurrences": entry.occurrences,
            "user_confirmed": entry.user_confirmed,
            "dismissed_reason": entry.dismissed_reason,
            "action_item_id": str(entry.action_item_id) if entry.action_item_id else None,
        }

    def _apply_ledger_snapshot(
        self,
        entry: PromiseLedgerEntry,
        snapshot: dict[str, Any],
    ) -> None:
        text = self._clean_optional(snapshot.get("text"))
        if text:
            entry.text = text
        canonical_key = self._clean_optional(snapshot.get("canonical_key"))
        if canonical_key:
            entry.canonical_key = canonical_key
        canonical_text = self._clean_optional(snapshot.get("canonical_text")) or text
        if canonical_text:
            entry.canonical_text = canonical_text
        entry.owner_name = self._clean_optional(snapshot.get("owner_name") or snapshot.get("owner"))
        entry.team_id = self._coerce_uuid(snapshot.get("team_id"))
        entry.assigned_user_id = self._coerce_uuid(snapshot.get("assigned_user_id"))
        status = self._clean_optional(snapshot.get("status"))
        if status in _VALID_LEDGER_STATUSES:
            entry.status = status
        priority = self._clean_optional(snapshot.get("priority"))
        if priority:
            entry.priority = priority
        risk_level = self._clean_optional(snapshot.get("risk_level"))
        if risk_level:
            entry.risk_level = risk_level
        try:
            entry.confidence = float(snapshot.get("confidence") or entry.confidence or 0.0)
        except (TypeError, ValueError):
            pass
        entry.due_date_text = self._clean_optional(
            snapshot.get("due_date_text") or snapshot.get("due_date")
        )
        entry.due_at = self._parse_datetime(snapshot.get("due_at"))
        entry.reminder_at = self._parse_datetime(snapshot.get("reminder_at"))
        entry.completed_at = self._parse_datetime(snapshot.get("completed_at"))
        entry.notification_sent_at = self._parse_datetime(snapshot.get("notification_sent_at"))
        try:
            entry.occurrences = max(1, int(snapshot.get("occurrences") or entry.occurrences or 1))
        except (TypeError, ValueError):
            pass
        if "user_confirmed" in snapshot:
            entry.user_confirmed = bool(snapshot.get("user_confirmed"))
        entry.dismissed_reason = self._clean_optional(snapshot.get("dismissed_reason"))
        entry.action_item_id = self._coerce_uuid(snapshot.get("action_item_id"))

    def _split_evidence(
        self,
        evidence: list[dict[str, Any]],
        indices: list[int],
    ) -> list[dict[str, Any]]:
        if not evidence:
            return []
        selected: list[dict[str, Any]] = []
        for index in indices:
            if 0 <= index < len(evidence):
                selected.append(evidence[index])
        return selected or evidence[:1]

    def _notification_body(self, entry: PromiseLedgerEntry) -> str:
        due = f" · 기한 {entry.due_date_text}" if entry.due_date_text else ""
        owner = f"{entry.owner_name} · " if entry.owner_name else ""
        return f"{owner}{entry.text[:80]}{due}"

    def _match_semantic_promise(
        self,
        promise: PromiseRadarPromise,
        semantic_promises: list[_SemanticPromise],
    ) -> _SemanticPromise | None:
        best: _SemanticPromise | None = None
        best_score = 0.0
        for semantic in semantic_promises:
            score = self._promise_similarity(promise.text, semantic.text)
            if score > best_score:
                best = semantic
                best_score = score
        return best if best_score >= 0.48 else None

    def _canonical_key(self, text: str) -> str:
        normalized = self._normalized_text(text)
        return (normalized or text.strip().lower())[:512]

    def _parse_due_at(self, due_date: str | None, anchor: datetime | None) -> datetime | None:
        if not due_date:
            return None
        text = due_date.strip().lower()
        base = (anchor or datetime.now(UTC).replace(tzinfo=None)).replace(tzinfo=None)
        hour, minute = self._parse_due_time(text)

        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed.replace(hour=hour, minute=minute)
            except ValueError:
                pass

        month_day = re.search(r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
        if month_day:
            month = int(month_day.group(1))
            day = int(month_day.group(2))
            try:
                candidate = base.replace(
                    month=month,
                    day=day,
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )
                if candidate < base:
                    candidate = candidate.replace(year=candidate.year + 1)
                return candidate
            except ValueError:
                return None

        slash_month_day = re.search(r"(?<!\d)(\d{1,2})[./-](\d{1,2})(?!\d)", text)
        if slash_month_day:
            month = int(slash_month_day.group(1))
            day = int(slash_month_day.group(2))
            try:
                candidate = base.replace(
                    month=month,
                    day=day,
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )
                if candidate < base:
                    candidate = candidate.replace(year=candidate.year + 1)
                return candidate
            except ValueError:
                return None

        relative_day = re.search(r"(\d+)\s*일\s*(후|뒤|내)", text)
        if relative_day:
            return (base + timedelta(days=int(relative_day.group(1)))).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

        relative_week = re.search(r"(\d+)\s*주\s*(후|뒤|내)", text)
        if relative_week:
            return (base + timedelta(weeks=int(relative_week.group(1)))).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

        if "오늘" in text:
            return base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if "내일" in text:
            return (base + timedelta(days=1)).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
        if "모레" in text:
            return (base + timedelta(days=2)).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

        weekday_match = re.search(r"(이번|다음)?\s*주?\s*([월화수목금토일])(?:요일)?", text)
        if weekday_match:
            prefix = weekday_match.group(1)
            weekday = _WEEKDAY_TO_INDEX[weekday_match.group(2)]
            if prefix == "다음":
                start = base + timedelta(days=(7 - base.weekday()) % 7)
                candidate = start + timedelta(days=weekday)
            elif prefix == "이번":
                start = base - timedelta(days=base.weekday())
                candidate = start + timedelta(days=weekday)
                if candidate < base:
                    candidate += timedelta(days=7)
            else:
                candidate = base + timedelta(days=(weekday - base.weekday()) % 7)
            return candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if "이번 주" in text:
            days_until_friday = (4 - base.weekday()) % 7
            return (base + timedelta(days=days_until_friday)).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
        if "다음 주" in text:
            return (base + timedelta(days=7)).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
        return None

    def _parse_due_time(self, text: str) -> tuple[int, int]:
        match = re.search(r"(오전|오후)?\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분?)?", text)
        if not match:
            return 18, 0
        meridiem = match.group(1)
        hour = int(match.group(2))
        minute = int(match.group(3) or 0)
        if meridiem == "오후" and hour < 12:
            hour += 12
        if meridiem == "오전" and hour == 12:
            hour = 0
        hour = min(max(hour, 0), 23)
        minute = min(max(minute, 0), 59)
        return hour, minute

    def _ledger_risk_level(
        self,
        priority: str,
        due_at: datetime | None,
        occurrences: int,
    ) -> str:
        now = datetime.now(UTC).replace(tzinfo=None)
        if due_at is not None and due_at < now:
            return "high"
        if priority.lower() == "high" and occurrences >= 2:
            return "high"
        if occurrences >= 3:
            return "high"
        if priority.lower() == "high" or occurrences >= 2 or due_at is not None:
            return "medium"
        return "low"

    def _merge_evidence(
        self,
        existing: list[dict[str, Any]],
        new_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, str, float | None]] = set()
        for item in [*existing, *new_items]:
            key = (
                str(item.get("source_task_id") or ""),
                str(item.get("transcript") or ""),
                item.get("start_seconds"),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged[:8]

    def _owner_risks_from_entries(
        self,
        entries: list[PromiseLedgerEntryResponse],
    ) -> list[PromiseRadarOwnerRisk]:
        buckets: dict[str, dict[str, Any]] = {}
        now = datetime.now(UTC).replace(tzinfo=None)
        for entry in entries:
            owner = entry.owner or entry.speaker_label or "미지정"
            bucket = buckets.setdefault(
                owner, {"open": 0, "stale": 0, "recurring": 0, "latest": []}
            )
            bucket["open"] += 1
            if entry.due_at is not None and entry.due_at < now:
                bucket["stale"] += 1
            if entry.occurrences >= 2:
                bucket["recurring"] += 1
            if len(bucket["latest"]) < 3:
                bucket["latest"].append(entry.text)

        risks = []
        for owner, values in buckets.items():
            risk_score = min(
                100,
                int(values["open"]) * 8 + int(values["stale"]) * 24 + int(values["recurring"]) * 16,
            )
            risks.append(
                PromiseRadarOwnerRisk(
                    owner=owner,
                    open_promises=int(values["open"]),
                    stale_promises=int(values["stale"]),
                    recurring_promises=int(values["recurring"]),
                    risk_score=risk_score,
                    latest_promises=list(values["latest"]),
                )
            )
        return sorted(risks, key=lambda item: item.risk_score, reverse=True)

    def _briefing_question(self, entry: PromiseLedgerEntryResponse) -> str:
        owner = f"{entry.owner}님의 " if entry.owner else ""
        if entry.status == "blocked":
            return f"{owner}'{entry.text}' 약속의 차단 원인을 해소했습니까?"
        if entry.occurrences >= 3:
            return f"{owner}'{entry.text}' 약속이 {entry.occurrences}회 반복됐습니다. 완료 기준을 확정했습니까?"
        if entry.due_at is not None and entry.due_at < datetime.now(UTC).replace(tzinfo=None):
            return f"{owner}'{entry.text}' 약속의 기한이 지났습니다. 완료 또는 재조정됐습니까?"
        return f"{owner}'{entry.text}' 진행 상태를 확인했습니까?"

    def _briefing_checkpoint(self, entry: PromiseLedgerEntryResponse) -> str:
        owner = entry.owner or entry.speaker_label or "담당자 미지정"
        due = entry.due_at.strftime("%m/%d %H:%M") if entry.due_at else entry.due_date
        due_text = f" · 기한 {due}" if due else ""
        if entry.risk_level == "high" or entry.status in {"blocked", "delayed"}:
            prefix = "우선 확인"
        elif entry.occurrences >= 2:
            prefix = "반복 확인"
        else:
            prefix = "상태 확인"
        return f"{prefix}: {owner} · {entry.text}{due_text}"

    def _reminder_candidate(self, entry: PromiseLedgerEntryResponse) -> PromiseReminderCandidate:
        due_at = entry.due_at
        reminder_at = entry.reminder_at
        if reminder_at is None and due_at is not None:
            reminder_at = due_at - timedelta(hours=3)
        calendar_event = {
            "title": f"약속 확인: {entry.text[:80]}",
            "description": self._calendar_description(entry),
            "start_datetime": due_at.isoformat() if due_at else None,
            "end_datetime": (due_at + timedelta(minutes=30)).isoformat() if due_at else None,
            "status": "tentative",
            "source": "promise_radar",
        }
        return PromiseReminderCandidate(
            ledger_entry_id=entry.id,
            title=calendar_event["title"],
            owner=entry.owner,
            due_at=due_at,
            reminder_at=reminder_at,
            calendar_event=calendar_event,
        )

    async def _assignee_suggestions(
        self,
        session: AsyncSession,
        entry: PromiseLedgerEntry,
        *,
        limit: int = 5,
    ) -> list[PromiseAssigneeSuggestion]:
        users: list[User] = []
        if entry.team_id is not None:
            result = await session.execute(
                select(User)
                .join(TeamMember, TeamMember.user_id == User.id)
                .where(TeamMember.team_id == entry.team_id, User.is_active)
                .limit(50)
            )
            users = list(result.scalars().all())
        elif entry.owner_id is not None:
            result = await session.execute(select(User).where(User.id == entry.owner_id))
            user = result.scalar_one_or_none()
            if user is not None:
                users = [user]

        if not users:
            return []

        history_counts: dict[UUID, int] = {}
        if entry.owner_name:
            scoped = (
                PromiseLedgerEntry.team_id == entry.team_id
                if entry.team_id is not None
                else PromiseLedgerEntry.owner_id == entry.owner_id
            )
            result = await session.execute(
                select(PromiseLedgerEntry.assigned_user_id).where(
                    scoped,
                    PromiseLedgerEntry.owner_name == entry.owner_name,
                    PromiseLedgerEntry.assigned_user_id.is_not(None),
                )
            )
            for assigned_user_id in result.scalars().all():
                if assigned_user_id is not None:
                    history_counts[assigned_user_id] = history_counts.get(assigned_user_id, 0) + 1

        suggestions: list[PromiseAssigneeSuggestion] = []
        for user in users:
            confidence, rationale = self._assignee_confidence(entry, user, history_counts)
            suggestions.append(
                PromiseAssigneeSuggestion(
                    user_id=str(user.id),
                    display_name=user.display_name,
                    email=user.email,
                    confidence=confidence,
                    rationale=rationale,
                )
            )
        suggestions.sort(key=lambda item: item.confidence, reverse=True)
        return suggestions[: max(1, min(limit, 10))]

    def _assignee_confidence(
        self,
        entry: PromiseLedgerEntry,
        user: User,
        history_counts: dict[UUID, int],
    ) -> tuple[float, str]:
        if entry.assigned_user_id == user.id:
            return 0.99, "이미 이 약속에 지정된 사용자입니다."
        owner = (entry.owner_name or "").strip().lower()
        display = user.display_name.strip().lower()
        email = user.email.strip().lower()
        email_local = email.split("@", 1)[0]
        normalized_owner = self._normalized_person_alias(owner)
        normalized_display = self._normalized_person_alias(display)
        normalized_email_local = self._normalized_person_alias(email_local)
        if owner and (owner == display or owner in display or owner in email):
            return 0.92, "회의에서 추출된 담당자 이름이 사용자 이름/이메일과 일치합니다."
        if (
            normalized_owner
            and normalized_display
            and (
                normalized_owner == normalized_display
                or normalized_owner in normalized_display
                or normalized_display.endswith(normalized_owner)
                or self._same_korean_given_name(normalized_owner, normalized_display)
            )
        ):
            return 0.9, "화자/담당자 별칭이 사용자 이름과 일치합니다."
        if (
            normalized_owner
            and normalized_email_local
            and (
                normalized_owner in normalized_email_local
                or normalized_email_local.endswith(normalized_owner)
            )
        ):
            return 0.88, "화자/담당자 별칭이 사용자 이메일 ID와 일치합니다."
        if normalized_owner and normalized_owner in email:
            return 0.86, "화자/담당자 별칭이 사용자 이메일과 일치합니다."
        history_count = history_counts.get(user.id, 0)
        if history_count >= 3:
            return 0.84, f"같은 담당자 이름으로 과거 {history_count}회 지정됐습니다."
        if history_count:
            return 0.72, f"같은 담당자 이름으로 과거 {history_count}회 지정된 이력이 있습니다."
        if entry.owner_id == user.id:
            return 0.48, "개인 원장의 소유자입니다."
        return 0.35, "팀 멤버 후보입니다. 이름 매칭 또는 과거 지정 이력은 아직 약합니다."

    def _normalized_person_alias(self, value: str) -> str:
        base = value.lower().split("@", 1)[0]
        cleaned = re.sub(r"[\s._+-]+", "", base)
        suffixes = (
            "님께서",
            "팀장님",
            "대표님",
            "매니저님",
            "선생님",
            "대리님",
            "과장님",
            "부장님",
            "팀장",
            "대표",
            "매니저",
            "선생",
            "대리",
            "과장",
            "부장",
            "님이",
            "님은",
            "님은요",
            "님께",
            "님도",
            "님",
            "씨",
            "께서",
        )
        changed = True
        while changed and cleaned:
            changed = False
            for suffix in suffixes:
                if cleaned.endswith(suffix):
                    cleaned = cleaned[: -len(suffix)]
                    changed = True
                    break
        return cleaned

    def _same_korean_given_name(self, left: str, right: str) -> bool:
        if len(left) < 2 or len(right) < 2:
            return False
        if len(left) > 2 and len(right) > 2 and left != right:
            return False
        left_tail = left[-2:] if self._looks_korean_name(left) else left
        right_tail = right[-2:] if self._looks_korean_name(right) else right
        return left_tail == right_tail

    def _looks_korean_name(self, value: str) -> bool:
        return bool(re.fullmatch(r"[가-힣]{2,5}", value))

    def _quality_score(self, entry: PromiseLedgerEntry) -> PromiseQualityScore:
        score = 0
        strengths: list[str] = []
        issues: list[str] = []
        if entry.owner_name or entry.assigned_user_id or entry.speaker_label:
            score += 24
            strengths.append("담당자 또는 화자 근거가 있습니다.")
        else:
            issues.append("담당자 또는 화자 정보가 없습니다.")

        if entry.due_at or entry.due_date_text:
            score += 22
            strengths.append("기한 정보가 있습니다.")
        else:
            issues.append("기한이 없어 알림/캘린더 자동화가 약합니다.")

        normalized_text = entry.text.lower()
        if len(entry.text.strip()) >= 8 and any(
            term in normalized_text for term in _QUALITY_ACTION_TERMS
        ):
            score += 20
            strengths.append("행동 동사가 포함되어 있습니다.")
        else:
            issues.append("해야 할 행동이 명확하지 않습니다.")

        if entry.evidence:
            score += 16
            strengths.append("회의 원문 근거가 연결되어 있습니다.")
        else:
            issues.append("원문 근거가 없어 신뢰도 설명이 약합니다.")

        if any(term in normalized_text for term in _QUALITY_COMPLETION_TERMS):
            score += 10
            strengths.append("검증 또는 완료 기준 단서가 있습니다.")
        else:
            issues.append("완료 기준 또는 검증 단서가 부족합니다.")

        if entry.confidence >= 0.75:
            score += 8
            strengths.append("추출 신뢰도가 높습니다.")
        elif entry.confidence < 0.5:
            issues.append("추출 신뢰도가 낮아 사용자 확인이 필요합니다.")
        else:
            score += 4

        level = (
            "excellent"
            if score >= 85
            else "good"
            if score >= 70
            else "weak"
            if score >= 50
            else "risky"
        )
        return PromiseQualityScore(
            score=min(score, 100),
            level=level,
            strengths=strengths,
            issues=issues,
        )

    def _identity_confidence(
        self,
        entry: PromiseLedgerEntry,
        evidence: list[PromiseRadarEvidence],
    ) -> tuple[float | None, list[str]]:
        """Estimate how strongly owner/speaker/assignee identity is grounded."""
        score = 0.0
        factors: list[str] = []
        if entry.owner_name:
            score += 0.24
            factors.append("담당자 이름")
        if entry.assigned_user_id:
            score += 0.24
            factors.append("팀 사용자 지정")
        if entry.speaker_label:
            score += 0.16
            factors.append("화자 라벨")
        if entry.speaker_profile_id:
            score += 0.18
            factors.append("저장된 화자 프로필")
        best_voiceprint = 0.0
        for item in evidence:
            if item.voiceprint_similarity is not None:
                best_voiceprint = max(best_voiceprint, item.voiceprint_similarity)
            if (
                item.speaker
                and entry.owner_name
                and self._owner_key(item.speaker) == self._owner_key(entry.owner_name)
            ):
                score += 0.08
                factors.append("근거 발화자 일치")
                break
        if best_voiceprint >= 0.9:
            score += 0.16
            factors.append("목소리 유사도 90% 이상")
        elif best_voiceprint >= 0.8:
            score += 0.12
            factors.append("목소리 유사도 80% 이상")
        elif best_voiceprint >= 0.7:
            score += 0.06
            factors.append("목소리 유사도 70% 이상")
        if not factors:
            return None, []
        return round(min(score, 1.0), 3), factors

    def _ics_content(
        self,
        *,
        uid: str,
        title: str,
        description: str,
        start: datetime,
        end: datetime,
        promise_id: str | None = None,
    ) -> str:
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Voice to TextNote//Promise Radar//KO",
            "CALSCALE:GREGORIAN",
            "BEGIN:VEVENT",
            f"UID:{self._ics_escape(uid)}",
            f"DTSTAMP:{self._calendar_utc(datetime.now(UTC).replace(tzinfo=None))}",
            f"DTSTART:{self._calendar_utc(start)}",
            f"DTEND:{self._calendar_utc(end)}",
            f"SUMMARY:{self._ics_escape(title)}",
            f"DESCRIPTION:{self._ics_escape(description)}",
        ]
        if promise_id:
            lines.append(f"X-VOICE-TEXTNOTE-PROMISE-ID:{self._ics_escape(promise_id)}")
        lines.extend(
            [
                "STATUS:TENTATIVE",
                "END:VEVENT",
                "END:VCALENDAR",
                "",
            ]
        )
        return "\r\n".join(lines)

    def _google_calendar_url(
        self,
        title: str,
        description: str,
        start: datetime,
        end: datetime,
    ) -> str:
        dates = f"{self._calendar_utc(start)}/{self._calendar_utc(end)}"
        return (
            "https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={quote(title)}"
            f"&dates={dates}"
            f"&details={quote(description)}"
        )

    def _calendar_utc(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")

    def _ics_escape(self, value: str) -> str:
        return (
            value.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
        )

    def _calendar_description(self, entry: PromiseLedgerEntryResponse) -> str:
        evidence = entry.evidence[0].transcript if entry.evidence else entry.text
        return "\n".join(
            [
                f"담당자: {entry.owner or '미지정'}",
                f"상태: {entry.status}",
                f"위험도: {entry.risk_level}",
                f"근거: {evidence}",
            ]
        )

    def _slack_payload(self, entry: PromiseLedgerEntryResponse) -> dict[str, Any]:
        due_text = entry.due_at.isoformat() if entry.due_at else entry.due_date or "기한 없음"
        evidence = entry.evidence[0].transcript if entry.evidence else entry.text
        return {
            "text": f"Promise Radar: {entry.text}",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Promise Radar"},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*약속*\n{entry.text}"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*담당자*\n{entry.owner or '미지정'}"},
                        {"type": "mrkdwn", "text": f"*기한*\n{due_text}"},
                        {"type": "mrkdwn", "text": f"*상태*\n{entry.status}"},
                        {"type": "mrkdwn", "text": f"*위험도*\n{entry.risk_level}"},
                    ],
                },
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"근거: {evidence[:250]}"}],
                },
            ],
        }

    def _google_tasks_payload(self, entry: PromiseLedgerEntryResponse) -> dict[str, Any]:
        notes = self._calendar_description(entry)
        payload: dict[str, Any] = {
            "title": entry.text[:1024],
            "notes": notes[:8192],
            "status": "needsAction",
        }
        if entry.due_at is not None:
            due = entry.due_at
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            payload["due"] = (
                due.astimezone(UTC)
                .isoformat(timespec="milliseconds")
                .replace(
                    "+00:00",
                    "Z",
                )
            )
        return payload

    def _google_task_metadata(self, entry: PromiseLedgerEntry) -> dict[str, str]:
        calendar_event = entry.calendar_event if isinstance(entry.calendar_event, dict) else {}
        external_tasks = calendar_event.get("external_tasks")
        if not isinstance(external_tasks, dict):
            return {}
        google_tasks = external_tasks.get("google_tasks")
        if not isinstance(google_tasks, dict):
            return {}
        return {
            key: str(value)
            for key, value in google_tasks.items()
            if key
            in {
                "external_id",
                "tasklist",
                "external_url",
                "external_status",
                "source_task_id",
                "canonical_key",
                "idempotency_key",
                "synced_at",
            }
            and value
        }

    def _external_idempotency_key(self, entry: PromiseLedgerEntry, *, provider: str) -> str:
        return f"promise:{provider}:{entry.id}"

    def _external_sync_contract(
        self,
        entry: PromiseLedgerEntry,
        *,
        provider: str,
        tasklist: str | None = None,
        external_id: str | None = None,
    ) -> dict[str, str | None]:
        return {
            "provider": provider,
            "ledger_entry_id": str(entry.id),
            "canonical_key": entry.canonical_key,
            "source_task_id": entry.last_source_task_id or entry.source_task_id,
            "tasklist": tasklist,
            "external_id": external_id,
            "idempotency_key": self._external_idempotency_key(entry, provider=provider),
        }

    def _action_item_priority(self, priority: str, risk_level: str) -> str:
        if risk_level == "high":
            return "critical"
        normalized = priority.lower()
        return normalized if normalized in {"low", "medium", "high", "critical"} else "medium"

    def _coerce_uuid(self, value: Any) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None

    async def _get_record(self, session: AsyncSession, task_id: str) -> TaskResult | None:
        result = await session.execute(select(TaskResult).where(TaskResult.task_id == task_id))
        return result.scalar_one_or_none()

    async def _load_previous_summaries(
        self,
        *,
        session: AsyncSession,
        current: TaskResult,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
        team_id: UUID | str | None,
        limit: int,
    ) -> list[TaskResult]:
        stmt = select(TaskResult).where(
            TaskResult.task_id != current.task_id,
            TaskResult.task_type == "summary",
            TaskResult.status == "completed",
        )
        if current.created_at is not None:
            stmt = stmt.where(TaskResult.created_at <= current.created_at)

        team_uuid = self._coerce_uuid(team_id)
        if team_uuid is not None:
            stmt = stmt.join(MeetingOwnership, MeetingOwnership.task_id == TaskResult.task_id)
            stmt = stmt.where(MeetingOwnership.team_id == team_uuid)
        elif owner_id is not None:
            stmt = stmt.join(MeetingOwnership, MeetingOwnership.task_id == TaskResult.task_id)
            stmt = stmt.where(
                MeetingOwnership.owner_id == owner_id,
                MeetingOwnership.team_id.is_(None),
            )
        elif guest_session_id:
            stmt = stmt.where(
                TaskResult.is_guest.is_(True),
                TaskResult.guest_session_id == guest_session_id,
            )

        stmt = stmt.order_by(TaskResult.created_at.desc()).limit(max(1, min(limit, 100)))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    def _extract_promises(self, record: TaskResult) -> list[_ExtractedPromise]:
        data = self._result_data(record)
        created_at = self._created_at(record)
        raw_items = data.get("action_items")
        promises: list[_ExtractedPromise] = []

        if isinstance(raw_items, list):
            for item in raw_items:
                text = self._promise_payload_text(item)
                if not text:
                    continue
                promises.append(
                    _ExtractedPromise(
                        text=text,
                        owner=self._promise_payload_owner(item),
                        due_date=self._promise_payload_due_date(item),
                        priority=self._promise_payload_priority(item),
                        source_task_id=record.task_id,
                        source_created_at=created_at,
                        evidence=self._short_evidence(text),
                    )
                )

        if promises:
            return promises

        next_steps = data.get("next_steps")
        if isinstance(next_steps, list):
            for step in next_steps:
                text = self._promise_payload_text(step)
                if text:
                    promises.append(
                        _ExtractedPromise(
                            text=text,
                            owner=self._promise_payload_owner(step),
                            due_date=self._promise_payload_due_date(step),
                            priority=self._promise_payload_priority(step),
                            source_task_id=record.task_id,
                            source_created_at=created_at,
                            evidence=self._short_evidence(text),
                            confidence=0.58,
                        )
                    )
        return promises

    def _promise_payload_text(self, item: Any) -> str:
        if isinstance(item, str):
            return item.strip()
        if not isinstance(item, dict):
            return ""
        return str(
            item.get("task")
            or item.get("title")
            or item.get("text")
            or item.get("description")
            or item.get("summary")
            or ""
        ).strip()

    def _promise_payload_owner(self, item: Any) -> str | None:
        if not isinstance(item, dict):
            return None
        return self._clean_optional(
            item.get("assignee") or item.get("owner") or item.get("responsible")
        )

    def _promise_payload_due_date(self, item: Any) -> str | None:
        if not isinstance(item, dict):
            return None
        return self._clean_optional(item.get("deadline") or item.get("due_date") or item.get("due"))

    def _promise_payload_priority(self, item: Any) -> str:
        if not isinstance(item, dict):
            return "medium"
        return str(item.get("priority") or "medium")

    def _extract_decisions(self, record: TaskResult) -> list[str]:
        data = self._result_data(record)
        decisions = data.get("key_decisions")
        if isinstance(decisions, list):
            return [str(decision).strip() for decision in decisions if str(decision).strip()]
        return []

    def _match_carried_promises(
        self,
        current_promises: list[_ExtractedPromise],
        previous_promises: list[_ExtractedPromise],
    ) -> list[PromiseRadarCarryOver]:
        matches: list[PromiseRadarCarryOver] = []
        used_previous: set[int] = set()
        for current in current_promises:
            best_index = -1
            best_score = 0.0
            for index, previous in enumerate(previous_promises):
                if index in used_previous:
                    continue
                score = self._promise_similarity(
                    current.text,
                    previous.text,
                    current.owner,
                    previous.owner,
                )
                if score > best_score:
                    best_index = index
                    best_score = score
            if best_index >= 0 and best_score >= 0.34:
                used_previous.add(best_index)
                matches.append(
                    PromiseRadarCarryOver(
                        previous=previous_promises[best_index].to_schema(),
                        current=current.to_schema(),
                        similarity=round(best_score, 3),
                    )
                )
        return matches

    def _find_stale_promises(
        self,
        previous_promises: list[_ExtractedPromise],
        current_promises: list[_ExtractedPromise],
        current_record: TaskResult,
    ) -> list[_ExtractedPromise]:
        current_text = self._record_text(current_record)
        stale: list[_ExtractedPromise] = []
        seen: set[str] = set()
        for previous in previous_promises:
            normalized = self._normalized_text(previous.text)
            if normalized in seen:
                continue
            seen.add(normalized)
            promise_match = max(
                (
                    self._promise_similarity(
                        previous.text,
                        current.text,
                        previous.owner,
                        current.owner,
                    )
                    for current in current_promises
                ),
                default=0.0,
            )
            text_match = self._promise_similarity(previous.text, current_text)
            if promise_match < 0.28 and text_match < 0.18:
                stale.append(previous)
        return stale

    def _find_decision_drifts(
        self,
        current_record: TaskResult,
        current_decisions: list[str],
        previous_decisions: list[tuple[TaskResult, str]],
    ) -> list[PromiseRadarDecisionDrift]:
        drifts: list[PromiseRadarDecisionDrift] = []
        for current_decision in current_decisions:
            for previous_record, previous_decision in previous_decisions:
                score = self._promise_similarity(current_decision, previous_decision)
                if 0.30 <= score < 0.86 and self._normalized_text(
                    current_decision
                ) != self._normalized_text(previous_decision):
                    drifts.append(
                        PromiseRadarDecisionDrift(
                            previous_decision=previous_decision,
                            current_decision=current_decision,
                            previous_task_id=previous_record.task_id,
                            current_task_id=current_record.task_id,
                            similarity=round(score, 3),
                            evidence="유사한 주제의 결정이 과거 회의와 다르게 표현되었습니다.",
                        )
                    )
                    break
        return drifts

    def _build_promise_chains(
        self,
        promises: list[_ExtractedPromise],
        current_task_id: str,
    ) -> list[PromiseRadarPromiseChain]:
        clusters: list[list[_ExtractedPromise]] = []
        for promise in sorted(promises, key=self._promise_sort_key):
            best_cluster: list[_ExtractedPromise] | None = None
            best_score = 0.0
            for cluster in clusters:
                score = max(
                    self._promise_similarity(promise.text, item.text, promise.owner, item.owner)
                    for item in cluster
                )
                owner_matches = self._owner_key(promise.owner) == self._owner_key(cluster[-1].owner)
                if owner_matches:
                    score += 0.08
                if score > best_score:
                    best_score = score
                    best_cluster = cluster
            if best_cluster is not None and best_score >= 0.34:
                best_cluster.append(promise)
            else:
                clusters.append([promise])

        chains = [self._cluster_to_chain(cluster, current_task_id) for cluster in clusters]
        return sorted(
            chains,
            key=lambda chain: (
                {"high": 2, "medium": 1, "low": 0}.get(chain.risk_level, 0),
                chain.occurrences,
                chain.age_days,
            ),
            reverse=True,
        )

    def _cluster_to_chain(
        self,
        cluster: list[_ExtractedPromise],
        current_task_id: str,
    ) -> PromiseRadarPromiseChain:
        ordered = sorted(cluster, key=self._promise_sort_key)
        first = ordered[0]
        latest = ordered[-1]
        first_dt = self._parse_datetime(first.source_created_at)
        latest_dt = self._parse_datetime(latest.source_created_at)
        age_days = max(0, (latest_dt - first_dt).days) if first_dt and latest_dt else 0
        appears_now = latest.source_task_id == current_task_id
        status = (
            "recurring"
            if appears_now and len(ordered) > 1
            else "active"
            if appears_now
            else "stale"
        )
        risk_level = self._chain_risk_level(status, len(ordered), age_days)
        owner = latest.owner or first.owner
        return PromiseRadarPromiseChain(
            canonical_text=latest.text,
            owner=owner,
            occurrences=len(ordered),
            first_seen_at=first.source_created_at,
            last_seen_at=latest.source_created_at,
            age_days=age_days,
            status=status,
            risk_level=risk_level,
            links=[
                PromiseRadarChainLink(
                    task_id=item.source_task_id,
                    created_at=item.source_created_at,
                    text=item.text,
                    owner=item.owner,
                    due_date=item.due_date,
                )
                for item in ordered
            ],
        )

    def _build_owner_risks(
        self,
        chains: list[PromiseRadarPromiseChain],
        stale: list[_ExtractedPromise],
        carried: list[PromiseRadarCarryOver],
    ) -> list[PromiseRadarOwnerRisk]:
        owners: dict[str, dict[str, Any]] = {}
        for chain in chains:
            owner = self._owner_key(chain.owner)
            bucket = owners.setdefault(
                owner,
                {
                    "open": 0,
                    "stale": 0,
                    "recurring": 0,
                    "latest": [],
                },
            )
            if chain.status in {"active", "recurring", "stale"}:
                bucket["open"] += 1
            if chain.status == "stale":
                bucket["stale"] += 1
            if chain.status == "recurring":
                bucket["recurring"] += 1
            if len(bucket["latest"]) < 3:
                bucket["latest"].append(chain.canonical_text)

        for promise in stale:
            owner = self._owner_key(promise.owner)
            bucket = owners.setdefault(owner, {"open": 0, "stale": 0, "recurring": 0, "latest": []})
            if promise.text not in bucket["latest"] and len(bucket["latest"]) < 3:
                bucket["latest"].append(promise.text)

        for item in carried:
            owner = self._owner_key(item.current.owner or item.previous.owner)
            bucket = owners.setdefault(owner, {"open": 0, "stale": 0, "recurring": 0, "latest": []})
            bucket["recurring"] = max(bucket["recurring"], 1)

        risks = []
        for owner, values in owners.items():
            risk_score = min(
                100,
                int(values["open"]) * 8 + int(values["stale"]) * 18 + int(values["recurring"]) * 12,
            )
            risks.append(
                PromiseRadarOwnerRisk(
                    owner=owner,
                    open_promises=int(values["open"]),
                    stale_promises=int(values["stale"]),
                    recurring_promises=int(values["recurring"]),
                    risk_score=risk_score,
                    latest_promises=list(values["latest"]),
                )
            )
        return sorted(risks, key=lambda item: item.risk_score, reverse=True)

    def _build_follow_up_questions(
        self,
        stale: list[_ExtractedPromise],
        drifts: list[PromiseRadarDecisionDrift],
        chains: list[PromiseRadarPromiseChain],
    ) -> list[str]:
        questions: list[str] = []
        for chain in chains:
            if chain.status == "recurring" and chain.occurrences >= 3:
                owner = f"{chain.owner}님의 " if chain.owner else ""
                questions.append(
                    f"{owner}'{chain.canonical_text}' 약속이 {chain.occurrences}회 반복됐습니다. 오늘 완료 기준을 정했습니까?"
                )
        for promise in stale[:5]:
            owner = f"{promise.owner}님이 맡은 " if promise.owner else ""
            questions.append(f"지난 회의의 {owner}'{promise.text}' 진행 상태는 확인됐습니까?")
        for drift in drifts[:3]:
            questions.append(
                f"'{drift.previous_decision}' 결정이 '{drift.current_decision}'로 변경된 것이 맞습니까?"
            )
        return questions

    def _risk_score(
        self,
        stale: list[_ExtractedPromise],
        carried: list[PromiseRadarCarryOver],
        drifts: list[PromiseRadarDecisionDrift],
        chains: list[PromiseRadarPromiseChain],
        owner_risks: list[PromiseRadarOwnerRisk],
    ) -> int:
        chain_pressure = sum(
            18 if chain.risk_level == "high" else 9 if chain.risk_level == "medium" else 2
            for chain in chains
        )
        owner_pressure = max((owner.risk_score for owner in owner_risks), default=0) // 3
        return min(
            100,
            len(stale) * 12 + len(carried) * 7 + len(drifts) * 18 + chain_pressure + owner_pressure,
        )

    def _headline(
        self,
        *,
        current_count: int,
        stale_count: int,
        drift_count: int,
        risk_score: int,
    ) -> str:
        if current_count == 0 and stale_count == 0 and drift_count == 0:
            return "추적할 약속이나 결정 변경이 아직 없습니다."
        if risk_score >= 70:
            return "과거 약속과 결정 변경 후보가 많아 후속 확인이 필요합니다."
        if stale_count or drift_count:
            return "이번 회의 전에 확인해야 할 미해결 약속과 결정 변경 후보가 있습니다."
        return "이번 회의의 새 약속이 정리됐고 과거 미해결 위험은 낮습니다."

    def _result_data(self, record: TaskResult) -> dict[str, Any]:
        data = record.result_data if isinstance(record.result_data, dict) else {}
        nested = data.get("summary_content")
        if isinstance(nested, dict):
            merged = dict(data)
            merged.update(nested)
            return merged
        return data

    async def _meeting_titles_for_entries(
        self,
        session: AsyncSession,
        entries: list[PromiseLedgerEntry],
    ) -> dict[str, str]:
        task_ids: set[str] = set()
        for entry in entries:
            for task_id in (entry.source_task_id, entry.last_source_task_id):
                if task_id:
                    task_ids.add(str(task_id))
        if not task_ids:
            return {}
        result = await session.execute(select(TaskResult).where(TaskResult.task_id.in_(task_ids)))
        titles: dict[str, str] = {}
        for record in result.scalars().all():
            title = self._meeting_title(record)
            if title:
                titles[record.task_id] = title
        return titles

    def _meeting_title(self, record: TaskResult) -> str | None:
        data = self._result_data(record)
        for key in ("title", "meeting_title", "subject"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            value = metadata.get("title") or metadata.get("meeting_title")
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("summary_text", "summary", "markdown"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                line = next(
                    (item.strip("# -\t ") for item in value.splitlines() if item.strip()),
                    "",
                )
                if line:
                    return line[:80]
        return None

    def _fallback_series_title(self, entry: PromiseLedgerEntry) -> str:
        text = entry.semantic_summary or entry.canonical_text or entry.text
        owner = entry.owner_name or entry.speaker_label
        return f"{owner}: {text[:64]}" if owner else text[:80]

    def _meeting_series_key(self, title: str) -> str:
        normalized = self._normalized_text(title)
        if not normalized:
            normalized = "general"
        return normalized[:80]

    def _record_text(self, record: TaskResult) -> str:
        data = self._result_data(record)
        parts: list[str] = []
        for key in ("summary_text", "summary", "markdown"):
            value = data.get(key)
            if isinstance(value, str):
                parts.append(value)
        for key in ("key_decisions", "next_steps"):
            value = data.get(key)
            if isinstance(value, list):
                parts.extend(str(item) for item in value)
        for item in data.get("action_items") or []:
            if isinstance(item, dict):
                parts.append(str(item.get("task") or item.get("title") or ""))
        return "\n".join(parts)

    def _created_at(self, record: TaskResult) -> str:
        value = record.completed_at or record.created_at
        return value.isoformat() if value else ""

    def _promise_sort_key(self, promise: _ExtractedPromise) -> datetime:
        return self._parse_datetime(promise.source_created_at) or datetime.min

    def _parse_datetime(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed.replace(tzinfo=None)
        except ValueError:
            return None

    def _chain_risk_level(self, status: str, occurrences: int, age_days: int) -> str:
        if status == "stale" and age_days >= 14:
            return "high"
        if status == "recurring" and (occurrences >= 3 or age_days >= 14):
            return "high"
        if status in {"stale", "recurring"}:
            return "medium"
        return "low"

    def _short_evidence(self, text: str) -> str:
        return text if len(text) <= 160 else f"{text[:157]}..."

    def _clean_optional(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _extraction_text_matches(self, expected: str, actual: str) -> bool:
        expected_norm = self._normalized_text(expected)
        actual_norm = self._normalized_text(actual)
        if not expected_norm or not actual_norm:
            return False
        if expected_norm in actual_norm or actual_norm in expected_norm:
            return True
        expected_tokens = set(self._tokens(expected))
        actual_tokens = set(self._tokens(actual))
        if not expected_tokens or not actual_tokens:
            return False
        overlap = len(expected_tokens & actual_tokens)
        return (overlap / len(expected_tokens)) >= 0.72

    def _similarity(self, left: str, right: str) -> float:
        left_tokens = set(self._tokens(left))
        right_tokens = set(self._tokens(right))
        if not left_tokens or not right_tokens:
            return 0.0
        overlap = len(left_tokens & right_tokens)
        union = len(left_tokens | right_tokens)
        return overlap / union if union else 0.0

    def _promise_similarity(
        self,
        left: str,
        right: str,
        left_owner: str | None = None,
        right_owner: str | None = None,
    ) -> float:
        token_score = self._similarity(left, right)
        char_score = self._char_ngram_similarity(left, right)
        normalized_left = self._normalized_text(left)
        normalized_right = self._normalized_text(right)
        containment = 0.0
        if normalized_left and normalized_right:
            if normalized_left in normalized_right or normalized_right in normalized_left:
                containment = min(len(normalized_left), len(normalized_right)) / max(
                    len(normalized_left),
                    len(normalized_right),
                )
        owner_bonus = 0.0
        if (
            left_owner
            and right_owner
            and self._owner_key(left_owner) == self._owner_key(right_owner)
        ):
            owner_bonus = 0.06
        return min(1.0, token_score * 0.55 + char_score * 0.30 + containment * 0.09 + owner_bonus)

    def _char_ngram_similarity(self, left: str, right: str, n: int = 3) -> float:
        left_norm = re.sub(r"\s+", "", self._normalized_text(left))
        right_norm = re.sub(r"\s+", "", self._normalized_text(right))
        if not left_norm or not right_norm:
            return 0.0
        left_grams = self._ngrams(left_norm, n)
        right_grams = self._ngrams(right_norm, n)
        if not left_grams or not right_grams:
            return 1.0 if left_norm == right_norm else 0.0
        return (2 * len(left_grams & right_grams)) / (len(left_grams) + len(right_grams))

    def _ngrams(self, text: str, n: int) -> set[str]:
        if len(text) <= n:
            return {text}
        return {text[index : index + n] for index in range(len(text) - n + 1)}

    def _tokens(self, text: str) -> list[str]:
        tokens: list[str] = []
        for raw in _TOKEN_RE.findall(text.lower()):
            token = self._normalize_token(raw)
            if len(token) < 2 or token in _STOPWORDS:
                continue
            tokens.append(token)
        return tokens

    def _normalized_text(self, text: str) -> str:
        return " ".join(self._tokens(text))

    def _normalize_token(self, raw: str) -> str:
        token = raw.strip().lower()
        for suffix in _KOREAN_TOKEN_SUFFIXES:
            if token.endswith(suffix) and len(token) > len(suffix) + 1:
                token = token[: -len(suffix)]
                break
        for prefix, normalized in _SYNONYM_MAP.items():
            if token == prefix or token.startswith(prefix):
                return normalized
        return _SYNONYM_MAP.get(token, token)

    def _owner_key(self, owner: str | None) -> str:
        return owner.strip() if owner and owner.strip() else "미지정"
