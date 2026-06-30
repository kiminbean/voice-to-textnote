"""
요약 결과 기반 관계 추론형 마인드맵 생성기.
"""

import json
import re

from pydantic import ValidationError

from backend.ml.zai_client import ZAIClient, structured_json_completion_options
from backend.schemas.summary import MindMapEdge, MindMapNode
from backend.utils.json_helpers import strip_json_comments
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class MindMapGenerator:
    """ZAI-compatible LLM API를 사용해 완료된 요약 결과를 마인드맵 그래프로 변환한다."""

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
            edges = [
                MindMapEdge.model_validate(edge) for edge in raw_edges if isinstance(edge, dict)
            ]
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
        base_url: str | None = None,
    ) -> tuple[MindMapNode, list[MindMapEdge]]:
        """ZAI-compatible LLM API를 호출해 마인드맵을 생성한다."""
        prompt = self.build_prompt(summary_data)

        logger.info(
            "ZAI-compatible API 마인드맵 생성 시작",
            model=model,
            max_tokens=max_tokens,
            summary_task_id=summary_data.get("task_id"),
        )

        client = ZAIClient(api_key=api_key, base_url=base_url) if base_url else ZAIClient(api_key=api_key)
        # response_format=json_object: ZAI-compatible 모델이 valid JSON을 반환하도록 강제.
        # 일반 모드는 간헐적으로 깨진 JSON(이스케이프 누락 등)을 생성해 파싱이 실패함.
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **structured_json_completion_options(model, base_url),
        )

        response_text = response.choices[0].message.content or ""
        usage = response.usage

        logger.info(
            "ZAI-compatible API 마인드맵 응답 수신",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

        try:
            return self.parse_response(response_text)
        except ValueError:
            logger.warning(
                "마인드맵 AI 응답 파싱 실패, 요약 기반 기본 마인드맵으로 폴백",
                summary_task_id=summary_data.get("task_id"),
            )
            return build_fallback_mind_map(summary_data)


def build_fallback_mind_map(summary_data: dict) -> tuple[MindMapNode, list[MindMapEdge]]:
    """LLM JSON 응답이 깨졌을 때 요약 데이터만으로 표시 가능한 마인드맵을 만든다."""
    summary_text = str(summary_data.get("summary_text") or "").strip()
    root = MindMapNode(
        id="root",
        title=_short_title(summary_text) or "회의 요약",
        summary=summary_text,
        source_refs=["summary_text"],
        children=[],
    )
    edges: list[MindMapEdge] = []

    sections = summary_data.get("sections") or {}
    if isinstance(sections, dict):
        for index, (title, content) in enumerate(sections.items()):
            content_text = str(content or "").strip()
            if not str(title).strip() and not content_text:
                continue
            node_id = f"section_{index}"
            root.children.append(
                MindMapNode(
                    id=node_id,
                    title=str(title).strip() or f"섹션 {index + 1}",
                    summary=content_text,
                    source_refs=[f"sections.{title}"],
                )
            )
            edges.append(MindMapEdge(source="root", target=node_id, relation="contains"))

    grouped_items = [
        ("key_decisions", "주요 결정", summary_data.get("key_decisions")),
        ("next_steps", "다음 단계", summary_data.get("next_steps")),
    ]
    for group_id, title, items in grouped_items:
        if not isinstance(items, list) or not items:
            continue
        child_nodes = [
            MindMapNode(
                id=f"{group_id}_{index}",
                title=_short_title(str(item)),
                summary=str(item),
                source_refs=[group_id],
            )
            for index, item in enumerate(items[:5])
            if str(item).strip()
        ]
        if not child_nodes:
            continue
        root.children.append(
            MindMapNode(
                id=group_id,
                title=title,
                summary="\n".join(node.summary for node in child_nodes),
                source_refs=[group_id],
                children=child_nodes,
            )
        )
        edges.append(MindMapEdge(source="root", target=group_id, relation="contains"))
        edges.extend(
            MindMapEdge(source=group_id, target=node.id, relation="contains")
            for node in child_nodes
        )

    action_items = summary_data.get("action_items") or []
    if isinstance(action_items, list) and action_items:
        children = []
        for index, item in enumerate(action_items[:5]):
            if not isinstance(item, dict):
                continue
            task = str(item.get("task") or "").strip()
            if not task:
                continue
            children.append(
                MindMapNode(
                    id=f"action_items_{index}",
                    title=_short_title(task),
                    summary=task,
                    source_refs=["action_items"],
                )
            )
        if children:
            root.children.append(
                MindMapNode(
                    id="action_items",
                    title="액션 아이템",
                    summary="\n".join(node.summary for node in children),
                    source_refs=["action_items"],
                    children=children,
                )
            )
            edges.append(MindMapEdge(source="root", target="action_items", relation="contains"))
            edges.extend(
                MindMapEdge(source="action_items", target=node.id, relation="owner_of")
                for node in children
            )

    if not root.children and summary_text:
        root.children.append(
            MindMapNode(
                id="summary",
                title="핵심 요약",
                summary=summary_text,
                source_refs=["summary_text"],
            )
        )
        edges.append(MindMapEdge(source="root", target="summary", relation="contains"))

    return root, edges


def _short_title(text: str, limit: int = 28) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def _format_string_list(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "- 없음"
    return "\n".join(f"- {item}" for item in items)


def _clean_json_response(response_text: str) -> str:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n")
        cleaned = cleaned[first_newline + 1 :]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].rstrip()

    cleaned = strip_json_comments(cleaned)
    return re.sub(r",\s*([}\]])", r"\1", cleaned)
