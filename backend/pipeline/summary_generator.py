"""
AI 회의 요약 생성기 - Claude API 기반
REQ-SUM-001: MinutesSegment[], SpeakerStats[]로 Claude API 프롬프트 빌드
REQ-SUM-002: Claude 응답을 구조화된 결과로 파싱
REQ-SUM-003: API 실패(네트워크/타임아웃) 시 예외 발생 (Celery 재시도용)
REQ-SUM-004: 유효하지 않은 JSON 응답 → raw text로 graceful 처리, 예외 없음
"""

import json

import anthropic

from backend.schemas.summary import ActionItem, SummaryResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SummaryGenerator:
    """
    Claude API를 사용하여 회의 요약을 생성하는 클래스

    사용법:
        generator = SummaryGenerator()
        result = generator.generate_summary(
            segments=minutes_segments,
            speaker_stats=speaker_stats,
            api_key=settings.anthropic_api_key,
            model=settings.summary_model,
            max_tokens=settings.summary_max_tokens,
        )
    """

    # JSON 응답 형식 지시문 (SPEC HARD rule: 이 형식으로 응답 요청)
    JSON_FORMAT_INSTRUCTION = (
        '다음 JSON 형식으로 응답하세요: {"summary_text": "...", '
        '"action_items": [...], "key_decisions": [...], "next_steps": [...]}'
    )

    def build_prompt(
        self,
        segments: list[dict],
        speaker_stats: list[dict],
    ) -> str:
        """
        회의록 세그먼트와 화자 통계를 기반으로 Claude API 프롬프트 생성 (REQ-SUM-001)

        Args:
            segments: MinutesSegment dict 목록 (speaker_name, text, start, end)
            speaker_stats: SpeakerStats dict 목록 (speaker_name, total_speaking_time, speaking_ratio)

        Returns:
            Claude API에 전달할 프롬프트 문자열
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
            # HH:MM:SS 형식 시간 변환
            time_str = _seconds_to_hhmmss(start)
            dialogue_lines.append(f"[{time_str}] {speaker}: {text}")
        dialogue_section = "\n".join(dialogue_lines) if dialogue_lines else "대화 내용 없음"

        # 최종 프롬프트 조합
        prompt = f"""다음은 회의 녹취록입니다. 회의 내용을 분석하여 핵심 요약을 작성해 주세요.

## 화자 정보
{stats_section}

## 회의 대화 내용
{dialogue_section}

## 요청 사항
위 회의 내용을 분석하여 아래 항목을 작성해 주세요:
1. summary_text: 회의 전체 핵심 요약 (3-5문장)
2. action_items: 각 담당자가 수행해야 할 구체적인 액션 아이템 목록
   - 각 항목: assignee(담당자), task(작업 내용), deadline(마감일, 없으면 null), priority(low/medium/high)
3. key_decisions: 회의에서 내린 주요 결정 사항 목록
4. next_steps: 향후 진행해야 할 다음 단계 목록

{self.JSON_FORMAT_INSTRUCTION}"""

        return prompt

    def parse_response(self, response_text: str) -> SummaryResult:
        """
        Claude API 응답 텍스트를 SummaryResult로 파싱 (REQ-SUM-002, REQ-SUM-004)

        Args:
            response_text: Claude API 응답 텍스트

        Returns:
            SummaryResult 객체
            - 유효한 JSON: 구조화된 결과
            - 유효하지 않은 JSON: summary_text에 raw text, 나머지 빈 리스트 (REQ-SUM-004)
        """
        try:
            # JSON 파싱 시도
            data = json.loads(response_text)

            # ActionItem 객체 변환
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
            # 유효하지 않은 JSON → raw text 저장, 빈 리스트 (REQ-SUM-004: NO error)
            logger.warning(
                "Claude 응답이 유효한 JSON이 아님. raw text를 summary_text에 저장",
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
    ) -> SummaryResult:
        """
        Claude API를 호출하여 회의 요약 생성 (REQ-SUM-001, REQ-SUM-002, REQ-SUM-003)

        Note: Anthropic 클라이언트를 함수 내에서 생성 (싱글톤 아님).
              Celery 워커는 동기 환경이므로 sync 클라이언트 사용.

        Args:
            segments: MinutesSegment dict 목록
            speaker_stats: SpeakerStats dict 목록
            api_key: Anthropic API 키 (직접 전달)
            model: Claude 모델명
            max_tokens: 최대 응답 토큰 수

        Returns:
            SummaryResult 객체

        Raises:
            Exception: API 호출 실패 시 (네트워크, 타임아웃 등) → Celery 재시도용 (REQ-SUM-003)
        """
        # 프롬프트 빌드 (REQ-SUM-001)
        prompt = self.build_prompt(segments, speaker_stats)

        logger.info(
            "Claude API 요약 생성 시작",
            model=model,
            max_tokens=max_tokens,
            segments_count=len(segments),
        )

        # Anthropic 클라이언트 생성 (api_key 직접 전달, 싱글톤 아님)
        # REQ-SUM-003: API 실패 시 예외 발생 (catch하지 않음 → Celery가 재시도)
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        # 응답 텍스트 추출
        response_text = response.content[0].text

        logger.info(
            "Claude API 응답 수신",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        # 응답 파싱 (REQ-SUM-002, REQ-SUM-004)
        return self.parse_response(response_text)


def _seconds_to_hhmmss(seconds: float) -> str:
    """초를 HH:MM:SS 형식으로 변환 (프롬프트 타임스탬프용)"""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
