"""
SPEC-GUEST-001: 게스트 미들웨어 단위 테스트

REQ-GUEST-005: Authorization: Bearer guest:<token> 헤더로 게스트 인증 통과
REQ-GUEST-006: 만료/잘못된 게스트 토큰 → 401 반환
REQ-GUEST-007: Redis에 세션 없는 게스트 토큰 → 401 반환
REQ-GUEST-008: 기존 API Key 인증 흐름 영향 없음
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from jose import jwt

# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------


def _make_guest_token(
    session_id: str,
    secret: str | None = None,
    expires_delta: timedelta | None = None,
    token_type: str = "guest",
) -> str:
    """테스트용 게스트 JWT 생성"""
    if secret is None:
        from backend.app.config import settings
        secret = settings.jwt_secret
    if expires_delta is None:
        expires_delta = timedelta(hours=24)
    expire = datetime.now(UTC) + expires_delta
    payload = {
        "sub": session_id,
        "type": token_type,
        "exp": expire,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis_with_session():
    """유효한 게스트 세션이 있는 Redis mock"""
    redis_mock = AsyncMock()
    # exists() → 세션 존재 (1 반환)
    redis_mock.exists.return_value = 1
    redis_mock.setex.return_value = True
    return redis_mock


@pytest.fixture
def mock_redis_without_session():
    """게스트 세션이 없는 Redis mock (만료/삭제된 세션)"""
    redis_mock = AsyncMock()
    # exists() → 세션 없음 (0 반환)
    redis_mock.exists.return_value = 0
    return redis_mock


@pytest.fixture
def guest_middleware_app(mock_redis_with_session):
    """게스트 미들웨어가 통합된 테스트 앱"""
    from backend.app.dependencies import get_redis_client
    from backend.app.middleware.auth import verify_api_key

    app = FastAPI()
    app.dependency_overrides[get_redis_client] = lambda: mock_redis_with_session

    @app.get("/protected")
    async def protected_route(
        request: Request,
        _api_key: str = Depends(verify_api_key),
    ):
        return {
            "ok": True,
            "is_guest": getattr(request.state, "is_guest", False),
            "guest_session_id": getattr(request.state, "guest_session_id", None),
        }

    return TestClient(app)


@pytest.fixture
def guest_app_no_session(mock_redis_without_session):
    """Redis에 게스트 세션이 없는 테스트 앱 (만료 시뮬레이션)"""
    from backend.app.dependencies import get_redis_client
    from backend.app.middleware.auth import verify_api_key

    app = FastAPI()
    app.dependency_overrides[get_redis_client] = lambda: mock_redis_without_session

    @app.get("/protected")
    async def protected_route(
        request: Request,
        _api_key: str = Depends(verify_api_key),
    ):
        return {"ok": True}

    return TestClient(app)


# ---------------------------------------------------------------------------
# REQ-GUEST-005: 유효한 게스트 토큰으로 인증 통과
# ---------------------------------------------------------------------------


class TestGuestTokenPassesAuth:
    """유효한 게스트 토큰으로 인증이 통과되는지 검증"""

    def test_valid_guest_token_returns_200(self, guest_middleware_app, mock_redis_with_session):
        """REQ-GUEST-005: 유효한 게스트 토큰 → 200"""
        session_id = "test-session-uuid-1234"
        token = _make_guest_token(session_id)

        response = guest_middleware_app.get(
            "/protected",
            headers={"Authorization": f"Bearer guest:{token}"},
        )
        assert response.status_code == 200

    def test_guest_token_sets_is_guest_state(self, guest_middleware_app):
        """REQ-GUEST-005: 게스트 토큰 인증 후 request.state.is_guest = True"""
        session_id = "test-session-uuid-1234"
        token = _make_guest_token(session_id)

        response = guest_middleware_app.get(
            "/protected",
            headers={"Authorization": f"Bearer guest:{token}"},
        )
        assert response.status_code == 200
        assert response.json()["is_guest"] is True

    def test_guest_token_sets_session_id_state(self, guest_middleware_app):
        """REQ-GUEST-005: 게스트 토큰 인증 후 request.state.guest_session_id 설정"""
        session_id = "test-session-uuid-5678"
        token = _make_guest_token(session_id)

        response = guest_middleware_app.get(
            "/protected",
            headers={"Authorization": f"Bearer guest:{token}"},
        )
        assert response.status_code == 200
        assert response.json()["guest_session_id"] == session_id

    def test_guest_token_checks_redis_for_session(
        self, mock_redis_with_session, guest_middleware_app
    ):
        """REQ-GUEST-005: Redis에서 게스트 세션 존재 여부 확인"""
        session_id = "test-session-uuid-9999"
        token = _make_guest_token(session_id)

        guest_middleware_app.get(
            "/protected",
            headers={"Authorization": f"Bearer guest:{token}"},
        )

        # Redis exists() 호출 확인
        mock_redis_with_session.exists.assert_called_once_with(
            f"guest:session:{session_id}"
        )


# ---------------------------------------------------------------------------
# REQ-GUEST-006: 만료/잘못된 게스트 토큰 → 401
# ---------------------------------------------------------------------------


class TestExpiredGuestTokenReturns401:
    """만료된 게스트 토큰 처리 테스트"""

    def test_expired_guest_token_returns_401(self, guest_middleware_app):
        """REQ-GUEST-006: 만료된 게스트 JWT → 401"""
        session_id = "expired-session-uuid"
        # 과거 만료 시간으로 토큰 생성
        token = _make_guest_token(session_id, expires_delta=timedelta(seconds=-1))

        response = guest_middleware_app.get(
            "/protected",
            headers={"Authorization": f"Bearer guest:{token}"},
        )
        assert response.status_code == 401

    def test_malformed_guest_token_returns_401(self, guest_middleware_app):
        """REQ-GUEST-006: 형식이 잘못된 게스트 토큰 → 401"""
        response = guest_middleware_app.get(
            "/protected",
            headers={"Authorization": "Bearer guest:not-a-valid-jwt"},
        )
        assert response.status_code == 401

    def test_wrong_secret_guest_token_returns_401(self, guest_middleware_app):
        """REQ-GUEST-006: 잘못된 시크릿으로 서명된 게스트 토큰 → 401"""
        session_id = "wrong-secret-session"
        token = _make_guest_token(session_id, secret="wrong-secret-key")

        response = guest_middleware_app.get(
            "/protected",
            headers={"Authorization": f"Bearer guest:{token}"},
        )
        assert response.status_code == 401

    def test_non_guest_type_token_as_guest_returns_401(self, guest_middleware_app):
        """REQ-GUEST-006: type이 'guest'가 아닌 토큰을 게스트 형식으로 전달 → 401"""
        session_id = "wrong-type-session"
        # type: "user" 토큰을 "Bearer guest:" 형식으로 전달
        token = _make_guest_token(session_id, token_type="user")

        response = guest_middleware_app.get(
            "/protected",
            headers={"Authorization": f"Bearer guest:{token}"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# REQ-GUEST-007: Redis에 세션 없는 경우 → 401
# ---------------------------------------------------------------------------


class TestInvalidGuestTokenReturns401:
    """Redis에 게스트 세션이 없는 경우 401 반환 테스트"""

    def test_missing_redis_session_returns_401(self, guest_app_no_session):
        """REQ-GUEST-007: Redis에 세션 없음 (만료 또는 삭제) → 401"""
        session_id = "missing-session-uuid"
        token = _make_guest_token(session_id)

        response = guest_app_no_session.get(
            "/protected",
            headers={"Authorization": f"Bearer guest:{token}"},
        )
        assert response.status_code == 401

    def test_missing_session_error_message(self, guest_app_no_session):
        """REQ-GUEST-007: Redis 세션 없음 에러 메시지 확인"""
        session_id = "missing-session-uuid"
        token = _make_guest_token(session_id)

        response = guest_app_no_session.get(
            "/protected",
            headers={"Authorization": f"Bearer guest:{token}"},
        )
        assert response.status_code == 401
        # 에러 메시지에 민감 정보 미포함 확인
        response_text = response.text
        assert session_id not in response_text
