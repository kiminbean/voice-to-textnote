"""
협업 편집 서비스 — LWW 충돌 해결, Redis/인메모리 상태 관리, 디바운스 영속화
SPEC-COLLAB-001: REQ-COLLAB-010~022

# @MX:NOTE: LWW(Last-Writer-Wins) 충돌 해결. 서버 타임스탬프 기준.
#            Redis가 없으면 인메모리 dict로 fallback (테스트/개발용).
"""

from __future__ import annotations

import time
from typing import Any

import redis.asyncio as aioredis

from backend.schemas.collab import CollabUser, EditMessage, FieldState
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class CollabService:
    """
    협업 편집 비즈니스 로직.

    - apply_edit: LWW로 필드 업데이트 + 브로드캐스트 메시지 생성
    - get_sync_state: 현재 room의 전체 필드 상태 반환
    - flush_room: 미저장 편집을 DB 영속화용 dict로 반환
    """

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client
        # 인메모리 fallback: room_id → {field_name → FieldState}
        self._state: dict[str, dict[str, FieldState]] = {}
        # dirty 추적: room_id → {field_name → value}
        self._dirty: dict[str, dict[str, str]] = {}

    # ── 편집 적용 (LWW) ──────────────────────────────────────────────

    async def apply_edit(
        self,
        room_id: str,
        user: CollabUser,
        edit: EditMessage,
    ) -> dict[str, Any]:
        """
        편집을 적용하고 브로드캐스트 메시지를 반환한다.
        LWW: 서버 타임스탬프가 더 늦으면 덮어쓴다.
        """
        now = time.time()

        if room_id not in self._state:
            self._state[room_id] = {}
        if room_id not in self._dirty:
            self._dirty[room_id] = {}

        current = self._state[room_id].get(edit.field)

        # LWW: 기존 타임스탬프보다 새 타임스탬프가 크면 승자
        if current is not None and current.server_ts > now:
            logger.warning(
                "LWW: 과거 편집 무시",
                room_id=room_id,
                field=edit.field,
                existing_ts=current.server_ts,
                incoming_ts=now,
            )
            # 기존 값 유지, 기존 브로드캐스트 반환
            return {
                "type": "edit_broadcast",
                "field": edit.field,
                "value": current.value,
                "user_id": current.user_id,
                "user_name": "",
                "server_ts": current.server_ts,
            }

        new_state = FieldState(
            value=edit.value,
            user_id=user.user_id,
            server_ts=now,
        )
        self._state[room_id][edit.field] = new_state
        self._dirty[room_id][edit.field] = edit.value

        # Redis에도 즉시 저장 (가능한 경우)
        if self._redis is not None:
            try:
                key = f"collab:state:{room_id}"
                await self._redis.hset(key, edit.field, edit.value)
                await self._redis.expire(key, 86400)  # 24h TTL
            except Exception:
                logger.warning("Redis 저장 실패, 인메모리로 대체", room_id=room_id)

        logger.debug(
            "편집 적용",
            room_id=room_id,
            field=edit.field,
            user_id=user.user_id,
            server_ts=now,
        )

        return {
            "type": "edit_broadcast",
            "field": edit.field,
            "value": edit.value,
            "user_id": user.user_id,
            "user_name": user.display_name,
            "server_ts": now,
        }

    # ── 상태 조회 ─────────────────────────────────────────────────────

    async def get_sync_state(self, room_id: str) -> dict[str, FieldState]:
        """room의 전체 필드 상태를 반환한다."""
        return dict(self._state.get(room_id, {}))

    # ── 디바운스 / 영속화 ─────────────────────────────────────────────

    def get_dirty_fields(self, room_id: str) -> dict[str, str]:
        """미저장(dirty) 필드 목록을 반환한다."""
        return dict(self._dirty.get(room_id, {}))

    def clear_dirty_fields(self, room_id: str) -> None:
        """dirty 필드를 초기화한다."""
        self._dirty.pop(room_id, None)

    def has_unpersisted_changes(self, room_id: str) -> bool:
        """미저장 변경사항이 있는지 확인한다."""
        dirty = self._dirty.get(room_id)
        return dirty is not None and len(dirty) > 0

    async def flush_room(self, room_id: str) -> dict[str, str] | None:
        """
        room의 dirty 필드를 flush용 dict로 반환하고 dirty를 초기화.
        실제 DB 저장은 호출자(celery/API)가 수행한다.
        """
        dirty = self._dirty.get(room_id)
        if not dirty:
            return None

        result = dict(dirty)
        self.clear_dirty_fields(room_id)

        logger.info(
            "Room flush",
            room_id=room_id,
            fields=list(result.keys()),
        )
        return result
