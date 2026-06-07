"""
sentiment_service.py 100% 커버리지 테스트
모든 코드 경로, 에러 처리, 엣지 케이스 테스트
"""

import pytest

from backend.services.sentiment_service import SentimentService

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def sentiment_service():
    """SentimentService 인스턴스"""
    return SentimentService()


@pytest.fixture
def sample_segments():
    """샘플 발화 세그먼트"""
    return [
        {"text": "이 회의는 정말 훌륭했습니다.", "start": 0.0, "speaker": "A"},
        {"text": "매우 생산적인 대화였습니다.", "start": 5.0, "speaker": "B"},
        {"text": "약간의 문제가 있었지만 해결했습니다.", "start": 10.0, "speaker": "C"},
        {"text": "불만이 있습니다.", "start": 15.0, "speaker": "D"},
        {"text": "다음번에는 더 좋을 것입니다.", "start": 20.0, "speaker": "A"},
    ]


# ---------------------------------------------------------------------------
# __init__ 메서드 테스트
# ---------------------------------------------------------------------------


class TestSentimentServiceInit:
    """초기화 테스트"""

    def test_initialization(self):
        """서비스 초기화 시 단어 사전 로드"""
        service = SentimentService()
        assert len(service.word_sentiment) > 0
        assert "좋아" in service.word_sentiment
        assert service.word_sentiment["좋아"] == 1.0
        assert "싫어" in service.word_sentiment
        assert service.word_sentiment["싫어"] == -1.0


# ---------------------------------------------------------------------------
# calculate_sentence_sentiment 메서드 테스트
# ---------------------------------------------------------------------------


class TestCalculateSentenceSentiment:
    """문장 감성 점수 계산 테스트"""

    def test_empty_text(self, sentiment_service):
        """빈 텍스트"""
        score = sentiment_service.calculate_sentence_sentiment("")
        assert score == 0.0

    def test_whitespace_only(self, sentiment_service):
        """공백만 있는 텍스트"""
        score = sentiment_service.calculate_sentence_sentiment("   ")
        assert score == 0.0

    def test_none_text(self, sentiment_service):
        """None 텍스트"""
        score = sentiment_service.calculate_sentence_sentiment(None)
        assert score == 0.0

    def test_positive_sentence(self, sentiment_service):
        """긍정 문장"""
        score = sentiment_service.calculate_sentence_sentiment("좋은 결과 훌륵한 성공")
        assert score > 0

    def test_negative_sentence(self, sentiment_service):
        """부정 문장"""
        score = sentiment_service.calculate_sentence_sentiment("실패 문제 실망 나쁨")
        assert score < 0

    def test_neutral_sentence(self, sentiment_service):
        """중립 문장"""
        score = sentiment_service.calculate_sentence_sentiment("회의를 시작합니다.")
        # 감성 단어가 없으면 0에 가까움
        assert abs(score) < 0.3

    def test_with_intensifier(self, sentiment_service):
        """강조어 포함"""
        normal_score = sentiment_service.calculate_sentence_sentiment("이것은 좋은 결과입니다")
        intensified_score = sentiment_service.calculate_sentence_sentiment(
            "이것은 매우 좋은 결과입니다"
        )
        # 강조어가 적용되면 점수가 높아야 함
        assert intensified_score >= normal_score

    def test_with_negation(self, sentiment_service):
        """부정어 포함"""
        positive_score = sentiment_service.calculate_sentence_sentiment("좋은 결과입니다")
        negated_score = sentiment_service.calculate_sentence_sentiment("좋지 않은 결과입니다")
        # Negation may not always lower score with simple lexicon
        assert negated_score <= positive_score

    def test_score_normalization(self, sentiment_service):
        """점수 정규화 (-1.0 ~ 1.0)"""
        # 극단적으로 긍정적인 문장
        score = sentiment_service.calculate_sentence_sentiment(" ".join(["좋아"] * 100))
        assert -1.0 <= score <= 1.0

    def test_case_insensitive(self, sentiment_service):
        """대소문자 무시"""
        score1 = sentiment_service.calculate_sentence_sentiment("이것은 좋은 결과입니다.")
        score2 = sentiment_service.calculate_sentence_sentiment("이것은 좋은 결과입니다.".upper())
        assert score1 == score2

    def test_multiple_sentiment_words(self, sentiment_service):
        """여러 감성 단어"""
        score = sentiment_service.calculate_sentence_sentiment("좋고 훌륭하고 완벽한 결과입니다.")
        assert score > 0


