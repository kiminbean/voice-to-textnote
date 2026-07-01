"""
Cross-meeting promise radar schemas.
"""

from __future__ import annotations

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


class PromiseQualityScore(BaseModel):
    """Actionability score for one promise ledger item."""

    score: int = Field(ge=0, le=100)
    level: str = Field(description="excellent, good, weak, or risky")
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class PromiseAssigneeSuggestion(BaseModel):
    """Suggested app user for a promise owner/speaker."""

    user_id: str | None = None
    display_name: str
    email: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class PromiseOwnerAlias(BaseModel):
    """Learned alias connecting extracted owner/speaker/user identity."""

    alias: str
    canonical_owner: str
    speaker_label: str | None = None
    speaker_profile_id: str | None = None
    assigned_user_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_count: int = Field(ge=1)


class PromiseMatchExplanation(BaseModel):
    """Human-readable explanation for a Promise Radar match or status guess."""

    ledger_entry_id: str
    matched_task_id: str | None = None
    matched_text: str | None = None
    similarity: float = Field(ge=0.0, le=1.0)
    overlap_terms: list[str] = Field(default_factory=list)
    confidence_factors: list[str] = Field(default_factory=list)
    rationale: str
    evidence: list[PromiseRadarEvidence] = Field(default_factory=list)


class PromiseEvidencePack(BaseModel):
    """Immutable evidence snapshot for an Autopilot status decision."""

    ledger_entry_id: str
    source_task_id: str | None = None
    matched_text: str | None = None
    similarity: float = Field(ge=0.0, le=1.0)
    marker_hits: list[str] = Field(default_factory=list)
    confidence_factors: list[str] = Field(default_factory=list)
    evidence: list[PromiseRadarEvidence] = Field(default_factory=list)
    captured_at: datetime


