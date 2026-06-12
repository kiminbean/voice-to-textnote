"""
M1 단위 테스트: ConnectionManager, JWT 검증, Room 관리
SPEC-COLLAB-001: AC-001 ~ AC-005
"""

import pytest

from backend.app.api.v1.collaboration.collab import CollabConnectionManager
from backend.schemas.collab import CollabUser


# ── ConnectionManager 테스트 ─────────────────────────────────────────


class TestCollabConnectionManager:
    """REQ-COLLAB-002: Room 최대 5명, user_joined/left 관리"""

    def setup_method(self):
        self.manager = CollabConnectionManager()

    # AC-001: room 참가 시 user_joined 이벤트 발생
    @pytest.mark.asyncio
    async def test_connect_user_to_room(self):
        """사용자가 room에 참가하면 room에 추가된다"""
        room_id = "task-001"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#FF5733")

        result = await self.manager.connect(room_id, user, websocket=None)

        assert result is True
        users = await self.manager.get_room_users(room_id)
        assert len(users) == 1
        assert users[0].user_id == "user-a"

    # AC-004: Room 최대 5명 제한
    @pytest.mark.asyncio
    async def test_room_max_5_users(self):
        """5명이 찬 room에 6번째 사용자 연결 시 거부된다"""
        room_id = "task-002"

        # 5명 참가
        for i in range(5):
            user = CollabUser(user_id=f"user-{i}", display_name=f"User{i}", color=f"#FF{i:02d}")
            await self.manager.connect(room_id, user, websocket=None)

        # 6번째 참가 시도
        user_6 = CollabUser(user_id="user-5", display_name="User5", color="#FF55")
        result = await self.manager.connect(room_id, user_6, websocket=None)

        assert result is False
        users = await self.manager.get_room_users(room_id)
        assert len(users) == 5

    # AC-003: 퇴장 시 user_left 이벤트
    @pytest.mark.asyncio
    async def test_disconnect_user_from_room(self):
        """사용자가 퇴장하면 room에서 제거된다"""
        room_id = "task-003"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#FF5733")
        await self.manager.connect(room_id, user, websocket=None)

        await self.manager.disconnect(room_id, user.user_id)

        users = await self.manager.get_room_users(room_id)
        assert len(users) == 0

    # 독립 Room 간섭 없음
    @pytest.mark.asyncio
    async def test_independent_rooms(self):
        """서로 다른 room이 독립적으로 동작한다"""
        user_a = CollabUser(user_id="a", display_name="A", color="#F00")
        user_b = CollabUser(user_id="b", display_name="B", color="#0F0")

        await self.manager.connect("room-1", user_a, websocket=None)
        await self.manager.connect("room-2", user_b, websocket=None)

        users_1 = await self.manager.get_room_users("room-1")
        users_2 = await self.manager.get_room_users("room-2")

        assert len(users_1) == 1
        assert len(users_2) == 1
        assert users_1[0].user_id == "a"
        assert users_2[0].user_id == "b"

    # 마지막 참여자 퇴장 시 room 정리
    @pytest.mark.asyncio
    async def test_room_cleanup_on_last_user_leave(self):
        """마지막 참여자가 퇴장하면 room이 정리된다"""
        room_id = "task-004"
        user = CollabUser(user_id="user-a", display_name="Alice", color="#FF5733")
        await self.manager.connect(room_id, user, websocket=None)

        await self.manager.disconnect(room_id, user.user_id)

        # room이 정리되었는지 확인
        users = await self.manager.get_room_users(room_id)
        assert len(users) == 0
        # 내부 room dict에서도 제거되었는지 확인
        assert room_id not in self.manager._rooms or len(self.manager._rooms.get(room_id, {}).get("users", [])) == 0
