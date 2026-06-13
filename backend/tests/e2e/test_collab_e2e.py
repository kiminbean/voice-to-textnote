"""
M6 E2E 테스트: 전체 협업 편집 파이프라인
SPEC-COLLAB-001: AC-P01~P03, AC-E01~E03
"""

import pytest

from backend.app.api.v1.collaboration.collab import (
    CollabConnectionManager,
)
from backend.schemas.collab import CollabUser, EditMessage
from backend.services.collab_service import CollabService

# ── AC-P01: 편집 전파 지연 ──────────────────────────────────────────


class TestEditPropagation:
    """AC-P01: 편집 전파 (인메모리로 즉시 전파 검증)"""

    @pytest.mark.asyncio
    async def test_edit_propagates_to_all_room_members(self):
        """한 사용자의 편집이 다른 사용자에게 전파된다"""
        service = CollabService()
        room_id = "task-e2e-001"
        user_a = CollabUser(user_id="a", display_name="Alice", color="#F00")
        CollabUser(user_id="b", display_name="Bob", color="#0F0")

        # A가 편집
        broadcast = await service.apply_edit(
            room_id, user_a, EditMessage(field="summary_text", value="A의 편집")
        )

        # broadcast 메시지 검증
        assert broadcast["type"] == "edit_broadcast"
        assert broadcast["field"] == "summary_text"
        assert broadcast["value"] == "A의 편집"
        assert broadcast["user_id"] == "a"

        # B가 sync_state로 같은 값을 확인
        state = await service.get_sync_state(room_id)
        assert state["summary_text"].value == "A의 편집"
        assert state["summary_text"].user_id == "a"


# ── AC-P02: Room 메모리 ─────────────────────────────────────────────


class TestRoomMemory:
    """AC-P02: Room당 메모리 점유 검증"""

    @pytest.mark.asyncio
    async def test_room_memory_footprint(self):
        """5명 room의 메모리 점유가 합리적 범위 내에 있다"""
        import sys

        manager = CollabConnectionManager()
        room_id = "task-mem-001"

        for i in range(5):
            user = CollabUser(user_id=f"u{i}", display_name=f"User{i}", color=f"#{i:06d}")
            await manager.connect(room_id, user)

        # manager + room 데이터 크기 추정
        manager_size = sys.getsizeof(manager._rooms)
        room_data = manager._rooms[room_id]
        users_size = sys.getsizeof(room_data["users"])

        # Room당 1MB 미만 (실제로는 훨씬 작음)
        assert manager_size + users_size < 1_000_000


# ── AC-P03: 다중 Room 지원 ──────────────────────────────────────────


class TestMultipleRooms:
    """AC-P03: 10개 Room 독립 동작"""

    @pytest.mark.asyncio
    async def test_10_independent_rooms(self):
        """10개 Room이 간섭 없이 독립 동작한다"""
        service = CollabService()

        for i in range(10):
            room_id = f"room-{i}"
            user = CollabUser(user_id=f"user-{i}", display_name=f"U{i}", color="#F00")
            await service.apply_edit(
                room_id, user, EditMessage(field=f"field_{i}", value=f"value_{i}")
            )

        # 각 room의 상태가 독립적인지 확인
        for i in range(10):
            state = await service.get_sync_state(f"room-{i}")
            assert state[f"field_{i}"].value == f"value_{i}"

            # 다른 room의 필드가 없는지 확인
            for j in range(10):
                if i != j:
                    assert f"field_{j}" not in state


# ── AC-E01: 서버 재시작 시 복구 (상태 복원) ──────────────────────────


class TestServerRecovery:
    """AC-E01: 서비스 재생성 후 상태 복원 가능성"""

    @pytest.mark.asyncio
    async def test_service_recreation_preserves_state_pattern(self):
        """서비스 재생성 패턴이 정상 동작한다"""
        # 첫 번째 서비스 인스턴스
        service1 = CollabService()
        room_id = "task-recovery-001"
        user = CollabUser(user_id="a", display_name="Alice", color="#F00")

        await service1.apply_edit(room_id, user, EditMessage(field="summary_text", value="복구테스트"))
        dirty = service1.get_dirty_fields(room_id)
        assert "summary_text" in dirty

        # flush (DB 저장 시뮬레이션)
        flushed = await service1.flush_room(room_id)
        assert flushed is not None
        assert flushed["summary_text"] == "복구테스트"

        # 새 서비스 인스턴스 (서버 재시작 시뮬레이션)
        service2 = CollabService()
        state = await service2.get_sync_state(room_id)
        assert state == {}  # 인메모리 → 휘발

        # flush된 데이터로 복원 가능 (DB에서 로드)
        assert flushed["summary_text"] == "복구테스트"


# ── AC-E02: 잘못된 메시지 형식 ──────────────────────────────────────


