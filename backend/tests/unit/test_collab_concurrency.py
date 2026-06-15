"""
SPEC-BUGFIX-002 REQ-BF2-002: collab_service race condition 근본 해결 검증.

Lua script 기반 atomic check-and-set이 MAX_PARTICIPANTS 초과를 방지하는지 확인.
fakeredis가 eval을 지원하지 않으므로, _is_real_redis 폴백 경로의 동시성을 검증한다.
프로덕션 Redis 환경에서는 Lua script가 추가 보장한다.
"""
import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from backend.services.collab_service import MAX_PARTICIPANTS, CollabService

pytestmark = pytest.mark.asyncio


async def _make_mock_redis() -> AsyncMock:
    store: dict[str, dict[str, str]] = {}

    redis = AsyncMock()

    async def _hset(key, field, value):
        store.setdefault(key, {})[field] = value

    async def _hget(key, field):
        return store.get(key, {}).get(field)

    async def _hgetall(key):
        return dict(store.get(key, {}))

    async def _hexists(key, field):
        return field in store.get(key, {})

    async def _hlen(key):
        return len(store.get(key, {}))

    async def _hdel(key, field):
        return store.get(key, {}).pop(field, None) is not None

    async def _expire(key, ttl):
        return True

    redis.hset = AsyncMock(side_effect=_hset)
    redis.hget = AsyncMock(side_effect=_hget)
    redis.hgetall = AsyncMock(side_effect=_hgetall)
    redis.hexists = AsyncMock(side_effect=_hexists)
    redis.hlen = AsyncMock(side_effect=_hlen)
    redis.hdel = AsyncMock(side_effect=_hdel)
    redis.expire = AsyncMock(side_effect=_expire)
    redis.delete = AsyncMock(return_value=1)
    return redis


class TestAddPresenceConcurrency:
    """REQ-BF2-002: 동시 add_presence 호출 시 MAX_PARTICIPANTS 위반 여부."""

    async def test_concurrent_add_presence_respects_limit(self):
        """10명 동시 입장 시도 → MAX_PARTICIPANTS(5) 초과하지 않아야 함."""
        svc = CollabService()
        redis = await _make_mock_redis()
        task_id = "test-concurrent-task"

        async def try_join(user_id: str) -> bool:
            joined, _ = await svc.add_presence(redis, task_id, user_id, user_id)
            return joined

        tasks = [try_join(f"user_{i}") for i in range(MAX_PARTICIPANTS + 5)]
        results = await asyncio.gather(*tasks)

        joined_count = sum(1 for r in results if r)
        assert joined_count <= MAX_PARTICIPANTS, (
            f"MAX_PARTICIPANTS 초과: {joined_count} > {MAX_PARTICIPANTS}"
        )

    async def test_rejoin_existing_user_always_succeeds(self):
        """이미 참여한 사용자는 MAX_PARTICIPANTS와 무관하게 재입장 가능."""
        svc = CollabService()
        redis = await _make_mock_redis()
        task_id = "test-rejoin-task"

        for i in range(MAX_PARTICIPANTS):
            joined, _ = await svc.add_presence(redis, task_id, f"user_{i}", f"user_{i}")
            assert joined

        joined, _ = await svc.add_presence(redis, task_id, "user_0", "user_0")
        assert joined


class TestApplyEditLWW:
    """REQ-BF2-002: LWW 타임스탬프 비교 검증."""

    async def test_stale_edit_rejected(self):
        """과거 타임스탬프의 편집은 거부되어야 함."""
        svc = CollabService()
        redis = await _make_mock_redis()
        task_id = "test-lww-task"

        newer_ts = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
        applied, stored = await svc.apply_edit(redis, task_id, "field1", "new_value", newer_ts)
        assert applied
        assert stored == newer_ts

        older_ts = datetime(2026, 6, 15, 11, 0, 0, tzinfo=UTC)
        applied, stored = await svc.apply_edit(redis, task_id, "field1", "stale_value", older_ts)
        assert not applied
        assert stored == newer_ts

    async def test_newer_edit_accepted(self):
        """최신 타임스탬프의 편집은 수락되어야 함."""
        svc = CollabService()
        redis = await _make_mock_redis()
        task_id = "test-lww-newer-task"

        ts1 = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
        await svc.apply_edit(redis, task_id, "field1", "value1", ts1)

        ts2 = datetime(2026, 6, 15, 13, 0, 0, tzinfo=UTC)
        applied, stored = await svc.apply_edit(redis, task_id, "field1", "value2", ts2)
        assert applied
        assert stored == ts2

    async def test_equal_timestamp_accepted(self):
        """동일 타임스탬프는 last-writer-wins로 수락."""
        svc = CollabService()
        redis = await _make_mock_redis()
        task_id = "test-lww-equal-task"

        ts = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
        await svc.apply_edit(redis, task_id, "field1", "first", ts)

        applied, _ = await svc.apply_edit(redis, task_id, "field1", "second", ts)
        assert applied
