"""
OpenAI-compatible LLM 클라이언트 유틸리티
"""

import os
from typing import Any

from openai import AsyncOpenAI

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
_ZAI_CODING_PLAN_BASE_URL = "https://api.z.ai/api/coding/paas/v4"


def _is_zai_glm_request(model: str, base_url: str | None = None) -> bool:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    normalized_base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "").lower()
    return model.strip().lower().startswith("glm-") and (
        provider == "zai" or "api.z.ai" in normalized_base_url
    )


def structured_json_completion_options(
    model: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Return JSON-mode options, including ZAI/GLM settings that preserve final content.

    GLM-5.2 enables thinking by default. With small structured-output budgets,
    reasoning tokens can exhaust max_tokens before assistant.content is emitted.
    JSON endpoints need final machine-readable content, so disable thinking for
    these calls and keep a deterministic sampling profile.
    """
    options: dict[str, Any] = {"response_format": {"type": "json_object"}}
    if _is_zai_glm_request(model, base_url):
        options.update(
            {
                "temperature": 0,
                "top_p": 0.01,
                "extra_body": {
                    "thinking": {"type": "disabled"},
                    "reasoning_effort": "none",
                },
            }
        )
    return options


def _get_llm_api_key() -> str | None:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if provider == "zai":
        return os.getenv("ZAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    return os.getenv("OPENAI_API_KEY") or os.getenv("ZAI_API_KEY")


def _get_llm_base_url() -> str:
    configured = os.getenv("OPENAI_BASE_URL")
    if configured:
        return configured.rstrip("/")
    if os.getenv("LLM_PROVIDER", "openai").strip().lower() == "zai":
        return _ZAI_CODING_PLAN_BASE_URL
    return _DEFAULT_OPENAI_BASE_URL


def get_openai_client() -> AsyncOpenAI:
    """
    OpenAI 클라이언트 인스턴스를 반환합니다.

    Returns:
        AsyncOpenAI: OpenAI 클라이언트 인스턴스
    """
    api_key = _get_llm_api_key()
    base_url = _get_llm_base_url()

    if not api_key:
        logger.warning("LLM API key 환경 변수가 설정되지 않았습니다. 품질 평가 기능이 제한됩니다.")
        # 개발 환경을 위한 기본 설정 (실제 프로덕션에서는 API 키 필수)
        return AsyncOpenAI(api_key="dummy-key", base_url=base_url)

    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        logger.info("OpenAI-compatible LLM 클라이언트가 성공적으로 초기화되었습니다.")
        return client
    except Exception as e:
        logger.error(f"OpenAI-compatible LLM 클라이언트 초기화 실패: {str(e)}")
        # 실패 시 대체 클라이언트 반환
        return AsyncOpenAI(api_key="dummy-key", base_url=base_url)


# 전역 클라이언트 인스턴스
_openai_client = None


def get_cached_openai_client() -> AsyncOpenAI:
    """
    캐시된 OpenAI 클라이언트 인스턴스를 반환합니다.

    Returns:
        AsyncOpenAI: OpenAI 클라이언트 인스턴스
    """
    global _openai_client
    if _openai_client is None:
        _openai_client = get_openai_client()
    return _openai_client
