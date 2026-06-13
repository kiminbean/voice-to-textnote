"""
회의록 품질 평가 서비스
SPEC-QUALITY-MONITOR-001: 실시간 점수/피드백/추세 분석 확장
"""

import json
import os
import re
import uuid as _uuid
from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.quality_feedback_models import QualityFeedback, QualityScoreSnapshot
from backend.ml.openai_client import get_openai_client
from backend.schemas.quality import (
    AssessmentFocus,
    AssessmentSummary,
    FeedbackCategory,
    ImprovementSuggestion,
    ImprovementType,
    IssueSeverity,
    LiveQualityScoreResponse,
    Priority,
    QualityAssessmentResponse,
    QualityFeedbackCreate,
    QualityFeedbackResponse,
    QualityFeedbackSummary,
    QualityIssue,
    QualityScore,
    QualityTrendPoint,
    QualityTrendsResponse,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class QualityService:
    """회의록 품질 평가 서비스"""

    def __init__(self):
        self.openai_client = get_openai_client()
        self.assessment_weights = {
            "completeness": 0.25,  # 완전성
            "clarity": 0.20,  # 명확성
            "structure": 0.20,  # 구조
            "content": 0.20,  # 내용
            "action_items": 0.15,  # 액션 아이템
        }
        self.severity_thresholds = {
            IssueSeverity.CRITICAL: 0.9,
            IssueSeverity.HIGH: 0.7,
            IssueSeverity.MEDIUM: 0.4,
            IssueSeverity.LOW: 0.1,
        }

    async def assess_minutes(
        self,
        task_id: str,
        meeting_content: str,
        meeting_title: str,
        include_details: bool = True,
        custom_criteria: dict[str, int | float | list[str]] | None = None,
        assessment_focus: list[AssessmentFocus] | None = None,
        db: AsyncSession | None = None,
    ) -> QualityAssessmentResponse:
        """
        회의록 품질 평가 수행

        Args:
            task_id: Task ID
            meeting_content: 회의 내용
            meeting_title: 회의 제목
            include_details: 세부 정보 포함 여부
            custom_criteria: 커스텀 평가 기준
            assessment_focus: 평가 집중 영역
            db: 데이터베이션 세션

        Returns:
            QualityAssessmentResponse
        """
        try:
            # 기본 분석 수행
            basic_analysis = await self._perform_basic_analysis(meeting_content)

            # AI 기반 심층 분석
            ai_analysis = await self._ai_based_assessment(
                meeting_content, meeting_title, assessment_focus or list(AssessmentFocus)
            )

            # 개별 카테고리 평가
            category_scores = await self._evaluate_categories(
                basic_analysis, ai_analysis, custom_criteria
            )

            # 종합 점수 계산
            overall_score = self._calculate_overall_score(category_scores)

            # 문제 식별
            issues = await self._identify_issues(basic_analysis, ai_analysis, overall_score)

            # 평가 요약 생성
            summary = await self._create_assessment_summary(
                overall_score, category_scores, issues, meeting_title
            )

            # 추천 사항 생성
            recommendations = await self._generate_recommendations(issues, category_scores)

            return QualityAssessmentResponse(
                task_id=task_id,
                assessment_summary=summary,
                category_scores=category_scores,
                issues=issues if include_details else [],
                recommendations=recommendations,
                metadata={
                    "analysis_version": "1.0.0",
                    "analysis_timestamp": datetime.now().isoformat(),
                    "content_length": len(meeting_content),
                    "word_count": len(meeting_content.split()),
                },
            )

        except Exception as e:
            logger.error(f"Quality assessment failed for task {task_id}", error=str(e))
            raise

    async def _perform_basic_analysis(self, content: str) -> dict[str, int | float | list[str]]:
        """기본 분석 수행"""
        words = content.split()
        sentences = re.split(r"[.!?]+", content)

        # 기본 통계
        analysis = {
            "word_count": len(words),
            "sentence_count": len([s for s in sentences if s.strip()]),
            "paragraph_count": len(content.split("\n\n")),
            "avg_sentence_length": len(words) / len([s for s in sentences if s.strip()]),
            "has_action_items": bool(
                re.search(r"(action|todo|task|todo list|deliverable)", content, re.IGNORECASE)
            ),
            "has_decisions": bool(
                re.search(r"(decide|decision|agree|resolve)", content, re.IGNORECASE)
            ),
            "has_attendees": bool(
                re.search(r"(attendee|participant|present)", content, re.IGNORECASE)
            ),
            "has_timeline": bool(
                re.search(r"(time|date|schedule|deadline)", content, re.IGNORECASE)
            ),
            "has_structure": bool(
                re.search(r"(agenda|section|topic|item)", content, re.IGNORECASE)
            ),
            "readability_score": self._calculate_readability(words, sentences),
        }

        return analysis

    def _calculate_readability(self, words: list[str], sentences: list[str]) -> float:
        """가독성 점수 계산 (간단한 Flesch Reading Ease 공식)"""
        if not sentences:
            return 0.0

        avg_sentence_length = len(words) / len(sentences)
        avg_syllables_per_word = sum(len(word) for word in words) / len(words) * 0.39

        # Flesch Reading Ease: 206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word
        # 간단화된 버전 (0-100 점)
        score = max(
            0, min(100, 206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word)
        )
        return score

    async def _ai_based_assessment(
        self, content: str, title: str, assessment_focus: list[AssessmentFocus]
    ) -> dict[str, str | float | list[str]]:
        """AI 기반 심층 분석"""

        prompt = f"""
        다음 회의록의 품질을 평가해주세요. 회의 제목: {title}

        평가 기준:
        - 완전성 (completeness): 모든 중요한 내용이 포함되었는가
        - 명확성 (clarity): 내용이 명확하고 이해하기 쉬운가
        - 구조 (structure): 논리적 구조가 잘 되어있는가
        - 내용 (content): 내용이 유용하고 정보가 풍부한가
        - 액션 아이템 (action_items): 실행할 사항이 명확하게 제시되었는가

        회의록 내용:
        {content[:3000]}  # 최대 3000자까지만 분석

        다음 형식으로 JSON 응답을 생성해주세요:
        {{
            "completeness_score": 0-100,
            "clarity_score": 0-100,
            "structure_score": 0-100,
            "content_score": 0-100,
            "action_items_score": 0-100,
            "strengths": ["강점1", "강점2"],
            "weaknesses": ["약점1", "약점2"],
            "key_issues": ["주요 문제1", "주요 문제2"]
        }}
        """

        try:
            # response_format=json_object: 모델이 항상 valid JSON을 반환하도록 강제.
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            ai_text = response.choices[0].message.content
            # JSON 파싱 (간단한 방식)
            json_start = ai_text.find("{")
            json_end = ai_text.rfind("}") + 1

            if json_start != -1 and json_end != -1:
                json_str = ai_text[json_start:json_end]
                return json.loads(json_str)
            else:
                # JSON 파싱 실패 시 기본값 반환
                return self._get_default_ai_assessment()

        except Exception as e:
            logger.error("AI assessment failed", error=str(e))
            return self._get_default_ai_assessment()

    def _get_default_ai_assessment(self) -> dict[str, str | float | list[str]]:
        """AI 분석 실패 시 기본값 반환"""
        return {
            "completeness_score": 60.0,
            "clarity_score": 65.0,
            "structure_score": 70.0,
            "content_score": 75.0,
            "action_items_score": 50.0,
            "strengths": ["기본적인 내용 포함"],
            "weaknesses": ["심층 분석 불가"],
            "key_issues": ["AI 분석 실패"],
        }

    async def _evaluate_categories(
        self,
        basic_analysis: dict[str, int | float | list[str]],
        ai_analysis: dict[str, str | float | list[str]],
        custom_criteria: dict[str, int | float | list[str]] | None = None,
    ) -> list[QualityScore]:
        """개별 카테고리 평가"""

        scores = []

        # 완전성 평가
        completeness_score = self._evaluate_completeness(basic_analysis, ai_analysis)
        scores.append(
            QualityScore(
                category="completeness",
                score=completeness_score,
                description="회의록의 완전성 (정보 누락 검사)",
            )
        )

        # 명확성 평가
        clarity_score = self._evaluate_clarity(basic_analysis, ai_analysis)
        scores.append(
            QualityScore(category="clarity", score=clarity_score, description="내용의 명확성")
        )

        # 구조 평가
        structure_score = self._evaluate_structure(basic_analysis, ai_analysis)
        scores.append(
            QualityScore(category="structure", score=structure_score, description="회의록의 구조")
        )

        # 내용 평가
        content_score = self._evaluate_content(basic_analysis, ai_analysis)
        scores.append(
            QualityScore(category="content", score=content_score, description="내용의 품질")
        )

        # 액션 아이템 평가
        action_items_score = self._evaluate_action_items(basic_analysis, ai_analysis)
        scores.append(
            QualityScore(
                category="action_items",
                score=action_items_score,
                description="액션 아이템의 명확성",
            )
        )

        # 커스텀 기준이 있는 경우 추가 평가
        if custom_criteria:
            scores.extend(
                await self._evaluate_custom_criteria(custom_criteria, basic_analysis, ai_analysis)
            )

        return scores

    def _evaluate_completeness(
        self,
        basic_analysis: dict[str, int | float | list[str]],
        ai_analysis: dict[str, str | float | list[str]],
    ) -> float:
        """완전성 평가"""
        score = 0.0
        components = 0

        # 기본 요소 확인
        if basic_analysis.get("has_attendees", False):
            score += 20
        components += 1

        if basic_analysis.get("has_timeline", False):
            score += 20
        components += 1

        if basic_analysis.get("has_decisions", False):
            score += 20
        components += 1

        if basic_analysis.get("has_action_items", False):
            score += 20
        components += 1

        # AI 분석 결과 반영
        if "completeness_score" in ai_analysis:
            score += ai_analysis["completeness_score"] * 0.2
            components += 1

        # 단어 수 기준
        word_count = basic_analysis.get("word_count", 0)
        if word_count > 500:
            score += min(20, (word_count - 500) / 50)
        components += 1

        return min(100, score / max(components, 1))

    def _evaluate_clarity(
        self,
        basic_analysis: dict[str, int | float | list[str]],
        ai_analysis: dict[str, str | float | list[str]],
    ) -> float:
        """명확성 평가"""
        score = 0.0
        components = 0

        # 문장 길이 기준
        avg_sentence_length = basic_analysis.get("avg_sentence_length", 0)
        if 15 <= avg_sentence_length <= 30:
            score += 30
        else:
            score += max(0, 30 - abs(avg_sentence_length - 22.5) * 2)
        components += 1

        # 가독성
        readability = basic_analysis.get("readability_score", 0)
        score += min(40, readability * 0.4)
        components += 1

        # AI 명확성 점수
        if "clarity_score" in ai_analysis:
            score += ai_analysis["clarity_score"] * 0.3
            components += 1

        return min(100, score / max(components, 1))

    def _evaluate_structure(
        self,
        basic_analysis: dict[str, int | float | list[str]],
        ai_analysis: dict[str, str | float | list[str]],
    ) -> float:
        """구조 평가"""
        score = 0.0
        components = 0

        # 단락 수
        paragraph_count = basic_analysis.get("paragraph_count", 0)
        if paragraph_count >= 3:
            score += 30
        else:
            score += paragraph_count * 10
        components += 1

        # 구조적 요소 확인
        if basic_analysis.get("has_structure", False):
            score += 30
        components += 1

        # AI 구조 점수
        if "structure_score" in ai_analysis:
            score += ai_analysis["structure_score"] * 0.4
            components += 1

        return min(100, score / max(components, 1))

    def _evaluate_content(
        self,
        basic_analysis: dict[str, int | float | list[str]],
        ai_analysis: dict[str, str | float | list[str]],
    ) -> float:
        """내용 평가"""
        score = 0.0
        components = 0

        # 단어 수 기준
        word_count = basic_analysis.get("word_count", 0)
        if word_count > 200:
            score += 40
        else:
            score += word_count * 0.2
        components += 1

        # AI 내용 점수
        if "content_score" in ai_analysis:
            score += ai_analysis["content_score"] * 0.6
            components += 1

        return min(100, score / max(components, 1))

    def _evaluate_action_items(
        self,
        basic_analysis: dict[str, int | float | list[str]],
        ai_analysis: dict[str, str | float | list[str]],
    ) -> float:
        """액션 아이템 평가"""
        score = 0.0
        components = 0

        # 액션 아이템 존재 여부
        if basic_analysis.get("has_action_items", False):
            score += 50
        else:
            score += 10  # 적은 점수 부여
        components += 1

        # AI 액션 아이템 점수
        if "action_items_score" in ai_analysis:
            score += ai_analysis["action_items_score"] * 0.5
            components += 1

        return min(100, score / max(components, 1))

    async def _evaluate_custom_criteria(
        self,
        custom_criteria: dict[str, int | float | list[str]],
        basic_analysis: dict[str, int | float | list[str]],
        ai_analysis: dict[str, str | float | list[str]],
    ) -> list[QualityScore]:
        """커스텀 기준 평가"""
        scores = []

        # 간단한 커스텀 기준 구현 (확장 가능)
        for criterion_name, criterion_value in custom_criteria.items():
            if isinstance(criterion_value, int | float):
                score = min(100, max(0, criterion_value))
                scores.append(
                    QualityScore(
                        category=f"custom_{criterion_name}",
                        score=score,
                        description=f"커스텀 기준: {criterion_name}",
                    )
                )

        return scores

    def _calculate_overall_score(self, category_scores: list[QualityScore]) -> float:
        """종합 점수 계산"""
        if not category_scores:
            return 0.0

        # 기본 카테고리만 고려
        basic_categories = ["completeness", "clarity", "structure", "content", "action_items"]
        relevant_scores = [
            score.score for score in category_scores if score.category in basic_categories
        ]

        if not relevant_scores:
            return 0.0

        return sum(relevant_scores) / len(relevant_scores)

    async def _identify_issues(
        self,
        basic_analysis: dict[str, int | float | list[str]],
        ai_analysis: dict[str, str | float | list[str]],
        overall_score: float,
    ) -> list[QualityIssue]:
        """문제 식별"""
        issues = []

        # 완전성 문제
        if not basic_analysis.get("has_attendees", False):
            issues.append(
                QualityIssue(
                    id="issue_001",
                    category="completeness",
                    severity=IssueSeverity.HIGH,
                    description="참석자 정보가 누락되었습니다",
                    suggestion="회의 시작 시 참석자 목록을 명시해주세요",
                )
            )

        if not basic_analysis.get("has_timeline", False):
            issues.append(
                QualityIssue(
                    id="issue_002",
                    category="completeness",
                    severity=IssueSeverity.MEDIUM,
                    description="시간 정보가 누락되었습니다",
                    suggestion="회의 시간 및 소요 시간을 기록해주세요",
                )
            )

        # 명확성 문제
        avg_sentence_length = basic_analysis.get("avg_sentence_length", 0)
        if avg_sentence_length > 50:
            issues.append(
                QualityIssue(
                    id="issue_003",
                    category="clarity",
                    severity=IssueSeverity.MEDIUM,
                    description="문장이 너무 깁니다",
                    suggestion=f"평균 문장 길이: {avg_sentence_length:.0f}자. 30자 이하로 줄이세요",
                )
            )

        # 액션 아이템 문제
        if not basic_analysis.get("has_action_items", False):
            issues.append(
                QualityIssue(
                    id="issue_004",
                    category="action_items",
                    severity=IssueSeverity.HIGH,
                    description="액션 아이템이 정의되지 않았습니다",
                    suggestion="의결 사항과 실행 계획을 명확히 기록하세요",
                )
            )

        # AI 분석에서 심각한 문제가 발견된 경우
        if "key_issues" in ai_analysis:
            for i, issue in enumerate(ai_analysis["key_issues"][:3]):
                severity = IssueSeverity.HIGH if i < 1 else IssueSeverity.MEDIUM
                issues.append(
                    QualityIssue(
                        id=f"issue_ai_{i:03d}",
                        category="ai_analysis",
                        severity=severity,
                        description=issue,
                        suggestion=f"AI 분석에 의한 제안: {issue}",
                    )
                )

        # 전체 점수에 따라 심각도 조정
        if overall_score < 50:
            for issue in issues:
                if issue.severity == IssueSeverity.MEDIUM:
                    issue.severity = IssueSeverity.HIGH
                elif issue.severity == IssueSeverity.LOW:
                    issue.severity = IssueSeverity.MEDIUM

        return issues

    async def _create_assessment_summary(
        self,
        overall_score: float,
        category_scores: list[QualityScore],
        issues: list[QualityIssue],
        title: str,
    ) -> AssessmentSummary:
        """평가 요약 생성"""
        # 등급 계산
        grade = self._calculate_grade(overall_score)

        # 문제 통계
        total_issues = len(issues)
        critical_issues = len([i for i in issues if i.severity == IssueSeverity.CRITICAL])

        # 강점 및 약점 식별
        strengths = []
        weaknesses = []

        for score in category_scores:
            if score.score >= 80:
                strengths.append(f"{score.category} 우수")
            elif score.score < 60:
                weaknesses.append(f"{score.category} 개선 필요")

        # AI 분석에서 강점/약점 추가
        strengths.extend(["기본적인 정보 포함", "논리적 구조"])
        if overall_score >= 70:
            strengths.append("전체적으로 좋은 품질")
        else:
            weaknesses.append("전체적인 품질 개선 필요")

        return AssessmentSummary(
            overall_score=overall_score,
            grade=grade,
            total_issues=total_issues,
            critical_issues=critical_issues,
            strengths=list(set(strengths)),  # 중복 제거
            weaknesses=list(set(weaknesses)),  # 중복 제거
            last_assessed=datetime.now(),
        )

    def _calculate_grade(self, score: float) -> str:
        """점수에 따른 등급 계산"""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "C+"
        elif score >= 65:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    async def _generate_recommendations(
        self, issues: list[QualityIssue], category_scores: list[QualityScore]
    ) -> list[str]:
        """추천 사항 생성"""
        recommendations = []

        # 점수가 낮은 카테고리에 대한 추천
        for score in category_scores:
            if score.score < 70:
                if score.category == "completeness":
                    recommendations.append("모든 중요한 정보(참석자, 시간, 의사결정)를 포함하세요")
                elif score.category == "clarity":
                    recommendations.append("문장을 더 짧게 만들고 명확한 어휘를 사용하세요")
                elif score.category == "structure":
                    recommendations.append("논리적인 섹션으로 나누고 명확한 구조를 만드세요")
                elif score.category == "content":
                    recommendations.append("더 구체적인 정보와 예시를 추가하세요")
                elif score.category == "action_items":
                    recommendations.append("명확한 액션 아이템과 책임자를 정의하세요")

        # 심각한 문제에 대한 추천
        critical_issues = [
            i for i in issues if i.severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH]
        ]
        for issue in critical_issues[:3]:  # 상위 3개만
            if issue.suggestion:
                recommendations.append(f"{issue.description}: {issue.suggestion}")

        # 일반적인 추천
        recommendations.extend(
            [
                "정기적인 품질 검사를 실시하세요",
                "참석자 피드백을 반영하여 개선하세요",
                "유사한 회의의 템플릿을 활용하세요",
            ]
        )

        return list(set(recommendations))  # 중복 제거

    async def get_improvement_suggestions(
        self,
        task_id: str,
        improvement_type: str = "all",
        priority: str = "high",
        db: AsyncSession | None = None,
    ) -> list[ImprovementSuggestion]:
        """개선 제안 가져오기"""
        suggestions = []

        # 개선 제안 템플릿
        templates = {
            "structure": [
                {
                    "title": "논리적 구조 개선",
                    "description": "회의록을 논리적인 섹션으로 나누고 명확한 제목을 사용하세요",
                    "type": ImprovementType.STRUCTURE,
                    "priority": Priority.HIGH,
                    "example": "## 회의 의사결정\n\n1. 의제 1: 결정 내용...",
                    "estimated_effort": "30분",
                    "impact": "높음",
                },
                {
                    "title": "개요 추가",
                    "description": "회의 시작 시 전체 개요를 제공하세요",
                    "type": ImprovementType.STRUCTURE,
                    "priority": Priority.MEDIUM,
                    "example": "## 회의 개요\n\n1. 도입\n2. 주요 안건\n3. 결론",
                    "estimated_effort": "15분",
                    "impact": "중간",
                },
            ],
            "content": [
                {
                    "title": "구체적인 정보 추가",
                    "description": "추상적인 내용 대신 구체적인 사실과 숫자를 포함하세요",
                    "type": ImprovementType.CONTENT,
                    "priority": Priority.HIGH,
                    "example": "매출이 증가했다 → 매출이 20% 증가하여 Q3 목표 달성",
                    "estimated_effort": "20분",
                    "impact": "높음",
                },
                {
                    "title": "배경 정보 제공",
                    "description": "의사결정에 대한 배경 정보를 포함하세요",
                    "type": ImprovementType.CONTENT,
                    "priority": Priority.MEDIUM,
                    "example": "이 의사결정은 이전의 토론 결과에 기반합니다",
                    "estimated_effort": "10분",
                    "impact": "중간",
                },
            ],
            "clarity": [
                {
                    "title": "간결한 문장 사용",
                    "description": "긴 문장을 여러 개의 짧은 문장으로 나누세요",
                    "type": ImprovementType.CLARITY,
                    "priority": Priority.HIGH,
                    "example": "긴 문장 → 짧은 문장 1. 짧은 문장 2.",
                    "estimated_effort": "25분",
                    "impact": "높음",
                },
                {
                    "title": "명확한 용어 사용",
                    "description": "전문 용어나 약어 설명을 포함하세요",
                    "type": ImprovementType.CLARITY,
                    "priority": Priority.MEDIUM,
                    "example": "KPI (Key Performance Indicator)",
                    "estimated_effort": "15분",
                    "impact": "중간",
                },
            ],
            "completeness": [
                {
                    "title": "모든 요소 포함",
                    "description": "참석자, 시간, 의사결정, 액션 아이템을 모두 포함하세요",
                    "type": ImprovementType.COMPLETENESS,
                    "priority": Priority.HIGH,
                    "estimated_effort": "20분",
                    "impact": "높음",
                },
                {
                    "title": "다음 회의 예정 추가",
                    "description": "다음 회의 시간과 안건을 명시하세요",
                    "type": ImprovementType.COMPLETENESS,
                    "priority": Priority.MEDIUM,
                    "estimated_effort": "10분",
                    "impact": "중간",
                },
            ],
        }

        # 개선 유형 필터링
        if improvement_type == "all":
            selected_templates = []
            for category_templates in templates.values():
                selected_templates.extend(category_templates)
        else:
            selected_templates = templates.get(improvement_type, [])

        # 우선순위 필터링
        if priority != "all":
            selected_templates = [t for t in selected_templates if t["priority"].value == priority]

        # ImprovementSuggestion 객체 생성
        for i, template in enumerate(selected_templates):
            suggestions.append(
                ImprovementSuggestion(
                    id=f"improvement_{task_id}_{i:03d}",
                    type=template["type"],
                    priority=template["priority"],
                    title=template["title"],
                    description=template["description"],
                    example=template.get("example"),
                    estimated_effort=template.get("estimated_effort"),
                    impact=template.get("impact"),
                )
            )

        return suggestions

    async def generate_action_plan(self, improvements: list[ImprovementSuggestion]) -> list[str]:
        """개선 계획 생성"""
        if not improvements:
            return ["개선 제안이 없습니다"]

        action_plan = []
        action_plan.append("## 개선 계획")

        # 우선순위별로 정렬
        high_priority = [i for i in improvements if i.priority == Priority.HIGH]
        medium_priority = [i for i in improvements if i.priority == Priority.MEDIUM]
        low_priority = [i for i in improvements if i.priority == Priority.LOW]

        if high_priority:
            action_plan.append("\n### 1순위 (즉시 실행)")
            for improvement in high_priority:
                action_plan.append(f"- {improvement.title}")
                if improvement.estimated_effort:
                    action_plan.append(f"  - 예상 소요 시간: {improvement.estimated_effort}")

        if medium_priority:
            action_plan.append("\n### 2순위 (단기 실행)")
            for improvement in medium_priority:
                action_plan.append(f"- {improvement.title}")
                if improvement.estimated_effort:
                    action_plan.append(f"  - 예상 소요 시간: {improvement.estimated_effort}")

        if low_priority:
            action_plan.append("\n### 3순위 (장기 실행)")
            for improvement in low_priority:
                action_plan.append(f"- {improvement.title}")
                if improvement.estimated_effort:
                    action_plan.append(f"  - 예상 소요 시간: {improvement.estimated_effort}")

        # 실행 계획
        action_plan.append("\n### 실행 계획")
        action_plan.append("1. 1순위 항목을 즉시 실행합니다")
        action_plan.append("2. 2순위 항목은 1-2주 내에 실행합니다")
        action_plan.append("3. 3순위 항목은 1개월 내에 실행합니다")
        action_plan.append("4. 정기적으로 진행 상황을 검토합니다")

        return action_plan

    # ------------------------------------------------------------------
    # SPEC-QUALITY-MONITOR-001: 실시간 점수 / 피드백 / 추세 분석
    # ------------------------------------------------------------------

    async def compute_live_score(
        self,
        task_id: str,
        meeting_content: str,
        db: AsyncSession | None = None,
        persist_snapshot: bool = True,
    ) -> LiveQualityScoreResponse:
        """경량 실시간 품질 점수 계산 (AI 호출 없음).

        Args:
            task_id: 평가 대상 Task ID
            meeting_content: 회의록 본문
            db: 스냅샷 저장용 DB 세션 (None이면 저장 생략)
            persist_snapshot: True면 QualityScoreSnapshot에 저장

        Returns:
            LiveQualityScoreResponse
        """
        basic = await self._perform_basic_analysis(meeting_content)

        # AI 분석은 호출하지 않고 기본 분석만으로 카테고리 점수 산출
        empty_ai: dict[str, str | float | list[str]] = {}
        completeness = self._evaluate_completeness(basic, empty_ai)
        clarity = self._evaluate_clarity(basic, empty_ai)
        structure = self._evaluate_structure(basic, empty_ai)

        overall = (completeness + clarity + structure) / 3.0
        grade = self._calculate_grade(overall)
        now = datetime.now()

        if db is not None and persist_snapshot:
            snapshot = QualityScoreSnapshot()
            snapshot.id = _uuid.uuid4()
            snapshot.task_id = task_id
            snapshot.overall_score = overall
            snapshot.grade = grade
            snapshot.completeness_score = completeness
            snapshot.clarity_score = clarity
            snapshot.structure_score = structure
            snapshot.mode = "lightweight"
            db.add(snapshot)
            await db.commit()

        return LiveQualityScoreResponse(
            task_id=task_id,
            overall_score=round(overall, 2),
            grade=grade,
            completeness_score=round(completeness, 2),
            clarity_score=round(clarity, 2),
            structure_score=round(structure, 2),
            word_count=int(basic.get("word_count", 0) or 0),
            computed_at=now,
            mode="lightweight",
        )

    async def submit_feedback(
        self,
        db: AsyncSession,
        task_id: str,
        user_id: _uuid.UUID | None,
        payload: QualityFeedbackCreate,
    ) -> QualityFeedbackResponse:
        """사용자 피드백을 저장한다."""
        feedback = QualityFeedback()
        feedback.id = _uuid.uuid4()
        feedback.task_id = task_id
        feedback.user_id = user_id
        feedback.rating = payload.rating
        feedback.category = payload.category.value
        feedback.comment = payload.comment

        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)

        return QualityFeedbackResponse(
            id=str(feedback.id),
            task_id=feedback.task_id,
            rating=feedback.rating,
            category=FeedbackCategory(feedback.category),
            comment=feedback.comment,
            created_at=feedback.created_at,
        )

    async def get_feedback_summary(
        self,
        db: AsyncSession,
        task_id: str,
        recent_limit: int = 10,
    ) -> QualityFeedbackSummary:
        """누적 피드백 요약."""
        avg_stmt = select(
            func.count(QualityFeedback.id),
            func.avg(QualityFeedback.rating),
        ).where(QualityFeedback.task_id == task_id)
        agg = (await db.execute(avg_stmt)).one()
        total = int(agg[0] or 0)
        avg_rating = float(agg[1]) if agg[1] is not None else None

        cat_stmt = (
            select(QualityFeedback.category, func.count(QualityFeedback.id))
            .where(QualityFeedback.task_id == task_id)
            .group_by(QualityFeedback.category)
        )
        breakdown: dict[str, int] = {
            row[0]: int(row[1]) for row in (await db.execute(cat_stmt)).all()
        }

        recent_stmt = (
            select(QualityFeedback)
            .where(QualityFeedback.task_id == task_id)
            .order_by(desc(QualityFeedback.created_at))
            .limit(max(1, min(recent_limit, 50)))
        )
        recent_rows = (await db.execute(recent_stmt)).scalars().all()
        recent = [
            QualityFeedbackResponse(
                id=str(row.id),
                task_id=row.task_id,
                rating=row.rating,
                category=FeedbackCategory(row.category),
                comment=row.comment,
                created_at=row.created_at,
            )
            for row in recent_rows
        ]

        return QualityFeedbackSummary(
            task_id=task_id,
            total_feedbacks=total,
            avg_rating=round(avg_rating, 2) if avg_rating is not None else None,
            category_breakdown=breakdown,
            recent=recent,
        )

    async def get_quality_trends(
        self,
        db: AsyncSession,
        task_id: str,
        limit: int = 50,
        warning_drop_threshold: float | None = None,
    ) -> QualityTrendsResponse:
        """저장된 품질 스냅샷으로 추세 분석을 수행한다."""
        if warning_drop_threshold is None:
            try:
                warning_drop_threshold = float(os.getenv("QUALITY_TRENDS_WARNING_DROP", "10"))
            except (TypeError, ValueError):
                warning_drop_threshold = 10.0

        stmt = (
            select(QualityScoreSnapshot)
            .where(QualityScoreSnapshot.task_id == task_id)
            .order_by(QualityScoreSnapshot.created_at)
            .limit(max(1, min(limit, 500)))
        )
        rows = (await db.execute(stmt)).scalars().all()

        if not rows:
            return QualityTrendsResponse(
                task_id=task_id,
                points=[],
                points_count=0,
                avg_score=None,
                min_score=None,
                max_score=None,
                trend_direction="insufficient_data",
                warning=None,
            )

        points = [
            QualityTrendPoint(
                timestamp=row.created_at,
                overall_score=row.overall_score,
                grade=row.grade,
                mode=row.mode,
            )
            for row in rows
        ]
        scores = [p.overall_score for p in points]
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)

        if len(scores) < 2:
            direction = "insufficient_data"
            warning = None
        else:
            first_half = scores[: len(scores) // 2] or scores[:1]
            second_half = scores[len(scores) // 2:] or scores[-1:]
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)
            delta = second_avg - first_avg

            if delta > 2.0:
                direction = "up"
            elif delta < -2.0:
                direction = "down"
            else:
                direction = "stable"

            warning = None
            drop = scores[0] - scores[-1]
            if drop >= warning_drop_threshold:
                warning = (
                    f"품질 점수가 초기값 대비 {drop:.1f}점 하락했습니다. 원인 검토를 권장합니다."
                )

        return QualityTrendsResponse(
            task_id=task_id,
            points=points,
            points_count=len(points),
            avg_score=round(avg_score, 2),
            min_score=round(min_score, 2),
            max_score=round(max_score, 2),
            trend_direction=direction,
            warning=warning,
        )
