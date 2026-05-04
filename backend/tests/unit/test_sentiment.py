"""
감정 분석기 유닛 테스트
SPEC-SENTIMENT-001: SentimentAnalyzer, 스키마, Celery 태스크
"""

import json

import pytest

from backend.pipeline.sentiment_analyzer import SentimentAnalyzer
from backend.schemas.sentiment import (
    SentimentCreateRequest,
    SentimentResponse,
    SentimentResult,
    SentimentSegment,
    SentimentStatusResponse,
    SpeakerSentiment,
)


# ── Fixtures ──

@pytest.fixture
def sample_segments():
    return [
        {"start": 0.0, "end": 5.0, "speaker_name": "김대리", "text": "안녕하세요, 오늘 회의 시작하겠습니다."},
        {"start": 5.0, "end": 12.0, "speaker_name": "이과장", "text": "네, 이번 프로젝트 진행 상황 공유드리겠습니다."},
        {"start": 12.0, "end": 20.0, "speaker_name": "박부장", "text": "일정이 계속 지연되고 있는데, 이게 어떻게 된 건가요?"},
        {"start": 20.0, "end": 28.0, "speaker_name": "김대리", "text": "죄송합니다. 리소스 부족 문제가 있었습니다."},
        {"start": 28.0, "end": 35.0, "speaker_name": "이과장", "text": "하지만 이번 주까지는 완료할 수 있습니다! 긍정적으로 봐주세요."},
    ]


@pytest.fixture
def sample_speaker_stats():
    return [
        {"speaker_name": "김대리", "speaking_ratio": 30.0, "total_speaking_time": 13.0},
        {"speaker_name": "이과장", "speaking_ratio": 35.0, "total_speaking_time": 15.0},
        {"speaker_name": "박부장", "speaking_ratio": 35.0, "total_speaking_time": 15.0},
    ]


@pytest.fixture
def analyzer():
    return SentimentAnalyzer()


# ── Prompt Building ──

class TestBuildPrompt:
    def test_contains_dialogue(self, analyzer, sample_segments, sample_speaker_stats):
        prompt = analyzer.build_prompt(sample_segments, sample_speaker_stats)
        assert "김대리" in prompt
        assert "안녕하세요" in prompt
        assert "박부장" in prompt

    def test_contains_speaker_stats(self, analyzer, sample_segments, sample_speaker_stats):
        prompt = analyzer.build_prompt(sample_segments, sample_speaker_stats)
        assert "30.0%" in prompt

    def test_empty_inputs(self, analyzer):
        prompt = analyzer.build_prompt([], [])
        assert "대화 내용 없음" in prompt
        assert "화자 정보 없음" in prompt


# ── Response Parsing ──

class TestParseResponse:
    def test_valid_json_response(self, analyzer):
        response = json.dumps({
            "overall_sentiment": "neutral",
            "overall_emotion": "neutral",
            "segments": [
                {
                    "start": 0.0, "end": 5.0,
                    "speaker": "김대리", "text": "안녕하세요",
                    "sentiment": "positive", "emotion": "joy", "confidence": 0.9,
                },
                {
                    "start": 12.0, "end": 20.0,
                    "speaker": "박부장", "text": "일정 지연 어떻게 된 건가요?",
                    "sentiment": "negative", "emotion": "frustration", "confidence": 0.8,
                },
            ],
        })

        result = analyzer.parse_response(response)
        assert isinstance(result, SentimentResult)
        assert result.overall_sentiment == "neutral"
        assert len(result.segments) == 2
        assert result.segments[0].sentiment == "positive"
        assert result.segments[1].emotion == "frustration"
        assert len(result.speakers) == 2
        assert len(result.emotional_timeline) == 2

    def test_markdown_wrapped_response(self, analyzer):
        inner = json.dumps({
            "overall_sentiment": "positive",
            "overall_emotion": "joy",
            "segments": [],
        })
        response = f"```json\n{inner}\n```"
        result = analyzer.parse_response(response)
        assert result.overall_sentiment == "positive"

    def test_invalid_json_returns_empty_result(self, analyzer):
        result = analyzer.parse_response("이것은 JSON이 아닙니다")
        assert isinstance(result, SentimentResult)
        assert result.overall_sentiment == "neutral"
        assert len(result.segments) == 0

    def test_invalid_sentiment_normalized(self, analyzer):
        response = json.dumps({
            "overall_sentiment": "mixed",
            "overall_emotion": "happy",
            "segments": [
                {"start": 0, "end": 5, "speaker": "A", "text": "hi",
                 "sentiment": "very_positive", "emotion": "joy", "confidence": 0.9},
            ],
        })
        result = analyzer.parse_response(response)
        assert result.segments[0].sentiment == "neutral"  # invalid → neutral

    def test_confidence_clamped(self, analyzer):
        response = json.dumps({
            "overall_sentiment": "neutral",
            "overall_emotion": "neutral",
            "segments": [
                {"start": 0, "end": 5, "speaker": "A", "text": "hi",
                 "sentiment": "positive", "emotion": "joy", "confidence": 1.5},
            ],
        })
        result = analyzer.parse_response(response)
        assert result.segments[0].confidence == 1.0


