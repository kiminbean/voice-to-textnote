"""
액션 아이템 추출 엔진
SPEC-ACTION-001: 회의록 텍스트에서 할 일/액션 아이템 자동 추출

규칙 기반 + 키워드 매칭으로 액션 아이템을 추출합니다.
LLM 기반 추출은 summary 엔진과 동일한 OpenAI API를 사용할 수 있지만,
기본 구현은 규칙 기반으로 외부 의존성 없이 동작합니다.
"""

import re
from dataclasses import dataclass

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 한국어 액션 아이템 키워드
_KO_ACTION_PATTERNS = [
    # "~해주세요", "~하겠습니다", "~할게요" 등
    re.compile(
        r"(?P<context>[^.\n]{0,50})"
        r"(?P<task>(?:.{5,80}?(?:해\s*야\s*하|하\s*겠습니|하\s*겠다|해\s*주세요|"
        r"하\s*기로\s*하|진\s*행\s*하|검\s*토\s*하|확인\s*하|수정\s*하|"
        r"작성\s*하|준비\s*하|공유\s*하|전달\s*하|회신\s*하|"
        r"만들\s*어|만들\s*겠|설정\s*하|등록\s*하|삭제\s*하|"
        r"업\s*데이트|반영\s*하|적용\s*하|배포\s*하|"
        r"도입\s*하|개선\s*하|추가\s*하|변경\s*하)))",
        re.IGNORECASE,
    ),
    # "TODO:", "할 일:", "액션 아이템:" 마커
    re.compile(
        r"(?:TODO|할\s*일|액션\s*아이템|ACTION\s*ITEM)[：:]\s*(?P<task>.{5,100})",
        re.IGNORECASE,
    ),
]

# 영어 액션 아이템 키워드
_EN_ACTION_PATTERNS = [
    re.compile(
        r"(?P<context>[^.\n]{0,50})"
        r"(?P<task>(?:.{5,80}?(?:will\s+|need\s+to\s+|should\s+|must\s+|going\s+to\s+|"
        r"please\s+|let'?s?\s+|make\s+sure\s+|follow\s+up|"
        r"schedule|prepare|review|send|create|update|check|fix|implement|deploy)))",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:TODO|ACTION\s*ITEM|FOLLOW\s*UP|NEXT\s*STEP)[：:]\s*(?P<task>.{5,100})",
        re.IGNORECASE,
    ),
]

# 담당자 패턴
_KO_ASSIGNEE_PATTERNS = [
    re.compile(r"(?:담당|담당자|맡은|담당은)[：:\s]*([가-힣]{2,4})(?:님)?"),
    re.compile(r"([가-힣]{2,4})(?:님(?:이|이|께서|은|는))?\s*(?:해|하세요|진행|담당|맡)"),
    re.compile(r"([가-힣]{2,4})님(?:께서)?\s*(?:~?까지|~?하게)"),
]

_EN_ASSIGNEE_PATTERNS = [
    re.compile(r"(?:assigned\s+to|owner|responsible)[：:\s]*(\w+\s?\w*)", re.IGNORECASE),
    re.compile(r"(\w+)\s+(?:will|should|needs?\s+to)\s+", re.IGNORECASE),
]

# 기한/마감일 패턴
_KO_DEADLINE_PATTERNS = [
    re.compile(r"(오늘|내일|모레|글피)(?:까지)?"),
    re.compile(r"(\d{1,2})월\s*(\d{1,2})일?(?:까지|까지는|까지로)?"),
    re.compile(r"(?:이번\s*|다음\s*)?(?:주|월|화|수|목|금|토|일)(?:요일)?(?:까지)?"),
    re.compile(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})"),
    re.compile(r"(이번\s*주|다음\s*주|이번\s*달|다음\s*달|이번\s*분기)(?:까지)?"),
]

_EN_DEADLINE_PATTERNS = [
    re.compile(r"by\s+(?:the\s+)?(?:end\s+of\s+)?(\w+\s+\d{1,2}(?:st|nd|rd|th)?)", re.IGNORECASE),
    re.compile(
        r"(?:deadline|due)[：:\s]*(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\w+\s+\d{1,2})", re.IGNORECASE
    ),
    re.compile(
        r"(?:by|before|until)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        re.IGNORECASE,
    ),
    re.compile(r"(tomorrow|today|next\s+week|this\s+week|end\s+of\s+month)", re.IGNORECASE),
]

# 우선순위 키워드
_PRIORITY_HIGH = re.compile(
    r"(?:긴급|urgent|즉시|immediately|높은\s*우선|high\s*priority|ASAP|asap|최우선|꼭|반드시)",
    re.IGNORECASE,
)
_PRIORITY_LOW = re.compile(
    r"(?:나중에|later|여유|low\s*priority|시간\s*될\s*때|when\s*possible|천천히)",
    re.IGNORECASE,
)


@dataclass
class ExtractedActionItem:
    """추출된 액션 아이템 데이터 클래스"""

    task: str
    assignee: str | None = None
    deadline: str | None = None
    priority: str | None = None
    context: str | None = None


def _extract_assignee(text: str, language: str = "ko") -> str | None:
    """텍스트에서 담당자 추출"""
    patterns = _KO_ASSIGNEE_PATTERNS if language == "ko" else _EN_ASSIGNEE_PATTERNS
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return None


def _extract_deadline(text: str, language: str = "ko") -> str | None:
    """텍스트에서 기한/마감일 추출"""
    patterns = _KO_DEADLINE_PATTERNS if language == "ko" else _EN_DEADLINE_PATTERNS
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            return m.group(0).strip()
    return None


def _extract_priority(text: str) -> str | None:
    """텍스트에서 우선순위 추출"""
    if _PRIORITY_HIGH.search(text):
        return "high"
    if _PRIORITY_LOW.search(text):
        return "low"
    return "medium"


def extract_action_items(
    text: str,
    language: str = "ko",
    include_deadlines: bool = True,
    include_assignees: bool = True,
) -> list[ExtractedActionItem]:
    """
    회의록 텍스트에서 액션 아이템 추출

    Args:
        text: 회의록 텍스트
        language: 언어 코드 (ko, en)
        include_deadlines: 기한 추출 포함 여부
        include_assignees: 담당자 추출 포함 여부

    Returns:
        추출된 액션 아이템 목록
    """
    if not text or len(text.strip()) < 10:
        return []

    patterns = _KO_ACTION_PATTERNS if language == "ko" else _EN_ACTION_PATTERNS
    items: list[ExtractedActionItem] = []
    seen_tasks: set[str] = set()

    for pattern in patterns:
        for match in pattern.finditer(text):
            task_text = match.group("task").strip()
            if not task_text:
                continue  # pragma: no cover

            # 중복 제거 (정규화)
            normalized = re.sub(r"\s+", " ", task_text).lower()
            if normalized in seen_tasks:
                continue
            if len(task_text) < 5:
                continue  # pragma: no cover

            seen_tasks.add(normalized)

            # 주변 컨텍스트 (앞뒤 문장)
            context = match.group("context").strip() if "context" in match.groupdict() else None

            # 담당자, 기한, 우선순위 추출
            search_text = (context or "") + " " + task_text
            assignee = _extract_assignee(search_text, language) if include_assignees else None
            deadline = _extract_deadline(search_text, language) if include_deadlines else None
            priority = _extract_priority(search_text)

            items.append(
                ExtractedActionItem(
                    task=task_text,
                    assignee=assignee,
                    deadline=deadline,
                    priority=priority,
                    context=context if context and len(context) > 3 else None,
                )
            )

    # 최대 50개로 제한
    return items[:50]
