"""Sales contact brief generation service."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

import redis.asyncio as aioredis
from openai import OpenAI

from backend.app.config import settings
from backend.schemas.sales_contact_brief import (
    SalesContactBriefResponse,
    SalesContactDeal,
    SalesContactIdentity,
    SalesNextStep,
)
from backend.schemas.study_pack import StudySourceRef
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SALES_CONTACT_BRIEF_KEY_PREFIX = "sales_contact_brief:"
_MINUTES_KEY_PREFIX = "task:min:result:"


def _sales_contact_brief_cache_key(task_id: str) -> str:
    return f"{_SALES_CONTACT_BRIEF_KEY_PREFIX}{task_id}"


class SalesContactBriefSourceNotFoundError(ValueError):
    """Raised when source minutes or cached contact brief content is missing."""


class SalesContactBriefValidationError(ValueError):
    """Raised when generated contact brief content cannot be validated."""


class SalesContactBriefService:
    """Generate customer/contact follow-up artifacts from completed minutes results."""

    def _get_client(self) -> OpenAI:
        return OpenAI(api_key=settings.openai_api_key)

    async def get(
        self,
        task_id: str,
        redis_client: aioredis.Redis,
    ) -> SalesContactBriefResponse:
        """Load a cached sales contact brief."""
        raw = await redis_client.get(_sales_contact_brief_cache_key(task_id))
        if raw is None:
            raise SalesContactBriefSourceNotFoundError("영업 연락처 브리프를 찾을 수 없습니다.")
        return SalesContactBriefResponse.model_validate_json(cast(str | bytes | bytearray, raw))

    async def generate(
        self,
        task_id: str,
        redis_client: aioredis.Redis,
        *,
        language: str = "ko",
        max_tokens: int = 1200,
        force_refresh: bool = False,
    ) -> SalesContactBriefResponse:
        """Generate or return a cached sales contact brief for a minutes task."""
        cache_key = _sales_contact_brief_cache_key(task_id)
        if not force_refresh:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return SalesContactBriefResponse.model_validate_json(
                    cast(str | bytes | bytearray, cached)
                )

        minutes_data = await self._load_minutes(task_id, redis_client)
        transcript = self._format_transcript(minutes_data)
        if not transcript.strip():
            raise SalesContactBriefSourceNotFoundError("회의록 내용이 비어 있습니다.")

        source_refs = self._extract_source_refs(minutes_data)
        prompt = self._build_prompt(transcript, language=language)
        client = self._get_client()
        logger.info("Sales contact brief API 호출", task_id=task_id)
        response = client.chat.completions.create(
            model=settings.summary_model,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = response.choices[0].message.content or ""
        payload = self._parse_response(response_text)
        result = SalesContactBriefResponse(
            task_id=task_id,
            contact=SalesContactIdentity.model_validate(payload.get("contact") or {}),
            deal=SalesContactDeal.model_validate(payload.get("deal") or {}),
            customer_needs=[
                str(item).strip()
                for item in payload.get("customer_needs", [])
                if str(item).strip()
            ],
            pain_points=[
                str(item).strip() for item in payload.get("pain_points", []) if str(item).strip()
            ],
            objections=[
                str(item).strip() for item in payload.get("objections", []) if str(item).strip()
            ],
            next_steps=[
                SalesNextStep.model_validate(item)
                for item in payload.get("next_steps", [])
                if isinstance(item, dict)
            ],
            follow_up_message=str(payload.get("follow_up_message", "")).strip(),
            source_refs=source_refs,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._validate_result(result)
        await redis_client.set(
            cache_key,
            result.model_dump_json(),
            ex=settings.summary_result_ttl,
        )
        return result

    async def _load_minutes(
        self,
        task_id: str,
        redis_client: aioredis.Redis,
    ) -> dict[str, Any]:
        raw = await redis_client.get(f"{_MINUTES_KEY_PREFIX}{task_id}")
        if raw is None:
            raise SalesContactBriefSourceNotFoundError(
                "회의록을 찾을 수 없습니다. 처리가 완료되었는지 확인하세요."
            )
        try:
            data = json.loads(cast(str | bytes | bytearray, raw))
        except json.JSONDecodeError as exc:
            raise SalesContactBriefValidationError("회의록 JSON을 해석할 수 없습니다.") from exc
        if not isinstance(data, dict):
            raise SalesContactBriefValidationError("회의록 결과 형식이 올바르지 않습니다.")
        return data

    def _format_transcript(self, minutes_data: dict[str, Any]) -> str:
        segments = minutes_data.get("segments", [])
        if not isinstance(segments, list) or not segments:
            return str(minutes_data.get("raw_text", ""))

        lines = []
        for index, seg in enumerate(segments):
            if not isinstance(seg, dict):
                continue
            speaker = seg.get("speaker_name") or seg.get("speaker") or "알 수 없음"
            text = str(seg.get("text", "")).strip()
            start = seg.get("start", 0.0)
            lines.append(f"[{index} | {start}s | {speaker}] {text}")
        return "\n".join(lines)

    def _extract_source_refs(self, minutes_data: dict[str, Any]) -> list[StudySourceRef]:
        refs: list[StudySourceRef] = []
        segments = minutes_data.get("segments", [])
        if not isinstance(segments, list):
            return refs
        for index, seg in enumerate(segments[:20]):
            if not isinstance(seg, dict):
                continue
            refs.append(
                StudySourceRef(
                    segment_index=index,
                    speaker=seg.get("speaker_name") or seg.get("speaker"),
                    start=seg.get("start"),
                    end=seg.get("end"),
                    text=str(seg.get("text", ""))[:240],
                )
            )
        return refs

    def _build_prompt(self, transcript: str, *, language: str) -> str:
        return f"""다음 영업/고객 대화 녹취록을 바탕으로 고객 후속 브리프를 생성하세요.

