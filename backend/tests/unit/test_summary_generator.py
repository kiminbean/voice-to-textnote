"""
SummaryGenerator 단위 테스트 (RED phase)
REQ-SUM-001: 프롬프트 빌드
REQ-SUM-002: Claude 응답 파싱 (구조화 결과)
REQ-SUM-003: API 실패 시 예외 발생
REQ-SUM-004: 유효하지 않은 JSON → raw text로 graceful 처리
목표: 100% 커버리지
"""

import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 테스트용 mock 데이터
# ---------------------------------------------------------------------------

MOCK_MINUTES_SEGMENTS = [
    {
        "speaker_id": "SPEAKER_00",
        "speaker_name": "Speaker 1",
        "text": "오늘 회의 시작하겠습니다.",
        "start": 0.0,
        "end": 5.0,
    },
    {
        "speaker_id": "SPEAKER_01",
        "speaker_name": "Speaker 2",
        "text": "네, 안건 1번부터 논의하죠.",
        "start": 5.0,
        "end": 10.0,
    },
]

MOCK_SPEAKER_STATS = [
    {
        "speaker_id": "SPEAKER_00",
        "speaker_name": "Speaker 1",
        "total_speaking_time": 5.0,
        "segment_count": 1,
        "speaking_ratio": 50.0,
    },
    {
        "speaker_id": "SPEAKER_01",
        "speaker_name": "Speaker 2",
        "total_speaking_time": 5.0,
        "segment_count": 1,
        "speaking_ratio": 50.0,
    },
]

# 정상적인 Claude API 응답 (JSON)
VALID_CLAUDE_RESPONSE_JSON = json.dumps(
    {
        "summary_text": "오늘 회의에서는 안건 1번을 논의했습니다.",
        "action_items": [
            {
                "assignee": "Speaker 1",
                "task": "보고서 작성",
                "deadline": "2025-01-15",
                "priority": "high",
            }
        ],
        "key_decisions": ["안건 1번 승인"],
        "next_steps": ["다음 주 후속 미팅"],
    }
)

# 유효하지 않은 JSON Claude 응답
INVALID_JSON_RESPONSE = "안녕하세요. 이것은 회의 요약입니다. {잘못된 JSON"


def _make_mock_claude_response(text: str) -> MagicMock:
    """OpenAI API 응답 mock 생성 (chat.completions.create 반환값 형식)"""
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = text
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    return mock_response


def _patch_openai():
    """OpenAI 클라이언트 패처 반환"""
    return patch("backend.pipeline.summary_generator.OpenAI")


# ---------------------------------------------------------------------------
# build_prompt 테스트 (REQ-SUM-001)
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """SummaryGenerator.build_prompt() 메서드 테스트"""

    def test_build_prompt_returns_string(self):
        """build_prompt()는 문자열을 반환해야 함"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        prompt = generator.build_prompt(MOCK_MINUTES_SEGMENTS, MOCK_SPEAKER_STATS)
        assert isinstance(prompt, str)

    def test_build_prompt_contains_speaker_text(self):
        """프롬프트에 화자 발화 내용 포함"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        prompt = generator.build_prompt(MOCK_MINUTES_SEGMENTS, MOCK_SPEAKER_STATS)
        assert "오늘 회의 시작하겠습니다" in prompt

    def test_build_prompt_contains_speaker_names(self):
        """프롬프트에 화자 이름 포함"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        prompt = generator.build_prompt(MOCK_MINUTES_SEGMENTS, MOCK_SPEAKER_STATS)
        assert "Speaker 1" in prompt

    def test_build_prompt_contains_json_format_instruction(self):
        """프롬프트에 JSON 응답 형식 지시문 포함 (HARD rule)"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        prompt = generator.build_prompt(MOCK_MINUTES_SEGMENTS, MOCK_SPEAKER_STATS)
        # SPEC 요구사항: JSON 형식으로 응답하라는 지시문 포함
        assert "summary_text" in prompt
        assert "action_items" in prompt
        assert "key_decisions" in prompt
        assert "next_steps" in prompt

    def test_build_prompt_empty_segments(self):
        """빈 segments로도 프롬프트 생성 가능"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        prompt = generator.build_prompt([], [])
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_prompt_includes_speaker_stats(self):
        """프롬프트에 화자 통계 포함"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        prompt = generator.build_prompt(MOCK_MINUTES_SEGMENTS, MOCK_SPEAKER_STATS)
        # 발화 비율이나 시간 정보가 포함되어야 함
        assert "50" in prompt or "speaking" in prompt.lower() or "발화" in prompt