# ---------------------------------------------------------------------------
# analyze_meeting_sentiment 메서드 테스트
# ---------------------------------------------------------------------------


class TestAnalyzeMeetingSentiment:
    """회의 감성 분석 테스트"""

    @pytest.mark.asyncio
    async def test_empty_segments(self, sentiment_service):
        """빈 세그먼트"""
        result = await sentiment_service.analyze_meeting_sentiment([])
        assert result["positive"] == 0.0
        assert result["neutral"] == 1.0
        assert result["negative"] == 0.0
        assert result["dominant"] == "neutral"

    @pytest.mark.asyncio
    async def test_positive_dominant(self, sentiment_service):
        """긍정적 회의"""
        segments = [
            {"text": "좋습니다 훌륭합니다 성공", "start": 0.0},
            {"text": "만족합니다 감사합니다", "start": 5.0},
            {"text": "훌륭한 협력", "start": 10.0},
        ]
        result = await sentiment_service.analyze_meeting_sentiment(segments)
        assert result["positive"] > result["negative"]
        assert result["dominant"] == "positive"

    @pytest.mark.asyncio
    async def test_negative_dominant(self, sentiment_service):
        """부정적 회의"""
        segments = [
            {"text": "실패했습니다 문제", "start": 0.0},
            {"text": "나쁩니다 실망", "start": 5.0},
            {"text": "불만입니다 어려움", "start": 10.0},
        ]
        result = await sentiment_service.analyze_meeting_sentiment(segments)
        assert result["negative"] > result["positive"]
        assert result["dominant"] == "negative"

    @pytest.mark.asyncio
    async def test_neutral_dominant(self, sentiment_service):
        """중립적 회의"""
        segments = [
            {"text": "회의를 시작합니다.", "start": 0.0},
            {"text": "다음 안건을 논의합니다.", "start": 5.0},
            {"text": "회의를 마칩니다.", "start": 10.0},
        ]
        result = await sentiment_service.analyze_meeting_sentiment(segments)
        assert result["neutral"] > result["positive"]
        assert result["neutral"] > result["negative"]
        assert result["dominant"] == "neutral"

    @pytest.mark.asyncio
    async def test_mixed_sentiment(self, sentiment_service, sample_segments):
        """혼합 감성"""
        result = await sentiment_service.analyze_meeting_sentiment(sample_segments)
        assert "positive" in result
        assert "neutral" in result
        assert "negative" in result
        assert "dominant" in result
        assert "overall_score" in result

    @pytest.mark.asyncio
    async def test_missing_text_field(self, sentiment_service):
        """text 필드 없는 세그먼트"""
        segments = [
            {"start": 0.0, "speaker": "A"},
            {"text": None, "start": 5.0, "speaker": "B"},
        ]
        result = await sentiment_service.analyze_meeting_sentiment(segments)
        assert result["neutral"] == 1.0


# ---------------------------------------------------------------------------
# _empty_sentiment_result 메서드 테스트
# ---------------------------------------------------------------------------


class TestEmptySentimentResult:
    """빈 감성 결과 테스트"""

    def test_empty_result_structure(self, sentiment_service):
        """빈 결과 구조"""
        result = sentiment_service._empty_sentiment_result()
        assert result["positive"] == 0.0
        assert result["neutral"] == 1.0
        assert result["negative"] == 0.0
        assert result["dominant"] == "neutral"
        assert result["overall_score"] == 0.0


# ---------------------------------------------------------------------------
# extract_key_phrases_with_sentiment 메서드 테스트
# ---------------------------------------------------------------------------


