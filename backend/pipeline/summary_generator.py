"""
AI 회의 요약 생성기 - OpenAI API 기반
REQ-SUM-001: MinutesSegment[], SpeakerStats[]로 OpenAI API 프롬프트 빌드
REQ-SUM-002: OpenAI 응답을 구조화된 결과로 파싱
REQ-SUM-003: API 실패(네트워크/타임아웃) 시 예외 발생 (Celery 재시도용)
REQ-SUM-004: 유효하지 않은 JSON 응답 → raw text로 graceful 처리, 예외 없음
"""

import json

from openai import OpenAI

from backend.schemas.summary import ActionItem, SummaryResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SummaryGenerator:
    """
    OpenAI API를 사용하여 회의 요약을 생성하는 클래스
    """

    # JSON 응답 형식 지시문
    JSON_FORMAT_INSTRUCTION = (
        '다음 JSON 형식으로 응답하세요: {"summary_text": "...", '
        '"action_items": [...], "key_decisions": [...], "next_steps": [...]}'
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

        prompt = f"""다음은 회의 녹취록입니다. 회의 내용을 분석하여 핵심 요약을 작성해 주세요.

## 화자 정보
{stats_section}

## 회의 대화 내용
{dialogue_section}

## 요청 사항
위 회의 내용을 분석하여 아래 항목을 작성해 주세요:
{items_section}

{self.JSON_FORMAT_INSTRUCTION}"""

        return prompt

    def parse_response(self, response_text: str) -> SummaryResult:
        """
        API 응답 텍스트를 SummaryResult로 파싱 (REQ-SUM-002, REQ-SUM-004)
        """
        try:
            data = json.loads(response_text)

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

            return SummaryResult(
                summary_text=data.get("summary_text", ""),
                action_items=action_items,
                key_decisions=data.get("key_decisions", []),
                next_steps=data.get("next_steps", []),
            )

        except (json.JSONDecodeError, ValueError, KeyError):
            logger.warning(
                "API 응답이 유효한 JSON이 아님. raw text를 summary_text에 저장",
                response_preview=response_text[:100],
            )
            return SummaryResult(
                summary_text=response_text,
                action_items=[],
                key_decisions=[],
                next_steps=[],
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
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
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

    섹션 제목을 번호 목록으로 만들고, 기본 4개 항목(summary_text 등)도
    JSON 출력에 포함되도록 지시한다.
    """
    sections = template_structure.get("sections", [])
    lines: list[str] = []

    # 양식 섹션을 출력 항목으로 나열
    for i, section in enumerate(sections, start=1):
        title = section.get("title", f"섹션 {i}")
        lines.append(f"{i}. {title}: 해당 섹션 내용 작성")

    # JSON 출력에는 반드시 기본 필드 포함 (파싱 호환성)
    lines.append(
        "\n위 내용을 다음 JSON 필드에 맞게 정리해 주세요: "
        "summary_text(전체 요약), action_items(액션 아이템), "
        "key_decisions(결정 사항), next_steps(다음 단계)"
    )

    return "\n".join(lines)
