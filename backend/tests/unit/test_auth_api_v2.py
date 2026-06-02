"""
SPEC-TEAM-001: Auth API 추가 단위 테스트 (커버리지 67% → 100%)

커버리지되지 않은 엔드포인트:
- POST /auth/guest - 게스트 세션 생성
- POST /auth/google - Google 소셜 로그인
- POST /auth/apple - Apple 소셜 로그인
- POST /auth/link/{provider} - 소셜 계정 연동
- DELETE /auth/link/{provider} - 소셜 계정 연동 해제
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_client():
    """인증 테스트용 TestClient"""
    from backend.app.dependencies import get_db_session, get_redis_client
    from backend.app.main import app

    async def mock_db_session():
        yield AsyncMock()

    async def mock_redis():
        mock_redis = MagicMock()
        mock_redis.setex = AsyncMock()
        return mock_redis

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_redis_client] = mock_redis

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /auth/guest - 게스트 세션 생성
# ---------------------------------------------------------------------------


class TestGuestSession:
    """게스트 세션 생성 엔드포인트"""

    def test_guest_session_created_200(self, auth_client):
        """게스트 세션 생성 성공 시 200 + GuestSessionResponse 반환"""
        from backend.app.dependencies import get_redis_client
        from backend.app.main import app

        mock_redis = MagicMock()
        mock_redis.setex = AsyncMock()

        app.dependency_overrides[get_redis_client] = lambda: mock_redis

        with patch("backend.app.api.v1.auth.settings") as mock_s, \
             patch("backend.app.api.v1.auth.uuid.uuid4", return_value=uuid.UUID("12345678-1234-5678-1234-567812345678")):
            mock_s.guest_session_ttl_hours = 24
            mock_s.jwt_secret = "test-secret"

            with patch("backend.app.api.v1.auth.jwt.encode") as mock_encode:
                mock_encode.return_value = "mock-guest-token"

                response = auth_client.post("/api/v1/auth/guest")

        app.dependency_overrides.pop(get_redis_client, None)

        assert response.status_code == 200
        data = response.json()
        assert "guest_session_id" in data
        assert "guest_token" in data
        assert "expires_at" in data


# ---------------------------------------------------------------------------
# POST /auth/google - Google 소셜 로그인
# ---------------------------------------------------------------------------


class TestGoogleLogin:
    """Google 소셜 로그인 엔드포인트"""

    def test_google_login_success_200(self, auth_client):
        """Google 로그인 성공 시 200 + TokenResponse 반환"""
        mock_user_info = MagicMock()
        mock_user_info.provider = "google"
        mock_user_info.provider_id = "google-123"
        mock_user_info.email = "google@example.com"
        mock_user_info.display_name = "Google User"
        mock_user_info.avatar_url = "https://example.com/avatar.jpg"

        with patch("backend.app.api.v1.auth.verify_google_token") as mock_verify, \
             patch("backend.app.api.v1.auth._auth_service") as mock_svc:
            mock_verify.return_value = mock_user_info
            mock_svc.social_login_or_register = AsyncMock(
                return_value=(MagicMock(), "access-token", "refresh-token")
            )

            response = auth_client.post(
                "/api/v1/auth/google",
                json={"id_token": "valid-google-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_google_login_invalid_token_401(self, auth_client):
        """유효하지 않은 Google token으로 로그인 시 401 반환"""
        with patch("backend.app.api.v1.auth.verify_google_token") as mock_verify:
            mock_verify.side_effect = ValueError("Invalid Google token")

            response = auth_client.post(
                "/api/v1/auth/google",
                json={"id_token": "invalid-token"},
            )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/apple - Apple 소셜 로그인
# ---------------------------------------------------------------------------


class TestAppleLogin:
    """Apple 소셜 로그인 엔드포인트"""

    def test_apple_login_success_200(self, auth_client):
        """Apple 로그인 성공 시 200 + TokenResponse 반환"""
        mock_user_info = MagicMock()
        mock_user_info.provider = "apple"
        mock_user_info.provider_id = "apple-123"
        mock_user_info.email = "apple@example.com"
        mock_user_info.display_name = "Apple User"
        mock_user_info.avatar_url = None

        with patch("backend.app.api.v1.auth.verify_apple_token") as mock_verify, \
             patch("backend.app.api.v1.auth._auth_service") as mock_svc:
            mock_verify.return_value = mock_user_info
            mock_svc.social_login_or_register = AsyncMock(
                return_value=(MagicMock(), "access-token", "refresh-token")
            )

            response = auth_client.post(
                "/api/v1/auth/apple",
                json={"id_token": "valid-apple-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_apple_login_with_display_name(self, auth_client):
        """display_name이 요청에 포함된 경우 우선 적용"""
        mock_user_info = MagicMock()
        mock_user_info.provider = "apple"
        mock_user_info.provider_id = "apple-123"
        mock_user_info.email = "apple@example.com"
        mock_user_info.display_name = "Default Name"
        mock_user_info.avatar_url = None

        with patch("backend.app.api.v1.auth.verify_apple_token") as mock_verify, \
             patch("backend.app.api.v1.auth._auth_service") as mock_svc:
            mock_verify.return_value = mock_user_info
            mock_svc.social_login_or_register = AsyncMock(
                return_value=(MagicMock(), "access-token", "refresh-token")
            )

            response = auth_client.post(
                "/api/v1/auth/apple",
                json={
                    "id_token": "valid-apple-token",
                    "display_name": "Custom Name",
                },
            )

        assert response.status_code == 200

    def test_apple_login_invalid_token_401(self, auth_client):
        """유효하지 않은 Apple token으로 로그인 시 401 반환"""
        with patch("backend.app.api.v1.auth.verify_apple_token") as mock_verify:
            mock_verify.side_effect = ValueError("Invalid Apple token")

            response = auth_client.post(
                "/api/v1/auth/apple",
                json={"id_token": "invalid-token"},
            )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/link/{provider} - 소셜 계정 연동
# ---------------------------------------------------------------------------


class TestLinkProvider:
    """소셜 계정 연동 엔드포인트"""

    def test_link_google_success_200(self, auth_client):
        """Google 계정 연동 성공"""
        from backend.app.dependencies import get_current_user

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.display_name = "User"
        mock_user.is_active = True
        mock_user.created_at = datetime.now(UTC).replace(tzinfo=None)
        mock_user.provider = "email"
        mock_user.avatar_url = None

        mock_user_info = MagicMock()
        mock_user_info.provider_id = "google-123"
        mock_user_info.avatar_url = "https://example.com/avatar.jpg"

        async def mock_get_user():
            return mock_user

        from backend.app.main import app
        app.dependency_overrides[get_current_user] = mock_get_user

        with patch("backend.app.api.v1.auth.verify_google_token") as mock_verify, \
             patch("backend.app.api.v1.auth._auth_service") as mock_svc:
            mock_verify.return_value = mock_user_info
            mock_svc.link_provider = AsyncMock(return_value=mock_user)

            response = auth_client.post(
                "/api/v1/auth/link/google",
                json={"id_token": "valid-google-token"},
            )

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert "email" in data

    def test_link_invalid_provider_400(self, auth_client):
        """지원하지 않는 제공자 연동 시도 시 400 반환"""
        from backend.app.dependencies import get_current_user

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        async def mock_get_user():
            return mock_user

        from backend.app.main import app
        app.dependency_overrides[get_current_user] = mock_get_user

        response = auth_client.post(
            "/api/v1/auth/link/invalid_provider",
            json={"id_token": "some-token"},
        )

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 400

    def test_link_invalid_token_401(self, auth_client):
        """유효하지 않은 token으로 연동 시도 시 401 반환"""
        from backend.app.dependencies import get_current_user

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        async def mock_get_user():
            return mock_user

        from backend.app.main import app
        app.dependency_overrides[get_current_user] = mock_get_user

        with patch("backend.app.api.v1.auth.verify_google_token") as mock_verify:
            mock_verify.side_effect = ValueError("Invalid token")

            response = auth_client.post(
                "/api/v1/auth/link/google",
                json={"id_token": "invalid-token"},
            )

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /auth/link/{provider} - 소셜 계정 연동 해제
# ---------------------------------------------------------------------------


class TestUnlinkProvider:
    """소셜 계정 연동 해제 엔드포인트"""

    def test_unlink_google_success_200(self, auth_client):
        """Google 계정 연동 해제 성공"""
        from backend.app.dependencies import get_current_user

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.display_name = "User"
        mock_user.is_active = True
        mock_user.created_at = datetime.now(UTC).replace(tzinfo=None)
        mock_user.provider = "email"
        mock_user.avatar_url = None

        async def mock_get_user():
            return mock_user

        from backend.app.main import app
        app.dependency_overrides[get_current_user] = mock_get_user

        with patch("backend.app.api.v1.auth._auth_service") as mock_svc:
            mock_svc.unlink_provider = AsyncMock(return_value=mock_user)

            response = auth_client.delete("/api/v1/auth/link/google")

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert "email" in data

    def test_unlink_invalid_provider_400(self, auth_client):
        """지원하지 않는 제공자 해제 시도 시 400 반환"""
        from backend.app.dependencies import get_current_user

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        async def mock_get_user():
            return mock_user

        from backend.app.main import app
        app.dependency_overrides[get_current_user] = mock_get_user

        response = auth_client.delete("/api/v1/auth/link/invalid_provider")

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 400
