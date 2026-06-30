"""Sales contact brief schemas for customer follow-up workflows."""

from pydantic import BaseModel, Field

from backend.schemas.study_pack import StudySourceRef


class SalesContactBriefCreateRequest(BaseModel):
    """Sales contact brief generation request."""

    language: str = Field(default="ko", min_length=2, max_length=16, description="Output language")
    max_tokens: int = Field(
        default=1200,
        ge=512,
        le=4096,
        description="ZAI-compatible API max response tokens",
    )
    force_refresh: bool = Field(default=False, description="Regenerate even when cached")


class SalesContactIdentity(BaseModel):
    """Extracted customer/contact identity."""

    name: str | None = Field(default=None, description="Contact name")
    company: str | None = Field(default=None, description="Company or account")
    role: str | None = Field(default=None, description="Role/title")
    email: str | None = Field(default=None, description="Email address")
    phone: str | None = Field(default=None, description="Phone number")


class SalesContactDeal(BaseModel):
    """Sales opportunity metadata inferred from the transcript."""

    stage: str = Field(default="unknown", description="Opportunity stage")
    value_hint: str | None = Field(default=None, description="Value/budget hint")
    urgency: str = Field(default="unknown", description="low/medium/high/unknown")


class SalesNextStep(BaseModel):
    """Actionable sales follow-up step."""

    task: str = Field(..., min_length=1, description="Follow-up task")
    owner: str | None = Field(default=None, description="Suggested owner")
    due: str | None = Field(default=None, description="Due date or timing phrase")


class SalesContactBriefResponse(BaseModel):
    """Generated sales contact brief response."""

    task_id: str = Field(..., min_length=1, description="Source minutes task ID")
    contact: SalesContactIdentity = Field(default_factory=SalesContactIdentity)
    deal: SalesContactDeal = Field(default_factory=SalesContactDeal)
    customer_needs: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    next_steps: list[SalesNextStep] = Field(default_factory=list)
    follow_up_message: str = Field(default="")
    source_refs: list[StudySourceRef] = Field(default_factory=list)
    created_at: str = Field(..., description="ISO-8601 creation timestamp")


class SalesContactListItem(BaseModel):
    """Compact customer/contact entry derived from a generated sales brief."""

    artifact_task_id: str = Field(..., description="Persisted sales brief artifact task ID")
    source_task_id: str = Field(..., description="Source minutes task ID")
    contact: SalesContactIdentity = Field(default_factory=SalesContactIdentity)
    deal: SalesContactDeal = Field(default_factory=SalesContactDeal)
    customer_needs: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    next_steps: list[SalesNextStep] = Field(default_factory=list)
    follow_up_message: str = Field(default="")
    crm_status: str = Field(default="open", description="User-managed CRM follow-up status")
    crm_note: str = Field(default="", description="User-managed CRM note")
    crm_updated_at: str | None = Field(default=None, description="CRM note/status update time")
    created_at: str = Field(..., description="Brief creation timestamp")
    completed_at: str | None = Field(default=None, description="Persisted artifact completion time")


class SalesContactCrmUpdateRequest(BaseModel):
    """Editable CRM fields for a generated sales/contact artifact."""

    status: str = Field(default="open", min_length=1, max_length=32)
    note: str = Field(default="", max_length=2000)


class SalesContactListResponse(BaseModel):
    """Paginated sales/contact brief index."""

    items: list[SalesContactListItem]
    total: int
    page: int
    page_size: int
