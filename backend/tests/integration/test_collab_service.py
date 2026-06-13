"""
M2 통합 테스트: LWW 충돌 해결, Redis 상태 관리, DB 영속화
SPEC-COLLAB-001: AC-010 ~ AC-022
"""

import time

import pytest

from backend.app.api.v1.collaboration.collab import CollabConnectionManager
from backend.schemas.collab import CollabUser, EditMessage
from backend.services.collab_service import CollabService

# ── 픽스처 ───────────────────────────────────────────────────────────


@pytest.fixture
def manager():
    return CollabConnectionManager()


@pytest.fixture
def service():
    """Redis 없이 동작하는 서비스 (인메모리 fallback)"""
    return CollabService(redis_client=None)


@pytest.fixture
def room_with_users(manager):
    """2명이 접속한 room 설정"""
    room_id = "task-lww-001"
    user_a = CollabUser(user_id="user-a", display_name="Alice", color="#F00")
    user_b = CollabUser(user_id="user-b", display_name="Bob", color="#0F0")
    import asyncio
    asyncio.get_event_loop().run_until_complete(manager.connect(room_id, user_a))
    asyncio.get_event_loop().run_until_complete(manager.connect(room_id, user_b))
    return room_id, user_a, user_b


# ── AC-010: 단일 편집 브로드캐스트 ──────────────────────────────────


class TestEditBroadcast:
    """REQ-COLLAB-010: 편집 브로드캐스트"""

    @pytest.mark.asyncio
    async def test_edit_updates_field_and_returns_broadcast(self, service):
        """edit → 필드 업데이트 + 브로드캐스트 메시지 생성"""
        room_id = "task-bc-001"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#F00")

        edit = EditMessage(field="summary_text", value="새 요약", client_ts=1.0)
        broadcast = await service.apply_edit(room_id, user, edit)

        assert broadcast is not None
        assert broadcast["type"] == "edit_broadcast"
        assert broadcast["field"] == "summary_text"
        assert broadcast["value"] == "새 요약"
        assert broadcast["user_id"] == "user-a"
        assert broadcast["user_name"] == "Alice"
        assert "server_ts" in broadcast

    @pytest.mark.asyncio
    async def test_edit_excludes_sender_from_user_id(self, service):
        """브로드캐스트 메시지에 sender 정보는 포함되지만,
        ConnectionManager에서 exclude_user로 필터링한다"""
        user = CollabUser(user_id="user-a", display_name="Alice", color="#F00")
        edit = EditMessage(field="summary_text", value="test")
        broadcast = await service.apply_edit("room-1", user, edit)

        assert broadcast["user_id"] == "user-a"


# ── AC-011: LWW 충돌 해결 ───────────────────────────────────────────


class TestLWWConflictResolution:
    """REQ-COLLAB-011: 서버 타임스탬프 기준 Last-Writer-Wins"""

    @pytest.mark.asyncio
    async def test_later_edit_wins(self, service):
        """동시 편집 시 서버 타임스탬프가 더 늦은 쪽이 승자"""
        room_id = "task-lww-001"
        user_a = CollabUser(user_id="user-a", display_name="Alice", color="#F00")
        user_b = CollabUser(user_id="user-b", display_name="Bob", color="#0F0")

        # A가 먼저 편집
        edit_a = EditMessage(field="summary_text", value="A 수정")
        await service.apply_edit(room_id, user_a, edit_a)

        # B가 나중에 편집 (B가 승자)
        edit_b = EditMessage(field="summary_text", value="B 수정")
        await service.apply_edit(room_id, user_b, edit_b)

        state = await service.get_sync_state(room_id)
        assert state["summary_text"].value == "B 수정"

    @pytest.mark.asyncio
    async def test_lww_timestamp_ordering(self, service):
        """필드 상태의 server_ts가 단조 증가한다"""
        room_id = "task-ts-001"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#F00")

        edit1 = EditMessage(field="summary_text", value="first")
        result1 = await service.apply_edit(room_id, user, edit1)
        ts1 = result1["server_ts"]

        # 약간의 시간 간격
        time.sleep(0.01)

        edit2 = EditMessage(field="summary_text", value="second")
        result2 = await service.apply_edit(room_id, user, edit2)
        ts2 = result2["server_ts"]

        assert ts2 > ts1


# ── AC-012: 신규 참여자 상태 동기화 ──────────────────────────────────


