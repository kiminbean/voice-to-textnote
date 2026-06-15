"""
회의 효율성 평가 API 스키마
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ParticipationMetric(BaseModel):
    """화자 참여도 지표"""
    speaker_id: str
    speaker_name: str
    speaking_time_seconds: int
    speaking_percentage: float
    segment_count: int
    avg_segment_length: float
    participation_balance_score: float = Field(..., ge=0.0, le=1.0)


class DecisionMetric(BaseModel):
    """결정 관련 지표"""
    total_decisions: int
    decisions_per_hour: float
    avg_decision_time_minutes: float
    decision_clarity_score: float = Field(..., ge=0.0, le=1.0)


class ActionItemMetric(BaseModel):
    """액션 아이템 지표"""
    total_action_items: int
    action_items_per_hour: float
    action_item_completion_rate: float | None = None
    action_item_clarity_score: float = Field(..., ge=0.0, le=1.0)


class TimeDistributionMetric(BaseModel):
    """시간 분배 지표"""
    total_meeting_duration_minutes: float
    actual_speaking_time_minutes: float
    silence_percentage: float
    agenda_adherence_score: float = Field(..., ge=0.0, le=1.0)
    time_efficiency_score: float = Field(..., ge=0.0, le=1.0)


class KeywordMetric(BaseModel):
    """키워드 분석 지표"""
    total_keywords: int
    unique_keywords: int
    keyword_diversity_score: float = Field(..., ge=0.0, le=1.0)
    action_keywords_count: int
    decision_keywords_count: int


class SentimentTrend(BaseModel):
    """감정 추이"""
    overall_sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    sentiment_trend: str = Field(..., pattern="^(improving|stable|declining)$")
    sentiment_volatility: float = Field(..., ge=0.0, le=1.0)


class EfficiencyMetrics(BaseModel):
    """종합 효율성 지표"""
    participation_balance: float = Field(..., ge=0.0, le=1.0)
    time_efficiency: float = Field(..., ge=0.0, le=1.0)
    decision_effectiveness: float = Field(..., ge=0.0, le=1.0)
    action_item_quality: float = Field(..., ge=0.0, le=1.0)
    overall_efficiency_score: float = Field(..., ge=0.0, le=1.0)
    efficiency_grade: str = Field(..., pattern="^(A|B|C|D|F)$")

    # 상세 분석 데이터
    participation_metrics: list[ParticipationMetric]
    decision_metric: DecisionMetric
    action_item_metric: ActionItemMetric
    time_distribution: TimeDistributionMetric
    keyword_metric: KeywordMetric
    sentiment_trend: SentimentTrend | None = None


class Recommendation(BaseModel):
    """개선 제안"""
    category: str = Field(..., pattern="^(participation|time|decision|action_item|general)$")
    priority: str = Field(..., pattern="^(high|medium|low)$")
    title: str
    description: str
    specific_actions: list[str]
    expected_improvement: str


class EfficiencyRecommendations(BaseModel):
    """개선 제안 목록"""
    participation_recommendations: list[Recommendation]
    time_recommendations: list[Recommendation]
    decision_recommendations: list[Recommendation]
    action_item_recommendations: list[Recommendation]
    general_recommendations: list[Recommendation]
    total_recommendations: int
    quick_wins: list[str]


class EfficiencyScoreResponse(BaseModel):
    """회의 효율성 평가 응답"""
    task_id: str
    analyzed_at: datetime
    analysis_depth: str
    efficiency_metrics: EfficiencyMetrics
    recommendations: EfficiencyRecommendations | None = None

    # 메타 정보
    meeting_duration_minutes: float
    total_speakers: int
    total_segments: int
    total_words: int
