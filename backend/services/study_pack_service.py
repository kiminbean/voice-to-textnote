"""Study Pack generation service."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

import redis.asyncio as aioredis
from openai import OpenAI

from backend.app.config import settings
from backend.schemas.study_pack import (
    StudyFlashcard,
    StudyKeyConcept,
    StudyPackMode,
    StudyPackResponse,
    StudyQuizQuestion,
    StudySourceRef,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_STUDY_PACK_KEY_PREFIX = "study_pack:"
_MINUTES_KEY_PREFIX = "task:min:result:"


def _study_pack_cache_key(task_id: str, mode: StudyPackMode) -> str:
    return f"{_STUDY_PACK_KEY_PREFIX}{task_id}:{mode.value}"


class StudyPackSourceNotFoundError(ValueError):
    """Raised when source minutes/transcript content is missing."""


class StudyPackValidationError(ValueError):
    """Raised when generated study pack content cannot be validated."""


class StudyPackService:
    """Generate study artifacts from completed minutes results."""

    def _get_client(self) -> OpenAI:
        return OpenAI(api_key=settings.openai_api_key)

    async def get(
        self,
        task_id: str,
        redis_client: aioredis.Redis,
        *,
        mode: StudyPackMode = StudyPackMode.GENERAL,
    ) -> StudyPackResponse:
        """Load a cached study pack."""
        raw = await redis_client.get(_study_pack_cache_key(task_id, mode))
        if raw is None:
            raise StudyPackSourceNotFoundError("학습팩을 찾을 수 없습니다.")
        return StudyPackResponse.model_validate_json(cast(str | bytes | bytearray, raw))

    async def generate(
        self,
        task_id: str,
        redis_client: aioredis.Redis,
        *,
        mode: StudyPackMode = StudyPackMode.GENERAL,
        language: str = "ko",
        max_tokens: int = 1800,
        force_refresh: bool = False,
    ) -> StudyPackResponse:
        """Generate or return a cached study pack for a minutes task."""
        cache_key = _study_pack_cache_key(task_id, mode)
        if not force_refresh:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return StudyPackResponse.model_validate_json(cast(str | bytes | bytearray, cached))

        minutes_data = await self._load_minutes(task_id, redis_client)
        transcript = self._format_transcript(minutes_data)
        if not transcript.strip():
            raise StudyPackSourceNotFoundError("회의록 내용이 비어 있습니다.")

        source_refs = self._extract_source_refs(minutes_data)
        prompt = self._build_prompt(transcript, mode=mode, language=language)
        client = self._get_client()
        logger.info("Study Pack API 호출", task_id=task_id, mode=mode.value)
        response = client.chat.completions.create(
            model=settings.summary_model,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = response.choices[0].message.content or ""
        payload = self._parse_response(response_text)
        result = StudyPackResponse(
            task_id=task_id,
            mode=mode,
            language=language,
            key_concepts=[
                StudyKeyConcept.model_validate(item)
                for item in payload.get("key_concepts", [])
                if isinstance(item, dict)
            ],
            flashcards=[
                StudyFlashcard.model_validate(item)
                for item in payload.get("flashcards", [])
                if isinstance(item, dict)
            ],
            quiz_questions=[
                StudyQuizQuestion.model_validate(item)
                for item in payload.get("quiz_questions", [])
                if isinstance(item, dict)
            ],
            study_notes=str(payload.get("study_notes", "")),
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
            raise StudyPackSourceNotFoundError(
                "회의록을 찾을 수 없습니다. 처리가 완료되었는지 확인하세요."
            )
        try:
            data = json.loads(cast(str | bytes | bytearray, raw))
        except json.JSONDecodeError as exc:
            raise StudyPackValidationError("회의록 JSON을 해석할 수 없습니다.") from exc
        if not isinstance(data, dict):
            raise StudyPackValidationError("회의록 결과 형식이 올바르지 않습니다.")
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

    def _build_prompt(self, transcript: str, *, mode: StudyPackMode, language: str) -> str:
        return f"""다음 녹취록을 바탕으로 학습팩을 생성하세요.

## 모드
{mode.value}

## 언어
{language}

## 녹취록
{transcript}

## 지시사항
- 반드시 녹취록에 있는 내용만 사용하세요.
- 추측하거나 녹취록 밖의 사실을 추가하지 마세요.
- source_refs에는 근거가 되는 세그먼트 인덱스를 넣으세요.
- 아래 JSON 형식만 출력하세요.

{{
  "key_concepts": [
    {{"term": "핵심 개념", "explanation": "녹취록 기반 설명", "source_refs": [0]}}
  ],
  "flashcards": [
    {{"front": "질문", "back": "정답", "source_refs": [0]}}
  ],
  "quiz_questions": [
    {{"question": "문제", "answer": "정답", "difficulty": "easy", "source_refs": [0]}}
  ],
  "study_notes": "학습 노트"
}}"""

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise StudyPackValidationError("AI 응답이 JSON 형식이 아닙니다.") from exc
        if not isinstance(parsed, dict):
            raise StudyPackValidationError("AI 응답 루트는 객체여야 합니다.")
        return parsed

    def _validate_result(self, result: StudyPackResponse) -> None:
        if not result.key_concepts:
            raise StudyPackValidationError("AI 응답에 key_concepts가 없습니다.")
        if not result.flashcards:
            raise StudyPackValidationError("AI 응답에 flashcards가 없습니다.")
        if not result.quiz_questions:
            raise StudyPackValidationError("AI 응답에 quiz_questions가 없습니다.")
        if not result.study_notes.strip():
            raise StudyPackValidationError("AI 응답에 study_notes가 없습니다.")
