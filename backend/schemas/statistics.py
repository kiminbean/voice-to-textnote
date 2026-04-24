"""
SPEC-STATS-001: 회의 통계 대시보드 Pydantic 스키마
"""

from pydantic import BaseModel, Field


class SpeakerStat(BaseModel):
    """화자별 통계."""

    speaker: str = Field(..., description="화자 ID (예: SPEAKER_00)")
    speaking_time_seconds: float = Field(..., ge=0)
    speaking_ratio: float = Field(..., ge=0, le=1, description="전체 대비 발화 비율 (0~1)")
    segment_count: int = Field(..., ge=0)
    word_count: int = Field(..., ge=0)


class KeywordStat(BaseModel):
    """키워드 빈도."""

    keyword: str
    count: int = Field(..., ge=1)


class StatisticsResponse(BaseModel):
    """회의 통계 응답."""

    task_id: str
    total_segments: int = Field(..., ge=0)
    total_words: int = Field(..., ge=0)
    total_duration_seconds: float = Field(..., ge=0, description="세그먼트가 차지하는 총 발화 시간")
    unique_speakers: int = Field(..., ge=0)
    speakers: list[SpeakerStat]
    top_keywords: list[KeywordStat]
