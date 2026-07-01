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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.auth_models import MeetingOwnership, TeamMember, User
from backend.db.device_token_models import DeviceToken
from backend.db.models import ActionItem, TaskResult
from backend.db.promise_ledger_models import PromiseLedgerEntry, PromiseLedgerEvent
from backend.ml.zai_client import AsyncZAIClient, structured_json_completion_options
from backend.schemas.promise_radar import (
    PromiseAccuracyCase,
    PromiseAccuracyEvaluation,
    PromiseAssigneeSuggestion,
    PromiseAutomationPolicy,
    PromiseAutomationPolicyUpdateRequest,
    PromiseAutopilotAssessment,
    PromiseAutopilotConfirmRequest,
    PromiseAutopilotResponse,
    PromiseAutopilotReviewItem,
    PromiseAutopilotReviewQueue,
    PromiseCalendarExportResponse,
    PromiseConflictResolveRequest,
    PromiseDigest,
    PromiseEvidencePack,
    PromiseExternalExportRequest,
    PromiseExternalExportResponse,
    PromiseLearningFeedbackRequest,
    PromiseLearningFeedbackResponse,
    PromiseLearningProfile,
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
    PromiseTaskLinkResponse,
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
_AUTOMATION_POLICY_MODES = {"safe_auto", "preview_only", "completed_only", "manual_only"}
_AUTOMATION_POLICY_DEFAULT_ALLOWED = {"completed", "delayed", "changed", "dismissed"}
_AUTOPILOT_MARKERS = {
    "completed": (
        "완료",
        "끝냈",
        "끝났",
        "처리",
        "해결",
        "반영",
        "배포했",
        "done",
        "completed",
        "finished",
        "resolved",
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
        "전환",
        "대신",
        "재조정",
        "범위 조정",
        "우선순위 변경",
        "changed",
        "rescheduled",
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
            raise ValueError("회의 요약을 찾을 수 없습니다")

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
        ).limit(max(1, min(limit, 100)))
        result = await session.execute(stmt)
        return [self._entry_to_response(entry) for entry in result.scalars().all()]

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
        return self._build_next_meeting_briefing(entries)

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

        target.risk_level = self._ledger_risk_level(target.priority, target.due_at, target.occurrences)
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
        due_at = payload.due_at.replace(tzinfo=None) if payload.due_at else self._parse_due_at(
            due_text,
            original.last_seen_at,
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
            horizon = moment + (
                timedelta(days=1) if normalized == "daily" else timedelta(days=7)
            )
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
        if not candidate_assessments:
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
        start = (response.due_at or response.reminder_at or datetime.now(UTC).replace(tzinfo=None))
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
                predicted_status = self._clean_optional(new.get("predicted_status")) or current_status
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
                        status_false_positive[old_status] = status_false_positive.get(old_status, 0) + 1
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
        return PromiseExternalExportResponse(
            ledger_entry_id=str(entry.id),
            provider=provider,
            sent=sent,
            payload=slack_payload,
            message=message,
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
        return PromiseExternalExportResponse(
            ledger_entry_id=str(entry.id),
            provider="google_tasks",
            sent=sent,
            payload={"endpoint": endpoint, "query": query, "task": task_payload},
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
            predicted_by_status[predicted] = predicted_by_status.get(predicted, 0) + 1
            if predicted == expected:
                correct += 1
                correct_by_status[predicted] = correct_by_status.get(predicted, 0) + 1
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
        return PromiseAccuracyEvaluation(
            case_count=len(cases),
            correct_count=correct,
            accuracy=round(correct / len(cases), 3) if cases else 0.0,
            status_precision=precision,
            failures=failures,
        )

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
        elif explanation.similarity >= 0.18:
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

        if conflict is None and status == entry.status and entry.due_at is not None and entry.due_at < now:
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
            if policy.high_risk_requires_review and entry is not None and entry.risk_level == "high":
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
            labels = ", ".join(f"{status}:{'/'.join(markers[:2])}" for status, markers in active.items())
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
        return (
            bool(explanation.matched_text)
            and explanation.similarity >= _EVIDENCE_LOCK_MIN_SIMILARITY
            and bool(explanation.evidence)
            and len(explanation.confidence_factors) >= _EVIDENCE_LOCK_MIN_FACTORS
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
            score = self._promise_similarity(entry.text, text, entry.owner_name, payload.get("speaker"))
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
        )

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
                speaker_profile_id=str(entry.speaker_profile_id) if entry.speaker_profile_id else None,
                assigned_user_id=entry.assigned_user_id,
            )
            add_alias(
                str(entry.speaker_profile_id) if entry.speaker_profile_id else None,
                entry.owner_name,
                speaker_label=entry.speaker_label,
                speaker_profile_id=str(entry.speaker_profile_id) if entry.speaker_profile_id else None,
                assigned_user_id=entry.assigned_user_id,
            )
            for item in entry.evidence or []:
                if isinstance(item, dict):
                    add_alias(item.get("speaker"), entry.owner_name, assigned_user_id=entry.assigned_user_id)
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
            for (alias, canonical, speaker_label, speaker_profile_id, assigned_user_id), count in grouped.items()
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
            statuses = ["completed"] if mode == "completed_only" else sorted(
                _AUTOMATION_POLICY_DEFAULT_ALLOWED
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
        day_start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(PromiseLedgerEvent)
            .where(
                PromiseLedgerEvent.actor_user_id == target_user_id,
                PromiseLedgerEvent.event_type == "digest_notification_sent",
                PromiseLedgerEvent.created_at >= day_start,
            )
            .order_by(PromiseLedgerEvent.created_at.desc())
            .limit(10)
        )
        for event in result.scalars().all():
            if isinstance(event.new_value, dict) and event.new_value.get("cadence") == cadence:
                return True
        return False

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
            "owner": entry.owner_name,
            "team_id": str(entry.team_id) if entry.team_id else None,
            "assigned_user_id": str(entry.assigned_user_id) if entry.assigned_user_id else None,
            "status": entry.status,
            "priority": entry.priority,
            "risk_level": entry.risk_level,
            "confidence": entry.confidence,
            "due_date": entry.due_date_text,
            "due_at": entry.due_at.isoformat() if entry.due_at else None,
            "reminder_at": entry.reminder_at.isoformat() if entry.reminder_at else None,
            "notification_sent_at": (
                entry.notification_sent_at.isoformat() if entry.notification_sent_at else None
            ),
            "occurrences": entry.occurrences,
            "user_confirmed": entry.user_confirmed,
            "dismissed_reason": entry.dismissed_reason,
            "action_item_id": str(entry.action_item_id) if entry.action_item_id else None,
        }

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
        normalized_owner = self._normalized_person_alias(owner)
        normalized_display = self._normalized_person_alias(display)
        if owner and (owner == display or owner in display or owner in email):
            return 0.92, "회의에서 추출된 담당자 이름이 사용자 이름/이메일과 일치합니다."
        if normalized_owner and normalized_display and (
            normalized_owner == normalized_display
            or normalized_owner in normalized_display
            or normalized_display.endswith(normalized_owner)
        ):
            return 0.9, "화자/담당자 별칭이 사용자 이름과 일치합니다."
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
        cleaned = re.sub(r"[\s._@+-]+", "", value.lower())
        for suffix in ("님께서", "님", "씨", "께서", "님이", "님은", "님은요"):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)]
        return cleaned

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
        if len(entry.text.strip()) >= 8 and any(term in normalized_text for term in _QUALITY_ACTION_TERMS):
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

        level = "excellent" if score >= 85 else "good" if score >= 70 else "weak" if score >= 50 else "risky"
        return PromiseQualityScore(
            score=min(score, 100),
            level=level,
            strengths=strengths,
            issues=issues,
        )

    def _ics_content(
        self,
        *,
        uid: str,
        title: str,
        description: str,
        start: datetime,
        end: datetime,
    ) -> str:
        return "\r\n".join(
            [
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
                "STATUS:TENTATIVE",
                "END:VEVENT",
                "END:VCALENDAR",
                "",
            ]
        )

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
            value.replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace(",", "\\,")
            .replace(";", "\\;")
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
            payload["due"] = due.astimezone(UTC).isoformat(timespec="milliseconds").replace(
                "+00:00",
                "Z",
            )
        return payload

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
                if not isinstance(item, dict):
                    continue
                text = str(item.get("task") or item.get("title") or "").strip()
                if not text:
                    continue
                promises.append(
                    _ExtractedPromise(
                        text=text,
                        owner=self._clean_optional(item.get("assignee") or item.get("owner")),
                        due_date=self._clean_optional(item.get("deadline") or item.get("due_date")),
                        priority=str(item.get("priority") or "medium"),
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
                text = str(step).strip()
                if text:
                    promises.append(
                        _ExtractedPromise(
                            text=text,
                            owner=None,
                            due_date=None,
                            priority="medium",
                            source_task_id=record.task_id,
                            source_created_at=created_at,
                            evidence=self._short_evidence(text),
                            confidence=0.58,
                        )
                    )
        return promises

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
        if left_owner and right_owner and self._owner_key(left_owner) == self._owner_key(right_owner):
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