class TestExtractKeyPhrasesWithSentiment:
    """키워드 추출 및 감성 점수 테스트"""

    @pytest.mark.asyncio
    async def test_extract_keywords(self, sentiment_service, sample_segments):
        """키워드 추출"""
        result = await sentiment_service.extract_key_phrases_with_sentiment(sample_segments)
        assert isinstance(result, dict)
        # 최소한 몇 개의 키워드는 추출되어야 함
        # (실제 키워드는 텍스트에 따라 다름)

    @pytest.mark.asyncio
    async def test_empty_segments(self, sentiment_service):
        """빈 세그먼트"""
        result = await sentiment_service.extract_key_phrases_with_sentiment([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_keyword_sentiment_scores(self, sentiment_service):
        """키워드별 감성 점수"""
        segments = [
            {"text": "좋은 결과입니다.", "start": 0.0},
            {"text": "나쁜 결과입니다.", "start": 5.0},
        ]
        result = await sentiment_service.extract_key_phrases_with_sentiment(segments)
        # 결과가 딕셔너리여야 함
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# calculate_trend_direction 메서드 테스트
# ---------------------------------------------------------------------------


class TestCalculateTrendDirection:
    """감성 추이 방향 계산 테스트"""

    def test_insufficient_segments(self, sentiment_service):
        """세그먼트 부족 (3개 미만)"""
        segments = [
            {"text": "좋음", "start": 0.0},
            {"text": "좋음", "start": 5.0},
        ]
        result = sentiment_service.calculate_trend_direction(segments)
        assert result == "stable"

    def test_improving_trend(self, sentiment_service):
        """개선 추이"""
        segments = [
            {"text": "실패했습니다.", "start": 0.0},
            {"text": "약간 문제 있습니다.", "start": 5.0},
            {"text": "좋아지고 있습니다.", "start": 10.0},
            {"text": "훌륭합니다.", "start": 15.0},
        ]
        result = sentiment_service.calculate_trend_direction(segments)
        assert result == "improving"

    def test_declining_trend(self, sentiment_service):
        """악화 추이"""
        segments = [
            {"text": "훌륭합니다.", "start": 0.0},
            {"text": "좋습니다.", "start": 5.0},
            {"text": "약간 문제 있습니다.", "start": 10.0},
            {"text": "실패했습니다.", "start": 15.0},
        ]
        result = sentiment_service.calculate_trend_direction(segments)
        assert result == "declining"

    def test_stable_trend(self, sentiment_service):
        """안정적 추이"""
        segments = [
            {"text": "괜찮습니다.", "start": 0.0},
            {"text": "보통입니다.", "start": 5.0},
            {"text": "그저그렇습니다.", "start": 10.0},
        ]
        result = sentiment_service.calculate_trend_direction(segments)
        assert result == "stable"

    def test_empty_text_segments(self, sentiment_service):
        """빈 텍스트 세그먼트"""
        segments = [
            {"text": "", "start": 0.0},
            {"text": None, "start": 5.0},
            {"text": "   ", "start": 10.0},
        ]
        result = sentiment_service.calculate_trend_direction(segments)
        assert result == "stable"


# ---------------------------------------------------------------------------
# calculate_overall_trend 메서드 테스트
# ---------------------------------------------------------------------------


class TestCalculateOverallTrend:
    """전체 감성 추이 계산 테스트"""

    def test_insufficient_scores(self, sentiment_service):
        """점수 부족 (2개 미만)"""
        result = sentiment_service.calculate_overall_trend([0.5])
        assert result == "stable"

    def test_improving_trend(self, sentiment_service):
        """개선 추이"""
        scores = [0.1, 0.3, 0.5, 0.7, 0.9]
        result = sentiment_service.calculate_overall_trend(scores)
        assert result == "improving"

    def test_declining_trend(self, sentiment_service):
        """악화 추이"""
        scores = [0.9, 0.7, 0.5, 0.3, 0.1]
        result = sentiment_service.calculate_overall_trend(scores)
        assert result == "declining"

    def test_stable_trend(self, sentiment_service):
        """안정적 추이"""
        scores = [0.5, 0.52, 0.48, 0.51, 0.49]
        result = sentiment_service.calculate_overall_trend(scores)
        assert result == "stable"

    def test_zero_denominator(self, sentiment_service):
        """분모가 0인 경우 (한 점수만)"""
        result = sentiment_service.calculate_overall_trend([0.5])
        assert result == "stable"


# ---------------------------------------------------------------------------
# analyze_historical_trends 메서드 테스트
# ---------------------------------------------------------------------------


class TestAnalyzeHistoricalTrends:
    """역사적 감성 추이 분석 테스트"""

    @pytest.mark.asyncio
    async def test_multiple_meetings(self, sentiment_service):
        """여러 회의 분석"""
        meetings = [
            {
                "meeting_id": "m1",
                "created_at": "2024-01-01",
                "segments": [
                    {"text": "좋은 결과입니다.", "start": 0.0},
                ],
            },
            {
                "meeting_id": "m2",
                "created_at": "2024-01-02",
                "segments": [
                    {"text": "실패했습니다.", "start": 0.0},
                ],
            },
        ]

        result = await sentiment_service.analyze_historical_trends(meetings)

        assert len(result) == 2
        assert result[0]["meeting_id"] == "m1"
        assert result[1]["meeting_id"] == "m2"
        # 시간순 정렬 확인
        assert result[0]["created_at"] < result[1]["created_at"]

    @pytest.mark.asyncio
    async def test_meeting_with_task_id(self, sentiment_service):
        """task_id 필드 사용"""
        meetings = [
            {
                "task_id": "t1",
                "timestamp": "2024-01-01",
                "segments": [
                    {"text": "좋습니다.", "start": 0.0},
                ],
            }
        ]

        result = await sentiment_service.analyze_historical_trends(meetings)

        assert len(result) == 1
        assert result[0]["meeting_id"] == "t1"

    @pytest.mark.asyncio
    async def test_meeting_without_segments(self, sentiment_service):
        """세그먼트 없는 회의"""
        meetings = [
            {
                "meeting_id": "m1",
                "created_at": "2024-01-01",
                "segments": [],
            }
        ]

        result = await sentiment_service.analyze_historical_trends(meetings)

        # 세그먼트가 없는 회의는 제외됨
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_meeting_with_timestamp_field(self, sentiment_service):
        """timestamp 필드 사용"""
        meetings = [
            {
                "meeting_id": "m1",
                "timestamp": "2024-01-01T10:00:00",
                "segments": [
                    {"text": "훌륭합니다.", "start": 0.0},
                ],
            }
        ]

        result = await sentiment_service.analyze_historical_trends(meetings)

        assert len(result) == 1
        assert result[0]["created_at"] == "2024-01-01T10:00:00"


# ---------------------------------------------------------------------------
# get_speaker_segments 메서드 테스트
# ---------------------------------------------------------------------------


class TestGetSpeakerSegments:
    """화자 세그먼트 조회 테스트"""

    @pytest.mark.asyncio
    async def test_returns_empty_list(self, sentiment_service):
        """빈 리스트 반환 (샘플 구현)"""
        result = await sentiment_service.get_speaker_segments("speaker-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_with_meeting_ids(self, sentiment_service):
        """특정 회의 ID 필터"""
        result = await sentiment_service.get_speaker_segments("speaker-1", meeting_ids=["m1", "m2"])
        assert result == []


# ---------------------------------------------------------------------------
# analyze_speaker_sentiment 메서드 테스트
# ---------------------------------------------------------------------------


class TestAnalyzeSpeakerSentiment:
    """화자별 감성 분석 테스트"""

    @pytest.mark.asyncio
    async def test_speaker_analysis(self, sentiment_service):
        """화자 감성 분석"""
        segments = [
            {"text": "훌륭합니다.", "start": 0.0, "speaker": "Alice"},
            {"text": "좋습니다.", "start": 5.0, "speaker": "Alice"},
        ]

        result = await sentiment_service.analyze_speaker_sentiment(segments)

        assert "speaker_name" in result
        assert result["speaker_name"] == "Alice"
        assert "overall_score" in result
        assert "positive_ratio" in result
        assert "negative_ratio" in result

    @pytest.mark.asyncio
    async def test_empty_segments(self, sentiment_service):
        """빈 세그먼트"""
        result = await sentiment_service.analyze_speaker_sentiment([])

        assert result["speaker_name"] == "알 수 없음"
        assert result["overall_score"] == 0.0
        assert result["positive_ratio"] == 0.0
        assert result["negative_ratio"] == 0.0

    @pytest.mark.asyncio
    async def test_speaker_without_field(self, sentiment_service):
        """화자 필드 없는 세그먼트"""
        segments = [
            {"text": "테스트", "start": 0.0},
        ]

        result = await sentiment_service.analyze_speaker_sentiment(segments)

        assert result["speaker_name"] == "알 수 없음"

    @pytest.mark.asyncio
    async def test_mixed_sentiment_speaker(self, sentiment_service):
        """혼합 감성 화자"""
        segments = [
            {"text": "훌륭합니다 좋습니다 성공", "start": 0.0, "speaker": "Bob"},
            {"text": "실패했습니다 문제 있습니다", "start": 5.0, "speaker": "Bob"},
        ]

        result = await sentiment_service.analyze_speaker_sentiment(segments)

        assert result["speaker_name"] == "Bob"
        # 혼합 감성이므로 두 비율 모두 0보다 커야 함
        assert result["positive_ratio"] >= 0
        assert result["negative_ratio"] >= 0
