"""
회의록 품질 평가 관련 스키마
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AssessmentFocus(StrEnum):
    """평가 집중 영역"""

    COMPLETENESS = "completeness"  # 완전성
    CLARITY = "clarity"  # 명확성
    STRUCTURE = "structure"  # 구조
    CONTENT = "content"  # 내용
    ACTION_ITEMS = "action_items"  # 액션 아이템
    DECISIONS = "decisions"  # 의사결정
    ATTENDEES = "attendees"  # 참석자 정보
    TIMELINE = "timeline"  # 시간 정보


class IssueSeverity(StrEnum):
    """문제 심각도"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImprovementType(StrEnum):
    """개선 제안 유형"""

    STRUCTURE = "structure"
    CONTENT = "content"
    CLARITY = "clarity"
    COMPLETENESS = "completeness"
    FORMAT = "format"


class Priority(StrEnum):
    """우선순위"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class QualityScore(BaseModel):
    """개별 평가 항목 점수"""

    category: str = Field(..., description="평가 카테고리")
    score: float = Field(..., ge=0.0, le=100.0, description="점수 (0-100)")
    max_score: float = Field(default=100.0, description="최대 점수")
    description: str = Field(..., description="설명")
    details: dict[str, str | int | float] | None = Field(default=None, description="세부 정보")


class QualityIssue(BaseModel):
    """품질 문제"""

    id: str = Field(..., description="문제 ID")
    category: str = Field(..., description="카테고리")
    severity: IssueSeverity = Field(..., description="심각도")
    description: str = Field(..., description="문제 설명")
    affected_content: str | None = Field(default=None, description="영향받은 내용")
    suggestion: str | None = Field(default=None, description="개선 방안")
    location: dict[str, int] | None = Field(default=None, description="위치 정보 (시작, 끝 인덱스)")


class ImprovementSuggestion(BaseModel):
    """개선 제안"""

    id: str = Field(..., description="제안 ID")
    type: ImprovementType = Field(..., description="제안 유형")
    priority: Priority = Field(..., description="우선순위")
    title: str = Field(..., description="제안 제목")
    description: str = Field(..., description="제안 설명")
    example: str | None = Field(default=None, description="예시")
    estimated_effort: str | None = Field(default=None, description="예상 노력")
    impact: str | None = Field(default=None, description="영향도")


class QualityAssessmentRequest(BaseModel):
    """품질 평가 요청"""

    criteria: dict[str, int | float | list[str]] | None = Field(
        default=None, description="커스텀 평가 기준"
    )
    assessment_focus: list[AssessmentFocus] = Field(
        default=[AssessmentFocus.COMPLETENESS, AssessmentFocus.CLARITY],
        description="평가 집중 영역",
    )
    include_history: bool = Field(default=True, description="과거 히스토리 고려 여부")


class AssessmentSummary(BaseModel):
    """평가 요약"""

    overall_score: float = Field(..., ge=0.0, le=100.0, description="전체 점수")
    grade: str = Field(..., description="등급 (A+, A, B, C, D)")
    total_issues: int = Field(..., ge=0, description="총 문제 수")
    critical_issues: int = Field(..., ge=0, description="심각 문제 수")
    strengths: list[str] = Field(default_factory=list, description="강점 목록")
    weaknesses: list[str] = Field(default_factory=list, description="약점 목록")
    last_assessed: datetime = Field(default_factory=datetime.now, description="마지막 평가 시간")


class QualityAssessmentResponse(BaseModel):
    """품질 평가 응답"""

    task_id: str = Field(..., description="Task ID")
    assessment_summary: AssessmentSummary = Field(..., description="평가 요약")
    category_scores: list[QualityScore] = Field(default_factory=list, description="카테고리별 점수")
    issues: list[QualityIssue] = Field(default_factory=list, description="발견된 문제 목록")
    recommendations: list[str] = Field(default_factory=list, description="추천 사항")
    metadata: dict[str, str | int | float] = Field(default_factory=dict, description="메타데이터")


class QualityImprovementResponse(BaseModel):
    """개선 제안 응답"""

    task_id: str = Field(..., description="Task ID")
    improvements: list[ImprovementSuggestion] = Field(
        default_factory=list, description="개선 제안 목록"
    )
    suggested_actions: list[str] = Field(default_factory=list, description="제안 액션 목록")
    total_improvements: int = Field(..., ge=0, description="총 개선 제안 수")
    priority_breakdown: dict[str, int] = Field(
        default_factory=dict, description="우선순위별 개선 제안 수"
    )
    estimated_completion_time: str | None = Field(default=None, description="예상 완료 시간")


class ActionPlan(BaseModel):
    """개선 계획"""

    task_id: str = Field(..., description="Task ID")
    phases: list[dict[str, str | list[str] | int]] = Field(
        default_factory=list, description="개선 단계"
    )
    timeline: dict[str, str] = Field(default_factory=dict, description="시간 계획")
    resources: list[str] = Field(default_factory=list, description="필요 리소스")


class QualityHistory(BaseModel):
    """품질 평가 이력"""

    task_id: str = Field(..., description="Task ID")
    assessment_id: str = Field(..., description="평가 ID")
    assessment_date: datetime = Field(..., description="평가 시간")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="전체 점수")
    grade: str = Field(..., description="등급")
    changes: dict[str, float | str] | None = Field(default=None, description="변화량")


# ---------------------------------------------------------------------------
# SPEC-QUALITY-MONITOR-001: 실시간 모니터링/피드백/추세 스키마
# ---------------------------------------------------------------------------


class FeedbackCategory(StrEnum):
    """피드백 카테고리"""

    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"
    STRUCTURE = "structure"
    OTHER = "other"


class LiveQualityScoreResponse(BaseModel):
    """실시간 경량 품질 점수 응답 (AI 호출 없음)"""

    task_id: str = Field(..., description="Task ID")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="전체 점수")
    grade: str = Field(..., description="등급 (A+ ~ F)")
    completeness_score: float = Field(..., ge=0.0, le=100.0)
    clarity_score: float = Field(..., ge=0.0, le=100.0)
    structure_score: float = Field(..., ge=0.0, le=100.0)
    word_count: int = Field(..., ge=0)
    computed_at: datetime
    mode: str = Field(default="lightweight", description="평가 모드")


class QualityFeedbackCreate(BaseModel):
    """품질 피드백 제출 요청"""

    rating: int = Field(..., ge=1, le=5, description="별점 1~5")
    category: FeedbackCategory = Field(
        default=FeedbackCategory.OTHER, description="피드백 카테고리"
    )
    comment: str | None = Field(default=None, max_length=2000, description="자유 텍스트 코멘트")


class QualityFeedbackResponse(BaseModel):
    """단일 피드백 응답"""

    id: str = Field(..., description="피드백 ID")
    task_id: str
    rating: int
    category: FeedbackCategory
    comment: str | None = None
    created_at: datetime


class QualityFeedbackSummary(BaseModel):
    """피드백 누적 요약"""

    task_id: str
    total_feedbacks: int = Field(..., ge=0)
    avg_rating: float | None = Field(default=None, ge=0.0, le=5.0)
    category_breakdown: dict[str, int] = Field(default_factory=dict)
    recent: list[QualityFeedbackResponse] = Field(default_factory=list)


class QualityTrendPoint(BaseModel):
    """추세 데이터 포인트"""

    timestamp: datetime
    overall_score: float = Field(..., ge=0.0, le=100.0)
    grade: str
    mode: str


class QualityTrendsResponse(BaseModel):
    """품질 추세 분석 응답"""

    task_id: str
    points: list[QualityTrendPoint] = Field(default_factory=list)
    points_count: int = Field(..., ge=0)
    avg_score: float | None = Field(default=None, ge=0.0, le=100.0)
    min_score: float | None = Field(default=None, ge=0.0, le=100.0)
    max_score: float | None = Field(default=None, ge=0.0, le=100.0)
    trend_direction: str = Field(
        default="stable",
        description="up | down | stable | insufficient_data",
    )
    warning: str | None = Field(default=None, description="추세에 따른 경고 메시지")
