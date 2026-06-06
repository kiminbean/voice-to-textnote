"""
캘린더 서비스 계층
SPEC-REFACTOR-001: calendar 라우터에서 비즈니스 로직 분리

CalendarService는 회의록 데이터 조회, 미팅 정보 추출,
캘린더 이벤트 생성/조회/삭제를 담당한다.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.errors import not_found
from backend.db.models import TaskResult
from backend.schemas.calendar import CalendarEvent
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 캘린더 이벤트 Redis TTL (7일)
_EVENT_TTL_SECONDS = 86400 * 7


class CalendarService:
    """
    캘린더 이벤트 비즈니스 로직 처리

    라우터는 이 서비스를 통해 간접적으로 Redis/DB에 접근한다.
    """

    # 지원되는 캘린더 서비스
    SUPPORTED_CALENDARS = {"google", "outlook", "apple"}

    # --- 조회 ---

    async def get_meeting_data(
        self,
        redis_client: aioredis.Redis,
        db: AsyncSession,
        task_id: str,
    ) -> dict[str, Any] | None:
        """Redis 또는 DB에서 회의 데이터 조회"""
        redis_key = f"task:min:result:{task_id}"
        raw = await redis_client.get(redis_key)
        if raw:
            return json.loads(raw)

        stmt = select(TaskResult).where(
            TaskResult.task_id == task_id,
            TaskResult.task_type == "minutes",
            TaskResult.status == "completed",
        )
        result = await db.execute(stmt)
        record = result.scalars().first()

        if record and record.result_data:
            return record.result_data  # pragma: no cover

        return None

    async def get_event(
        self,
        redis_client: aioredis.Redis,
        task_id: str,
    ) -> dict[str, Any]:
        """
        Redis에서 캘린더 이벤트 조회.

        Raises:
            NotFoundError: 이벤트가 존재하지 않음
        """
        event_key = f"calendar:event:{task_id}"
        raw = await redis_client.get(event_key)

        if not raw:
            not_found(f"캘린더 이벤트를 찾을 수 없습니다. (task_id: {task_id})")

        return json.loads(raw)

    # --- 생성 ---

    def extract_meeting_info(self, meeting_data: dict[str, Any]) -> dict[str, Any]:
        """회의록에서 미팅 정보 추출"""
        segments = meeting_data.get("segments", [])

        info: dict[str, Any] = {
            "title": "회의록",
            "description": "",
            "participants": set(),
            "duration_minutes": 0,
            "action_items": [],
            "key_decisions": [],
            "date": datetime.now().date(),
            "start_time": "09:00",
            "location": "온라인 미팅",
        }

        for segment in segments:
            speaker = segment.get("speaker", "알 수 없음")
            info["participants"].add(speaker)

            text = segment.get("text", "")
            if any(
                kw in text.lower()
                for kw in ("할 일", "해야 할 것", "action", "todo", "task")
            ):
                info["action_items"].append(f"- {text.strip()}")

        info["participants"] = list(info["participants"])

        if segments:
            first_start = segments[0].get("start", 0)
            last_end = segments[-1].get("end", 0)
            info["duration_minutes"] = int((last_end - first_start) / 60)

        return info

    def generate_calendar_event(self, meeting_info: dict[str, Any]) -> CalendarEvent:
        """미팅 정보로 CalendarEvent 객체 생성"""
        event_date = meeting_info["date"]
        start_time = datetime.strptime(meeting_info["start_time"], "%H:%M")
        end_time = start_time + timedelta(minutes=meeting_info["duration_minutes"])

        description_parts = [meeting_info["description"]]

        if meeting_info["action_items"]:
            description_parts.append("\n## 📋 액션 아이템")
            description_parts.extend(meeting_info["action_items"])

        if meeting_info["key_decisions"]:
            description_parts.append("\n## 🎯 주요 결정 사항")
            for i, decision in enumerate(meeting_info["key_decisions"], 1):
                description_parts.append(f"{i}. {decision}")

        if meeting_info["participants"]:
            description_parts.append("\n## 👥 참가자")
            description_parts.append(", ".join(meeting_info["participants"]))

        return CalendarEvent(
            title=meeting_info["title"],
            description="\n".join(description_parts),
            start_datetime=datetime.combine(event_date, start_time.time()),
            end_datetime=datetime.combine(event_date, end_time.time()),
            location=meeting_info["location"],
            participants=meeting_info["participants"],
            action_items=meeting_info["action_items"],
            duration_minutes=meeting_info["duration_minutes"],
            calendar_type="google",
            status="confirmed",
        )

    async def create_and_save_event(
        self,
        redis_client: aioredis.Redis,
        db: AsyncSession,
        task_id: str,
        calendar_type: str,
    ) -> CalendarEvent:
        """
        회의록에서 캘린더 이벤트를 생성하고 Redis에 저장.

        Raises:
            NotFoundError: 회의록 데이터를 찾을 수 없음
        """
        meeting_data = await self.get_meeting_data(redis_client, db, task_id)
        if meeting_data is None:
            not_found(f"회의록 데이터를 찾을 수 없습니다. (task_id: {task_id})")

        meeting_info = self.extract_meeting_info(meeting_data)
        event = self.generate_calendar_event(meeting_info)
        event.calendar_type = calendar_type

        event_key = f"calendar:event:{task_id}"
        event_data = event.model_dump(mode="json")
        await redis_client.setex(event_key, _EVENT_TTL_SECONDS, json.dumps(event_data))

        logger.info("캘린더 이벤트 생성 완료", task_id=task_id, calendar_type=calendar_type)
        return event

    # --- 삭제 ---

    async def delete_event(
        self,
        redis_client: aioredis.Redis,
        task_id: str,
    ) -> bool:
        """
        Redis에서 캘린더 이벤트 삭제.

        Returns:
            True if deleted

        Raises:
            NotFoundError: 이벤트가 존재하지 않음
        """
        event_key = f"calendar:event:{task_id}"
        result = await redis_client.delete(event_key)

        if result == 0:
            not_found(f"캘린더 이벤트를 찾을 수 없습니다. (task_id: {task_id})")

        return True
