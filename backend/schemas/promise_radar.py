"""
Cross-meeting promise radar schemas.
"""

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
    follow_up_questions: list[str] = Field(default_factory=list)
