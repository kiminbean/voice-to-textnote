"""
SPEC-RELATED-001: 관련 회의 추천(Related Meetings) API 스키마

특정 회의(task_id)의 상위 키워드를 기준으로 FTS5 인덱스에서 유사한 다른
회의를 찾아 반환한다. 새로운 임베딩 의존성 없이 기존 search_index(FTS5)와
KeywordService(TF-IDF + TextRank)를 재사용한다.

응답 구조:
- source_task_id: 기준이 된 회의 task_id
- keywords: 기준 회의에서 추출된 상위 키워드
- items: 관련 회의 목록 (공유 키워드/관련도 순 정렬)
- total: 반환된 관련 회의 수
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RelatedMeetingItem(BaseModel):
    """관련 회의 결과 항목"""

    task_id: str = Field(..., description="관련 회의의 task_id")
    task_type: str = Field(..., description="작업 유형 (minutes, summary, sales_contact_brief)")
    snippet: str = Field(default="", description="FTS5 snippet 하이라이트가 적용된 컨텍스트")
    shared_keywords: list[str] = Field(
        default_factory=list,
        description="기준 회의와 공유하는 키워드 목록",
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="공유 키워드 비율 기반 관련도 점수 (0.0~1.0)",
    )
    created_at: datetime = Field(..., description="관련 회의 생성 시각")
    completed_at: datetime | None = Field(default=None, description="관련 회의 완료 시각")

    model_config = {"from_attributes": True}


class RelatedMeetingsResponse(BaseModel):
    """관련 회의 추천 API 응답"""

    source_task_id: str = Field(..., description="기준이 된 회의 task_id")
    keywords: list[str] = Field(
        default_factory=list,
        description="기준 회의에서 추출된 상위 키워드",
    )
    items: list[RelatedMeetingItem] = Field(
        default_factory=list,
        description="관련 회의 목록 (관련도 내림차순)",
    )
    total: int = Field(default=0, ge=0, description="반환된 관련 회의 수")
