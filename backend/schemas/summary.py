"""
AI 요약 생성 요청/응답 Pydantic v2 스키마
REQ-SUM-005: ActionItem, SummaryCreateRequest, SummaryResult, SummaryResponse, SummaryStatusResponse
"""

from pydantic import BaseModel, Field

from backend.schemas.transcription import TaskStatus


class ActionItem(BaseModel):
    """회의 액션 아이템 (REQ-SUM-005)"""

    # frozen=True: 불변 객체
    model_config = {"frozen": True}

    # 담당자 (None 허용)
    assignee: str | None = Field(default=None, description="담당자 이름")
    # 작업 내용 (필수)
    task: str = Field(..., description="수행해야 할 작업")
    # 마감일 (None 허용)
    deadline: str | None = Field(default=None, description="마감 날짜 (자유 형식)")
    # 우선순위 (기본값: medium)
    priority: str = Field(default="medium", description="우선순위 (low/medium/high)")


class SummaryCreateRequest(BaseModel):
    """POST /api/v1/summaries 요청 본문 (REQ-SUM-005)"""

    # 회의록 작업 ID (필수)
    minutes_task_id: str = Field(..., description="회의록 작업 ID")
    # 최대 토큰 수 (기본값: 2000)
    max_tokens: int = Field(default=2000, description="Claude API 최대 응답 토큰 수")
    # REQ-TMPL-004: 양식 ID (None이면 기본 4개 항목으로 요약)
    template_id: str | None = Field(default=None, description="양식 ID (양식 기반 요약 시 사용)")


class SummaryResult(BaseModel):
    """Claude API 응답을 파싱한 요약 결과 (REQ-SUM-002)"""

    model_config = {"frozen": True}

    # 요약 텍스트 (필수)
    summary_text: str = Field(..., description="회의 전체 요약")
    # 액션 아이템 목록
    action_items: list[ActionItem] = Field(default_factory=list, description="액션 아이템 목록")
    # 주요 결정 사항
    key_decisions: list[str] = Field(default_factory=list, description="주요 결정 사항 목록")
    # 다음 단계
    next_steps: list[str] = Field(default_factory=list, description="다음 단계 목록")
    # REQ-UI-003: 양식 섹션별 내용 (양식 선택 시에만 존재)
    sections: dict[str, str] = Field(default_factory=dict, description="양식 섹션별 내용")


class SummaryResponse(BaseModel):
    """GET /api/v1/summaries/{task_id} 응답 (REQ-SUM-005)"""

    # 작업 ID
    task_id: str = Field(..., description="요약 작업 ID")
    # 현재 상태
    status: TaskStatus
    # 원본 회의록 작업 ID
    minutes_task_id: str = Field(..., description="원본 회의록 작업 ID")
    # 요약 텍스트
    summary_text: str = Field(default="", description="회의 전체 요약")
    # 액션 아이템
    action_items: list[ActionItem] = Field(default_factory=list)
    # 주요 결정
    key_decisions: list[str] = Field(default_factory=list)
    # 다음 단계
    next_steps: list[str] = Field(default_factory=list)
    # REQ-UI-003: 양식 섹션별 내용 (양식 선택 시에만 존재)
    sections: dict[str, str] = Field(default_factory=dict, description="양식 섹션별 내용")
    # REQ-UI-001: 양식 구조 정보 (양식 선택 시에만 존재)
    template_structure: dict | None = Field(default=None, description="양식 구조 정보")
    # 토큰 사용량 (None 허용)
    tokens_used: dict | None = Field(default=None, description="Claude API 토큰 사용량")
    # 생성 소요 시간 (None 허용)
    generation_time_seconds: float | None = Field(
        default=None, description="요약 생성 소요 시간 (초)"
    )


class SummaryStatusResponse(BaseModel):
    """GET /api/v1/summaries/{task_id}/status 응답 (REQ-SUM-012)"""

    # 작업 ID
    task_id: str = Field(..., description="요약 작업 ID")
    # 현재 상태
    status: TaskStatus
    # 진행률 (0.0~1.0)
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="진행률")
    # 상태 메시지 (None 허용)
    message: str | None = Field(default=None, description="상태 메시지")
