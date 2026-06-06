"""
SPEC-ENHANCED-STATS-001: 고급 통계 대시보드 Pydantic 스키마

시계열 데이터, 화자 참여도 패턴, 키워드 빈도 추이, 회의 효율성 지표
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TimeSeriesDataPoint(BaseModel):
    """시계열 데이터 포인트."""

    timestamp: datetime = Field(..., description="데이터 포인트 시간")
    value: float = Field(..., ge=0, description="측정값")
    label: str | None = Field(None, description="추가 라벨 (예: 요약, 질의)")


class SpeakerParticipationPattern(BaseModel):
    """화자별 참여도 패턴."""

    speaker: str = Field(..., description="화자 ID")
    total_speaking_time: float = Field(..., ge=0, description="총 발화 시간 (초)")
    participation_rate: float = Field(..., ge=0, le=1, description="참여율 (0~1)")
    average_segment_length: float = Field(..., ge=0, description="평균 발화 구간 길이 (초)")
    intervention_count: int = Field(..., ge=0, description="끼어든 횟수")
    most_active_hour: str = Field(..., description="가장 활발한 시간대")


class KeywordTrend(BaseModel):
    """키워드 빈도 추이."""

    keyword: str = Field(..., description="키워드")
    total_count: int = Field(..., ge=0, description="전체 등장 횟수")
    trend_direction: str = Field(..., description="추세 방향 (up/down/stable)")
    frequency_change: float = Field(..., description="빈도 변화율")
    first_appearance: datetime | None = Field(None, description="첫 등장 시간")
    last_appearance: datetime | None = Field(None, description="마지막 등장 시간")


class EfficiencyMetrics(BaseModel):
    """회의 효율성 지표."""

    total_duration_seconds: float = Field(..., ge=0, description="총 회의 시간 (초)")
    effective_duration_seconds: float = Field(..., ge=0, description="유효 발화 시간 (초)")
    silence_ratio: float = Field(..., ge=0, le=1, description="침묵 비율 (0~1)")
    speaking_turn_count: int = Field(..., ge=0, description="발화 전환 횟수")
    average_turn_length: float = Field(..., ge=0, description="평균 발화 전환 길이 (초)")
    participation_balance: float = Field(
        ..., ge=0, le=1, description="참여 균형도 (0~1, 1에 가까울수록 균형)"
    )


class MeetingSummary(BaseModel):
    """회의 요약 정보."""

    task_id: str
    title: str | None = Field(None, description="회의 제목")
    date: datetime | None = Field(None, description="회의 일자")
    duration_seconds: float = Field(..., ge=0, description="회의 시간 (초)")
    participant_count: int = Field(..., ge=0, description="참가자 수")
    efficiency_score: float = Field(..., ge=0, le=1, description="효율성 점수 (0~1)")


class EnhancedStatisticsResponse(BaseModel):
    """고급 통계 응답."""

    task_id: str
    time_range: str = Field(..., description="분석 시간 범위 (1d, 7d, 30d, 90d)")
    time_series: list[TimeSeriesDataPoint] = Field(
        default_factory=list, description="시계열 데이터"
    )
    speaker_patterns: list[SpeakerParticipationPattern] = Field(
        default_factory=list, description="화자별 참여도 패턴"
    )
    keyword_trends: list[KeywordTrend] = Field(default_factory=list, description="키워드 빈도 추이")
    efficiency_metrics: EfficiencyMetrics | None = Field(None, description="회의 효율성 지표")
    metadata: dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class OverviewResponse(BaseModel):
    """프로젝트 전체 통계 개요 응답."""

    period: str = Field(..., description="통계 기간 (7d, 30d, 90d, 180d)")
    total_meetings: int = Field(..., ge=0, description="총 회의 수")
    total_duration_seconds: float = Field(..., ge=0, description="총 회의 시간 (초)")
    total_participants: int = Field(..., ge=0, description="총 참가자 수 (중복 제거)")
    average_efficiency_score: float = Field(..., ge=0, le=1, description="평균 효율성 점수")
    top_meetings: list[MeetingSummary] = Field(default_factory=list, description="상위 회의 목록")
    active_speakers: list[str] = Field(default_factory=list, description="활발한 화자 목록")
    trending_keywords: list[KeywordTrend] = Field(default_factory=list, description="트렌딩 키워드")
    metadata: dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")
