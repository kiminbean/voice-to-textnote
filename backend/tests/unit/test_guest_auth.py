"""
SPEC-GUEST-001: 게스트 세션 API 단위 테스트

REQ-GUEST-001: POST /auth/guest → guest_session_id, guest_token, expires_at 반환
REQ-GUEST-002: 발급된 guest_token은 유효한 JWT (type: "guest")
REQ-GUEST-003: 게스트 세션 Redis 저장 (키: guest:session:{id}, TTL 86400)
REQ-GUEST-004: expires_at은 현재 시각 + 24시간
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis_for_guest():
    """게스트 세션 테스트용 Redis mock"""
    redis_mock = AsyncMock()
    redis_mock.setex.return_value = True
    redis_mock.exists.return_value = 1
    redis_mock.get.return_value = None
    return redis_mock


@pytest.fixture
def guest_test_app(mock_redis_for_guest):
    """게스트 엔드포인트가 포함된 테스트 앱"""
    from backend.app.api.v1.auth.auth import router
    from backend.app.dependencies import get_redis_client

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_redis_client] = lambda: mock_redis_for_guest

    return TestClient(app)


# ---------------------------------------------------------------------------
# REQ-GUEST-001: 게스트 세션 생성 - 응답 구조 검증
# ---------------------------------------------------------------------------


class TestCreateGuestSessionReturnsToken:
    """POST /auth/guest 엔드포인트 기본 동작 테스트"""

    def test_create_guest_session_returns_200(self, guest_test_app):
        """REQ-GUEST-001: POST /auth/guest → 200 OK"""
        response = guest_test_app.post("/auth/guest")
        assert response.status_code == 200

    def test_create_guest_session_returns_required_fields(self, guest_test_app):
        """REQ-GUEST-001: 응답에 guest_session_id, guest_token, expires_at 포함"""
        response = guest_test_app.post("/auth/guest")
        data = response.json()

        assert "guest_session_id" in data
        assert "guest_token" in data
        assert "expires_at" in data

    def test_create_guest_session_id_is_uuid(self, guest_test_app):
        """REQ-GUEST-001: guest_session_id는 UUID v4 형식"""
        import uuid

        response = guest_test_app.post("/auth/guest")
        data = response.json()
        session_id = data["guest_session_id"]

        # UUID 형식 검증 (ValueError 발생 시 유효하지 않은 UUID)
        parsed = uuid.UUID(session_id)
        assert str(parsed) == session_id

    def test_create_guest_session_returns_string_token(self, guest_test_app):
        """REQ-GUEST-001: guest_token은 비어있지 않은 문자열"""
        response = guest_test_app.post("/auth/guest")
        data = response.json()

        assert isinstance(data["guest_token"], str)
        assert len(data["guest_token"]) > 0

    def test_each_guest_session_has_unique_id(self, guest_test_app):
        """REQ-GUEST-001: 두 번 호출 시 서로 다른 guest_session_id 반환"""
        r1 = guest_test_app.post("/auth/guest")
        r2 = guest_test_app.post("/auth/guest")

        assert r1.json()["guest_session_id"] != r2.json()["guest_session_id"]


# ---------------------------------------------------------------------------
# REQ-GUEST-002: guest_token JWT 유효성 검증
# ---------------------------------------------------------------------------


class TestGuestTokenIsValidJWT:
    """발급된 guest_token의 JWT 구조 검증"""

    def test_guest_token_is_decodable_jwt(self, guest_test_app):
        """REQ-GUEST-002: guest_token은 디코딩 가능한 JWT"""
        from backend.app.config import settings

        response = guest_test_app.post("/auth/guest")
        token = response.json()["guest_token"]

        # jwt.decode() 예외 없이 성공해야 함
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        assert payload is not None

    def test_guest_token_has_type_guest(self, guest_test_app):
        """REQ-GUEST-002: JWT payload에 type: "guest" 포함"""
        from backend.app.config import settings

        response = guest_test_app.post("/auth/guest")
        token = response.json()["guest_token"]

        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        assert payload.get("type") == "guest"

    def test_guest_token_sub_matches_session_id(self, guest_test_app):
        """REQ-GUEST-002: JWT sub 클레임은 guest_session_id와 동일"""
        from backend.app.config import settings

        response = guest_test_app.post("/auth/guest")
        data = response.json()
        token = data["guest_token"]
        session_id = data["guest_session_id"]

        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        assert payload.get("sub") == session_id

    def test_guest_token_has_exp_claim(self, guest_test_app):
        """REQ-GUEST-002: JWT에 exp 클레임 포함"""
        from backend.app.config import settings

        response = guest_test_app.post("/auth/guest")
        token = response.json()["guest_token"]

        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        assert "exp" in payload


# ---------------------------------------------------------------------------
# REQ-GUEST-003: Redis 저장 검증
# ---------------------------------------------------------------------------


class TestGuestSessionStoredInRedis:
    """게스트 세션이 Redis에 올바르게 저장되는지 검증"""

    def test_guest_session_calls_redis_setex(self, mock_redis_for_guest, guest_test_app):
        """REQ-GUEST-003: Redis setex 호출 확인"""
        guest_test_app.post("/auth/guest")
        assert mock_redis_for_guest.setex.called

    def test_guest_session_redis_key_format(self, mock_redis_for_guest, guest_test_app):
        """REQ-GUEST-003: Redis 키 형식 = guest:session:{id}"""
        response = guest_test_app.post("/auth/guest")
        session_id = response.json()["guest_session_id"]

        # setex 호출 인수에서 키 확인
        call_args = mock_redis_for_guest.setex.call_args
        key = call_args[0][0]  # 첫 번째 위치 인수

        assert key == f"guest:session:{session_id}"

    def test_guest_session_redis_ttl_is_86400(self, mock_redis_for_guest, guest_test_app):
        """REQ-GUEST-003: Redis TTL = 86400초 (24시간)"""
        guest_test_app.post("/auth/guest")

        call_args = mock_redis_for_guest.setex.call_args
        ttl = call_args[0][1]  # 두 번째 위치 인수 (TTL)

        assert ttl == 86400


# ---------------------------------------------------------------------------
# REQ-GUEST-004: expires_at 24시간 검증
# ---------------------------------------------------------------------------


class TestGuestSessionExpiresIn24h:
    """게스트 세션 만료 시각 검증"""

    def test_expires_at_is_approximately_24h_from_now(self, guest_test_app):
        """REQ-GUEST-004: expires_at은 현재 시각 + 24시간 (±5초 허용)"""
        before = datetime.now(UTC)
        response = guest_test_app.post("/auth/guest")
        after = datetime.now(UTC)

        expires_at_str = response.json()["expires_at"]
        # ISO 형식 파싱 (timezone-aware or naive)
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)  # pragma: no cover

        expected_min = before + timedelta(hours=24) - timedelta(seconds=5)
        expected_max = after + timedelta(hours=24) + timedelta(seconds=5)

        assert expected_min <= expires_at <= expected_max

    def test_expires_at_is_valid_datetime_string(self, guest_test_app):
        """REQ-GUEST-004: expires_at은 파싱 가능한 datetime 문자열"""
        response = guest_test_app.post("/auth/guest")
        expires_at_str = response.json()["expires_at"]

        # 파싱 가능하면 성공
        parsed = datetime.fromisoformat(expires_at_str)
        assert parsed is not None
