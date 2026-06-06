"""
액션 아이템 추출 스키마
SPEC-ACTION-001: 회의록에서 할 일/액션 아이템 자동 추출
"""

from pydantic import BaseModel, Field


class ActionItemExtractRequest(BaseModel):
    """액션 아이템 추출 요청"""

    text: str = Field(
        ...,
        min_length=10,
        max_length=100000,
        description="회의록 텍스트 (STT 결과 또는 회의록 본문)",
    )
    language: str = Field(
        default="ko",
        description="텍스트 언어 코드 (ko, en, ja 등)",
    )
    include_deadlines: bool = Field(
        default=True,
        description="기한/마감일 추출 포함 여부",
    )
    include_assignees: bool = Field(
        default=True,
        description="담당자 추출 포함 여부",
    )


class ActionItem(BaseModel):
    """개별 액션 아이템"""

    id: int = Field(description="순번")
    task: str = Field(description="할 일 내용")
    assignee: str | None = Field(default=None, description="담당자")
    deadline: str | None = Field(default=None, description="기한/마감일")
    priority: str | None = Field(
        default=None,
        description="우선순위 (high/medium/low)",
    )
    context: str | None = Field(
        default=None,
        description="관련 컨텍스트 (원문 발화)",
    )


class ActionItemsResponse(BaseModel):
    """액션 아이템 추출 응답"""

    task_id: str = Field(description="작업 ID")
    status: str = Field(description="작업 상태")
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="추출된 액션 아이템 목록",
    )
    total_count: int = Field(default=0, description="추출된 액션 아이템 수")
    extracted_at: str = Field(description="추출 시각 (ISO 8601)")


class ActionItemFromMeetingRequest(BaseModel):
    """기존 회의록 작업 ID로 액션 아이템 추출"""

    minutes_task_id: str = Field(
        ...,
        description="회의록 작업 ID",
    )
    include_deadlines: bool = Field(default=True)
    include_assignees: bool = Field(default=True)
