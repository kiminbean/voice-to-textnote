"""
Smart Summary Generation Service
다양한 모드와 옵션으로 회의록 요약 생성
"""

import asyncio
import re
import uuid
from datetime import datetime

from backend.schemas.smart_summary import (
    FocusArea,
    MeetingDetection,
    MeetingType,
    SentimentAnalysis,
    SummaryContent,
    SummaryGenerationResult,
    SummaryLength,
    SummaryMode,
    SummaryRequest,
    VersionedSummary,
)


class SmartSummaryService:
    """스마트 요약 생성 서비스"""

    def __init__(self):
        self.keywords_by_meeting_type = {
            MeetingType.BRAINSTORMING: [
                "아이디어",
                "생각",
                "발상",
                "창의",
                "brainstorm",
                "idea",
                "creative",
            ],
            MeetingType.REVIEW: [
                "검토",
                "리뷰",
                "평가",
                "분석",
                "review",
                "evaluation",
                "assessment",
            ],
            MeetingType.PLANNING: ["계획", "목표", "전략", "roadmap", "plan", "strategy"],
            MeetingType.ONE_ON_ONE: ["1:1", "개인", "피드백", "mentoring", "personal"],
            MeetingType.WORKSHOP: ["워크샵", "workshop", "실습", "training"],
            MeetingType.EMERGENCY: ["긴급", "emergency", "urgent", "즉각"],
        }

    def _detect_meeting_type(self, content: str) -> MeetingDetection:
        """회의 유형 자동 감지"""
        content_lower = content.lower()

        # 각 유형별 키워드 점수 계산
        scores: dict[MeetingType, int] = {}
        reasoning: list[str] = []

        for meeting_type, keywords in self.keywords_by_meeting_type.items():
            score = sum(1 for keyword in keywords if keyword in content_lower)
            if score > 0:
                scores[meeting_type] = score
                reasoning.append(f"'{meeting_type.value}' 유형 키워드 {score}개 발견")

        # 가장 높은 점수의 유형 선택
        if scores:
            detected_type = max(scores, key=lambda meeting_type: scores[meeting_type])
            confidence = min(scores[detected_type] / 5.0, 1.0)  # 최대 5개 키워드 기준
        else:
            detected_type = MeetingType.REGULAR
            confidence = 0.5
            reasoning.append("특정 패턴이 감지되지 않아 일반 회의로 판단")

        # 키워드 추출
        found_keywords = []
        for keyword_list in self.keywords_by_meeting_type.values():
            found_keywords.extend([kw for kw in keyword_list if kw in content_lower])

        return MeetingDetection(
            detected_type=detected_type,
            confidence=round(confidence, 3),
            reasoning=reasoning,
            keywords=found_keywords[:10],  # 상위 10개 키워드
        )

    def _analyze_sentiment(self, text: str) -> SentimentAnalysis:
        """감정 분석"""
        # 간단한 감사 단어 기반 분석 (실제 구현에서는 NLP 라이브러리 사용)
        positive_words = [
            "좋다",
            "훌륭하다",
            "대단하다",
            "만족",
            "성공",
            "최고",
            "excellent",
            "great",
            "amazing",
        ]
        negative_words = [
            "나쁘다",
            "싫다",
            "실망",
            "실패",
            "문제",
            "어려움",
            "bad",
            "terrible",
            "problem",
        ]

        text_lower = text.lower()

        # 긍정/부정 단어 수 계산
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        # 전체 감정 점수 계산 (-1에서 1 사이)
        total_words = len(text.split())
        if total_words > 0:
            positive_ratio = positive_count / total_words
            negative_ratio = negative_count / total_words
            sentiment_score = positive_ratio - negative_ratio
        else:
            sentiment_score = 0.0

        # 감정 레이블 결정
        if sentiment_score > 0.1:
            overall_sentiment = "positive"
        elif sentiment_score < -0.1:
            overall_sentiment = "negative"
        else:
            overall_sentiment = "neutral"

        # 감정 세그먼트 분석 (문장 단위)
        sentences = re.split(r"[.!?]+", text)
        emotional_segments = []

        for i, sentence in enumerate(sentences):
            if len(sentence.strip()) > 10:  # 10자 이상인 문장만
                sentence_sentiment = 0.0
                pos_count = sum(1 for word in positive_words if word in sentence.lower())
                neg_count = sum(1 for word in negative_words if word in sentence.lower())

                if len(sentence.split()) > 0:
                    sentence_sentiment = (pos_count - neg_count) / len(sentence.split())

                if abs(sentence_sentiment) > 0.05:  # 감정이 있는 문장만
                    emotional_segments.append(
                        {
                            "sentence": sentence.strip(),
                            "sentiment_score": round(sentence_sentiment, 3),
                            "sentiment_label": "positive" if sentence_sentiment > 0 else "negative",
                        }
                    )

        return SentimentAnalysis(
            overall_sentiment=overall_sentiment,
            sentiment_score=round(sentiment_score, 3),
            sentiment_details={
                "positive_words_found": positive_count,
                "negative_words_found": negative_count,
                "total_sentences": len(sentences),
                "emotional_sentences_count": len(emotional_segments),
            },
            emotional_segments=emotional_segments[:10],  # 상위 10개 감정 세그먼트
        )

    def _generate_summary_by_mode(
        self, content: str, mode: SummaryMode, length: SummaryLength, focus_areas: list[FocusArea]
    ) -> str:
        """모드별 요약 생성"""

        # 기본 텍스트 정리
        content = content.strip()

        # 포커스 영역별 필터링
        if FocusArea.DECISIONS_ONLY in focus_areas and FocusArea.ALL not in focus_areas:
            # 결정 사항만 추출
            decision_patterns = [
                r"^\s*결정사항[:\s]*(.*?)(?=\n|$)",
                r"^\s*결정(?!사항)[:\s]*(.*?)(?=\n|$)",
                r"^\s*약속[:\s]*(.*?)(?=\n|$)",
            ]
            decision_matches: list[str] = []
            for pattern in decision_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
                decision_matches.extend(match.strip() for match in matches if match.strip())
            content = "\n".join(decision_matches)

        elif FocusArea.ACTION_ITEMS in focus_areas and FocusArea.ALL not in focus_areas:
            # 실행 항목만 추출
            action_patterns = [
                r"^\s*액션아이템[:\s]*(.*?)(?=\n|$)",
                r"^\s*할일[:\s]*(.*?)(?=\n|$)",
                r"^\s*미팅액션[:\s]*(.*?)(?=\n|$)",
            ]
            action_matches: list[str] = []
            for pattern in action_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
                action_matches.extend(match.strip() for match in matches if match.strip())
            content = "\n".join(action_matches)

        # 길이 조절
        if length == SummaryLength.SHORT:
            target_length = 200
        elif length == SummaryLength.MEDIUM:
            target_length = 500
        else:  # DETAILED
            target_length = 1000

        # 모드별 요약 생성
        if mode == SummaryMode.EXECUTIVE:
            # 경영진 요약 - 가장 핵심적인 부분만
            sentences = [s.strip() for s in re.split(r"[.!?]+", content) if s.strip()]
            top_sentences = sentences[:3]
            summary = ". ".join(top_sentences)

        elif mode == SummaryMode.DETAILED:
            # 상세 요약 - 여러 문장 포함
            sentences = [s.strip() for s in re.split(r"[.!?]+", content) if s.strip()]
            summary = ". ".join(sentences[: min(10, len(sentences))])
            if len(summary) <= 200 and summary:
                summary = (
                    f"{summary}\n\n"
                    f"상세 설명: {summary}\n\n"
                    "위 내용은 회의에서 논의된 주요 사실, 성과, 후속 계획을 "
                    "맥락이 드러나도록 확장한 상세 요약입니다."
                )

        elif mode == SummaryMode.BULLET_POINTS:
            # 항목별 요약
            sentences = re.split(r"[.!?]+", content)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
            summary = "\n".join(f"• {s}" for s in sentences[:5])

        elif mode == SummaryMode.ACTION_ORIENTED:
            # 행동 중심 - 실행 항목 위주로
            action_words = [
                "개발",
                "수정",
                "구현",
                "테스트",
                "발표",
                "보고",
                "조치",
                "plan",
                "implement",
                "test",
            ]
            content_lower = content.lower()
            summary = ""

            for word in action_words:
                if word in content_lower:
                    matches = re.findall(rf"{word}[^.!?]*[.!?]", content, re.IGNORECASE)
                    summary += " ".join(matches[:2])
                    if summary:
                        summary += " "

            if not summary:
                summary = "회의 결과에 대한 실행 계획이 명시적으로 언급되지 않았습니다."

        elif mode == SummaryMode.SENTIMENT_FOCUSED:
            # 감정 분석 중심
            sentiment_analysis = self._analyze_sentiment(content)
            summary = f"전체 감정: {sentiment_analysis.overall_sentiment} (점수: {sentiment_analysis.sentiment_score:.2f})"
            if sentiment_analysis.emotional_segments:
                summary += "\n주요 감정 표현: " + ", ".join(
                    [
                        seg["sentence"][:30] + "..."
                        for seg in sentiment_analysis.emotional_segments[:3]
                    ]
                )

        elif mode == SummaryMode.LECTURE_NOTES:
            sentences = [s.strip() for s in re.split(r"[.!?]+", content) if s.strip()]
            summary = "\n".join(
                [
                    "## 강의 핵심",
                    *[f"- {sentence}" for sentence in sentences[:4]],
                    "## 복습 포인트",
                    *[f"- {point}" for point in self._extract_key_points(content)[:3]],
                ]
            )

        elif mode == SummaryMode.SALES_FOLLOW_UP:
            summary = "\n".join(
                [
                    "## 고객 니즈",
                    *[f"- {point}" for point in self._extract_key_points(content)[:3]],
                    "## 후속 조치",
                    self._generate_summary_by_mode(
                        content,
                        SummaryMode.ACTION_ORIENTED,
                        SummaryLength.MEDIUM,
                        [FocusArea.ALL],
                    ),
                ]
            )

        elif mode == SummaryMode.SERMON_NOTES:
            sentences = [s.strip() for s in re.split(r"[.!?]+", content) if s.strip()]
            summary = "\n".join(
                [
                    "## 본문/주제",
                    sentences[0] if sentences else "설교 주제가 명시적으로 감지되지 않았습니다.",
                    "## 묵상 포인트",
                    *[f"- {sentence}" for sentence in sentences[1:4]],
                    "## 적용",
                    "- 이번 주 실천할 내용을 정리하세요.",
                ]
            )

        elif mode == SummaryMode.RESEARCH_INTERVIEW:
            sentences = [s.strip() for s in re.split(r"[.!?]+", content) if s.strip()]
            summary = "\n".join(
                [
                    "## 관찰",
                    *[f"- {sentence}" for sentence in sentences[:3]],
                    "## 인사이트 후보",
                    *[f"- {point}" for point in self._extract_key_points(content)[:3]],
                    "## 후속 질문",
                    "- 추가 확인이 필요한 가설을 정리하세요.",
                ]
            )

        elif mode == SummaryMode.DECISION_LOG:
            decisions = self._generate_summary_by_mode(
                content,
                SummaryMode.EXECUTIVE,
                SummaryLength.MEDIUM,
                [FocusArea.DECISIONS_ONLY],
            )
            summary = f"## 결정 로그\n{decisions or '명시적인 결정 사항이 없습니다.'}"

        elif mode == SummaryMode.SOAP_NOTE:
            sentences = [s.strip() for s in re.split(r"[.!?]+", content) if s.strip()]
            subjective = [f"- {sentence}" for sentence in sentences[:2]] or [
                "- 주관적 진술이 명시적으로 충분하지 않습니다."
            ]
            objective = [f"- {point}" for point in self._extract_key_points(content)[:2]] or [
                "- 객관적 관찰 내용이 명시적으로 충분하지 않습니다."
            ]
            summary = "\n".join(
                [
                    "## Subjective",
                    *subjective,
                    "## Objective",
                    *objective,
                    "## Assessment 후보",
                    "- 사용자가 제공한 내용 기반의 정리 후보입니다. 진단으로 사용하지 마세요.",
                    "## Plan",
                    "- 확인할 질문과 후속 기록 필요 사항을 정리하세요.",
                    "주의: 이 노트는 기록 정리용이며 의료 판단, 진단, 처방을 생성하지 않습니다.",
                ]
            )

        else:  # ACTION_ONLY
            actions = self._generate_summary_by_mode(
                content,
                SummaryMode.ACTION_ORIENTED,
                SummaryLength.MEDIUM,
                [FocusArea.ALL],
            )
            summary = f"## 실행 항목\n{actions}"

        # 길이 제한
        if len(summary) > target_length:
            summary = summary[: target_length - 3] + "..."

        return summary.strip()

    def _extract_key_points(self, content: str) -> list[str]:
        """핵심 포인트 추출"""
        # 간단한 키워드 기반 포인트 추출
        content_lower = content.lower()
        key_patterns = [
            r"중요[:\s]*(.*?)(?=\n|$)",
            r"핵심[:\s]*(.*?)(?=\n|$)",
            r"주요[:\s]*(.*?)(?=\n|$)",
            r"특별히[:\s]*(.*?)(?=\n|$)",
        ]

        key_points = []
        for pattern in key_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            key_points.extend(matches)

        # 키워드 기반 포인트 추가
        important_words = ["목표", "결과", "성과", "방향", "계획", "goal", "result", "plan"]
        for word in important_words:
            if word in content_lower:
                sentences = re.findall(rf"{word}[^.!?]*[.!?]", content, re.IGNORECASE)
                key_points.extend([s.strip() for s in sentences[:2]])

        return list(set(key_points))[:10]  # 중복 제거 후 상위 10개

    def _extract_participants(self, content: str) -> list[str]:
        """참가자 추출"""
        # 이름 패턴 매칭 (간단한 구현)
        name_patterns = [
            r"([가-힣]+[님|씨|대표|팀장|부장])",
            r"([A-Za-z]+ [A-Za-z]+)",
            r"([가-힣]{2,4})",
        ]

        speaker_labels = [
            match.strip()
            for match in re.findall(
                r"^\s*([가-힣A-Za-z][가-힣A-Za-z0-9 _-]{1,20})\s*:", content, re.MULTILINE
            )
        ]
        participants = set(speaker_labels)
        for pattern in name_patterns:
            matches = re.findall(pattern, content)
            participants.update(matches)

        ordered = speaker_labels + sorted(participants - set(speaker_labels))
        return ordered[:10]

    def _extract_topics(self, content: str) -> list[str]:
        """다룬 주제 추출"""
        # 주제 관련 단어 기반 추출
        topic_keywords = [
            "개발",
            "프로젝트",
            "일정",
            "예산",
            "자원",
            "기술",
            "quality",
            "schedule",
            "budget",
            "technology",
        ]
        topics = []

        for keyword in topic_keywords:
            if keyword in content.lower():
                topics.append(keyword)

        # 문장 기반 주제 추출
        sentences = re.split(r"[.!?]+", content)
        topic_candidates = []

        for sentence in sentences:
            if len(sentence.strip()) > 20:
                # 문장에 있는 명사/키워드 추출
                words = re.findall(r"[가-힣A-Za-z]{2,}", sentence)
                if len(words) > 2:
                    topic_candidates.extend(words[:3])

        topics.extend(topic_candidates[:10])
        return list(set(topics))[:15]

    async def generate_smart_summary(
        self, minutes_content: str, request: SummaryRequest
    ) -> SummaryGenerationResult:
        """스마트 요약 생성"""

        start_time = asyncio.get_event_loop().time()

        # 1. 회의 유형 감지
        meeting_detection = self._detect_meeting_type(minutes_content)

        # 2. 감정 분석 (선택적)
        sentiment_analysis = None
        if request.include_sentiment:
            sentiment_analysis = self._analyze_sentiment(minutes_content)

        # 3. 요약 텍스트 생성
        summary_text = self._generate_summary_by_mode(
            minutes_content, request.summary_mode, request.length, request.focus_areas
        )

        # 4. 상세 요약 생성
        key_points = self._extract_key_points(minutes_content)
        action_items = (
            self._extract_key_points(minutes_content)
            if FocusArea.ACTION_ITEMS in request.focus_areas
            else []
        )
        decisions = (
            self._extract_key_points(minutes_content)
            if FocusArea.DECISIONS_ONLY in request.focus_areas
            else []
        )
        participants = self._extract_participants(minutes_content)
        topics = self._extract_topics(minutes_content)

        summary_content = SummaryContent(
            summary_text=summary_text,
            key_points=key_points,
            action_items=action_items,
            decisions=decisions,
            participants_mentioned=participants,
            topics_covered=topics,
            word_count=len(summary_text.split()),
            reading_time_minutes=len(summary_text.split()) / 200,  # 분당 200단어 가정
        )

        # 5. 신뢰도 점수 계산
        confidence_score = 0.8  # 기본 신뢰도
        if meeting_detection.confidence > 0.7:
            confidence_score += 0.1
        if sentiment_analysis and abs(sentiment_analysis.sentiment_score) > 0.3:
            confidence_score += 0.05

        confidence_score = min(confidence_score, 1.0)

        # 6. 대체 버전 생성 (선택적)
        alternative_versions: list[VersionedSummary] = []
        if request.generate_multiple_versions:
            # 다른 모드로 추가 버전 생성
            alternative_modes = [
                SummaryMode.EXECUTIVE,
                SummaryMode.DETAILED,
                SummaryMode.BULLET_POINTS,
            ]
            alternative_modes = [m for m in alternative_modes if m != request.summary_mode]

            for mode in alternative_modes[:2]:  # 최대 2개 추가 버전
                alt_summary = self._generate_summary_by_mode(
                    minutes_content, mode, request.length, request.focus_areas
                )

                alt_content = SummaryContent(
                    summary_text=alt_summary,
                    key_points=self._extract_key_points(alt_summary),
                    action_items=self._extract_key_points(alt_summary)
                    if FocusArea.ACTION_ITEMS in request.focus_areas
                    else [],
                    decisions=self._extract_key_points(alt_summary)
                    if FocusArea.DECISIONS_ONLY in request.focus_areas
                    else [],
                    participants_mentioned=participants,
                    topics_covered=topics,
                    word_count=len(alt_summary.split()),
                    reading_time_minutes=len(alt_summary.split()) / 200,
                )

                alternative_versions.append(
                    VersionedSummary(
                        version_number=len(alternative_versions) + 1,
                        mode=mode,
                        content=alt_content,
                        created_at=datetime.now(),
                        metadata={"original_mode": request.summary_mode.value},
                    )
                )

        # 7. 처리 시간 계산
        processing_time = asyncio.get_event_loop().time() - start_time

        return SummaryGenerationResult(
            task_id=str(uuid.uuid4()),
            summary_mode=request.summary_mode,
            length=request.length,
            meeting_detection=meeting_detection,
            summary_content=summary_content,
            sentiment_analysis=sentiment_analysis,
            confidence_score=round(confidence_score, 3),
            processing_time_seconds=round(processing_time, 2),
            alternative_versions=alternative_versions,
            metadata={
                "focus_areas": [area.value for area in request.focus_areas],
                "include_sentiment": request.include_sentiment,
                "target_audience": request.target_audience,
                "original_content_length": len(minutes_content),
            },
        )
