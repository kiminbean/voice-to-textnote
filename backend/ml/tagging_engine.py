"""
SPEC-TAG-001: AI 기반 자동 태깅 엔진

회의록 텍스트에서 주제, 카테고리, 중요도 태그를 자동 추출.
OpenAI API 기반 (settings.summary_model 사용).
"""

import json
import re

import httpx

from backend.app.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 공유 httpx 클라이언트 (연결 재사용)
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """공유 httpx.AsyncClient 반환 (lazy init)"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def close_http_client() -> None:
    """태깅 엔진의 공유 HTTP 클라이언트를 종료."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
    _http_client = None


# 태깅 프롬프트 템플릿
_TAGGING_SYSTEM_PROMPT = """당신은 회의록 분석 전문가입니다.
주어진 회의록 텍스트를 분석하여 다음 종류의 태그를 추출하세요:

1. **topic** (주제): 회의의 핵심 주제. 2~5개.
2. **category** (카테고리): 회의 유형 분류. 1~2개. 가능한 값: [전체회의, 1:1, 브레인스토밍, 스프린트, 리뷰, 워크숍, 기타]
3. **priority** (중요도): 회의 중요도. 1개. 가능한 값: [긴급, 중요, 보통, 낮음]

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요:
```json
{
  "tags": [
    {"tag_type": "topic", "tag_value": "...", "confidence": 0.9},
    {"tag_type": "category", "tag_value": "...", "confidence": 0.8},
    {"tag_type": "priority", "tag_value": "...", "confidence": 0.85}
  ]
}
```

confidence는 0.0~1.0 사이 값이며, 확실할수록 높게 설정하세요."""


def _extract_json(text: str) -> dict:
    """응답 텍스트에서 JSON 블록 추출."""
    # ```json ... ``` 블록 찾기
    match = re.search(r"```json\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    # 그냥 { ... } 찾기
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


async def generate_auto_tags(content: str, max_tags: int = 10) -> list[dict]:
    """
    회의록 내용에서 자동 태그 생성.

    Returns:
        list of dicts with keys: tag_type, tag_value, confidence
    """
    # OpenAI API 키가 없으면 규칙 기반 폴백
    if not settings.openai_api_key:
        logger.info("OpenAI API 키 없음 - 규칙 기반 태깅 사용")
        return _rule_based_tags(content, max_tags)

    try:
        # 텍스트가 너무 길면 자르기
        truncated = content[:6000] if len(content) > 6000 else content

        client = _get_http_client()
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.summary_model,
                "messages": [
                    {"role": "system", "content": _TAGGING_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"다음 회의록을 분석해서 태그를 추출해주세요:\n\n{truncated}",
                    },
                ],
                "max_tokens": 1024,
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]

        parsed = _extract_json(raw_text)  # pragma: no cover
        tags = parsed.get("tags", [])  # pragma: no cover
        return tags[:max_tags]  # pragma: no cover

    except Exception as e:
        logger.warning("AI 자동 태깅 실패, 규칙 기반 폴백", error=str(e))
        return _rule_based_tags(content, max_tags)


def _rule_based_tags(content: str, max_tags: int) -> list[dict]:
    """
    규칙 기반 태깅 (API 키 없거나 실패 시 폴백).
    간단한 키워드 매칭으로 주제 추출.
    """
    import re
    from collections import Counter

    tags = []

    # 카테고리 감지
    category_keywords = {
        "스프린트": ["스프린트", "sprint", "백로그"],
        "리뷰": ["리뷰", "review", "회고", "레트로"],
        "브레인스토밍": ["브레인스토밍", "아이디어", "brainstorm"],
        "1:1": ["1:1", "일대일", "멘토링"],
    }
    detected_category = "기타"
    for cat, keywords in category_keywords.items():
        if any(kw in content.lower() for kw in keywords):
            detected_category = cat
            break

    tags.append(
        {
            "tag_type": "category",
            "tag_value": detected_category,
            "confidence": 0.6,
        }
    )

    # 중요도 감지
    priority = "보통"
    if any(w in content for w in ["긴급", "ASAP", "즉시", "critical"]):
        priority = "긴급"
    elif any(w in content for w in ["중요", "필수", "필히", "important"]):
        priority = "중요"

    tags.append(
        {
            "tag_type": "priority",
            "tag_value": priority,
            "confidence": 0.7,
        }
    )

    # 주제 추출 (명사구 기반 간단 추출)
    # 한글 2~6글자 단어 빈도수 기반
    korean_words = re.findall(r"[가-힣]{2,6}", content)
    # 불용어 제거
    stopwords = {
        "합니다",
        "합니다다",
        "그리고",
        "그래서",
        "하지만",
        "그러면",
        "이것",
        "그것",
        "저것",
        "여기",
        "거기",
        "저기",
        "이런",
        "그런",
        "저런",
        "어떤",
        "이렇게",
        "우리",
        "저희",
        "당신",
        "자신",
        "서로",
        "지금",
        "현재",
        "오늘",
        "내일",
        "어제",
        "그냥",
        "아주",
        "정말",
        "진짜",
        "매우",
        "같은",
        "다른",
        "새로운",
        "이런",
        "그런",
        "있습니다",
        "있어요",
        "습니다",
        "되어",
        "되는",
    }
    filtered = [w for w in korean_words if w not in stopwords]
    counter = Counter(filtered)
    top_topics = counter.most_common(max_tags - len(tags))

    for word, _ in top_topics[:5]:
        tags.append(
            {
                "tag_type": "topic",
                "tag_value": word,
                "confidence": 0.5,
            }
        )

    return tags[:max_tags]