# ── Speaker Stats Computation ──

class TestSpeakerStats:
    def test_correct_ratios(self, analyzer):
        segments = [
            SentimentSegment(start=0, end=5, speaker="A", sentiment="positive", emotion="joy", confidence=0.9),
            SentimentSegment(start=5, end=10, speaker="A", sentiment="positive", emotion="interest", confidence=0.8),
            SentimentSegment(start=10, end=15, speaker="A", sentiment="neutral", emotion="neutral", confidence=0.7),
            SentimentSegment(start=15, end=20, speaker="A", sentiment="negative", emotion="frustration", confidence=0.9),
        ]
        speakers = analyzer._compute_speaker_stats(segments)
        assert len(speakers) == 1
        assert speakers[0].speaker == "A"
        assert speakers[0].total_segments == 4
        assert speakers[0].positive_ratio == 0.5
        assert speakers[0].neutral_ratio == 0.25
        assert speakers[0].negative_ratio == 0.25
        assert speakers[0].dominant_emotion == "joy"  # joy and interest both count, joy first

    def test_multiple_speakers(self, analyzer):
        segments = [
            SentimentSegment(start=0, end=5, speaker="A", sentiment="positive", emotion="joy", confidence=0.9),
            SentimentSegment(start=5, end=10, speaker="B", sentiment="negative", emotion="anger", confidence=0.8),
        ]
        speakers = analyzer._compute_speaker_stats(segments)
        assert len(speakers) == 2

    def test_empty_segments(self, analyzer):
        speakers = analyzer._compute_speaker_stats([])
        assert len(speakers) == 0


# ── Schemas ──

class TestSchemas:
    def test_sentiment_segment_defaults(self):
        seg = SentimentSegment(start=0.0, end=5.0, speaker="테스트")
        assert seg.sentiment == "neutral"
        assert seg.emotion == "neutral"
        assert seg.confidence == 0.0

    def test_speaker_sentiment(self):
        sp = SpeakerSentiment(speaker="A", total_segments=5)
        assert sp.positive_ratio == 0.0
        assert sp.dominant_emotion == "neutral"

    def test_create_request(self):
        req = SentimentCreateRequest(minutes_task_id="abc-123")
        assert req.max_tokens == 4096

    def test_response_model(self):
        resp = SentimentResponse(task_id="t1", status="completed")
        assert resp.overall_sentiment == "neutral"
        assert resp.segments == []

    def test_status_response(self):
        sr = SentimentStatusResponse(task_id="t1", status="processing", progress=0.5)
        assert sr.message is None


# ── Integration: Prompt → Parse roundtrip ──

class TestIntegration:
    def test_prompt_produces_valid_structure(self, analyzer, sample_segments, sample_speaker_stats):
        """프롬프트가 모든 화자와 대화를 포함하는지 확인"""
        prompt = analyzer.build_prompt(sample_segments, sample_speaker_stats)

        # 모든 화자 포함
        for stat in sample_speaker_stats:
            assert stat["speaker_name"] in prompt

        # 모든 대화 포함
        for seg in sample_segments:
            assert seg["text"] in prompt

        # JSON 형식 지시 포함
        assert "segments" in prompt
        assert "sentiment" in prompt
        assert "emotion" in prompt