# ---------------------------------------------------------------------------
# parse_response 테스트 (REQ-SUM-002, REQ-SUM-004)
# ---------------------------------------------------------------------------


class TestParseResponse:
    """SummaryGenerator.parse_response() 메서드 테스트"""

    def test_parse_valid_json_returns_structured_result(self):
        """유효한 JSON 응답 → 구조화된 SummaryResult 반환"""
        from backend.pipeline.summary_generator import SummaryGenerator
        from backend.schemas.summary import SummaryResult

        generator = SummaryGenerator()
        result = generator.parse_response(VALID_CLAUDE_RESPONSE_JSON)
        assert isinstance(result, SummaryResult)

    def test_parse_valid_json_summary_text(self):
        """유효한 JSON → summary_text 올바르게 파싱"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        result = generator.parse_response(VALID_CLAUDE_RESPONSE_JSON)
        assert result.summary_text == "오늘 회의에서는 안건 1번을 논의했습니다."

    def test_parse_valid_json_action_items(self):
        """유효한 JSON → action_items 올바르게 파싱"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        result = generator.parse_response(VALID_CLAUDE_RESPONSE_JSON)
        assert len(result.action_items) == 1
        assert result.action_items[0].task == "보고서 작성"
        assert result.action_items[0].assignee == "Speaker 1"

    def test_parse_valid_json_key_decisions(self):
        """유효한 JSON → key_decisions 올바르게 파싱"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        result = generator.parse_response(VALID_CLAUDE_RESPONSE_JSON)
        assert result.key_decisions == ["안건 1번 승인"]

    def test_parse_valid_json_next_steps(self):
        """유효한 JSON → next_steps 올바르게 파싱"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        result = generator.parse_response(VALID_CLAUDE_RESPONSE_JSON)
        assert result.next_steps == ["다음 주 후속 미팅"]

    def test_parse_invalid_json_returns_raw_text(self):
        """유효하지 않은 JSON → summary_text에 raw text 저장, 빈 리스트 (REQ-SUM-004)"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        result = generator.parse_response(INVALID_JSON_RESPONSE)
        # raw text를 summary_text에 저장
        assert result.summary_text == INVALID_JSON_RESPONSE
        # 나머지는 빈 리스트
        assert result.action_items == []
        assert result.key_decisions == []
        assert result.next_steps == []

    def test_parse_invalid_json_no_exception(self):
        """유효하지 않은 JSON → 예외 없음 (REQ-SUM-004: NO error)"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        # 예외가 발생하면 안 됨
        try:
            result = generator.parse_response(INVALID_JSON_RESPONSE)
            assert result is not None
        except Exception as e:
            pytest.fail(f"parse_response()가 예외를 발생시켰음: {e}")

    def test_parse_json_with_missing_fields_uses_defaults(self):
        """JSON에 일부 필드 누락 → 기본값 사용"""
        from backend.pipeline.summary_generator import SummaryGenerator

        # action_items, key_decisions, next_steps 없는 JSON
        partial_json = json.dumps({"summary_text": "짧은 요약"})
        generator = SummaryGenerator()
        result = generator.parse_response(partial_json)
        assert result.summary_text == "짧은 요약"
        assert result.action_items == []
        assert result.key_decisions == []
        assert result.next_steps == []


# ---------------------------------------------------------------------------
# generate_summary 테스트 (REQ-SUM-003)
# ---------------------------------------------------------------------------


