"""
회의록 버전 관리 서비스
SPEC-VERSION-001
"""

import difflib
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import TaskResult
from backend.db.version_models import MinutesVersion
from backend.schemas.version import VersionCreate


class VersionService:
    """회의록 버전 CRUD + diff 계산."""

    async def _ensure_task_exists(self, session: AsyncSession, task_id: str) -> None:
        """task_id가 task_results에 존재하는지 확인."""
        stmt = select(TaskResult.id).where(TaskResult.task_id == task_id)
        result = await session.execute(stmt)
        if result.first() is None:
            raise HTTPException(
                status_code=404,
                detail=f"회의록을 찾을 수 없습니다: task_id={task_id}",
            )

    async def _next_version_number(self, session: AsyncSession, task_id: str) -> int:
        """task_id 기준 다음 버전 번호 계산."""
        stmt = select(func.max(MinutesVersion.version_number)).where(
            MinutesVersion.task_id == task_id
        )
        result = await session.execute(stmt)
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1

    async def create_version(
        self,
        session: AsyncSession,
        task_id: str,
        payload: VersionCreate,
        author_id: uuid.UUID | None = None,
    ) -> MinutesVersion:
        """새 버전 스냅샷 저장."""
        await self._ensure_task_exists(session, task_id)
        version_number = await self._next_version_number(session, task_id)

        version = MinutesVersion()
        version.id = uuid.uuid4()
        version.task_id = task_id
        version.version_number = version_number
        version.content = payload.content
        version.change_summary = payload.change_summary
        version.author_id = author_id

        session.add(version)
        await session.commit()
        await session.refresh(version)
        return version

    async def list_versions(
        self,
        session: AsyncSession,
        task_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[MinutesVersion], int]:
        """버전 목록 조회 (최신 버전 우선)."""
        await self._ensure_task_exists(session, task_id)

        count_stmt = select(func.count(MinutesVersion.id)).where(
            MinutesVersion.task_id == task_id
        )
        total = (await session.execute(count_stmt)).scalar_one()

        list_stmt = (
            select(MinutesVersion)
            .where(MinutesVersion.task_id == task_id)
            .order_by(MinutesVersion.version_number.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list((await session.execute(list_stmt)).scalars().all())
        return items, total

    async def get_version(
        self,
        session: AsyncSession,
        task_id: str,
        version_id: uuid.UUID,
    ) -> MinutesVersion:
        """특정 버전 단건 조회."""
        stmt = select(MinutesVersion).where(
            MinutesVersion.task_id == task_id,
            MinutesVersion.id == version_id,
        )
        result = await session.execute(stmt)
        version = result.scalar_one_or_none()
        if version is None:
            raise HTTPException(status_code=404, detail="버전을 찾을 수 없습니다.")
        return version

    def compute_diff(
        self,
        old_content: dict[str, Any],
        new_content: dict[str, Any],
    ) -> dict[str, Any]:
        """두 버전의 텍스트 unified diff 계산.

        회의록 JSON에서 텍스트 필드(summary_text, sections, action_items)를
        추출하여 줄 단위 diff를 생성한다.
        """

        def _flatten(content: dict[str, Any]) -> str:
            parts: list[str] = []
            if isinstance(content.get("summary_text"), str):
                parts.append(content["summary_text"])
            for section in content.get("sections") or []:
                if isinstance(section, dict):
                    if section.get("title"):
                        parts.append(f"[{section['title']}]")
                    if section.get("content"):
                        parts.append(section["content"])
            for item in content.get("action_items") or []:
                if isinstance(item, dict) and item.get("text"):
                    parts.append(f"- {item['text']}")
            return "\n".join(filter(None, parts))

        old_lines = _flatten(old_content).splitlines(keepends=True)
        new_lines = _flatten(new_content).splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))

        added = sum(
            1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
        )
        removed = sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        )

        return {
            "unified_diff": "".join(diff_lines),
            "added_lines": added,
            "removed_lines": removed,
            "changed": added > 0 or removed > 0,
        }

    async def delete_version(
        self,
        session: AsyncSession,
        task_id: str,
        version_id: uuid.UUID,
    ) -> None:
        """버전 삭제."""
        version = await self.get_version(session, task_id, version_id)
        await session.delete(version)
        await session.commit()
