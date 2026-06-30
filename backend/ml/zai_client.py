"""ZAI LLM client utilities."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_ZAI_CODING_PLAN_BASE_URL = "https://api.z.ai/api/coding/paas/v4"
_DEFAULT_LLM_PROVIDER = "zai"


@dataclass
class ZAIMessage:
    content: str | None


@dataclass
class ZAIChoice:
    message: ZAIMessage


@dataclass
class ZAIUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ZAIChatCompletion:
    choices: list[ZAIChoice]
    usage: ZAIUsage | None = None
    raw: dict[str, Any] | None = None


def _is_zai_glm_request(model: str, base_url: str | None = None) -> bool:
    provider = os.getenv("LLM_PROVIDER", _DEFAULT_LLM_PROVIDER).strip().lower()
    normalized_base_url = (base_url or os.getenv("ZAI_BASE_URL") or "").lower()
    return model.strip().lower().startswith("glm-") and (
        provider == "zai" or "api.z.ai" in normalized_base_url
    )


def structured_json_completion_options(
    model: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Return JSON-mode options, including ZAI/GLM settings that preserve final content."""
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
    return os.getenv("ZAI_API_KEY")


def _get_llm_base_url() -> str:
    configured = os.getenv("ZAI_BASE_URL")
    if configured:
        return configured.rstrip("/")
    return _ZAI_CODING_PLAN_BASE_URL


class _Completions:
    def __init__(self, client: ZAIClient) -> None:
        self._client = client

    def create(self, **kwargs: Any) -> ZAIChatCompletion:
        return self._client.create_chat_completion(**kwargs)


class _AsyncCompletions:
    def __init__(self, client: AsyncZAIClient) -> None:
        self._client = client

    async def create(self, **kwargs: Any) -> ZAIChatCompletion:
        return await self._client.create_chat_completion(**kwargs)


class _Chat:
    def __init__(self, client: ZAIClient) -> None:
        self.completions = _Completions(client)


class _AsyncChat:
    def __init__(self, client: AsyncZAIClient) -> None:
        self.completions = _AsyncCompletions(client)


class ZAIClient:
    def __init__(self, api_key: str, base_url: str | None = None, timeout_seconds: float = 120.0):
        self.api_key = api_key
        self.base_url = (base_url or _ZAI_CODING_PLAN_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.chat = _Chat(self)

    def create_chat_completion(self, **kwargs: Any) -> ZAIChatCompletion:
        payload = _build_payload(kwargs)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ZAI API error {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"ZAI API connection error: {exc.reason}") from exc

        return _parse_response(response_data)


class AsyncZAIClient:
    def __init__(self, api_key: str, base_url: str | None = None, timeout_seconds: float = 120.0):
        self._sync_client = ZAIClient(api_key, base_url, timeout_seconds)
        self.chat = _AsyncChat(self)

    async def create_chat_completion(self, **kwargs: Any) -> ZAIChatCompletion:
        return await asyncio.to_thread(self._sync_client.create_chat_completion, **kwargs)


def _build_payload(kwargs: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": kwargs["model"],
        "messages": kwargs["messages"],
    }
    for key in (
        "max_tokens",
        "temperature",
        "top_p",
        "response_format",
        "stream",
        "tools",
        "tool_choice",
    ):
        if key in kwargs and kwargs[key] is not None:
            payload[key] = kwargs[key]

    extra_body = kwargs.get("extra_body")
    if isinstance(extra_body, dict):
        payload.update(extra_body)
    return payload


def _parse_response(data: dict[str, Any]) -> ZAIChatCompletion:
    raw_choices = data.get("choices")
    choices: list[ZAIChoice] = []
    if isinstance(raw_choices, list):
        for item in raw_choices:
            if not isinstance(item, dict):
                continue
            message = item.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            choices.append(ZAIChoice(message=ZAIMessage(content=content)))

    raw_usage = data.get("usage")
    usage = None
    if isinstance(raw_usage, dict):
        usage = ZAIUsage(
            prompt_tokens=int(raw_usage.get("prompt_tokens") or 0),
            completion_tokens=int(raw_usage.get("completion_tokens") or 0),
            total_tokens=int(raw_usage.get("total_tokens") or 0),
        )
    return ZAIChatCompletion(choices=choices, usage=usage, raw=data)


def get_zai_client() -> AsyncZAIClient:
    api_key = _get_llm_api_key()
    base_url = _get_llm_base_url()

    if not api_key:
        logger.warning("ZAI API key 환경 변수가 설정되지 않았습니다. 품질 평가 기능이 제한됩니다.")
        return AsyncZAIClient(api_key="dummy-key", base_url=base_url)

    try:
        client = AsyncZAIClient(api_key=api_key, base_url=base_url)
        logger.info("ZAI LLM 클라이언트가 성공적으로 초기화되었습니다.")
        return client
    except Exception as exc:
        logger.error(f"ZAI LLM 클라이언트 초기화 실패: {str(exc)}")
        return AsyncZAIClient(api_key="dummy-key", base_url=base_url)


_zai_client: AsyncZAIClient | None = None


def get_cached_zai_client() -> AsyncZAIClient:
    global _zai_client
    if _zai_client is None:
        _zai_client = get_zai_client()
    return _zai_client
