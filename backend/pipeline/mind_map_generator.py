"""
요약 결과 기반 관계 추론형 마인드맵 생성기.
"""

import json
import re

from openai import OpenAI
from pydantic import ValidationError

from backend.schemas.summary import MindMapEdge, MindMapNode
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class MindMapGenerator:
    """OpenAI API를 사용해 완료된 요약 결과를 마인드맵 그래프로 변환한다."""

    JSON_FORMAT_INSTRUCTION = (
        '다음 JSON 형식으로만 응답하세요: {"root": {"id": "root", "title": "...", '
        '"summary": "...", "source_refs": [], "children": [...]}, '
        '"edges": [{"source": "root", "target": "node_id", "relation": "..."}]}'
    )

    def build_prompt(self, summary_data: dict) -> str:
        """요약 결과 dict를 관계 추론용 프롬프트로 변환한다."""
        sections = summary_data.get("sections") or {}
        section_lines = []
        if isinstance(sections, dict):
            for title, content in sections.items():
                section_lines.append(f"- {title}: {content}")

        action_item_lines = []
        for item in summary_data.get("action_items", []) or []:
            if isinstance(item, dict):
                assignee = item.get("assignee") or "담당자 미정"
                task = item.get("task", "")
                deadline = item.get("deadline") or "마감 미정"
                priority = item.get("priority", "medium")
                action_item_lines.append(f"- {assignee}: {task} / {deadline} / {priority}")

        prompt = f"""다음 회의 요약을 PLAUD 스타일의 관계 추론형 마인드맵으로 구조화해 주세요.

## 전체 요약
{summary_data.get("summary_text", "")}

## 섹션별 요약
{chr(10).join(section_lines) if section_lines else "- 섹션 정보 없음"}

## 주요 결정
{_format_string_list(summary_data.get("key_decisions"))}

## 다음 단계
{_format_string_list(summary_data.get("next_steps"))}

## 액션 아이템
{chr(10).join(action_item_lines) if action_item_lines else "- 액션 아이템 없음"}

## 생성 규칙
- root는 회의의 핵심 주제를 나타내세요.
- children은 주제, 결정, 실행 항목, 리스크/의존성을 2~4단계 깊이로 묶으세요.
- edges에는 명시적/추론 가능한 관계를 포함하세요. relation 예: supports, depends_on, leads_to, owner_of, risk_for.
- 모든 node id는 소문자 영문/숫자/언더스코어만 사용하고 중복하지 마세요.
- source_refs에는 근거가 된 summary_text, sections.<섹션명>, key_decisions, next_steps, action_items 중 하나 이상을 넣으세요.
- JSON 안에 주석이나 마크다운을 넣지 마세요.

{self.JSON_FORMAT_INSTRUCTION}"""
        return prompt

    def parse_response(self, response_text: str) -> tuple[MindMapNode, list[MindMapEdge]]:
        """API 응답 텍스트를 MindMapNode/Edge 구조로 파싱한다."""
        try:
            data = json.loads(_clean_json_response(response_text))
            root = MindMapNode.model_validate(data.get("root"))
            raw_edges = data.get("edges", [])
            edges = [MindMapEdge.model_validate(edge) for edge in raw_edges if isinstance(edge, dict)]
            return root, edges
        except (json.JSONDecodeError, TypeError, ValidationError, ValueError) as exc:
            logger.warning(
                "마인드맵 API 응답 JSON 파싱 실패",
                error=str(exc),
                response_preview=response_text[:200],
            )
            raise ValueError("마인드맵 응답을 구조화할 수 없습니다.") from exc

    def generate_mind_map(
        self,
        summary_data: dict,
        api_key: str,
        model: str,
        max_tokens: int,
    ) -> tuple[MindMapNode, list[MindMapEdge]]:
        """OpenAI API를 호출해 마인드맵을 생성한다."""
        prompt = self.build_prompt(summary_data)

        logger.info(
            "OpenAI API 마인드맵 생성 시작",
            model=model,
            max_tokens=max_tokens,
            summary_task_id=summary_data.get("task_id"),
        )

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.choices[0].message.content

        logger.info(
            "OpenAI API 마인드맵 응답 수신",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

        return self.parse_response(response_text)


def _format_string_list(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "- 없음"
    return "\n".join(f"- {item}" for item in items)


def _clean_json_response(response_text: str) -> str:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n")
        cleaned = cleaned[first_newline + 1:]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].rstrip()

    cleaned = _strip_json_comments(cleaned)
    return re.sub(r",\s*([}\]])", r"\1", cleaned)


def _strip_json_comments(text: str) -> str:
    lines = text.split("\n")
    result = []
    for line in lines:
        in_string = False
        i = 0
        stripped_line = line
        while i < len(line) - 1:
            ch = line[i]
            if ch == "\\" and in_string:
                i += 2
                continue
            if ch == '"':
                in_string = not in_string
            elif ch == "/" and line[i + 1] == "/" and not in_string:
                stripped_line = line[:i].rstrip()
                break
            i += 1
        result.append(stripped_line)
    return "\n".join(result)
