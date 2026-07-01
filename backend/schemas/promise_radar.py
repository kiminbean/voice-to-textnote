"""
Cross-meeting promise radar schemas.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PromiseRadarPromise(BaseModel):
    """A grounded promise/action extracted from a meeting summary."""

    text: str = Field(description="Promise or action text")
    owner: str | None = Field(default=None, description="Assignee or speaker name")
    due_date: str | None = Field(default=None, description="Free-form due date")
    priority: str = Field(default="medium", description="low/medium/high or source priority")
    source_task_id: str = Field(description="Source meeting/summary task id")
    source_created_at: str = Field(description="Source record creation timestamp")
    evidence: str = Field(description="Short source-grounded evidence text")
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)


class PromiseRadarCarryOver(BaseModel):
    """A promise that appears in both past and current meetings."""

    previous: PromiseRadarPromise
    current: PromiseRadarPromise
    similarity: float = Field(ge=0.0, le=1.0)


class PromiseRadarDecisionDrift(BaseModel):
    """A possible decision change detected across meetings."""

    previous_decision: str
    current_decision: str
    previous_task_id: str
    current_task_id: str
    similarity: float = Field(ge=0.0, le=1.0)
    evidence: str


class PromiseRadarChainLink(BaseModel):
    """One occurrence in a cross-meeting promise chain."""

    task_id: str
    created_at: str
    text: str
    owner: str | None = None
    due_date: str | None = None


class PromiseRadarPromiseChain(BaseModel):
    """A promise tracked across multiple meetings."""

    canonical_text: str
    owner: str | None = None
    occurrences: int = Field(ge=1)
    first_seen_at: str
    last_seen_at: str
    age_days: int = Field(ge=0)
    status: str = Field(description="active, recurring, or stale")
    risk_level: str = Field(description="low, medium, or high")
    links: list[PromiseRadarChainLink] = Field(default_factory=list)


class PromiseRadarOwnerRisk(BaseModel):
    """Owner-level promise load and risk summary."""

    owner: str
    open_promises: int = Field(ge=0)
    stale_promises: int = Field(ge=0)
    recurring_promises: int = Field(ge=0)
    risk_score: int = Field(ge=0, le=100)
    latest_promises: list[str] = Field(default_factory=list)


class PromiseRadarEvidence(BaseModel):
    """Source-grounded evidence for one ledger promise."""

    source_task_id: str
    meeting_link: str
    transcript: str
    speaker: str | None = None
    speaker_label: str | None = None
    speaker_profile_id: str | None = None
    voiceprint_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    start_seconds: float | None = Field(default=None, ge=0.0)
    end_seconds: float | None = Field(default=None, ge=0.0)


class PromiseLedgerEntryResponse(BaseModel):
    """Editable persisted promise ledger item."""

    id: str
    canonical_key: str
    canonical_text: str
    text: str
    owner: str | None = None
    team_id: str | None = None
    assigned_user_id: str | None = None
    speaker_label: str | None = None
    speaker_profile_id: str | None = None
    status: str = Field(description="open, completed, dismissed, delegated, blocked, or changed")
    priority: str
    risk_level: str
    confidence: float = Field(ge=0.0, le=1.0)
    due_date: str | None = None
    due_at: datetime | None = None
    reminder_at: datetime | None = None
    notification_sent_at: datetime | None = None
    occurrences: int = Field(ge=1)
    first_seen_at: datetime
    last_seen_at: datetime
    evidence: list[PromiseRadarEvidence] = Field(default_factory=list)
    user_confirmed: bool = False
    semantic_summary: str | None = None
    calendar_event: dict | None = None
    action_item_id: str | None = None
    dismissed_reason: str | None = None


class PromiseLedgerUpdateRequest(BaseModel):
    """User correction for a ledger item."""

    status: str | None = Field(
        default=None,
        description="open, completed, dismissed, delegated, blocked, or changed",
    )
    text: str | None = None
    owner: str | None = None
    team_id: str | None = None
    assigned_user_id: str | None = None
    priority: str | None = None
    due_date: str | None = None
    due_at: datetime | None = None
    reminder_at: datetime | None = None
    user_confirmed: bool | None = None
    dismissed_reason: str | None = None


class PromiseLedgerMergeRequest(BaseModel):
    """Merge duplicate/source ledger entries into the target entry."""

    source_entry_ids: list[str] = Field(min_length=1)
    note: str | None = None


class PromiseLedgerSplitRequest(BaseModel):
    """Create a new ledger entry by splitting part of an existing entry."""

    text: str = Field(min_length=1)
    owner: str | None = None
    due_date: str | None = None
    due_at: datetime | None = None
    priority: str | None = None
    evidence_indices: list[int] = Field(default_factory=list)
    note: str | None = None


class PromiseLedgerMergeResponse(BaseModel):
    """Result of a merge operation."""

    target: PromiseLedgerEntryResponse
    merged_entry_ids: list[str] = Field(default_factory=list)


class PromiseLedgerSplitResponse(BaseModel):
    """Result of a split operation."""

    original: PromiseLedgerEntryResponse
    created: PromiseLedgerEntryResponse


class PromiseLedgerHistoryEntry(BaseModel):
    """Auditable Promise Ledger history event."""

    id: str
    ledger_entry_id: str
    event_type: str
    actor_user_id: str | None = None
    old_value: dict | None = None
    new_value: dict | None = None
    note: str | None = None
    created_at: datetime


class PromiseReminderCandidate(BaseModel):
    """Internal reminder/calendar candidate derived from a promise."""

    ledger_entry_id: str
    title: str
    owner: str | None = None
    due_at: datetime | None = None
    reminder_at: datetime | None = None
    calendar_event: dict | None = None


class PromiseTaskLinkResponse(BaseModel):
    """Result of converting a promise into an internal action item."""

    ledger_entry_id: str
    action_item_id: str
    title: str
    status: str


class PromiseNotificationDispatchResponse(BaseModel):
    """Result of dispatching due Promise Radar push notifications."""

    considered_count: int = Field(ge=0)
    sent_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    invalid_tokens: list[str] = Field(default_factory=list)
    notified_entry_ids: list[str] = Field(default_factory=list)


class PromiseRadarDashboard(BaseModel):
    """Home/dashboard summary for active promise obligations."""

    open_count: int = Field(ge=0)
    high_risk_count: int = Field(ge=0)
    overdue_count: int = Field(ge=0)
    due_soon_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    unconfirmed_count: int = Field(ge=0)
    owner_hotspots: list[PromiseRadarOwnerRisk] = Field(default_factory=list)
    urgent_promises: list[PromiseLedgerEntryResponse] = Field(default_factory=list)
    recent_changes: list[PromiseLedgerHistoryEntry] = Field(default_factory=list)


class PromiseNextMeetingBriefing(BaseModel):
    """Pre-meeting brief assembled from unresolved ledger entries."""

    title: str
    high_risk_count: int = Field(ge=0)
    overdue_count: int = Field(ge=0)
    due_soon_count: int = Field(ge=0)
    owner_hotspots: list[PromiseRadarOwnerRisk] = Field(default_factory=list)
    promises: list[PromiseLedgerEntryResponse] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    reminder_candidates: list[PromiseReminderCandidate] = Field(default_factory=list)


class PromiseRadarResponse(BaseModel):
    """Promise radar response for one current meeting."""

    task_id: str
    generated_at: str
    headline: str
    risk_score: int = Field(ge=0, le=100)
    analyzed_meetings: int = Field(ge=0)
    current_promises: list[PromiseRadarPromise] = Field(default_factory=list)
    carried_over_promises: list[PromiseRadarCarryOver] = Field(default_factory=list)
    stale_promises: list[PromiseRadarPromise] = Field(default_factory=list)
    decision_drifts: list[PromiseRadarDecisionDrift] = Field(default_factory=list)
    promise_chains: list[PromiseRadarPromiseChain] = Field(default_factory=list)
    owner_risks: list[PromiseRadarOwnerRisk] = Field(default_factory=list)
    high_risk_count: int = Field(default=0, ge=0)
    ledger_entries: list[PromiseLedgerEntryResponse] = Field(default_factory=list)
    next_meeting_briefing: PromiseNextMeetingBriefing | None = None
    semantic_enrichment_status: str = Field(
        default="deterministic",
        description="deterministic, zai_applied, zai_unavailable, or zai_failed",
    )
    follow_up_questions: list[str] = Field(default_factory=list)