class PromiseAutopilotAssessment(BaseModel):
    """Autopilot status assessment for one unresolved promise."""

    ledger_entry_id: str
    previous_status: str
    suggested_status: str
    applied: bool = False
    requires_confirmation: bool = True
    evidence_locked: bool = False
    conflict_detected: bool = False
    conflict_reason: str | None = None
    threshold: float = Field(default=0.68, ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    explanation: PromiseMatchExplanation
    evidence_pack: PromiseEvidencePack | None = None


class PromiseAutopilotResponse(BaseModel):
    """Batch result for Promise Autopilot status assessment."""

    task_id: str
    autopilot_threshold: float = Field(default=0.68, ge=0.0, le=1.0)
    status_thresholds: dict[str, float] = Field(default_factory=dict)
    evidence_lock_enforced: bool = True
    preview_mode: bool = False
    assessed_count: int = Field(ge=0)
    applied_count: int = Field(ge=0)
    assessments: list[PromiseAutopilotAssessment] = Field(default_factory=list)


class PromiseAutopilotConfirmRequest(BaseModel):
    """User confirmation request for a previewed Autopilot assessment."""

    task_id: str
    suggested_status: str | None = None
    note: str | None = None


class PromiseAutopilotReviewItem(BaseModel):
    """One pending Autopilot review queue row with user-visible ledger context."""

    ledger_entry: PromiseLedgerEntryResponse
    assessment: PromiseAutopilotAssessment
    queued_at: datetime
    decision_required: bool = True


class PromiseAutopilotReviewQueue(BaseModel):
    """Batch review queue for pending Autopilot decisions."""

    task_id: str
    queue_count: int = Field(ge=0)
    actionable_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    items: list[PromiseAutopilotReviewItem] = Field(default_factory=list)


class PromiseConflictResolveRequest(BaseModel):
    """User-selected resolution for a conflicting Autopilot status signal."""

    status: str = Field(
        description="completed, delayed, changed, dismissed, open, or blocked",
    )
    note: str | None = None


class PromiseAutomationPolicy(BaseModel):
    """Scoped policy controlling how Promise Radar may auto-apply decisions."""

    scope: str
    mode: str = Field(
        default="safe_auto",
        description="safe_auto, preview_only, completed_only, or manual_only",
    )
    allowed_auto_statuses: list[str] = Field(default_factory=list)
    high_risk_requires_review: bool = True
    assignee_change_requires_review: bool = True
    conflict_requires_review: bool = True
    updated_at: datetime | None = None


class PromiseAutomationPolicyUpdateRequest(BaseModel):
    """Update request for scoped Promise Radar automation policy."""

    mode: str = Field(default="safe_auto")
    allowed_auto_statuses: list[str] = Field(default_factory=list)
    high_risk_requires_review: bool = True
    assignee_change_requires_review: bool = True
    conflict_requires_review: bool = True


class PromiseCalendarExportResponse(BaseModel):
    """Calendar handoff payload for Google Calendar or ICS import."""

    ledger_entry_id: str
    title: str
    due_at: datetime | None = None
    ics_filename: str
    ics_content: str
    google_calendar_url: str
    calendar_event: dict | None = None


class PromiseLearningFeedbackRequest(BaseModel):
    """User feedback used by the Promise Radar learning loop."""

    expected_status: str | None = None
    predicted_status: str | None = None
    expected_assigned_user_id: str | None = None
    expected_owner: str | None = None
    correction_type: str = Field(
        default="status",
        description="status, assignee, owner, merge, split, or autopilot",
    )
    note: str | None = None


class PromiseLearningProfile(BaseModel):
    """Scoped Promise Radar learning profile derived from ledger events."""

    scope: str
    autopilot_threshold: float = Field(ge=0.0, le=1.0)
    status_thresholds: dict[str, float] = Field(default_factory=dict)
    false_positive_count: int = Field(ge=0)
    confirmed_count: int = Field(ge=0)
    status_false_positive_count: dict[str, int] = Field(default_factory=dict)
    status_confirmed_count: dict[str, int] = Field(default_factory=dict)
    assignee_correction_count: int = Field(ge=0)
    evidence_lock_enabled: bool = True
    learned_owner_aliases: dict[str, str] = Field(default_factory=dict)
    owner_aliases: list[PromiseOwnerAlias] = Field(default_factory=list)


class PromiseLearningFeedbackResponse(BaseModel):
    """Persisted learning feedback result."""

    ledger_entry_id: str
    recorded: bool
    learning_profile: PromiseLearningProfile


class PromiseTimelineItem(BaseModel):
    """Readable timeline event for one promise."""

    id: str
    event_type: str
    label: str
    created_at: datetime
    actor_user_id: str | None = None
    status_before: str | None = None
    status_after: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_task_id: str | None = None
    note: str | None = None


class PromiseTimelineResponse(BaseModel):
    """Timeline for one promise ledger entry."""

    ledger_entry_id: str
    current_status: str
    items: list[PromiseTimelineItem] = Field(default_factory=list)


class PromisePreMeetingBrief(BaseModel):
    """Brief displayed before starting a new recording/meeting."""

    title: str
    readiness_score: int = Field(ge=0, le=100)
    summary: str
    promises: list[PromiseLedgerEntryResponse] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class PromiseDigest(BaseModel):
    """Daily or weekly digest for unresolved promises."""

    cadence: str = Field(description="daily or weekly")
    title: str
    generated_at: datetime
    open_count: int = Field(ge=0)
    overdue_count: int = Field(ge=0)
    due_soon_count: int = Field(ge=0)
    high_risk_count: int = Field(ge=0)
    lines: list[str] = Field(default_factory=list)
    promises: list[PromiseLedgerEntryResponse] = Field(default_factory=list)


class PromiseExternalExportRequest(BaseModel):
    """Request to create or send a first-party external work-tool handoff."""

    provider: str = Field(default="slack", description="slack or google_tasks")
    dry_run: bool = True
    access_token: str | None = Field(default=None, description="OAuth access token for Google Tasks")
    tasklist: str = Field(default="@default", description="Google Tasks task list id")
    parent_task_id: str | None = None
    previous_task_id: str | None = None


class PromiseExternalExportResponse(BaseModel):
    """External work-tool handoff result."""

    ledger_entry_id: str
    provider: str
    sent: bool
    payload: dict
    message: str
    external_id: str | None = None
    external_url: str | None = None


class PromiseAccuracyCase(BaseModel):
    """One expected Promise Radar accuracy fixture case."""

    id: str
    entry_text: str
    current_text: str
    expected_status: str
    owner: str | None = None
    due_at: datetime | None = None


class PromiseAccuracyEvaluation(BaseModel):
    """Precision/recall style Promise Radar evaluation summary."""

    case_count: int = Field(ge=0)
    correct_count: int = Field(ge=0)
    accuracy: float = Field(ge=0.0, le=1.0)
    status_precision: dict[str, float] = Field(default_factory=dict)
    failures: list[dict] = Field(default_factory=list)


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
    status: str = Field(
        description="open, completed, dismissed, delegated, blocked, delayed, or changed"
    )
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
    quality: PromiseQualityScore | None = None
    assignee_suggestions: list[PromiseAssigneeSuggestion] = Field(default_factory=list)


class PromiseLedgerUpdateRequest(BaseModel):
    """User correction for a ledger item."""

    status: str | None = Field(
        default=None,
        description="open, completed, dismissed, delegated, blocked, delayed, or changed",
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
    autopilot_assessments: list[PromiseAutopilotAssessment] = Field(default_factory=list)
    semantic_enrichment_status: str = Field(
        default="deterministic",
        description="deterministic, zai_applied, zai_unavailable, or zai_failed",
    )
    follow_up_questions: list[str] = Field(default_factory=list)