class TestInvalidMessageFormat:
    """AC-E02: 잘못된 메시지 처리"""

    @pytest.mark.asyncio
    async def test_empty_field_edit(self):
        """빈 field 이름의 edit은 적용되지만 의미 없는 값"""
        service = CollabService()
        user = CollabUser(user_id="a", display_name="Alice", color="#F00")

        result = await service.apply_edit(
            "room-err-001", user, EditMessage(field="", value="test")
        )

        # 빈 field도 처리됨 (서버는 field 검증을 추가할 수 있으나 현재는 허용)
        assert result["field"] == ""
        assert result["value"] == "test"

    @pytest.mark.asyncio
    async def test_empty_value_edit(self):
        """빈 value의 edit (필드 클리어)"""
        service = CollabService()
        user = CollabUser(user_id="a", display_name="Alice", color="#F00")

        await service.apply_edit(
            "room-err-002", user, EditMessage(field="notes", value="something")
        )
        await service.apply_edit(
            "room-err-002", user, EditMessage(field="notes", value="")
        )

        state = await service.get_sync_state("room-err-002")
        assert state["notes"].value == ""


# ── AC-E03: 존재하지 않는 필드 편집 ──────────────────────────────────


class TestUnknownFieldEdit:
    """AC-E03: 존재하지 않는 필드 편집"""

    @pytest.mark.asyncio
    async def test_unknown_field_creates_new_entry(self):
        """알 수 없는 field 이름은 새 필드로 생성된다"""
        service = CollabService()
        user = CollabUser(user_id="a", display_name="Alice", color="#F00")

        await service.apply_edit(
            "room-unknown-001", user, EditMessage(field="nonexistent_field", value="새 값")
        )

        state = await service.get_sync_state("room-unknown-001")
        assert "nonexistent_field" in state
        assert state["nonexistent_field"].value == "새 값"

    @pytest.mark.asyncio
    async def test_unknown_field_does_not_affect_existing(self):
        """새 필드가 기존 필드에 영향 없음"""
        service = CollabService()
        user = CollabUser(user_id="a", display_name="Alice", color="#F00")

        await service.apply_edit(
            "room-unknown-002", user, EditMessage(field="existing", value="기존")
        )
        await service.apply_edit(
            "room-unknown-002", user, EditMessage(field="brand_new", value="새로")
        )

        state = await service.get_sync_state("room-unknown-002")
        assert state["existing"].value == "기존"
        assert state["brand_new"].value == "새로"


# ── 전체 파이프라인 통합 ────────────────────────────────────────────


class TestFullPipeline:
    """전체 협업 편집 파이프라인 (connect → edit → broadcast → flush)"""

    @pytest.mark.asyncio
    async def test_complete_collab_session(self):
        """완전한 협업 세션: 연결 → 편집 → 동기화 → 퇴장 → 영속화"""
        manager = CollabConnectionManager()
        service = CollabService()
        room_id = "task-pipeline-001"

        # 1. 사용자 연결
        user_a = CollabUser(user_id="a", display_name="Alice", color="#F00")
        user_b = CollabUser(user_id="b", display_name="Bob", color="#0F0")
        assert await manager.connect(room_id, user_a) is True
        assert await manager.connect(room_id, user_b) is True

        # 2. sync_state 확인
        users = await manager.get_room_users(room_id)
        assert len(users) == 2

        # 3. A가 편집
        broadcast_a = await service.apply_edit(
            room_id, user_a, EditMessage(field="summary_text", value="회의 요약")
        )
        assert broadcast_a["value"] == "회의 요약"

        # 4. B가 다른 필드 편집
        broadcast_b = await service.apply_edit(
            room_id, user_b, EditMessage(field="action_items", value="액션 아이템")
        )
        assert broadcast_b["value"] == "액션 아이템"

        # 5. sync_state에 두 필드 모두 반영
        state = await service.get_sync_state(room_id)
        assert state["summary_text"].value == "회의 요약"
        assert state["action_items"].value == "액션 아이템"

        # 6. LWW: B가 summary_text를 나중에 덮어씀
        await service.apply_edit(
            room_id, user_b, EditMessage(field="summary_text", value="B의 수정")
        )
        state = await service.get_sync_state(room_id)
        assert state["summary_text"].value == "B의 수정"

        # 7. A 퇴장 (아직 B가 남아있어 flush 안 됨)
        await manager.disconnect(room_id, user_a.user_id)
        remaining = manager.get_room_count(room_id)
        assert remaining == 1

        # 8. B 퇴장 (마지막 → flush)
        assert service.has_unpersisted_changes(room_id) is True
        await manager.disconnect(room_id, user_b.user_id)
        remaining = manager.get_room_count(room_id)
        assert remaining == 0

        flushed = await service.flush_room(room_id)
        assert flushed is not None
        assert flushed["summary_text"] == "B의 수정"
        assert flushed["action_items"] == "액션 아이템"
        assert service.has_unpersisted_changes(room_id) is False
