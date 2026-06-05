"""
AI 회의 요약 생성기 - OpenAI API 기반
REQ-SUM-001: MinutesSegment[], SpeakerStats[]로 OpenAI API 프롬프트 빌드
REQ-SUM-002: OpenAI 응답을 구조화된 결과로 파싱
REQ-SUM-003: API 실패(네트워크/타임아웃) 시 예외 발생 (Celery 재시도용)
REQ-SUM-004: 유효하지 않은 JSON 응답 → raw text로 graceful 처리, 예외 없음
"""

import json
import re

from openai import OpenAI

from backend.schemas.summary import ActionItem, SummaryResult
from backend.utils.json_helpers import strip_json_comments
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SummaryGenerator:
    """
    OpenAI API를 사용하여 회의 요약을 생성하는 클래스
    """

    # JSON 응답 형식 지시문 (양식 없을 때)
    JSON_FORMAT_INSTRUCTION = (
        '다음 JSON 형식으로 응답하세요: {"summary_text": "...", '
        '"action_items": [...], "key_decisions": [...], "next_steps": [...]}'
    )

    # REQ-UI-003: JSON 응답 형식 지시문 (양식 있을 때 - 섹션별 개별 출력)
    JSON_FORMAT_WITH_SECTIONS = (
        '다음 JSON 형식으로 응답하세요: {{"summary_text": "전체 요약", '
        '"sections": {{{sections_keys}}}, '
        '"action_items": [...], "key_decisions": [...], "next_steps": [...]}}'
    )

    def build_prompt(
        self,
        segments: list[dict],
        speaker_stats: list[dict],
        template_structure: dict | None = None,
    ) -> str:
        """
        회의록 세그먼트와 화자 통계를 기반으로 프롬프트 생성 (REQ-SUM-001)

        Args:
            segments: MinutesSegment dict 목록
            speaker_stats: SpeakerStats dict 목록
            template_structure: 양식 구조 dict (REQ-TMPL-004: None이면 기본 4개 항목)

        Returns:
            OpenAI API 프롬프트 문자열
        """
        # 화자 통계 섹션 구성
        stats_lines = []
        for stat in speaker_stats:
            name = stat.get("speaker_name", "알 수 없음")
            speaking_time = stat.get("total_speaking_time", 0.0)
            speaking_ratio = stat.get("speaking_ratio", 0.0)
            stats_lines.append(
                f"- {name}: 발화 시간 {speaking_time:.1f}초 (비율 {speaking_ratio:.1f}%)"
            )
        stats_section = "\n".join(stats_lines) if stats_lines else "- 화자 정보 없음"

        # 대화 내용 섹션 구성
        dialogue_lines = []
        for seg in segments:
            speaker = seg.get("speaker_name", "알 수 없음")
            text = seg.get("text", "")
            start = seg.get("start", 0.0)
            time_str = _seconds_to_hhmmss(start)
            dialogue_lines.append(f"[{time_str}] {speaker}: {text}")
        dialogue_section = "\n".join(dialogue_lines) if dialogue_lines else "대화 내용 없음"

        # REQ-TMPL-004: 양식 구조가 있으면 섹션 기반 프롬프트, 없으면 기본 4개 항목
        if template_structure and template_structure.get("sections"):
            items_section = _build_template_items_section(template_structure)
        else:
            items_section = (
                "1. summary_text: 회의 전체 핵심 요약 (3-5문장)\n"
                "2. action_items: 각 담당자가 수행해야 할 구체적인 액션 아이템 목록\n"
                "   - 각 항목: assignee(담당자), task(작업 내용), deadline(마감일, 없으면 null), priority(low/medium/high)\n"
                "3. key_decisions: 회의에서 내린 주요 결정 사항 목록\n"
                "4. next_steps: 향후 진행해야 할 다음 단계 목록"
            )

        # REQ-UI-003: 양식 있을 때 섹션별 JSON 출력 지시
        if template_structure and template_structure.get("sections"):
            section_titles = [s.get("title", "") for s in template_structure["sections"] if s.get("title")]
            sections_keys = ", ".join(f'"{t}": "해당 내용"' for t in section_titles)
            format_instruction = self.JSON_FORMAT_WITH_SECTIONS.format(sections_keys=sections_keys)
            # 모든 섹션 키를 명시적으로 나열하여 누락 방지
            mandatory_sections = "\n".join(f'- "{t}"' for t in section_titles)
            mandatory_instruction = (
                f"\n\n[중요] sections 필드에 아래 키를 반드시 모두 포함하세요. "
                f"해당 내용이 회의에서 언급되지 않았더라도 빈 문자열로 포함해야 합니다:\n{mandatory_sections}"
                "\n\n[중요] JSON 안에 주석(// ...)을 절대 넣지 마세요. 순수 JSON만 출력하세요."
            )
        else:
            format_instruction = self.JSON_FORMAT_INSTRUCTION
            mandatory_instruction = "\n\n[중요] JSON 안에 주석(// ...)을 절대 넣지 마세요. 순수 JSON만 출력하세요."

        prompt = f"""다음은 회의 녹취록입니다. 회의 내용을 분석하여 핵심 요약을 작성해 주세요.

## 화자 정보
{stats_section}

## 회의 대화 내용
{dialogue_section}

## 요청 사항
위 회의 내용을 분석하여 아래 항목을 작성해 주세요:
{items_section}

{format_instruction}{mandatory_instruction}"""

        return prompt

    def parse_response(self, response_text: str) -> SummaryResult:
        """
        API 응답 텍스트를 SummaryResult로 파싱 (REQ-SUM-002, REQ-SUM-004)
        """
        try:
            # 마크다운 코드 블록 제거 (```json ... ``` 또는 ``` ... ```)
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                first_newline = cleaned.index("\n")
                cleaned = cleaned[first_newline + 1:]
                if cleaned.rstrip().endswith("```"):
                    cleaned = cleaned.rstrip()[:-3].rstrip()

            # JSON 주석 제거 — 문자열 내부의 // 는 보호
            # 각 줄에서 따옴표 밖에 있는 // 만 제거
            cleaned = strip_json_comments(cleaned)
            # 후행 쉼표 제거 (주석 제거 후 남은 ,} 또는 ,] 패턴)
            cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)

            data = json.loads(cleaned)

            raw_action_items = data.get("action_items", [])
            action_items = []
            for item in raw_action_items:
                if isinstance(item, dict):
                    action_items.append(
                        ActionItem(
                            assignee=item.get("assignee"),
                            task=item.get("task", ""),
                            deadline=item.get("deadline"),
                            priority=item.get("priority", "medium"),
                        )
                    )

            # REQ-UI-003: sections 파싱 (양식 기반 섹션별 내용)
            raw_sections = data.get("sections", {})
            sections: dict[str, str] = {}
            if isinstance(raw_sections, dict):
                for k, v in raw_sections.items():
                    sections[str(k)] = str(v) if v else ""

            return SummaryResult(
                summary_text=data.get("summary_text", ""),
                action_items=action_items,
                key_decisions=data.get("key_decisions", []),
                next_steps=data.get("next_steps", []),
                sections=sections,
            )

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "API 응답 JSON 파싱 실패 — 부분 추출 시도",
                error=str(exc),
                response_preview=response_text[:200],
            )
            # 잘린 JSON에서라도 summary_text 추출 시도
            summary_text = response_text
            sections: dict[str, str] = {}
            action_items_fallback: list[ActionItem] = []
            try:
                # "summary_text" 값 추출 (정규식)
                import re as _re
                st_match = _re.search(r'"summary_text"\s*:\s*"((?:[^"\\]|\\.)*)"', response_text)
                if st_match:
                    summary_text = st_match.group(1).replace('\\"', '"')
                # "sections" 내부 키-값 추출
                sec_match = _re.search(r'"sections"\s*:\s*\{([^}]*)\}', response_text, _re.DOTALL)
                if sec_match:
                    for kv in _re.finditer(r'"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', sec_match.group(1)):
                        sections[kv.group(1)] = kv.group(2).replace('\\"', '"')
            except Exception as parse_exc:
                # 폴백 파싱 실패는 치명적이지 않지만 디버깅을 위해 로그를 남긴다.
                logger.warning(
                    "요약 폴백 파싱 실패",
                    error=str(parse_exc),
                )
            return SummaryResult(
                summary_text=summary_text,
                action_items=action_items_fallback,
                key_decisions=[],
                next_steps=[],
                sections=sections,
            )

    def generate_summary(
        self,
        segments: list[dict],
        speaker_stats: list[dict],
        api_key: str,
        model: str,
        max_tokens: int,
        template_structure: dict | None = None,
    ) -> SummaryResult:
        """
        OpenAI API를 호출하여 회의 요약 생성

        Args:
            segments: MinutesSegment dict 목록
            speaker_stats: SpeakerStats dict 목록
            api_key: OpenAI API 키
            model: OpenAI 모델명 (gpt-4o-mini 등)
            max_tokens: 최대 응답 토큰 수
            template_structure: 양식 구조 dict (REQ-TMPL-004: None이면 기본 동작)

        Returns:
            SummaryResult 객체

        Raises:
            Exception: API 호출 실패 시 (REQ-SUM-003)
        """
        prompt = self.build_prompt(segments, speaker_stats, template_structure=template_structure)

        logger.info(
            "OpenAI API 요약 생성 시작",
            model=model,
            max_tokens=max_tokens,
            segments_count=len(segments),
        )

        client = OpenAI(api_key=api_key)
        # response_format=json_object: 모델이 항상 valid JSON을 반환하도록 강제.
        # 일반 모드는 간헐적으로 깨진 JSON을 생성해 raw text fallback으로 빠짐.
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        response_text = response.choices[0].message.content

        logger.info(
            "OpenAI API 응답 수신",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

        return self.parse_response(response_text)


def _seconds_to_hhmmss(seconds: float) -> str:
    """초를 HH:MM:SS 형식으로 변환"""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _build_template_items_section(template_structure: dict) -> str:
    """
    양식 구조의 섹션 목록을 프롬프트의 요청 항목으로 변환 (REQ-TMPL-004).
    sections 필드에 실제 내용을 채우도록 명확히 지시.
    """
    sections = template_structure.get("sections", [])
    lines: list[str] = []

    lines.append("아래 sections 필드의 각 항목에 회의 내용을 분석하여 상세히 작성해 주세요:")
    lines.append("")

    for i, section in enumerate(sections, start=1):
        title = section.get("title", f"섹션 {i}")
        lines.append(f'{i}. sections."{title}": 이 항목에 해당하는 내용을 회의 대화에서 추출하여 상세히 작성')

    lines.append("")
    lines.append("또한 다음 항목도 작성해 주세요:")
    lines.append('- summary_text: 회의 핵심 요약 (2-3문장으로 간결하게)')
    lines.append('- action_items: 담당자별 수행해야 할 구체적 작업 목록')
    lines.append('- key_decisions: 회의에서 내린 주요 결정 사항')
    lines.append('- next_steps: 향후 진행할 다음 단계')
    lines.append("")
    lines.append("[중요] sections 필드의 각 값에 실제 내용을 상세히 작성해야 합니다. 빈 문자열로 두지 마세요.")
    lines.append("[중요] summary_text에는 간결한 요약만 넣고, 상세 내용은 반드시 sections에 넣으세요.")

    return "\n".join(lines)