class TestGenerateSummary:
    """SummaryGenerator.generate_summary() 메서드 테스트"""

    def test_generate_summary_returns_summary_result(self):
        """정상 API 호출 → SummaryResult 반환"""
        from backend.pipeline.summary_generator import SummaryGenerator
        from backend.schemas.summary import SummaryResult

        mock_response = _make_mock_claude_response(VALID_CLAUDE_RESPONSE_JSON)

        with patch("backend.pipeline.summary_generator.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_cls.return_value = mock_client

            generator = SummaryGenerator()
            result = generator.generate_summary(
                segments=MOCK_MINUTES_SEGMENTS,
                speaker_stats=MOCK_SPEAKER_STATS,
                api_key="test-api-key",
                model="gpt-4o-mini",
                max_tokens=2000,
            )

        assert isinstance(result, SummaryResult)

    def test_generate_summary_calls_claude_api(self):
        """generate_summary() → OpenAI API 호출 확인"""
        from backend.pipeline.summary_generator import SummaryGenerator

        mock_response = _make_mock_claude_response(VALID_CLAUDE_RESPONSE_JSON)

        with patch("backend.pipeline.summary_generator.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_cls.return_value = mock_client

            generator = SummaryGenerator()
            generator.generate_summary(
                segments=MOCK_MINUTES_SEGMENTS,
                speaker_stats=MOCK_SPEAKER_STATS,
                api_key="test-api-key",
                model="gpt-4o-mini",
                max_tokens=2000,
            )

        mock_client.chat.completions.create.assert_called_once()

    def test_generate_summary_passes_api_key_to_client(self):
        """api_key를 OpenAI 클라이언트에 직접 전달"""
        from backend.pipeline.summary_generator import SummaryGenerator

        mock_response = _make_mock_claude_response(VALID_CLAUDE_RESPONSE_JSON)

        with patch("backend.pipeline.summary_generator.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_cls.return_value = mock_client

            generator = SummaryGenerator()
            generator.generate_summary(
                segments=MOCK_MINUTES_SEGMENTS,
                speaker_stats=MOCK_SPEAKER_STATS,
                api_key="my-secret-key",
                model="gpt-4o-mini",
                max_tokens=2000,
            )

        # api_key가 OpenAI() 생성자에 전달되어야 함
        mock_cls.assert_called_once_with(api_key="my-secret-key")

    def test_generate_summary_api_error_raises_exception(self):
        """API 오류(네트워크/타임아웃) → 예외 발생 (REQ-SUM-003)"""
        from backend.pipeline.summary_generator import SummaryGenerator

        with patch("backend.pipeline.summary_generator.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("API 연결 실패")
            mock_cls.return_value = mock_client

            generator = SummaryGenerator()
            with pytest.raises(Exception, match="API 연결 실패"):
                generator.generate_summary(
                    segments=MOCK_MINUTES_SEGMENTS,
                    speaker_stats=MOCK_SPEAKER_STATS,
                    api_key="test-key",
                    model="gpt-4o-mini",
                    max_tokens=2000,
                )

    def test_generate_summary_invalid_json_response_no_error(self):
        """API가 유효하지 않은 JSON 반환 → 예외 없음 (REQ-SUM-004)"""
        from backend.pipeline.summary_generator import SummaryGenerator
        from backend.schemas.summary import SummaryResult

        mock_response = _make_mock_claude_response(INVALID_JSON_RESPONSE)

        with patch("backend.pipeline.summary_generator.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_cls.return_value = mock_client

            generator = SummaryGenerator()
            result = generator.generate_summary(
                segments=MOCK_MINUTES_SEGMENTS,
                speaker_stats=MOCK_SPEAKER_STATS,
                api_key="test-key",
                model="gpt-4o-mini",
                max_tokens=2000,
            )

        assert isinstance(result, SummaryResult)
        # raw text가 summary_text에 저장됨 (REQ-SUM-004)
        assert result.summary_text == INVALID_JSON_RESPONSE
        assert result.action_items == []

    def test_generate_summary_empty_segments(self):
        """빈 segments → 정상 처리"""
        from backend.pipeline.summary_generator import SummaryGenerator

        empty_response = json.dumps(
            {"summary_text": "빈 회의", "action_items": [], "key_decisions": [], "next_steps": []}
        )
        mock_response = _make_mock_claude_response(empty_response)

        with patch("backend.pipeline.summary_generator.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_cls.return_value = mock_client

            generator = SummaryGenerator()
            result = generator.generate_summary(
                segments=[],
                speaker_stats=[],
                api_key="test-key",
                model="gpt-4o-mini",
                max_tokens=2000,
            )

        assert result.summary_text == "빈 회의"


# ---------------------------------------------------------------------------
# REQ-TMPL-004: template_structure 기반 프롬프트 생성 테스트
# ---------------------------------------------------------------------------

# 샘플 양식 구조
SAMPLE_TEMPLATE_STRUCTURE = {
    "sections": [
        {"title": "회의 개요", "level": 1},
        {"title": "주요 안건", "level": 2},
        {"title": "결정 사항", "level": 2},
        {"title": "다음 단계", "level": 2},
    ],
    "fields": {},
    "has_table": False,
    "raw_text_preview": "회의록 양식 미리보기",
}


class TestBuildPromptWithTemplateStructure:
    """template_structure 파라미터가 있는 build_prompt() 테스트 (REQ-TMPL-004)"""

    def test_build_prompt_accepts_template_structure_param(self):
        """build_prompt()가 template_structure 파라미터를 수락해야 함"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        # template_structure=None이면 기존 동작 유지
        prompt = generator.build_prompt(
            MOCK_MINUTES_SEGMENTS,
            MOCK_SPEAKER_STATS,
            template_structure=None,
        )
        assert isinstance(prompt, str)

    def test_build_prompt_with_template_structure_returns_string(self):
        """template_structure 있을 때도 문자열 반환"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        prompt = generator.build_prompt(
            MOCK_MINUTES_SEGMENTS,
            MOCK_SPEAKER_STATS,
            template_structure=SAMPLE_TEMPLATE_STRUCTURE,
        )
        assert isinstance(prompt, str)

    def test_build_prompt_with_template_includes_section_titles(self):
        """template_structure 있을 때 섹션 제목이 프롬프트에 포함되어야 함"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        prompt = generator.build_prompt(
            MOCK_MINUTES_SEGMENTS,
            MOCK_SPEAKER_STATS,
            template_structure=SAMPLE_TEMPLATE_STRUCTURE,
        )
        # 양식 섹션 제목이 포함되어야 함
        assert "회의 개요" in prompt or "주요 안건" in prompt or "결정 사항" in prompt

    def test_build_prompt_without_template_has_default_items(self):
        """template_structure 없을 때 기본 4개 항목 포함 (하위 호환성)"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        prompt = generator.build_prompt(MOCK_MINUTES_SEGMENTS, MOCK_SPEAKER_STATS)
        assert "summary_text" in prompt
        assert "action_items" in prompt
        assert "key_decisions" in prompt
        assert "next_steps" in prompt

    def test_build_prompt_with_template_has_json_instruction(self):
        """template_structure 있을 때도 JSON 응답 지시 포함"""
        from backend.pipeline.summary_generator import SummaryGenerator

        generator = SummaryGenerator()
        prompt = generator.build_prompt(
            MOCK_MINUTES_SEGMENTS,
            MOCK_SPEAKER_STATS,
            template_structure=SAMPLE_TEMPLATE_STRUCTURE,
        )
        # JSON 응답을 요청해야 함
        assert "json" in prompt.lower() or "JSON" in prompt

    def test_build_prompt_default_template_structure_is_none(self):
        """template_structure 기본값은 None (하위 호환성)"""
        import inspect

        from backend.pipeline.summary_generator import SummaryGenerator

        sig = inspect.signature(SummaryGenerator.build_prompt)
        params = sig.parameters
        assert "template_structure" in params
        assert params["template_structure"].default is None


class TestGenerateSummaryWithTemplateStructure:
    """template_structure 파라미터가 있는 generate_summary() 테스트 (REQ-TMPL-004)"""

    def test_generate_summary_accepts_template_structure(self):
        """generate_summary()가 template_structure 파라미터를 수락해야 함"""
        from backend.pipeline.summary_generator import SummaryGenerator
        from backend.schemas.summary import SummaryResult

        with patch("backend.pipeline.summary_generator.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = VALID_CLAUDE_RESPONSE_JSON
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice],
                usage=MagicMock(prompt_tokens=100, completion_tokens=50),
            )
            mock_cls.return_value = mock_client

            generator = SummaryGenerator()
            result = generator.generate_summary(
                segments=MOCK_MINUTES_SEGMENTS,
                speaker_stats=MOCK_SPEAKER_STATS,
                api_key="test-key",
                model="gpt-4o-mini",
                max_tokens=2000,
                template_structure=SAMPLE_TEMPLATE_STRUCTURE,
            )

        assert isinstance(result, SummaryResult)

    def test_generate_summary_default_template_structure_is_none(self):
        """generate_summary()의 template_structure 기본값은 None"""
        import inspect

        from backend.pipeline.summary_generator import SummaryGenerator

        sig = inspect.signature(SummaryGenerator.generate_summary)
        params = sig.parameters
        assert "template_structure" in params
        assert params["template_structure"].default is None

    def test_generate_summary_without_template_backward_compatible(self):
        """template_structure 없이 호출해도 기존 동작 (하위 호환성)"""
        from backend.pipeline.summary_generator import SummaryGenerator
        from backend.schemas.summary import SummaryResult

        with patch("backend.pipeline.summary_generator.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = VALID_CLAUDE_RESPONSE_JSON
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice],
                usage=MagicMock(prompt_tokens=100, completion_tokens=50),
            )
            mock_cls.return_value = mock_client

            generator = SummaryGenerator()
            # template_structure 없이 호출
            result = generator.generate_summary(
                segments=MOCK_MINUTES_SEGMENTS,
                speaker_stats=MOCK_SPEAKER_STATS,
                api_key="test-key",
                model="gpt-4o-mini",
                max_tokens=2000,
            )

        assert isinstance(result, SummaryResult)
