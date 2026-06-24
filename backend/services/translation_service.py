"""Artifact translation service for minutes and summaries."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.models import TaskResult
from backend.schemas.translation import TranslationResponse, TranslationSourceType
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class TranslationSourceNotFoundError(ValueError):
    """Raised when a task result or cached translation is missing."""


class TranslationValidationError(ValueError):
    """Raised when source or model output cannot be used."""


class TranslationService:
    """Translate persisted minutes or summary content."""

    def _get_client(self) -> OpenAI:
        return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    async def get(
        self,
        task_id: str,
        db: AsyncSession,
        *,
        target_language: str,
        source_type: TranslationSourceType = TranslationSourceType.AUTO,
    ) -> TranslationResponse:
        """Load a cached translation from task result metadata."""
        record = await self._load_record(task_id, db)
        cached = self._get_cached(record.result_data or {}, target_language, source_type)
        if cached is None:
            raise TranslationSourceNotFoundError("번역 결과를 찾을 수 없습니다.")
        return TranslationResponse.model_validate({**cached, "cached": True})

    async def translate(
        self,
        task_id: str,
        db: AsyncSession,
        *,
        target_language: str,
        source_language: str | None = None,
        source_type: TranslationSourceType = TranslationSourceType.AUTO,
        max_tokens: int = 2400,
        force_refresh: bool = False,
    ) -> TranslationResponse:
        """Generate or return a cached translation for a completed task."""
        record = await self._load_record(task_id, db)
        result_data = record.result_data or {}
        if not force_refresh:
            cached = self._get_cached(result_data, target_language, source_type)
            if cached is not None:
                return TranslationResponse.model_validate({**cached, "cached": True})

        resolved_type, source_text = self._extract_source_text(result_data, source_type)
        prompt = self._build_prompt(
            source_text,
            target_language=target_language,
            source_language=source_language,
            source_type=resolved_type,
        )
        client = self._get_client()
        logger.info(
            "Translation API 호출",
            task_id=task_id,
            source_type=resolved_type.value,
            target_language=target_language,
        )
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=settings.summary_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        translated_text = (response.choices[0].message.content or "").strip()
        if not translated_text:
            raise TranslationValidationError("AI 번역 응답이 비어 있습니다.")

        result = TranslationResponse(
            task_id=task_id,
            source_type=resolved_type,
            source_language=source_language,
            target_language=target_language,
            translated_text=translated_text,
            source_excerpt=source_text[:500],
            cached=False,
            created_at=datetime.now(UTC).isoformat(),
        )
        await self._persist_translation(record, db, result)
        return result

    async def _load_record(self, task_id: str, db: AsyncSession) -> TaskResult:
        stmt = select(TaskResult).where(TaskResult.task_id == task_id)
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None or record.result_data is None:
            raise TranslationSourceNotFoundError("회의록 또는 요약 결과를 찾을 수 없습니다.")
        return record

    def _get_cached(
        self,
        result_data: dict[str, Any],
        target_language: str,
        source_type: TranslationSourceType,
    ) -> dict[str, Any] | None:
        translations = result_data.get("translations")
        if not isinstance(translations, dict):
            return None
        target_key = self._language_key(target_language)
        if source_type is TranslationSourceType.AUTO:
            cached = translations.get(target_key)
        else:
            cached = translations.get(f"{source_type.value}:{target_key}")
        return cached if isinstance(cached, dict) else None

    def _extract_source_text(
        self,
        result_data: dict[str, Any],
        source_type: TranslationSourceType,
    ) -> tuple[TranslationSourceType, str]:
        if source_type is TranslationSourceType.SUMMARY:
            return source_type, self._extract_summary_text(result_data)
        if source_type is TranslationSourceType.MINUTES:
            return source_type, self._extract_minutes_text(result_data)

        summary_text = self._extract_summary_text(result_data, required=False)
        if summary_text:
            return TranslationSourceType.SUMMARY, summary_text
        return TranslationSourceType.MINUTES, self._extract_minutes_text(result_data)

    def _extract_summary_text(self, result_data: dict[str, Any], *, required: bool = True) -> str:
        candidates = [
            result_data.get("summary_text"),
            result_data.get("summary"),
            result_data.get("markdown"),
            result_data.get("text"),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        if required:
            raise TranslationValidationError("번역할 요약 텍스트가 비어 있습니다.")
        return ""

    def _extract_minutes_text(self, result_data: dict[str, Any]) -> str:
        segments = result_data.get("segments")
        if isinstance(segments, list) and segments:
            lines: list[str] = []
            for index, segment in enumerate(segments):
                if not isinstance(segment, dict):
                    continue
                text = str(segment.get("text", "")).strip()
                if not text:
                    continue
                speaker = segment.get("speaker_name") or segment.get("speaker")
                start = segment.get("start")
                prefix_parts = [str(index)]
                if start is not None:
                    prefix_parts.append(f"{start}s")
                if speaker:
                    prefix_parts.append(str(speaker))
                lines.append(f"[{' | '.join(prefix_parts)}] {text}")
            if lines:
                return "\n".join(lines)

        for key in ("raw_text", "text", "transcript", "markdown"):
            value = result_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise TranslationValidationError("번역할 회의록 텍스트가 비어 있습니다.")

    def _build_prompt(
        self,
        source_text: str,
        *,
        target_language: str,
        source_language: str | None,
        source_type: TranslationSourceType,
    ) -> str:
        source_language_line = source_language or "auto-detect"
        return f"""Translate the following {source_type.value} artifact.

Source language: {source_language_line}
Target language: {target_language}

Rules:
- Translate only the provided source text.
- Preserve speaker labels, timestamps, markdown headings, bullets, and line breaks where possible.
- Do not add summaries, explanations, or facts that are not present in the source.
- Return only the translated text.

Source:
{source_text}"""

    async def _persist_translation(
        self,
        record: TaskResult,
        db: AsyncSession,
        result: TranslationResponse,
    ) -> None:
        result_data = dict(record.result_data or {})
        translations = result_data.get("translations")
        if not isinstance(translations, dict):
            translations = {}
        target_key = self._language_key(result.target_language)
        payload = result.model_dump(mode="json")
        translations[target_key] = payload
        translations[f"{result.source_type.value}:{target_key}"] = payload
        result_data["translations"] = translations
        record.result_data = result_data
        await db.commit()

    def _language_key(self, language: str) -> str:
        return language.strip().lower()