class TestSyncState:
    """REQ-COLLAB-012: sync_state 전체 상태 전송"""

    @pytest.mark.asyncio
    async def test_sync_state_includes_all_edited_fields(self, service):
        """편집 이력이 sync_state에 모두 포함된다"""
        room_id = "task-sync-001"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#F00")

        # 여러 필드 편집
        await service.apply_edit(room_id, user, EditMessage(field="summary_text", value="요약"))
        await service.apply_edit(room_id, user, EditMessage(field="action_items", value="액션"))

        state = await service.get_sync_state(room_id)

        assert "summary_text" in state
        assert state["summary_text"].value == "요약"
        assert "action_items" in state
        assert state["action_items"].value == "액션"

    @pytest.mark.asyncio
    async def test_sync_state_empty_for_new_room(self, service):
        """새 room의 sync_state는 빈 dict"""
        state = await service.get_sync_state("nonexistent-room")
        assert state == {}


# ── AC-013: 독립 필드 편집 ──────────────────────────────────────────


class TestIndependentFieldEdits:
    """REQ-COLLAB-013: 필드 간 독립성"""

    @pytest.mark.asyncio
    async def test_different_fields_dont_interfere(self, service):
        """서로 다른 필드 편집이 독립적으로 적용된다"""
        room_id = "task-indep-001"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#F00")

        await service.apply_edit(room_id, user, EditMessage(field="field_a", value="A"))
        await service.apply_edit(room_id, user, EditMessage(field="field_b", value="B"))

        state = await service.get_sync_state(room_id)
        assert state["field_a"].value == "A"
        assert state["field_b"].value == "B"


# ── AC-020: Redis 즉시 저장 ──────────────────────────────────────────


class TestRedisImmediatePersist:
    """REQ-COLLAB-020: 편집 시 Redis에 즉시 반영"""

    @pytest.mark.asyncio
    async def test_edit_updates_inmemory_state(self, service):
        """편집 후 get_sync_state에 즉시 반영 (Redis 없이 인메모리로 동작)"""
        room_id = "task-redis-001"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#F00")

        await service.apply_edit(room_id, user, EditMessage(field="summary_text", value="즉시반영"))

        state = await service.get_sync_state(room_id)
        assert state["summary_text"].value == "즉시반영"


# ── AC-021: 디바운스 DB 영속화 ───────────────────────────────────────


class TestDebounceDBPersist:
    """REQ-COLLAB-021: 3초 디바운스 후 DB 영속화"""

    @pytest.mark.asyncio
    async def test_get_dirty_fields_after_edit(self, service):
        """편집 후 dirty 필드가 추적된다"""
        room_id = "task-debounce-001"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#F00")

        await service.apply_edit(room_id, user, EditMessage(field="summary_text", value="dirty"))

        dirty = service.get_dirty_fields(room_id)
        assert "summary_text" in dirty
        assert dirty["summary_text"] == "dirty"

    @pytest.mark.asyncio
    async def test_clear_dirty_after_flush(self, service):
        """flush 후 dirty 필드가 초기화된다"""
        room_id = "task-flush-001"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#F00")

        await service.apply_edit(room_id, user, EditMessage(field="summary_text", value="flush"))
        service.clear_dirty_fields(room_id)

        dirty = service.get_dirty_fields(room_id)
        assert dirty == {}


# ── AC-022: 세션 종료 시 영속화 ──────────────────────────────────────


class TestSessionEndPersist:
    """REQ-COLLAB-022: 마지막 사용자 퇴장 시 즉시 영속화"""

    @pytest.mark.asyncio
    async def test_has_unpersisted_changes_flag(self, service):
        """편집 후 has_unpersisted_changes가 True"""
        room_id = "task-end-001"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#F00")

        assert service.has_unpersisted_changes(room_id) is False

        await service.apply_edit(room_id, user, EditMessage(field="summary_text", value="edit"))

        assert service.has_unpersisted_changes(room_id) is True

    @pytest.mark.asyncio
    async def test_flush_on_session_end(self, service):
        """flush_room 호출 후 has_unpersisted_changes가 False"""
        room_id = "task-end-002"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#F00")

        await service.apply_edit(room_id, user, EditMessage(field="summary_text", value="final"))

        result = await service.flush_room(room_id)
        assert result is not None
        assert "summary_text" in result
        assert result["summary_text"] == "final"

        assert service.has_unpersisted_changes(room_id) is False
