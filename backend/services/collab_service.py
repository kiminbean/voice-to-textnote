"""
SPEC-COLLAB-001: 실시간 공동 편집 서비스

Redis에 실시간 문서 상태와 presence를 보관하고,
마지막 참여자 퇴장(또는 debounce 타임아웃) 시 DB에 flush 한다.

Redis 키 구조:
  collab:doc:{task_id}        → Hash {field: json_value}      (문서 본체)
  collab:doc_ts:{task_id}     → Hash {field: iso_timestamp}   (LWW 타임스탬프)
  collab:presence:{task_id}   → Hash {user_id: json_presence} (활성 사용자)
"""

import inspect
import json
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.collab_models import CollabSession
from backend.db.models import TaskResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 최대 동시 편집자 수
MAX_PARTICIPANTS = 5

# Debounce: 마지막 편집 후 이 시간 내 추가 편집이 없으면 DB flush (초)
DEBOUNCE_SECONDS = 3


_ADD_PRESENCE_LUA = """
local count = redis.call('hlen', KEYS[1])
local exists = redis.call('hexists', KEYS[1], ARGV[1])
if exists == 1 then
    redis.call('hset', KEYS[1], ARGV[1], ARGV[2])
    redis.call('expire', KEYS[1], ARGV[4])
    return 1
end
if count >= tonumber(ARGV[3]) then
    return 0
end
redis.call('hset', KEYS[1], ARGV[1], ARGV[2])
redis.call('expire', KEYS[1], ARGV[4])
return 1
"""

_APPLY_EDIT_LUA = """
local existing = redis.call('hget', KEYS[2], ARGV[1])
if existing then
    if ARGV[2] < existing then
        return {0, existing}
    end
end
redis.call('hset', KEYS[1], ARGV[1], ARGV[3])
redis.call('hset', KEYS[2], ARGV[1], ARGV[2])
return {1, ARGV[2]}
"""

# Redis 키 TTL (비활성 세션 자동 정리, 24시간)
SESSION_TTL_SECONDS = 86400


async def _resolve(value: Any) -> Any:
    """Redis test doubles may expose sync values while aioredis returns awaitables."""
    if inspect.isawaitable(value):
        return await value
    return value


def _is_real_redis(redis: Any) -> bool:
    """프로덕션 redis.asyncio.Redis 인스턴스인지 감지 (Lua eval 지원 여부 판단용)."""
    return type(redis).__module__.startswith("redis.")


def _redis_key_doc(task_id: str) -> str:
    return f"collab:doc:{task_id}"


def _redis_key_ts(task_id: str) -> str:
    return f"collab:doc_ts:{task_id}"


def _redis_key_presence(task_id: str) -> str:
    return f"collab:presence:{task_id}"


def _utcnow() -> datetime:
    """timezone-aware UTC 현재 시각."""
    return datetime.now(UTC)


