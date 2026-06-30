"""
Cross-meeting promise radar service.

The first implementation is intentionally deterministic: it compares persisted
summary action_items/key_decisions across a user's previous meetings before any
LLM embellishment. That keeps the feature useful even when the model provider is
temporarily unavailable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.auth_models import MeetingOwnership
from backend.db.models import TaskResult
from backend.schemas.promise_radar import (
    PromiseRadarCarryOver,
    PromiseRadarChainLink,
    PromiseRadarDecisionDrift,
    PromiseRadarOwnerRisk,
    PromiseRadarPromise,
    PromiseRadarPromiseChain,
    PromiseRadarResponse,
)

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


class PromiseRadarService:
    """Builds a cross-meeting promise/decision continuity brief."""

    async def build_radar(
        self,
        session: AsyncSession,
        task_id: str,
        *,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
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
            limit=limit,
        )
        return self.analyze_records(current, previous)

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
        limit: int,
    ) -> list[TaskResult]:
        stmt = select(TaskResult).where(
            TaskResult.task_id != current.task_id,
            TaskResult.task_type == "summary",
            TaskResult.status == "completed",
        )
        if current.created_at is not None:
            stmt = stmt.where(TaskResult.created_at <= current.created_at)

        if owner_id is not None:
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
                score = self._similarity(current.text, previous.text)
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
                (self._similarity(previous.text, current.text) for current in current_promises),
                default=0.0,
            )
            text_match = self._similarity(previous.text, current_text)
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
                score = self._similarity(current_decision, previous_decision)
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
                score = max(self._similarity(promise.text, item.text) for item in cluster)
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

    def _tokens(self, text: str) -> list[str]:
        tokens: list[str] = []
        for raw in _TOKEN_RE.findall(text.lower()):
            token = raw.strip()
            if len(token) < 2 or token in _STOPWORDS:
                continue
            tokens.append(token)
        return tokens

    def _normalized_text(self, text: str) -> str:
        return " ".join(self._tokens(text))

    def _owner_key(self, owner: str | None) -> str:
        return owner.strip() if owner and owner.strip() else "미지정"
