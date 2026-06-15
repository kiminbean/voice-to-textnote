"""
회의록 버전 관리 서비스
SPEC-VERSION-001
"""

import difflib
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
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
        """새 버전 스냅샷 저장 (동시 생성 시 IntegrityError catch-and-retry)."""
        await self._ensure_task_exists(session, task_id)

        for attempt in range(3):
            version_number = await self._next_version_number(session, task_id)
            version = MinutesVersion()
            version.id = uuid.uuid4()
            version.task_id = task_id
            version.version_number = version_number
            version.content = payload.content
            version.change_summary = payload.change_summary
            version.author_id = author_id

            session.add(version)
            try:
                await session.commit()
                await session.refresh(version)
                return version
            except IntegrityError:
                await session.rollback()
                if attempt == 2:
                    raise HTTPException(
                        status_code=409,
                        detail="버전 생성 충돌이 발생했습니다. 다시 시도해 주세요.",
                    )
        raise HTTPException(status_code=500, detail="버전 생성 재시도 한도 초과")

    async def list_versions(
        self,
        session: AsyncSession,
        task_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[MinutesVersion], int]:
        """버전 목록 조회 (최신 버전 우선)."""
        await self._ensure_task_exists(session, task_id)

        count_stmt = select(func.count(MinutesVersion.id)).where(MinutesVersion.task_id == task_id)
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

        added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        )

        return {
            "unified_diff": "".join(diff_lines),
            "added_lines": added,
            "removed_lines": removed,
            "changed": added > 0 or removed > 0,
        }

    @staticmethod
    def _normalize_sections(content: dict[str, Any]) -> dict[str, str]:
        """sections 배열을 {title: content_text} 매핑으로 정규화."""
        sections: dict[str, str] = {}
        for section in content.get("sections") or []:
            if not isinstance(section, dict):
                continue
            title = (section.get("title") or "").strip()
            if not title:
                continue
            body = section.get("content")
            sections[title] = str(body) if body is not None else ""
        return sections

    @staticmethod
    def _action_item_key(item: dict[str, Any]) -> str:
        """action_items 매칭에 사용할 안정 키. id 우선, 없으면 text."""
        if isinstance(item.get("id"), str | int):
            return f"id:{item['id']}"
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            return f"text:{text.strip()}"
        return f"hash:{hash(frozenset((k, str(v)) for k, v in item.items()))}"

    @classmethod
    def _normalize_action_items(cls, content: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """action_items를 {key: item_dict}로 정규화."""
        items: dict[str, dict[str, Any]] = {}
        for raw in content.get("action_items") or []:
            if not isinstance(raw, dict):
                continue
            items[cls._action_item_key(raw)] = raw
        return items

    def compute_structured_diff(
        self,
        old_content: dict[str, Any],
        new_content: dict[str, Any],
    ) -> dict[str, Any]:
        """회의록 JSON 구조 기반 diff 계산.

        summary_text, sections(title 매칭), action_items(id/text 매칭)을
        added/removed/modified로 분리한다. 라이브러리 diff 의존을 제거하여
        프런트에서 곧바로 UI 렌더링이 가능한 형태를 반환한다.
        """
        # summary_text -------------------------------------------------------
        old_summary = (
            old_content.get("summary_text")
            if isinstance(old_content.get("summary_text"), str)
            else None
        )
        new_summary = (
            new_content.get("summary_text")
            if isinstance(new_content.get("summary_text"), str)
            else None
        )
        summary_changed = (old_summary or "") != (new_summary or "")

        # sections -----------------------------------------------------------
        old_sections = self._normalize_sections(old_content)
        new_sections = self._normalize_sections(new_content)
        added_sections: list[dict[str, Any]] = []
        removed_sections: list[dict[str, Any]] = []
        modified_sections: list[dict[str, Any]] = []
        for title, body in new_sections.items():
            if title not in old_sections:
                added_sections.append(
                    {"title": title, "before_content": None, "after_content": body}
                )
            elif old_sections[title] != body:
                modified_sections.append(
                    {
                        "title": title,
                        "before_content": old_sections[title],
                        "after_content": body,
                    }
                )
        for title, body in old_sections.items():
            if title not in new_sections:
                removed_sections.append(
                    {"title": title, "before_content": body, "after_content": None}
                )

        # action_items -------------------------------------------------------
        old_items = self._normalize_action_items(old_content)
        new_items = self._normalize_action_items(new_content)
        added_items: list[dict[str, Any]] = []
        removed_items: list[dict[str, Any]] = []
        modified_items: list[dict[str, Any]] = []
        for key, item in new_items.items():
            if key not in old_items:
                added_items.append({"key": key, "before": None, "after": item})
            elif old_items[key] != item:
                modified_items.append({"key": key, "before": old_items[key], "after": item})
        for key, item in old_items.items():
            if key not in new_items:
                removed_items.append({"key": key, "before": item, "after": None})

        total_changes = (
            (1 if summary_changed else 0)
            + len(added_sections)
            + len(removed_sections)
            + len(modified_sections)
            + len(added_items)
            + len(removed_items)
            + len(modified_items)
        )

        return {
            "summary_text": {
                "changed": summary_changed,
                "before": old_summary,
                "after": new_summary,
            },
            "sections": {
                "added": added_sections,
                "removed": removed_sections,
                "modified": modified_sections,
            },
            "action_items": {
                "added": added_items,
                "removed": removed_items,
                "modified": modified_items,
            },
            "total_changes": total_changes,
            "changed": total_changes > 0,
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
