"""
CollabService 단위 테스트
SPEC-COLLAB-001: 실시간 공동 편집 서비스 (LWW, Presence, DB flush)
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.collab_service import (
    MAX_PARTICIPANTS,
    CollabService,
    _redis_key_doc,
    _redis_key_presence,
    _redis_key_ts,
    _resolve,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def collab_service():
    return CollabService()


@pytest.fixture
def mock_redis():
    """In-memory FakeRedis-like mock for hash operations."""
    redis = AsyncMock()
    # Simulate hash storage
    _hashes: dict[str, dict[str, str]] = {}
    _ttls: dict[str, int] = {}

    async def _hset(key, field=None, value=None, mapping=None):
        if mapping:
            _hashes.setdefault(key, {}).update(mapping)
            return len(mapping)
        if field is not None:
            _hashes.setdefault(key, {})[field] = value
            return 1
        return 0

    async def _hget(key, field):
        return _hashes.get(key, {}).get(field)

    async def _hgetall(key):
        return dict(_hashes.get(key, {}))

    async def _hlen(key):
        return len(_hashes.get(key, {}))

    async def _hexists(key, field):
        return field in _hashes.get(key, {})

    async def _hdel(key, *fields):
        h = _hashes.get(key, {})
        deleted = 0
        for f in fields:
            if f in h:
                del h[f]
                deleted += 1
        return deleted

    async def _expire(key, seconds):
        _ttls[key] = seconds
        return True

    async def _delete(*keys):
        deleted = 0
        for key in keys:
            if key in _hashes:
                del _hashes[key]
                deleted += 1
        return deleted

    redis.hset = _hset
    redis.hget = _hget
    redis.hgetall = _hgetall
    redis.hlen = _hlen
    redis.hexists = _hexists
    redis.hdel = _hdel
    redis.expire = _expire
    redis.delete = _delete

    # Expose internal state for test assertions
    redis._hashes = _hashes
    return redis


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()  # session.add() is synchronous in SQLAlchemy
    return session


@pytest.fixture
def sample_task_id():
    return "task-abc-123"


@pytest.fixture
def sample_user_id():
    return str(uuid.uuid4())


@pytest.fixture
def now_utc():
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# _ensure_task_exists
# ---------------------------------------------------------------------------


class TestEnsureTaskExists:
    @pytest.mark.asyncio
    async def test_task_exists(self, collab_service, mock_db_session, sample_task_id):
        mock_result = MagicMock()
        mock_result.first.return_value = ("some-id",)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await collab_service._ensure_task_exists(mock_db_session, sample_task_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_task_not_exists(self, collab_service, mock_db_session, sample_task_id):
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await collab_service._ensure_task_exists(mock_db_session, sample_task_id)
        assert result is False


# ---------------------------------------------------------------------------
# Presence
# ---------------------------------------------------------------------------


class TestAddPresence:
    @pytest.mark.asyncio
    async def test_add_first_user(self, collab_service, mock_redis, sample_task_id, sample_user_id):
        joined, presence = await collab_service.add_presence(
            mock_redis, sample_task_id, sample_user_id, "Alice"
        )
        assert joined is True
        assert len(presence) == 1
        assert presence[0]["display_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_add_same_user_idempotent(
        self, collab_service, mock_redis, sample_task_id, sample_user_id
    ):
        await collab_service.add_presence(mock_redis, sample_task_id, sample_user_id, "Alice")
        joined, presence = await collab_service.add_presence(
            mock_redis, sample_task_id, sample_user_id, "Alice"
        )
        assert joined is True
        assert len(presence) == 1

    @pytest.mark.asyncio
    async def test_add_multiple_users(self, collab_service, mock_redis, sample_task_id):
        for i in range(3):
            joined, _ = await collab_service.add_presence(
                mock_redis, sample_task_id, f"user-{i}", f"User{i}"
            )
            assert joined is True
        _, presence = await collab_service.add_presence(
            mock_redis, sample_task_id, "user-3", "User3"
        )
        assert len(presence) == 4

    @pytest.mark.asyncio
    async def test_room_full_rejects_new_user(self, collab_service, mock_redis, sample_task_id):
        for i in range(MAX_PARTICIPANTS):
            await collab_service.add_presence(mock_redis, sample_task_id, f"user-{i}", f"User{i}")
        joined, presence = await collab_service.add_presence(
            mock_redis, sample_task_id, "overflow-user", "Overflow"
        )
        assert joined is False
        assert presence == []

    @pytest.mark.asyncio
    async def test_real_redis_lua_success_returns_presence(
        self, collab_service, sample_task_id, sample_user_id
    ):
        class FakeRealRedis:
            __module__ = "redis.asyncio.client"

            async def eval(self, *_args):
                return 1

            async def hgetall(self, _key):
                return {
                    sample_user_id: (
                        f'{{"user_id":"{sample_user_id}","display_name":"Alice",'
                        '"avatar_url":null,"active_field":null}'
                    )
                }

        joined, presence = await collab_service.add_presence(
            FakeRealRedis(), sample_task_id, sample_user_id, "Alice"
        )

        assert joined is True
        assert presence == [
            {
                "user_id": sample_user_id,
                "display_name": "Alice",
                "avatar_url": None,
                "active_field": None,
            }
        ]

    @pytest.mark.asyncio
    async def test_real_redis_lua_rejects_full_room(self, collab_service, sample_task_id):
        class FakeRealRedis:
            __module__ = "redis.asyncio.client"

            def eval(self, *_args):
                return 0

        joined, presence = await collab_service.add_presence(
            FakeRealRedis(), sample_task_id, "overflow", "Overflow"
        )

        assert joined is False
        assert presence == []


class TestRemovePresence:
    @pytest.mark.asyncio
    async def test_remove_returns_remaining(self, collab_service, mock_redis, sample_task_id):
        await collab_service.add_presence(mock_redis, sample_task_id, "u1", "Alice")
        await collab_service.add_presence(mock_redis, sample_task_id, "u2", "Bob")
        remaining = await collab_service.remove_presence(mock_redis, sample_task_id, "u1")
        assert len(remaining) == 1
        assert remaining[0]["display_name"] == "Bob"

    @pytest.mark.asyncio
    async def test_remove_last_returns_empty(
        self, collab_service, mock_redis, sample_task_id, sample_user_id
    ):
        await collab_service.add_presence(mock_redis, sample_task_id, sample_user_id, "Alice")
        remaining = await collab_service.remove_presence(mock_redis, sample_task_id, sample_user_id)
        assert remaining == []


class TestUpdateActiveField:
    @pytest.mark.asyncio
    async def test_update_active_field(
        self, collab_service, mock_redis, sample_task_id, sample_user_id
    ):
        await collab_service.add_presence(mock_redis, sample_task_id, sample_user_id, "Alice")
        result = await collab_service.update_active_field(
            mock_redis, sample_task_id, sample_user_id, "summary_text"
        )
        assert len(result) == 1
        assert result[0]["active_field"] == "summary_text"

    @pytest.mark.asyncio
    async def test_update_nonexistent_user_returns_current(
        self, collab_service, mock_redis, sample_task_id
    ):
        result = await collab_service.update_active_field(
            mock_redis, sample_task_id, "ghost", "field"
        )
        assert result == []


class TestGetPresence:
    @pytest.mark.asyncio
    async def test_empty_presence(self, collab_service, mock_redis, sample_task_id):
        result = await collab_service.get_presence(mock_redis, sample_task_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_presence_order(self, collab_service, mock_redis, sample_task_id):
        await collab_service.add_presence(mock_redis, sample_task_id, "u1", "A")
        await collab_service.add_presence(mock_redis, sample_task_id, "u2", "B")
        result = await collab_service.get_presence(mock_redis, sample_task_id)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_invalid_presence_payloads_are_skipped(
        self, collab_service, mock_redis, sample_task_id
    ):
        presence_key = _redis_key_presence(sample_task_id)
        mock_redis._hashes[presence_key] = {
            "bad-json": "{not-json",
            "wrong-type": None,
        }

        result = await collab_service.get_presence(mock_redis, sample_task_id)

        assert result == []


class TestGetParticipantCount:
    @pytest.mark.asyncio
    async def test_zero(self, collab_service, mock_redis, sample_task_id):
        count = await collab_service.get_participant_count(mock_redis, sample_task_id)
        assert count == 0

    @pytest.mark.asyncio
    async def test_three(self, collab_service, mock_redis, sample_task_id):
        for i in range(3):
            await collab_service.add_presence(mock_redis, sample_task_id, f"u{i}", f"U{i}")
        count = await collab_service.get_participant_count(mock_redis, sample_task_id)
        assert count == 3


# ---------------------------------------------------------------------------
# Document (field-level LWW)
# ---------------------------------------------------------------------------


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_empty_document(self, collab_service, mock_redis, sample_task_id):
        doc, ts = await collab_service.get_document(mock_redis, sample_task_id)
        assert doc == {}
        assert ts == {}

    @pytest.mark.asyncio
    async def test_returns_stored_data(self, collab_service, mock_redis, sample_task_id, now_utc):
        await collab_service.apply_edit(
            mock_redis, sample_task_id, "summary_text", "Hello", now_utc
        )
        doc, ts = await collab_service.get_document(mock_redis, sample_task_id)
        assert doc["summary_text"] == "Hello"
        assert "summary_text" in ts

    @pytest.mark.asyncio
    async def test_invalid_document_json_and_timestamp_fall_back(
        self, collab_service, mock_redis, sample_task_id
    ):
        mock_redis._hashes[_redis_key_doc(sample_task_id)] = {
            "raw": "{bad-json",
            "none": None,
        }
        mock_redis._hashes[_redis_key_ts(sample_task_id)] = {
            "raw": "not-a-date",
            "none": None,
        }

        doc, ts = await collab_service.get_document(mock_redis, sample_task_id)

        assert doc == {"raw": "{bad-json", "none": None}
        assert ts == {}


class TestApplyEdit:
    @pytest.mark.asyncio
    async def test_first_edit_applied(self, collab_service, mock_redis, sample_task_id, now_utc):
        applied, server_ts = await collab_service.apply_edit(
            mock_redis, sample_task_id, "summary_text", "Hello", now_utc
        )
        assert applied is True
        assert server_ts is not None

    @pytest.mark.asyncio
    async def test_newer_edit_applied(self, collab_service, mock_redis, sample_task_id):
        old_ts = datetime(2025, 1, 1, tzinfo=UTC)
        new_ts = datetime(2025, 6, 13, tzinfo=UTC)

        await collab_service.apply_edit(mock_redis, sample_task_id, "f1", "old", old_ts)
        applied, _ = await collab_service.apply_edit(
            mock_redis, sample_task_id, "f1", "new", new_ts
        )
        assert applied is True

        doc, _ = await collab_service.get_document(mock_redis, sample_task_id)
        assert doc["f1"] == "new"

    @pytest.mark.asyncio
    async def test_stale_edit_rejected(self, collab_service, mock_redis, sample_task_id):
        old_ts = datetime(2025, 1, 1, tzinfo=UTC)
        new_ts = datetime(2025, 6, 13, tzinfo=UTC)

        await collab_service.apply_edit(mock_redis, sample_task_id, "f1", "new", new_ts)
        applied, returned_ts = await collab_service.apply_edit(
            mock_redis, sample_task_id, "f1", "stale", old_ts
        )
        assert applied is False

        doc, _ = await collab_service.get_document(mock_redis, sample_task_id)
        assert doc["f1"] == "new"

    @pytest.mark.asyncio
    async def test_equal_timestamp_applied(
        self, collab_service, mock_redis, sample_task_id, now_utc
    ):
        await collab_service.apply_edit(mock_redis, sample_task_id, "f1", "v1", now_utc)
        applied, _ = await collab_service.apply_edit(
            mock_redis, sample_task_id, "f1", "v2", now_utc
        )
        assert applied is True

    @pytest.mark.asyncio
    async def test_naive_timestamp_treated_as_utc(self, collab_service, mock_redis, sample_task_id):
        naive_ts = datetime(2025, 6, 13, 12, 0, 0)
        applied, _ = await collab_service.apply_edit(
            mock_redis, sample_task_id, "f1", "val", naive_ts
        )
        assert applied is True

    @pytest.mark.asyncio
    async def test_different_fields_independent(
        self, collab_service, mock_redis, sample_task_id, now_utc
    ):
        await collab_service.apply_edit(mock_redis, sample_task_id, "f1", "v1", now_utc)
        older = now_utc - timedelta(hours=1)
        applied, _ = await collab_service.apply_edit(mock_redis, sample_task_id, "f2", "v2", older)
        assert applied is True  # f2 has no prior timestamp

    @pytest.mark.asyncio
    async def test_complex_value_serialized(
        self, collab_service, mock_redis, sample_task_id, now_utc
    ):
        complex_val = {"nested": [1, 2, {"key": "value"}]}
        await collab_service.apply_edit(
            mock_redis, sample_task_id, "sections", complex_val, now_utc
        )
        doc, _ = await collab_service.get_document(mock_redis, sample_task_id)
        assert doc["sections"] == complex_val

    @pytest.mark.asyncio
    async def test_existing_naive_timestamp_is_normalized_before_stale_compare(
        self, collab_service, mock_redis, sample_task_id
    ):
        mock_redis._hashes[_redis_key_ts(sample_task_id)] = {"f1": "2025-06-13T12:00:00"}
        older = datetime(2025, 6, 13, 11, 0, 0, tzinfo=UTC)

        applied, stored_ts = await collab_service.apply_edit(
            mock_redis, sample_task_id, "f1", "stale", older
        )

        assert applied is False
        assert stored_ts == datetime(2025, 6, 13, 12, 0, 0, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_invalid_existing_timestamp_is_ignored(
        self, collab_service, mock_redis, sample_task_id
    ):
        mock_redis._hashes[_redis_key_ts(sample_task_id)] = {"f1": "not-a-date"}
        client_ts = datetime(2025, 6, 13, 12, 0, 0, tzinfo=UTC)

        applied, stored_ts = await collab_service.apply_edit(
            mock_redis, sample_task_id, "f1", "value", client_ts
        )

        assert applied is True
        assert stored_ts == client_ts

    @pytest.mark.asyncio
    async def test_real_redis_lua_rejects_stale_edit_with_bytes_timestamp(
        self, collab_service, sample_task_id
    ):
        stored_ts = "2025-06-13T12:00:00"

        class FakeRealRedis:
            __module__ = "redis.asyncio.client"

            async def eval(self, *_args):
                return [0, stored_ts.encode()]

        applied, returned_ts = await collab_service.apply_edit(
            FakeRealRedis(),
            sample_task_id,
            "f1",
            "stale",
            datetime(2025, 6, 13, 11, 0, 0, tzinfo=UTC),
        )

        assert applied is False
        assert returned_ts == datetime(2025, 6, 13, 12, 0, 0, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_real_redis_lua_applies_edit_with_string_timestamp(
        self, collab_service, sample_task_id
    ):
        stored_ts = "2025-06-13T12:00:00+00:00"

        class FakeRealRedis:
            __module__ = "redis.asyncio.client"

            def eval(self, *_args):
                return [1, stored_ts]

        applied, returned_ts = await collab_service.apply_edit(
            FakeRealRedis(),
            sample_task_id,
            "f1",
            "new",
            datetime(2025, 6, 13, 12, 0, 0, tzinfo=UTC),
        )

        assert applied is True
        assert returned_ts == datetime(2025, 6, 13, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# init_document_from_db
# ---------------------------------------------------------------------------


class TestInitDocumentFromDB:
    @pytest.mark.asyncio
    async def test_skip_if_redis_has_data(
        self, collab_service, mock_redis, mock_db_session, sample_task_id, now_utc
    ):
        await collab_service.apply_edit(mock_redis, sample_task_id, "f1", "redis_val", now_utc)
        # Should not query DB — mock_db_session.execute should not be called
        mock_db_session.execute = AsyncMock(side_effect=AssertionError("Should not query DB"))
        doc = await collab_service.init_document_from_db(
            mock_db_session, mock_redis, sample_task_id
        )
        assert doc["f1"] == "redis_val"

    @pytest.mark.asyncio
    async def test_seed_from_db_collab_session(
        self, collab_service, mock_redis, mock_db_session, sample_task_id
    ):
        collab_session_mock = MagicMock()
        collab_session_mock.content = {"summary_text": "DB content"}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = collab_session_mock
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        doc = await collab_service.init_document_from_db(
            mock_db_session, mock_redis, sample_task_id
        )
        assert doc["summary_text"] == "DB content"

    @pytest.mark.asyncio
    async def test_no_db_session_returns_empty(
        self, collab_service, mock_redis, mock_db_session, sample_task_id
    ):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        doc = await collab_service.init_document_from_db(
            mock_db_session, mock_redis, sample_task_id
        )
        assert doc == {}


# ---------------------------------------------------------------------------
# flush_to_db
# ---------------------------------------------------------------------------


class TestFlushToDB:
    @pytest.mark.asyncio
    async def test_flush_creates_new_session(
        self, collab_service, mock_redis, mock_db_session, sample_task_id, now_utc
    ):
        await collab_service.apply_edit(mock_redis, sample_task_id, "f1", "val", now_utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        editor_id = uuid.uuid4()
        result = await collab_service.flush_to_db(
            mock_db_session, mock_redis, sample_task_id, last_editor_id=editor_id
        )

        assert result is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_updates_existing_session(
        self, collab_service, mock_redis, mock_db_session, sample_task_id, now_utc
    ):
        await collab_service.apply_edit(mock_redis, sample_task_id, "f1", "updated", now_utc)

        existing = MagicMock()
        existing.content = {"f1": "old"}
        existing.peak_participants = 3
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        await collab_service.flush_to_db(mock_db_session, mock_redis, sample_task_id)

        assert existing.content == {"f1": "updated"}
        assert existing.peak_participants >= 3

    @pytest.mark.asyncio
    async def test_flush_clears_redis_when_no_participants(
        self, collab_service, mock_redis, mock_db_session, sample_task_id, now_utc
    ):
        await collab_service.apply_edit(mock_redis, sample_task_id, "f1", "val", now_utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        await collab_service.flush_to_db(mock_db_session, mock_redis, sample_task_id)

        # Redis keys should be deleted
        doc_key = _redis_key_doc(sample_task_id)
        assert doc_key not in mock_redis._hashes

    @pytest.mark.asyncio
    async def test_flush_preserves_redis_with_participants(
        self, collab_service, mock_redis, mock_db_session, sample_task_id, now_utc
    ):
        await collab_service.apply_edit(mock_redis, sample_task_id, "f1", "val", now_utc)
        await collab_service.add_presence(mock_redis, sample_task_id, "u1", "Alice")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        await collab_service.flush_to_db(mock_db_session, mock_redis, sample_task_id)

        # Redis should still have data since presence count > 0
        doc_key = _redis_key_doc(sample_task_id)
        assert doc_key in mock_redis._hashes


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------


class TestRedisKeys:
    def test_doc_key(self, sample_task_id):
        assert _redis_key_doc(sample_task_id) == f"collab:doc:{sample_task_id}"

    def test_ts_key(self, sample_task_id):
        assert _redis_key_ts(sample_task_id) == f"collab:doc_ts:{sample_task_id}"

    def test_presence_key(self, sample_task_id):
        assert _redis_key_presence(sample_task_id) == f"collab:presence:{sample_task_id}"


class TestResolve:
    @pytest.mark.asyncio
    async def test_sync_values_are_returned_directly(self):
        assert await _resolve("ready") == "ready"
