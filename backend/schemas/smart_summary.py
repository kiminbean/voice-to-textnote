"""
Smart Summary Generation API 스키마
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal, List, Optional

from pydantic import BaseModel, Field


class SummaryMode(str, Enum):
    """요약 모드"""
    EXECUTIVE = "executive"  # 경영진 요약 (간결, 핵심만)
    DETAILED = "detailed"    # 상세 요약 (완전한 내용)
    BULLET_POINTS = "bullet_points"  # 항목별 요약
    ACTION_ORIENTED = "action_oriented"  # 행동 중심 요약
    SENTIMENT_FOCUSED = "sentiment_focused"  # 감정 분석 중심


class SummaryLength(str, Enum):
    """요약 길이"""
    SHORT = "short"     # 짧음 (100-200자)
    MEDIUM = "medium"   # 중간 (200-500자)
    DETAILED = "detailed"  # 상세 (500-1000자)


class MeetingType(str, Enum):
    """회의 유형 자동 감지"""
    REGULAR = "regular"           # 정기 회의
    BRAINSTORMING = "brainstorming"  # 브레인스토밍
    REVIEW = "review"             # 검토 회의
    PLANNING = "planning"         # 계획 회의
    ONE_ON_ONE = "one_on_one"     # 1:1 면담
    WORKSHOP = "workshop"         # 워크샵
    EMERGENCY = "emergency"       # 긴급 회의


class FocusArea(str, Enum):
    """집중 영역"""
    ALL = "all"                  # 모든 내용 포함
    DECISIONS_ONLY = "decisions" # 결정 사항만
    ACTION_ITEMS = "action_items" # 실행 항목만
    SENTIMENT = "sentiment"      # 감정 분석만
    DISCUSSION = "discussion"    # 논의 내용만
    KEY_TAKEAWAYS = "takeaways"  # 핵심 요약만


class SummaryRequest(BaseModel):
    """요약 생성 요청"""
    summary_mode: SummaryMode = Field(
        default=SummaryMode.EXECUTIVE,
        description="요약 모드"
    )
    length: SummaryLength = Field(
        default=SummaryLength.MEDIUM,
        description="요약 길이"
    )
    focus_areas: List[FocusArea] = Field(
        default=[FocusArea.ALL],
        description="집중 영역 목록"
    )
    include_sentiment: bool = Field(
        default=True,
        description="감정 분석 포함 여부"
    )
    generate_multiple_versions: bool = Field(
        default=False,
        description="여러 버전의 요약 생성"
    )
    target_audience: str | None = Field(
        default=None,
        description="요청 대상 (예: 경영진, 개발자, 팀원)"
    )


class MeetingDetection(BaseModel):
    """회의 유형 자동 감지 결과"""
    detected_type: MeetingType = Field(description="감지된 회의 유형")
    confidence: float = Field(ge=0.0, le=1.0, description="신뢰도")
    reasoning: List[str] = Field(description="판단 근거")
    keywords: List[str] = Field(description="키워드 목록")


class SentimentAnalysis(BaseModel):
    """감정 분석 결과"""
    overall_sentiment: str = Field(description="전체 감정 (positive, neutral, negative)")
    sentiment_score: float = Field(ge=-1.0, le=1.0, description="감정 점수 (-1: 부정, 0: 중립, 1: 긍정)")
    sentiment_details: dict = Field(description="상세 감정 분석")
    emotional_segments: List[dict] = Field(description="감정 변화 세그먼트")


class SummaryContent(BaseModel):
    """요약 내용"""
    summary_text: str = Field(description="요약 텍스트")
    key_points: List[str] = Field(description="핵심 포인트 목록")
    action_items: List[str] = Field(description="실행 항목 목록")
    decisions: List[str] = Field(description="결정 사항 목록")
    participants_mentioned: List[str] = Field(description="언급된 참가자 목록")
    topics_covered: List[str] = Field(description="다룬 주제 목록")
    word_count: int = Field(description="단어 수")
    reading_time_minutes: float = Field(description="읽는 데 걸리는 시간 (분)")


class VersionedSummary(BaseModel):
    """버전별 요약"""
    version_number: int = Field(description="버전 번호")
    mode: SummaryMode = Field(description="요약 모드")
    content: SummaryContent = Field(description="요약 내용")
    created_at: datetime = Field(description="생성 시간")
    metadata: dict = Field(description="메타데이터")


class SummaryGenerationResult(BaseModel):
    """요약 생성 결과"""
    task_id: str = Field(description="요약 작업 ID")
    summary_mode: SummaryMode = Field(description="사용된 요약 모드")
    length: SummaryLength = Field(description="요약 길이")
    meeting_detection: MeetingDetection = Field(description="회의 유형 감지 결과")
    summary_content: SummaryContent = Field(description="요약 내용")
    sentiment_analysis: SentimentAnalysis | None = Field(default=None, description="감정 분석 결과")
    confidence_score: float = Field(ge=0.0, le=1.0, description="요약 품질 점수")
    processing_time_seconds: float = Field(description="처리 시간 (초)")
    alternative_versions: List[VersionedSummary] = Field(default_factory=list, description="대체 버전")
    metadata: dict = Field(default_factory=dict, description="추가 메타데이터")


class SmartSummaryResponse(BaseModel):
    """스마트 요약 응답"""
    task_id: str = Field(description="작업 ID")
    status: str = Field(description="상태")
    request: SummaryRequest = Field(description="요청 데이터")
    result: SummaryGenerationResult | None = Field(default=None, description="생성 결과")
    detected_meeting_type: MeetingType | None = Field(default=None, description="감지된 회의 유형")
    created_at: datetime = Field(description="생성 시간")
    completed_at: datetime | None = Field(default=None, description="완료 시간")
    error_message: str | None = Field(default=None, description="에러 메시지")


class SmartSummaryStatus(BaseModel):
    """스마트 요약 상태"""
    task_id: str = Field(description="작업 ID")
    status: str = Field(description="상태")
    progress_percent: float = Field(ge=0.0, le=100.0, description="진행률 (%)")
    current_step: str = Field(description="현재 처리 단계")
    estimated_remaining_seconds: float | None = Field(default=None, description="예상 남은 시간")
    error_message: str | None = Field(default=None, description="에러 메시지")