class CollabService:
    """
    실시간 공동 편집 코어 로직.

    ConnectionManager(collab.py)가 이 서비스를 호출하여
    Redis 상태를 조작하고, 필요시 DB에 영속화한다.
    """

    # ------------------------------------------------------------------
    # task_id 검증
    # ------------------------------------------------------------------

    async def _ensure_task_exists(self, session: AsyncSession, task_id: str) -> bool:
        """task_id가 task_results에 존재하는지 확인. 존재하지 않으면 False."""
        stmt = select(TaskResult.id).where(TaskResult.task_id == task_id)
        result = await session.execute(stmt)
        return result.first() is not None

    # ------------------------------------------------------------------
    # Presence (활성 사용자 관리)
    # ------------------------------------------------------------------

    async def add_presence(
        self,
        redis: aioredis.Redis,
        task_id: str,
        user_id: str,
        display_name: str,
        avatar_url: str | None = None,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """
        활성 사용자 추가.

        프로덕션 Redis에서는 Lua script로 원자적 check-and-set을 수행하고,
        Lua eval을 지원하지 않는 테스트 double에서는 기존 check-then-act로 폴백한다.

        Returns:
            (joined, presence_list)
            - joined=False → Room 가득 참 (5명)
            - joined=True → 입장 성공, 현재 전체 presence 목록 반환
        """
        presence_key = _redis_key_presence(task_id)
        presence_data = json.dumps(
            {
                "user_id": user_id,
                "display_name": display_name,
                "avatar_url": avatar_url,
                "active_field": None,
            },
            ensure_ascii=False,
        )

        if _is_real_redis(redis):
            joined_raw = await _resolve(
                redis.eval(
                    _ADD_PRESENCE_LUA,
                    1,
                    presence_key,
                    user_id,
                    presence_data,
                    str(MAX_PARTICIPANTS),
                    str(SESSION_TTL_SECONDS),
                )
            )
            if not joined_raw:
                return False, []
        else:
            already_in = cast(bool, await _resolve(redis.hexists(presence_key, user_id)))
            if not already_in:
                current_count = cast(int, await _resolve(redis.hlen(presence_key)))
                if current_count >= MAX_PARTICIPANTS:
                    return False, []
            await _resolve(redis.hset(presence_key, user_id, presence_data))
            await _resolve(redis.expire(presence_key, SESSION_TTL_SECONDS))

        presence_list = await self.get_presence(redis, task_id)
        return True, presence_list

    async def remove_presence(
        self,
        redis: aioredis.Redis,
        task_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """
        활성 사용자 제거.

        Returns:
            남은 presence 목록 (빈 리스트면 마지막 사용자였음)
        """
        presence_key = _redis_key_presence(task_id)
        await _resolve(redis.hdel(presence_key, user_id))
        return await self.get_presence(redis, task_id)

    async def update_active_field(
        self,
        redis: aioredis.Redis,
        task_id: str,
        user_id: str,
        active_field: str | None,
    ) -> list[dict[str, Any]]:
        """사용자의 현재 편집 필드 업데이트 (cursor presence)."""
        presence_key = _redis_key_presence(task_id)
        raw = cast(str | None, await _resolve(redis.hget(presence_key, user_id)))
        if raw is None:
            return await self.get_presence(redis, task_id)

        data = json.loads(raw)
        data["active_field"] = active_field
        await _resolve(redis.hset(presence_key, user_id, json.dumps(data, ensure_ascii=False)))
        return await self.get_presence(redis, task_id)

    async def get_presence(
        self,
        redis: aioredis.Redis,
        task_id: str,
    ) -> list[dict[str, Any]]:
        """현재 활성 사용자 전체 목록."""
        presence_key = _redis_key_presence(task_id)
        raw_map = cast(dict[str, str], await _resolve(redis.hgetall(presence_key)))
        result: list[dict[str, Any]] = []
        for raw in raw_map.values():
            try:
                result.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid presence data for task_id=%s", task_id)
        return result

    async def get_participant_count(
        self,
        redis: aioredis.Redis,
        task_id: str,
    ) -> int:
        """현재 활성 사용자 수."""
        return cast(int, await _resolve(redis.hlen(_redis_key_presence(task_id))))

    # ------------------------------------------------------------------
    # Document (field-level LWW)
    # ------------------------------------------------------------------

    async def get_document(
        self,
        redis: aioredis.Redis,
        task_id: str,
    ) -> tuple[dict[str, Any], dict[str, datetime]]:
        """
        현재 문서 전체와 필드별 타임스탬프 조회.

        Returns:
            (document, field_timestamps)
        """
        doc_key = _redis_key_doc(task_id)
        ts_key = _redis_key_ts(task_id)

        raw_doc = cast(dict[str, str], await _resolve(redis.hgetall(doc_key)))
        raw_ts = cast(dict[str, str], await _resolve(redis.hgetall(ts_key)))

        document: dict[str, Any] = {}
        for field, raw_value in raw_doc.items():
            try:
                document[field] = json.loads(raw_value)
            except (json.JSONDecodeError, TypeError):
                document[field] = raw_value

        field_timestamps: dict[str, datetime] = {}
        for field, raw_value in raw_ts.items():
            try:
                field_timestamps[field] = datetime.fromisoformat(raw_value)
            except (ValueError, TypeError):
                logger.warning("Invalid timestamp for field=%s task_id=%s", field, task_id)

        return document, field_timestamps

    async def apply_edit(
        self,
        redis: aioredis.Redis,
        task_id: str,
        field: str,
        value: Any,
        client_timestamp: datetime,
    ) -> tuple[bool, datetime]:
        """
        Field-level LWW 편집 적용 (atomic via Lua script on production Redis).

        Returns:
            (applied, stored_timestamp)
            - applied=True → 반영됨, stored_timestamp는 client_timestamp
            - applied=False → 거부됨 (stale), stored_timestamp는 기존값
        """
        doc_key = _redis_key_doc(task_id)
        ts_key = _redis_key_ts(task_id)

        client_ts = client_timestamp
        if client_ts.tzinfo is None:
            client_ts = client_ts.replace(tzinfo=UTC)

        client_ts_str = client_ts.isoformat()
        value_json = json.dumps(value, ensure_ascii=False)

        if _is_real_redis(redis):
            result = await _resolve(
                redis.eval(
                    _APPLY_EDIT_LUA,
                    2,
                    doc_key,
                    ts_key,
                    field,
                    client_ts_str,
                    value_json,
                )
            )
            applied = bool(result[0])
            stored_ts_str = result[1].decode() if isinstance(result[1], bytes) else result[1]
            stored_ts = datetime.fromisoformat(stored_ts_str)
            if stored_ts.tzinfo is None:
                stored_ts = stored_ts.replace(tzinfo=UTC)
            if not applied:
                return False, stored_ts
            return True, stored_ts

        existing_ts_raw = cast(str | None, await _resolve(redis.hget(ts_key, field)))
        if existing_ts_raw is not None:
            try:
                existing_ts = datetime.fromisoformat(existing_ts_raw)
            except (ValueError, TypeError):
                existing_ts = None
        else:
            existing_ts = None

        if existing_ts is not None:
            existing_ts_normalized = existing_ts
            if existing_ts_normalized.tzinfo is None:
                existing_ts_normalized = existing_ts_normalized.replace(tzinfo=UTC)
            if client_ts < existing_ts_normalized:
                return False, existing_ts_normalized

        await _resolve(redis.hset(doc_key, field, value_json))
        await _resolve(redis.hset(ts_key, field, client_ts_str))
        await _resolve(redis.expire(doc_key, SESSION_TTL_SECONDS))
        await _resolve(redis.expire(ts_key, SESSION_TTL_SECONDS))

        return True, client_ts

    async def init_document_from_db(
        self,
        session: AsyncSession,
        redis: aioredis.Redis,
        task_id: str,
    ) -> dict[str, Any]:
        """
        DB에서 최초 문서 스냅샷을 로드하여 Redis에 시드.

        기존 Redis 데이터가 있으면 덮어쓰지 않는다.
        """
        doc_key = _redis_key_doc(task_id)
        ts_key = _redis_key_ts(task_id)

        # 이미 Redis에 데이터가 있으면 스킵
        existing = cast(int, await _resolve(redis.hlen(doc_key)))
        if existing > 0:
            document, _ = await self.get_document(redis, task_id)
            return document

        # DB에서 CollabSession 조회
        stmt = select(CollabSession).where(CollabSession.task_id == task_id)
        result = await session.execute(stmt)
        collab_session = result.scalar_one_or_none()

        if collab_session and collab_session.content:
            now = _utcnow().isoformat()
            for field, value in collab_session.content.items():
                await _resolve(redis.hset(doc_key, field, json.dumps(value, ensure_ascii=False)))
                await _resolve(redis.hset(ts_key, field, now))
            await _resolve(redis.expire(doc_key, SESSION_TTL_SECONDS))
            await _resolve(redis.expire(ts_key, SESSION_TTL_SECONDS))

        document, _ = await self.get_document(redis, task_id)
        return document

    # ------------------------------------------------------------------
    # DB Flush (debounced persistence)
    # ------------------------------------------------------------------

    async def flush_to_db(
        self,
        session: AsyncSession,
        redis: aioredis.Redis,
        task_id: str,
        last_editor_id: uuid.UUID | None = None,
    ) -> CollabSession | None:
        """
        Redis 문서 스냅샷을 DB에 영속화 (upsert).

        활성 참여자가 0명일 때 호출된다.
        """
        document, _ = await self.get_document(redis, task_id)

        stmt = select(CollabSession).where(CollabSession.task_id == task_id)
        result = await session.execute(stmt)
        collab_session = result.scalar_one_or_none()

        presence_count = await self.get_participant_count(redis, task_id)
        peak = max(presence_count, 1)

        if collab_session is None:
            collab_session = CollabSession()
            collab_session.id = uuid.uuid4()
            collab_session.task_id = task_id
            session.add(collab_session)

        collab_session.content = document if document else None
        collab_session.last_editor_id = last_editor_id
        collab_session.peak_participants = max(collab_session.peak_participants or 1, peak)

        await session.commit()
        await session.refresh(collab_session)

        # Redis 데이터 정리 (참여자가 없으므로 세션 종료)
        if presence_count == 0:
            await _resolve(redis.delete(_redis_key_doc(task_id)))
            await _resolve(redis.delete(_redis_key_ts(task_id)))
            await _resolve(redis.delete(_redis_key_presence(task_id)))

        logger.info(
            "Flushed collab session to DB: task_id=%s, fields=%d",
            task_id,
            len(document),
        )
        return collab_session
