"""
MindMapGenerator 단위 테스트.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

MOCK_SUMMARY_RESULT = {
    "task_id": "summary-1",
    "status": "completed",
    "summary_text": "신제품 출시 일정과 고객 인터뷰 결과를 논의했습니다.",
    "sections": {"출시 일정": "6월 베타, 7월 정식 출시", "고객 피드백": "온보딩 개선 필요"},
    "key_decisions": ["6월 베타 출시를 유지한다"],
    "next_steps": ["온보딩 개선안을 다음 회의까지 정리한다"],
    "action_items": [
        {
            "assignee": "PM",
            "task": "온보딩 개선안 작성",
            "deadline": "다음 회의",
            "priority": "high",
        }
    ],
}


VALID_MIND_MAP_JSON = json.dumps(
    {
        "root": {
            "id": "root",
            "title": "신제품 출시",
            "summary": "출시 일정과 온보딩 개선을 중심으로 정리",
            "source_refs": ["summary_text"],
            "children": [
                {
                    "id": "launch_plan",
                    "title": "출시 일정",
                    "summary": "6월 베타 후 7월 정식 출시",
                    "source_refs": ["sections.출시 일정"],
                    "children": [],
                }
            ],
        },
        "edges": [
            {
                "source": "root",
                "target": "launch_plan",
                "relation": "contains",
            }
        ],
    }
)


def _make_mock_response(text: str) -> MagicMock:
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = text
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=80)
    return mock_response


class TestMindMapBuildPrompt:
    def test_build_prompt_contains_summary_fields(self):
        from backend.pipeline.mind_map_generator import MindMapGenerator

        prompt = MindMapGenerator().build_prompt(MOCK_SUMMARY_RESULT)

        assert "신제품 출시 일정" in prompt
        assert "출시 일정" in prompt
        assert "6월 베타 출시를 유지한다" in prompt
        assert "온보딩 개선안 작성" in prompt

    def test_build_prompt_requests_graph_json(self):
        from backend.pipeline.mind_map_generator import MindMapGenerator

        prompt = MindMapGenerator().build_prompt(MOCK_SUMMARY_RESULT)

        assert '"root"' in prompt
        assert '"edges"' in prompt
        assert "relation" in prompt


class TestMindMapParseResponse:
    def test_parse_valid_json_returns_root_and_edges(self):
        from backend.pipeline.mind_map_generator import MindMapGenerator
        from backend.schemas.summary import MindMapNode

        root, edges = MindMapGenerator().parse_response(VALID_MIND_MAP_JSON)

        assert isinstance(root, MindMapNode)
        assert root.id == "root"
        assert edges[0].relation == "contains"

    def test_parse_markdown_json_code_block(self):
        from backend.pipeline.mind_map_generator import MindMapGenerator

        root, edges = MindMapGenerator().parse_response(f"```json\n{VALID_MIND_MAP_JSON}\n```")

        assert root.title == "신제품 출시"
        assert len(edges) == 1

    def test_parse_invalid_json_raises_value_error(self):
        from backend.pipeline.mind_map_generator import MindMapGenerator

        with pytest.raises(ValueError, match="마인드맵 응답"):
            MindMapGenerator().parse_response("not-json")


class TestGenerateMindMap:
    def test_generate_mind_map_calls_openai(self):
        from backend.pipeline.mind_map_generator import MindMapGenerator

        with patch("backend.pipeline.mind_map_generator.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _make_mock_response(VALID_MIND_MAP_JSON)
            mock_cls.return_value = mock_client

            root, edges = MindMapGenerator().generate_mind_map(
                summary_data=MOCK_SUMMARY_RESULT,
                api_key="sk-test-key",
                model="gpt-4o-mini",
                max_tokens=2048,
            )

        mock_cls.assert_called_once_with(api_key="sk-test-key")
        mock_client.chat.completions.create.assert_called_once()
        assert root.id == "root"
        assert edges[0].target == "launch_plan"
