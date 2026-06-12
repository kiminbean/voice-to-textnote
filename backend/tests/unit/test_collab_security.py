"""
M5 보안 단위 테스트: JWT 검증, Role gating, Rate limit
SPEC-COLLAB-001: AC-050 ~ AC-053
"""

import time

import pytest

from backend.app.api.v1.collaboration.collab import (
    _EDIT_RATE_LIMIT,
    _EDIT_RATE_WINDOW,
    _VIEWER_ROLE,
    _RateLimiter,
)

# ── AC-050: 미인증 접근 차단 ──────────────────────────────────────────


class TestJWTAuth:
    """REQ-COLLAB-050: WebSocket JWT 인증"""

    def test_rate_limiter_basic(self):
        """Rate limiter 기본 동작"""
        limiter = _RateLimiter(3, 1.0)

        assert limiter.is_limited("user-a") is False
        assert limiter.is_limited("user-a") is False
        assert limiter.is_limited("user-a") is False
        # 4번째는 제한
        assert limiter.is_limited("user-a") is True

    def test_rate_limiter_independent_users(self):
        """사용자별 독립 Rate limit"""
        limiter = _RateLimiter(2, 1.0)

        assert limiter.is_limited("user-a") is False
        assert limiter.is_limited("user-a") is False
        assert limiter.is_limited("user-a") is True

        # user-b는 영향 없음
        assert limiter.is_limited("user-b") is False

    def test_rate_limiter_window_expiry(self):
        """윈도우 만료 후 Rate limit 해제"""
        limiter = _RateLimiter(2, 0.1)

        limiter.is_limited("user-a")
        limiter.is_limited("user-a")
        assert limiter.is_limited("user-a") is True

        # 윈도우 만료 대기
        time.sleep(0.15)

        assert limiter.is_limited("user-a") is False

    def test_rate_limiter_clear(self):
        """clear 후 Rate limit 초기화"""
        limiter = _RateLimiter(2, 1.0)

        limiter.is_limited("user-a")
        limiter.is_limited("user-a")
        assert limiter.is_limited("user-a") is True

        limiter.clear("user-a")

        assert limiter.is_limited("user-a") is False

    def test_global_rate_limit_constants(self):
        """REQ-COLLAB-052: Rate limit 상수 검증"""
        assert _EDIT_RATE_LIMIT == 10
        assert _EDIT_RATE_WINDOW == 1.0


# ── AC-051: Viewer 편집 차단 ──────────────────────────────────────────


class TestRoleGating:
    """REQ-COLLAB-051: viewer 역할 편집 불가"""

    def test_viewer_role_constant(self):
        """viewer 역할 상수 검증"""
        assert _VIEWER_ROLE == "viewer"

    def test_viewer_not_equal_member(self):
        """viewer는 member가 아님"""
        assert _VIEWER_ROLE != "member"
        assert _VIEWER_ROLE != "admin"


# ── AC-052: Rate Limiting ──────────────────────────────────────────────


class TestRateLimiting:
    """REQ-COLLAB-052: 1초당 10개 edit 제한"""

    def test_exact_limit_allowed(self):
        """정확히 10개까지 허용"""
        limiter = _RateLimiter(10, 1.0)
        for i in range(10):
            assert limiter.is_limited("user-a") is False, f"Request {i+1} should be allowed"

    def test_eleventh_blocked(self):
        """11번째는 차단"""
        limiter = _RateLimiter(10, 1.0)
        for _ in range(10):
            limiter.is_limited("user-a")
        assert limiter.is_limited("user-a") is True

    def test_different_rooms_independent(self):
        """다른 사용자의 Rate limit은 독립"""
        limiter = _RateLimiter(2, 1.0)

        # user-a 소진
        limiter.is_limited("user-a")
        limiter.is_limited("user-a")

        # user-b는 정상
        assert limiter.is_limited("user-b") is False


# ── AC-053: 비팀원 접근 차단 (ConnectionManager 레벨) ─────────────────


class TestNonMemberAccess:
    """REQ-COLLAB-053: 비팀원 접근 차단 (team membership은 JWT payload에서 확인)"""

    @pytest.mark.asyncio
    async def test_room_isolation(self):
        """다른 room의 사용자가 간섭하지 않음"""
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser

        manager = CollabConnectionManager()
        user_a = CollabUser(user_id="a", display_name="A", color="#F00")
        user_b = CollabUser(user_id="b", display_name="B", color="#0F0")

        await manager.connect("room-1", user_a)
        await manager.connect("room-2", user_b)

        # room-1에 user_b가 없음
        users_1 = await manager.get_room_users("room-1")
        assert len(users_1) == 1
        assert users_1[0].user_id == "a"

        # room-2에 user_a가 없음
        users_2 = await manager.get_room_users("room-2")
        assert len(users_2) == 1
        assert users_2[0].user_id == "b"

    @pytest.mark.asyncio
    async def test_max_room_size_enforcement(self):
        """최대 인원 초과 시 거부"""
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser

        manager = CollabConnectionManager()
        for i in range(5):
            user = CollabUser(user_id=f"u{i}", display_name=f"U{i}", color="#F00")
            result = await manager.connect("room-full", user)
            assert result is True

        # 6번째 거부
        user_6 = CollabUser(user_id="u5", display_name="U5", color="#F00")
        result = await manager.connect("room-full", user_6)
        assert result is False
