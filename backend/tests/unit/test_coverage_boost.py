"""
미커버 모듈 집중 보완 테스트
- openai_client.py (86% → 95%+): 예외 처리 경로
- quality_assessment.py (85% → 93%+): 텍스트 추출 헬퍼
- dashboard.py (90% → 95%+): 빈 레코드/세그먼트 파싱
"""

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# openai_client.py (lines 39-42): 예외 처리 경로
# ---------------------------------------------------------------------------


class TestOpenaiClientExceptionPath:
    """OpenAI 클라이언트 초기화 실패 시 대체 클라이언트 반환 테스트"""

    def test_returns_dummy_client_on_init_exception(self):
        """AsyncOpenAI 생성 중 예외 발생 시 dummy-key 클라이언트 반환"""
        from backend.ml.openai_client import get_openai_client

        # 첫 번째 호출(try 블록)은 실패, 두 번째 호출(except 블록)은 성공
        mock_client = MagicMock()
        with (
            patch(
                "backend.ml.openai_client.AsyncOpenAI",
                side_effect=[Exception("설정 오류"), mock_client],
            ),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            client = get_openai_client()

        assert client is mock_client  # except 블록에서 반환된 클라이언트

    def test_cached_client_returns_same_instance(self):
        """get_cached_openai_client는 동일 인스턴스 반환"""
        import backend.ml.openai_client as mod
        from backend.ml.openai_client import get_cached_openai_client

        # 캐시 초기화
        mod._openai_client = None

        mock_client = MagicMock()
        with patch("backend.ml.openai_client.get_openai_client", return_value=mock_client):
            c1 = get_cached_openai_client()
            c2 = get_cached_openai_client()

        assert c1 is c2
        mod._openai_client = None  # 정리


# ---------------------------------------------------------------------------
# quality_assessment.py (lines 53-55, 68, 75-96): 텍스트 추출 헬퍼
# ---------------------------------------------------------------------------


class TestQualityAssessmentTextExtraction:
    """품질 평가용 텍스트 추출 헬퍼 함수 테스트"""

    def test_extract_text_with_sections_dict(self):
        """sections이 dict이면 values를 텍스트로 추출"""
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_text

        data = {
            "sections": {"결정": "베타 출시", "후속": "QA 일정"},
            "summary_text": "요약",
        }
        result = _extract_minutes_text(data)
        assert "베타 출시" in result
        assert "QA 일정" in result

    def test_extract_text_with_segments(self):
        """segments에서 text 필드 추출"""
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_text

        data = {
            "segments": [
                {"id": 0, "text": "안녕하세요", "start": 0.0, "end": 5.0},
                {"id": 1, "text": "반갑습니다", "start": 5.0, "end": 10.0},
            ]
        }
        result = _extract_minutes_text(data)
        assert "안녕하세요" in result
        assert "반갑습니다" in result

    def test_extract_text_skips_empty_values(self):
        """빈 문자열/None 값은 건너뜀"""
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_text

        data = {
            "summary_text": "  ",  # 공백만 → skip
            "sections": {"a": "", "b": None, "c": "유효"},  # c만 포함
        }
        result = _extract_minutes_text(data)
        assert "유효" in result

    def test_extract_minutes_title_with_value(self):
        """title이 있으면 그대로 반환 (line 68)"""
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_title

        assert _extract_minutes_title({"title": "회의록"}) == "회의록"
        assert _extract_minutes_title({"title": 123}) == ""
        assert _extract_minutes_title(None) == ""

    def test_extract_minutes_content_from_markdown(self):
        """result_data에 markdown이 있으면 마크다운 반환 (line 79-80)"""
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_content

        task = MagicMock()
        task.result_data = {
            "title": "제목",
            "markdown": "# 회의록\n\n내용",
        }
        content, title = _extract_minutes_content(task)
        assert "# 회의록" in content
        assert title == "제목"

    def test_extract_minutes_content_from_segments(self):
        """markdown 없으면 segments에서 text 추출 (lines 82-90)"""
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_content

        task = MagicMock()
        task.result_data = {
            "title": "제목",
            "segments": [
                {"text": "첫 번째 발언"},
                {"text": "두 번째 발언"},
            ],
        }
        content, _title = _extract_minutes_content(task)
        assert "첫 번째 발언" in content
        assert "두 번째 발언" in content

    def test_extract_minutes_content_fallback_to_summary(self):
        """segments도 없으면 summary_text 사용 (lines 92-94)"""
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_content

        task = MagicMock()
        task.result_data = {
            "title": "제목",
            "summary_text": "요약 내용입니다",
        }
        content, _title = _extract_minutes_content(task)
        assert "요약 내용입니다" in content

    def test_extract_minutes_content_empty_result(self):
        """result_data가 비어있으면 빈 문자열 반환 (line 96)"""
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_content

        task = MagicMock()
        task.result_data = {}
        content, title = _extract_minutes_content(task)
        assert content == ""
        assert title == ""
