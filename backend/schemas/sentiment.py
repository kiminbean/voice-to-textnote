"""
감정 분석 요청/응답 Pydantic v2 스키마
SPEC-SENTIMENT-001: 화자별/구간별 감정 분석
"""

from pydantic import BaseModel, Field


class SentimentSegment(BaseModel):
    """개별 발화 구간의 감정 분석 결과"""

    start: float = Field(..., description="시작 시간 (초)")
    end: float = Field(..., description="종료 시간 (초)")
    speaker: str = Field(..., description="화자명")
    text: str = Field(default="", description="발화 내용")
    sentiment: str = Field(default="neutral", description="감정 레이블 (positive/neutral/negative)")
    emotion: str = Field(
        default="neutral",
        description="세부 감정 (joy/satisfaction/neutral/frustration/anger/sadness/surprise 등)",
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="감정 분석 신뢰도"
    )


class SpeakerSentiment(BaseModel):
    """화자별 감정 분석 요약"""

    speaker: str = Field(..., description="화자명")
    total_segments: int = Field(..., description="총 발화 구간 수")
    positive_ratio: float = Field(
        default=0.0, ge=0.0, le=1.0, description="긍정 발화 비율"
    )
    neutral_ratio: float = Field(
        default=0.0, ge=0.0, le=1.0, description="중립 발화 비율"
    )
    negative_ratio: float = Field(
        default=0.0, ge=0.0, le=1.0, description="부정 발화 비율"
    )
    dominant_emotion: str = Field(
        default="neutral", description="가장 많이 나타난 감정"
    )
    emotion_distribution: dict[str, int] = Field(
        default_factory=dict, description="감정별 발화 횟수"
    )


class SentimentCreateRequest(BaseModel):
    """POST /api/v1/sentiment 요청 본문"""

    minutes_task_id: str = Field(..., description="회의록 작업 ID")
    max_tokens: int = Field(default=4096, description="OpenAI API 최대 응답 토큰 수")


class SentimentResult(BaseModel):
    """감정 분석 전체 결과"""

    overall_sentiment: str = Field(
        default="neutral",
        description="회의 전체 감정 (positive/neutral/negative)",
    )
    overall_emotion: str = Field(
        default="neutral", description="회의 전체 주요 감정"
    )
    segments: list[SentimentSegment] = Field(
        default_factory=list, description="구간별 감정 분석 결과"
    )
    speakers: list[SpeakerSentiment] = Field(
        default_factory=list, description="화자별 감정 분석 요약"
    )
    emotional_timeline: list[dict] = Field(
        default_factory=list,
        description="감정 변화 타임라인 [{time, sentiment, emotion, speaker}]",
    )


class SentimentStatusResponse(BaseModel):
    """감정 분석 작업 상태"""

    task_id: str
    status: str
    progress: float = 0.0
    message: str | None = None
    error_message: str | None = None


class SentimentResponse(BaseModel):
    """감정 분석 전체 응답"""

    task_id: str
    status: str
    minutes_task_id: str = ""
    overall_sentiment: str = "neutral"
    overall_emotion: str = "neutral"
    segments: list[SentimentSegment] = []
    speakers: list[SpeakerSentiment] = []
    emotional_timeline: list[dict] = []
    generation_time_seconds: float | None = None
    error_message: str | None = None