## 언어
{language}

## 녹취록
{transcript}

## 지시사항
- 반드시 녹취록에 있는 내용만 사용하세요.
- 고객 신원, 니즈, pain point, objection, 다음 액션을 분리하세요.
- 확인되지 않은 이메일/전화/금액은 null로 두세요.
- follow_up_message는 고객에게 보낼 수 있는 짧은 후속 메시지 초안으로 작성하세요.
- source_refs에는 근거가 되는 세그먼트 인덱스를 넣으세요.
- 아래 JSON 형식만 출력하세요.

{{
  "contact": {{
    "name": "고객명 또는 null",
    "company": "회사명 또는 null",
    "role": "직책 또는 null",
    "email": null,
    "phone": null
  }},
  "deal": {{
    "stage": "lead|qualified|demo_requested|proposal|negotiation|closed|unknown",
    "value_hint": null,
    "urgency": "low|medium|high|unknown"
  }},
  "customer_needs": ["녹취록 기반 고객 니즈"],
  "pain_points": ["녹취록 기반 문제"],
  "objections": ["녹취록 기반 우려/장애물"],
  "next_steps": [
    {{"task": "후속 조치", "owner": "담당자 또는 null", "due": "기한 또는 null"}}
  ],
  "follow_up_message": "후속 메시지 초안",
  "source_refs": [0]
}}"""

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise SalesContactBriefValidationError("AI 응답이 JSON 형식이 아닙니다.") from exc
        if not isinstance(parsed, dict):
            raise SalesContactBriefValidationError("AI 응답 루트는 객체여야 합니다.")
        return parsed

    def _validate_result(self, result: SalesContactBriefResponse) -> None:
        if not result.customer_needs:
            raise SalesContactBriefValidationError("AI 응답에 customer_needs가 없습니다.")
        if not result.next_steps:
            raise SalesContactBriefValidationError("AI 응답에 next_steps가 없습니다.")
        if not result.follow_up_message.strip():
            raise SalesContactBriefValidationError("AI 응답에 follow_up_message가 없습니다.")
