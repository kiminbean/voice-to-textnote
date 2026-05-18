"""
회의록 품질 평가 관련 스키마
"""

from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
from enum import Enum
from datetime import datetime


class AssessmentFocus(str, Enum):
    """평가 집중 영역"""
    COMPLETENESS = "completeness"  # 완전성
    CLARITY = "clarity"          # 명확성
    STRUCTURE = "structure"      # 구조
    CONTENT = "content"          # 내용
    ACTION_ITEMS = "action_items" # 액션 아이템
    DECISIONS = "decisions"      # 의사결정
    ATTENDEES = "attendees"      # 참석자 정보
    TIMELINE = "timeline"        # 시간 정보


class IssueSeverity(str, Enum):
    """문제 심각도"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImprovementType(str, Enum):
    """개선 제안 유형"""
    STRUCTURE = "structure"
    CONTENT = "content"
    CLARITY = "clarity"
    COMPLETENESS = "completeness"
    FORMAT = "format"


class Priority(str, Enum):
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
    details: Optional[Dict[str, Union[str, int, float]]] = Field(
        default=None, description="세부 정보"
    )


class QualityIssue(BaseModel):
    """품질 문제"""
    id: str = Field(..., description="문제 ID")
    category: str = Field(..., description="카테고리")
    severity: IssueSeverity = Field(..., description="심각도")
    description: str = Field(..., description="문제 설명")
    affected_content: Optional[str] = Field(
        default=None, description="영향받은 내용"
    )
    suggestion: Optional[str] = Field(
        default=None, description="개선 방안"
    )
    location: Optional[Dict[str, int]] = Field(
        default=None, description="위치 정보 (시작, 끝 인덱스)"
    )


class ImprovementSuggestion(BaseModel):
    """개선 제안"""
    id: str = Field(..., description="제안 ID")
    type: ImprovementType = Field(..., description="제안 유형")
    priority: Priority = Field(..., description="우선순위")
    title: str = Field(..., description="제안 제목")
    description: str = Field(..., description="제안 설명")
    example: Optional[str] = Field(
        default=None, description="예시")
    estimated_effort: Optional[str] = Field(
        default=None, description="예상 노력"
    )
    impact: Optional[str] = Field(
        default=None, description="영향도"
    )


class QualityAssessmentRequest(BaseModel):
    """품질 평가 요청"""
    criteria: Optional[Dict[str, Union[int, float, List[str]]]] = Field(
        default=None,
        description="커스텀 평가 기준"
    )
    assessment_focus: List[AssessmentFocus] = Field(
        default=[AssessmentFocus.COMPLETENESS, AssessmentFocus.CLARITY],
        description="평가 집중 영역"
    )
    include_history: bool = Field(
        default=True,
        description="과거 히스토리 고려 여부"
    )


class AssessmentSummary(BaseModel):
    """평가 요약"""
    overall_score: float = Field(..., ge=0.0, le=100.0, description="전체 점수")
    grade: str = Field(..., description="등급 (A+, A, B, C, D)")
    total_issues: int = Field(..., ge=0, description="총 문제 수")
    critical_issues: int = Field(..., ge=0, description="심각 문제 수")
    strengths: List[str] = Field(
        default_factory=list, description="강점 목록"
    )
    weaknesses: List[str] = Field(
        default_factory=list, description="약점 목록"
    )
    last_assessed: datetime = Field(
        default_factory=datetime.now, description="마지막 평가 시간"
    )


class QualityAssessmentResponse(BaseModel):
    """품질 평가 응답"""
    task_id: str = Field(..., description="Task ID")
    assessment_summary: AssessmentSummary = Field(..., description="평가 요약")
    category_scores: List[QualityScore] = Field(
        default_factory=list, description="카테고리별 점수"
    )
    issues: List[QualityIssue] = Field(
        default_factory=list, description="발견된 문제 목록"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="추천 사항"
    )
    metadata: Dict[str, Union[str, int, float]] = Field(
        default_factory=dict, description="메타데이터"
    )


class QualityImprovementResponse(BaseModel):
    """개선 제안 응답"""
    task_id: str = Field(..., description="Task ID")
    improvements: List[ImprovementSuggestion] = Field(
        default_factory=list, description="개선 제안 목록"
    )
    suggested_actions: List[str] = Field(
        default_factory=list, description="제안 액션 목록"
    )
    total_improvements: int = Field(..., ge=0, description="총 개선 제안 수")
    priority_breakdown: Dict[str, int] = Field(
        default_factory=dict, description="우선순위별 개선 제안 수"
    )
    estimated_completion_time: Optional[str] = Field(
        default=None, description="예상 완료 시간"
    )


class ActionPlan(BaseModel):
    """개선 계획"""
    task_id: str = Field(..., description="Task ID")
    phases: List[Dict[str, Union[str, List[str], int]]] = Field(
        default_factory=list, description="개선 단계"
    )
    timeline: Dict[str, str] = Field(
        default_factory=dict, description="시간 계획"
    )
    resources: List[str] = Field(
        default_factory=list, description="필요 리소스"
    )


class QualityHistory(BaseModel):
    """품질 평가 이력"""
    task_id: str = Field(..., description="Task ID")
    assessment_id: str = Field(..., description="평가 ID")
    assessment_date: datetime = Field(..., description="평가 시간")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="전체 점수")
    grade: str = Field(..., description="등급")
    changes: Optional[Dict[str, Union[float, str]]] = Field(
        default=None, description="변화량"
    )