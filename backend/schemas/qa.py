"""
SPEC-QA-001: 회의 Q&A 스키마
"""

from pydantic import BaseModel, Field


class MeetingAskRequest(BaseModel):
    """회의 Q&A 질문 요청"""

    task_id: str = Field(..., min_length=1, max_length=255, description="회의록 task ID")
    question: str = Field(..., min_length=1, max_length=2000, description="자연어 질문")
    thread_id: str | None = Field(default=None, max_length=255, description="대화 스레드 ID (대화 이어가기)")


class QASource(BaseModel):
    """답변 출처 (트랜스크립트 세그먼트)"""

    segment_index: int = Field(description="세그먼트 인덱스")
    speaker: str | None = Field(default=None, description="화자명")
    text: str = Field(description="세그먼트 텍스트")


class MeetingAskResponse(BaseModel):
    """회의 Q&A 답변 응답"""

    answer: str = Field(description="AI 답변")
    sources: list[QASource] = Field(default_factory=list, description="출처 세그먼트")
    thread_id: str = Field(description="대화 스레드 ID")


class QAHistoryItem(BaseModel):
    """Q&A 이력 항목"""

    question: str
    answer: str
    sources: list[QASource] = Field(default_factory=list)
    created_at: str


class QAHistoryResponse(BaseModel):
    """Q&A 이력 응답"""

    items: list[QAHistoryItem]
    total: int
