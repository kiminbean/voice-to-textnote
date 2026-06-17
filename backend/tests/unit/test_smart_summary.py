"""
Smart Summary Service Unit Tests
"""

import pytest
from datetime import datetime

from backend.schemas.smart_summary import (
    SummaryRequest,
    SummaryMode,
    SummaryLength,
    FocusArea,
    MeetingType,
)
from backend.services.smart_summary_service import SmartSummaryService


class TestSmartSummaryService:
    """SmartSummaryService 단위 테스트"""
    
    def setup_method(self):
        """테스트 실행 전 초기화"""
        self.service = SmartSummaryService()
    
    def test_service_initialization(self):
        """서비스 초기화 테스트"""
        assert self.service.keywords_by_meeting_type is not None
        assert MeetingType.BRAINSTORMING in self.service.keywords_by_meeting_type
        assert MeetingType.REVIEW in self.service.keywords_by_meeting_type
        assert MeetingType.PLANNING in self.service.keywords_by_meeting_type
    
    def test_detect_meeting_type_brainstorming(self):
        """브레인스토밍 회의 유형 감지 테스트"""
        content = """
        아이디어 브레인스토밍 미팅입니다.
        창의적인 생각을 나누고 새로운 아이디어를 생성하는 시간입니다.
        creative thinking idea generation brainstorm session
        """
        
        detection = self.service._detect_meeting_type(content)
        
        assert detection.detected_type == MeetingType.BRAINSTORMING
        assert detection.confidence > 0.5
        assert len(detection.reasoning) > 0
        assert len(detection.keywords) > 0
    
    def test_detect_meeting_type_review(self):
        """검토 회의 유형 감지 테스트"""
        content = """
        프로젝트 검토 미팅입니다.
        성과를 평가하고 결과를 분석합니다.
        review evaluation assessment project check
        """
        
        detection = self.service._detect_meeting_type(content)
        
        assert detection.detected_type == MeetingType.REVIEW
        assert detection.confidence > 0.5
    
    def test_detect_meeting_type_regular(self):
        """일반 회의 유형 감지 테스트"""
        content = """
        정기 회의입니다.
        주간 진행 상황을 공유합니다.
        """
        
        detection = self.service._detect_meeting_type(content)
        
        # 특정 패턴이 없으면 일반 회의로 감지
        assert detection.detected_type == MeetingType.REGULAR
        assert detection.confidence >= 0.5
    
    def test_analyze_sentiment_positive(self):
        """긍정 감정 분석 테스트"""
        content = """
        이번 프로젝트는 훌륭하게 진행되고 있습니다.
        모든 팀원이 대단히 열심히 일했습니다.
        결과가 아주 좋고 만족스럽습니다.
        excellent great amazing wonderful fantastic
        """
        
        analysis = self.service._analyze_sentiment(content)
        
        assert analysis.overall_sentiment == "positive"
        assert analysis.sentiment_score > 0.0
        assert analysis.sentiment_details["positive_words_found"] > 0
        assert len(analysis.emotional_segments) > 0
    
    def test_analyze_sentiment_negative(self):
        """부정 감정 분석 테스트"""
        content = """
        프로젝트 진행이 어려웠습니다.
        문제가 많았고 결과가 실망스러웠습니다.
        bad terrible problem difficult issue
        """
        
        analysis = self.service._analyze_sentiment(content)
        
        assert analysis.overall_sentiment == "negative"
        assert analysis.sentiment_score < 0.0
    
    def test_analyze_sentiment_neutral(self):
        """중립 감정 분석 테스트"""
        content = """
        정기 회의가 열렸습니다.
        주간 진행 상황을 공유했습니다.
        다음 주 계획을 논의했습니다.
        """
        
        analysis = self.service._analyze_sentiment(content)
        
        assert analysis.overall_sentiment == "neutral"
        assert abs(analysis.sentiment_score) <= 0.1
    
    def test_generate_executive_summary(self):
        """경영진 요약 생성 테스트"""
        content = """
        이번 분기 매출이 20% 증가했습니다. 신제품 런칭 성공과 마케팅 전략 개선이 주요 요인입니다.
        고객 만족도도 15% 향상되었습니다. 다음 분기에는 해외 시장 진출을 계획하고 있습니다.
        """
        
        request = SummaryRequest(
            summary_mode=SummaryMode.EXECUTIVE,
            length=SummaryLength.MEDIUM,
            focus_areas=[FocusArea.ALL]
        )
        
        summary = self.service._generate_summary_by_mode(
            content, request.summary_mode, request.length, request.focus_areas
        )
        
        assert len(summary) > 0
        assert "분기 매출" in summary or "증가" in summary
        assert len(summary) <= 500  # 중간 길이 제한
    
    def test_generate_detailed_summary(self):
        """상세 요약 생성 테스트"""
        content = """
        이번 분기 매출이 20% 증가했습니다. 신제품 런칭 성공과 마켅팅 전략 개선이 주요 요인입니다.
        고객 만족도도 15% 향상되었습니다. 다음 분기에는 해외 시장 진출을 계획하고 있습니다.
        """
        
        request = SummaryRequest(
            summary_mode=SummaryMode.DETAILED,
            length=SummaryLength.DETAILED,
            focus_areas=[FocusArea.ALL]
        )
        
        summary = self.service._generate_summary_by_mode(
            content, request.summary_mode, request.length, request.focus_areas
        )
        
        assert len(summary) > 0
        assert len(summary) > 200  # 상세 요약은 더 길어야 함
    
    def test_generate_bullet_points_summary(self):
        """항목별 요약 생성 테스트"""
        content = """
        이번 분기 매출이 20% 증가했습니다. 신제품 런칭 성공과 마케팅 전략 개선이 주요 요인입니다.
        고객 만족도도 15% 향상되었습니다. 다음 분기에는 해외 시장 진출을 계획하고 있습니다.
        """
        
        request = SummaryRequest(
            summary_mode=SummaryMode.BULLET_POINTS,
            length=SummaryLength.MEDIUM,
            focus_areas=[FocusArea.ALL]
        )
        
        summary = self.service._generate_summary_by_mode(
            content, request.summary_mode, request.length, request.focus_areas
        )
        
        assert len(summary) > 0
        assert "•" in summary  # 항목 기호 포함
    
    def test_generate_action_oriented_summary(self):
        """행동 중심 요약 생성 테스트"""
        content = """
        개발팀은 새로운 기능을 구현해야 합니다. QA 팀은 테스트를 진행하고 마케팅 팀은 홍보를 준비합니다.
        이 기능은 다음 달에 출시될 예정입니다.
        """
        
        request = SummaryRequest(
            summary_mode=SummaryMode.ACTION_ORIENTED,
            length=SummaryLength.MEDIUM,
            focus_areas=[FocusArea.ALL]
        )
        
        summary = self.service._generate_summary_by_mode(
            content, request.summary_mode, request.length, request.focus_areas
        )
        
        assert len(summary) > 0
        assert "개발" in summary or "구현" in summary or "테스트" in summary
    
    def test_extract_key_points(self):
        """핵심 포인트 추출 테스트"""
        content = """
        이번 프로젝트의 중요한 목표는 시장 점유율 증가입니다.
        주요 성과는 신제품 런칭과 고객 확보입니다.
        특히 중요한 점은 비용 절감과 효율성 개선입니다.
        """
        
        key_points = self.service._extract_key_points(content)
        
        assert len(key_points) > 0
        assert any("목표" in point or "성과" in point for point in key_points)
    
    def test_extract_participants(self):
        """참가자 추출 테스트"""
        content = """
        김팀장: 프로젝트 진행 상황을 설명했습니다.
        이개발자: 기적적 어려움을 공유했습니다.
        마케터: 홍보 전략을 발표했습니다.
        """
        
        participants = self.service._extract_participants(content)
        
        assert len(participants) > 0
        assert any("김팀장" in participant for participant in participants)
        assert any("이개발자" in participant for participant in participants)
    
    def test_extract_topics(self):
        """주제 추출 테스트"""
        content = """
        프로젝트 개발과 일정 관리에 대해 논의했습니다.
        기술적 문제와 예산 배분을 다루었습니다.
        품질 관리와 마케팅 전략을 논의했습니다.
        """
        
        topics = self.service._extract_topics(content)
        
        assert len(topics) > 0
        assert any("개발" in topic or "프로젝트" in topic for topic in topics)
    
    @pytest.mark.asyncio
    async def test_generate_smart_summary_integration(self):
        """스마트 요약 생성 통합 테스트"""
        content = """
        이번 분기 회의입니다. 매출이 20% 증가했습니다.
        신제품 런칭이 성공적이었습니다. 고객 만족도도 향상되었습니다.
        다음 분기에는 해외 시장 진출을 계획합니다. 개발팀은 새 기능 구현해야 합니다.
        """
        
        request = SummaryRequest(
            summary_mode=SummaryMode.EXECUTIVE,
            length=SummaryLength.MEDIUM,
            focus_areas=[FocusArea.ALL],
            include_sentiment=True
        )
        
        result = await self.service.generate_smart_summary(content, request)
        
        # 결과 객체 확인
        assert result.task_id is not None
        assert result.summary_mode == SummaryMode.EXECUTIVE
        assert result.meeting_detection.detected_type is not None
        assert result.summary_content.summary_text is not None
        assert result.summary_content.word_count > 0
        assert 0 <= result.confidence_score <= 1
        assert result.processing_time_seconds >= 0
        assert len(result.summary_content.key_points) > 0
    
    @pytest.mark.asyncio
    async def test_generate_multiple_versions(self):
        """다중 버전 요약 생성 테스트"""
        content = """
        이번 분기 회의입니다. 매출이 20% 증가했습니다.
        신제품 런칭이 성공적이었습니다. 고객 만족도도 향상되었습니다.
        """
        
        request = SummaryRequest(
            summary_mode=SummaryMode.EXECUTIVE,
            length=SummaryLength.MEDIUM,
            focus_areas=[FocusArea.ALL],
            generate_multiple_versions=True
        )
        
        result = await self.service.generate_smart_summary(content, request)
        
        # 대체 버전 확인
        assert len(result.alternative_versions) > 0
        for version in result.alternative_versions:
            assert version.version_number >= 1
            assert version.content.summary_text is not None
            assert version.created_at is not None
    
    def test_summary_request_validation(self):
        """요약 요청 유효성 검증 테스트"""
        request = SummaryRequest(
            summary_mode=SummaryMode.EXECUTIVE,
            length=SummaryLength.MEDIUM,
            focus_areas=[FocusArea.ALL, FocusArea.DECISIONS],
            include_sentiment=True,
            generate_multiple_versions=False
        )
        
        assert request.summary_mode == SummaryMode.EXECUTIVE
        assert request.length == SummaryLength.MEDIUM
        assert len(request.focus_areas) == 2
        assert FocusArea.ALL in request.focus_areas
        assert FocusArea.DECISIONS in request.focus_areas
        assert request.include_sentiment == True
        assert request.generate_multiple_versions == False
    
    def test_meeting_detection_confidence_calculation(self):
        """회의 유형 감지 신뢰도 계산 테스트"""
        # 높은 신뢰도 테스트
        content_brainstorm = """
        브레인스토밍 아이디어 creative thinking idea generation
        창의적인 해결책을 모색합니다. 새로운 컨셉을 개발합니다.
        """
        detection_high = self.service._detect_meeting_type(content_brainstorm)
        assert detection_high.confidence > 0.7
        
        # 낮은 신뢰도 테스트
        content_neutral = "정기 회의입니다. 일반적인 내용을 공유했습니다."
        detection_low = self.service._detect_meeting_type(content_neutral)
        assert detection_low.confidence <= 0.7