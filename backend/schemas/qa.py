"""
SPEC-QA-001: 회의 Q&A 스키마
"""

from pydantic import BaseModel, Field


class MeetingAskRequest(BaseModel):
    """회의 Q&A 질문 요청"""

    task_id: str = Field(..., min_length=1, max_length=255, description="회의록 task ID")
    question: str = Field(..., min_length=1, max_length=2000, description="자연어 질문")
    thread_id: str | None = Field(
        default=None, max_length=255, description="대화 스레드 ID (대화 이어가기)"
    )


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


class CrossMeetingAskRequest(BaseModel):
    """여러 회의에 걸친 Q&A 근거 검색 요청"""

    question: str = Field(..., min_length=2, max_length=2000, description="자연어 질문")
    limit: int = Field(default=5, ge=1, le=20, description="검색할 근거 회의 수")


class CrossMeetingSource(BaseModel):
    """Cross-meeting Q&A 답변 근거"""

    task_id: str = Field(description="근거가 된 회의/요약 task ID")
    task_type: str = Field(description="근거 작업 유형")
    snippet: str = Field(description="검색 스니펫")
    created_at: str = Field(description="검색 인덱스 생성 시각")
    completed_at: str | None = Field(default=None, description="작업 완료 시각")


class CrossMeetingAskResponse(BaseModel):
    """여러 회의에 걸친 Q&A 근거 검색 응답"""

    answer: str = Field(description="근거 기반 요약 답변")
    sources: list[CrossMeetingSource] = Field(default_factory=list, description="근거 목록")
    query: str = Field(description="검색에 사용된 정규화 쿼리")
    total: int = Field(description="검색된 전체 근거 수")
