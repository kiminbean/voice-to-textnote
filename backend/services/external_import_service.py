"""External URL/text import service."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.search_models import ensure_search_index_table, index_search_entry
from backend.db.service import ResultService
from backend.schemas.external_import import (
    ExternalImportSourceType,
    ExternalTextImportRequest,
    ExternalTextImportResponse,
)


class ExternalImportValidationError(ValueError):
    """Raised when an external import request cannot be converted to minutes."""


class ExternalImportService:
    """Create minutes-compatible records from user-provided external text."""

    async def import_text(
        self,
        payload: ExternalTextImportRequest,
        db: AsyncSession,
        redis_client: aioredis.Redis,
    ) -> ExternalTextImportResponse:
        """Persist external text as a completed minutes result and index it."""
        content = self._normalize_content(payload.content)
        if not content:
            raise ExternalImportValidationError("가져올 본문이 비어 있습니다.")

        task_id = f"ext-{uuid.uuid4()}"
        now = datetime.now(UTC)
        source_url = str(payload.source_url)
        source_type = self._resolve_source_type(source_url, payload.source_type)
        markdown = self._build_markdown(
            title=payload.title,
            source_url=source_url,
            content=content,
        )
        result_data = self._build_minutes_result(
            task_id=task_id,
            title=payload.title,
            content=content,
            markdown=markdown,
            source_url=source_url,
            source_type=source_type,
            language=payload.language,
            created_at=now,
        )

        await ResultService().save_result(
            db,
            task_id=task_id,
            task_type="minutes",
            status="completed",
            result_data=result_data,
            input_metadata={
                "source": "external_import",
                "source_url": source_url,
                "source_type": source_type.value,
                "language": payload.language,
            },
        )
        await self._cache_result(redis_client, task_id, result_data, now)
        search_indexed = await self._index_result(db, task_id, result_data, now)

        return ExternalTextImportResponse(
            task_id=task_id,
            status="completed",
            title=payload.title,
            source_url=source_url,
            source_type=source_type,
            language=payload.language,
            result_url=f"/api/v1/minutes/{task_id}",
            search_indexed=search_indexed,
        )

    def _normalize_content(self, content: str) -> str:
        lines = [line.strip() for line in content.replace("\r\n", "\n").split("\n")]
        normalized = "\n".join(line for line in lines if line)
        return normalized.strip()

    def _resolve_source_type(
        self,
        source_url: str,
        requested_type: ExternalImportSourceType,
    ) -> ExternalImportSourceType:
        if requested_type != ExternalImportSourceType.WEB:
            return requested_type

        if re.search(r"(^|\.)(youtube\.com|youtu\.be)$", self._hostname(source_url)):
            return ExternalImportSourceType.YOUTUBE

        return requested_type

    def _hostname(self, source_url: str) -> str:
        return source_url.split("//", 1)[-1].split("/", 1)[0].split(":", 1)[0].lower()

    def _build_markdown(self, *, title: str, source_url: str, content: str) -> str:
        return "\n\n".join(
            [
                f"# {title}",
                f"원본: {source_url}",
                "## 가져온 원문",
                content,
            ]
        )

    def _build_minutes_result(
        self,
        *,
        task_id: str,
        title: str,
        content: str,
        markdown: str,
        source_url: str,
        source_type: ExternalImportSourceType,
        language: str,
        created_at: datetime,
    ) -> dict[str, Any]:
        word_count = len(content.split())
        duration = max(float(word_count) * 0.45, 1.0)
        completed_at = datetime.now(UTC)

        return {
            "task_id": task_id,
            "diarization_task_id": task_id,
            "status": "completed",
            "segments": [
                {
                    "speaker_id": "EXTERNAL_SOURCE",
                    "speaker_name": "외부 소스",
                    "text": content,
                    "start": 0.0,
                    "end": duration,
                }
            ],
            "speakers": [
                {
                    "speaker_id": "EXTERNAL_SOURCE",
                    "speaker_name": "외부 소스",
                    "total_speaking_time": duration,
                    "segment_count": 1,
                    "speaking_ratio": 100.0,
                }
            ],
            "total_duration": duration,
            "total_speakers": 1,
            "markdown": markdown,
            "title": title,
            "source": {
                "kind": "external_import",
                "url": source_url,
                "type": source_type.value,
                "language": language,
            },
            "created_at": created_at.isoformat(),
            "completed_at": completed_at.isoformat(),
        }

    async def _cache_result(
        self,
        redis_client: aioredis.Redis,
        task_id: str,
        result_data: dict[str, Any],
        created_at: datetime,
    ) -> None:
        import json

        status_data = {
            "task_id": task_id,
            "status": "completed",
            "progress": 1.0,
            "message": "외부 텍스트 가져오기 완료",
            "created_at": created_at.isoformat(),
            "updated_at": result_data["completed_at"],
        }
        await redis_client.setex(
            f"task:min:status:{task_id}",
            settings.minutes_result_ttl,
            json.dumps(status_data, ensure_ascii=False),
        )
        await redis_client.setex(
            f"task:min:result:{task_id}",
            settings.minutes_result_ttl,
            json.dumps(result_data, ensure_ascii=False),
        )

    async def _index_result(
        self,
        db: AsyncSession,
        task_id: str,
        result_data: dict[str, Any],
        created_at: datetime,
    ) -> bool:
        try:
            await db.run_sync(
                lambda sync_session: ensure_search_index_table(sync_session.connection())
            )
            await db.run_sync(
                lambda sync_session: index_search_entry(
                    sync_session,
                    task_id=task_id,
                    task_type="minutes",
                    result_data=result_data,
                    created_at=created_at.replace(tzinfo=None),
                )
            )
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            return False
