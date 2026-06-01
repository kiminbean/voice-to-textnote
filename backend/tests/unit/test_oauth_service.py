"""
REQ-OAUTH-001: OAuth 토큰 검증 서비스 단위 테스트

대상: services/oauth_service.py
  - verify_google_token (httpx + jwt mock)
  - verify_apple_token (httpx + jwt mock)
  - verify_apple_code_callback (trivial)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.oauth_service import (
    OAuthUserInfo,
    verify_apple_code_callback,
    verify_apple_token,
    verify_google_token,
)

# ---------------------------------------------------------------------------
# 공통 mock 데이터
# ---------------------------------------------------------------------------

_GOOGLE_CERTS = {
    "keys": [
        {
            "kid": "google-kid-123",
            "kty": "RSA",
            "alg": "RS256",
            "n": "fake",
            "e": "AQAB",
        }
    ]
}

_APPLE_CERTS = {
    "keys": [
        {
            "kid": "apple-kid-456",
            "kty": "RSA",
            "alg": "RS256",
            "n": "fake",
            "e": "AQAB",
        }
    ]
}

_GOOGLE_PAYLOAD = {
    "sub": "google-user-123",
    "email": "test@gmail.com",
    "name": "테스트유저",
    "picture": "https://avatar.example.com/test.jpg",
}

_APPLE_PAYLOAD = {
    "sub": "apple-user-456",
    "email": "test@icloud.com",
}


# ---------------------------------------------------------------------------
# verify_google_token
# ---------------------------------------------------------------------------


class TestVerifyGoogleToken:
    """Google ID token 검증."""

    @pytest.mark.asyncio
    async def test_successful_verification(self):
        """정상 토큰 → OAuthUserInfo 반환."""
        with patch("backend.services.oauth_service.settings") as mock_settings, \
             patch("backend.services.oauth_service.httpx.AsyncClient") as mock_client_cls, \
             patch("backend.services.oauth_service.jwt") as mock_jwt:

            mock_settings.google_client_id = "test-client-id"

            # httpx mock
            mock_resp = MagicMock()
            mock_resp.json.return_value = _GOOGLE_CERTS
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # jwt mock
            mock_jwt.get_unverified_header.return_value = {"kid": "google-kid-123"}
            mock_jwt.decode.return_value = _GOOGLE_PAYLOAD

            result = await verify_google_token("fake-id-token")

        assert isinstance(result, OAuthUserInfo)
        assert result.provider == "google"
        assert result.provider_id == "google-user-123"
        assert result.email == "test@gmail.com"
        assert result.display_name == "테스트유저"
        assert result.avatar_url == "https://avatar.example.com/test.jpg"

    @pytest.mark.asyncio
    async def test_no_client_id_raises(self):
        """GOOGLE_CLIENT_ID 미설정 시 ValueError."""
        with patch("backend.services.oauth_service.settings") as mock_settings:
            mock_settings.google_client_id = None
            with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID"):
                await verify_google_token("token")

    @pytest.mark.asyncio
    async def test_no_kid_in_header_raises(self):
        """JWT 헤더에 kid 없으면 ValueError."""
        with patch("backend.services.oauth_service.settings") as mock_settings, \
             patch("backend.services.oauth_service.httpx.AsyncClient") as mock_client_cls, \
             patch("backend.services.oauth_service.jwt") as mock_jwt:

            mock_settings.google_client_id = "test-client-id"
            mock_resp = MagicMock()
            mock_resp.json.return_value = _GOOGLE_CERTS
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            mock_jwt.get_unverified_header.return_value = {}

            with pytest.raises(ValueError, match="kid"):
                await verify_google_token("fake-id-token")

    @pytest.mark.asyncio
    async def test_no_matching_key_raises(self):
        """kid에 매칭되는 공개 키 없으면 ValueError."""
        with patch("backend.services.oauth_service.settings") as mock_settings, \
             patch("backend.services.oauth_service.httpx.AsyncClient") as mock_client_cls, \
             patch("backend.services.oauth_service.jwt") as mock_jwt:

            mock_settings.google_client_id = "test-client-id"
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"keys": [{"kid": "other-kid"}]}
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            mock_jwt.get_unverified_header.return_value = {"kid": "unknown-kid"}

            with pytest.raises(ValueError, match="공개 키"):
                await verify_google_token("fake-id-token")

    @pytest.mark.asyncio
    async def test_missing_sub_or_email_raises(self):
        """sub 또는 email 없으면 ValueError."""
        with patch("backend.services.oauth_service.settings") as mock_settings, \
             patch("backend.services.oauth_service.httpx.AsyncClient") as mock_client_cls, \
             patch("backend.services.oauth_service.jwt") as mock_jwt:

            mock_settings.google_client_id = "test-client-id"
            mock_resp = MagicMock()
            mock_resp.json.return_value = _GOOGLE_CERTS
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            mock_jwt.get_unverified_header.return_value = {"kid": "google-kid-123"}
            mock_jwt.decode.return_value = {"sub": None, "email": None}

            with pytest.raises(ValueError, match="필수 필드"):
                await verify_google_token("fake-id-token")

    @pytest.mark.asyncio
    async def test_jwt_decode_failure_raises(self):
        """JWT 디코드 실패 시 ValueError."""
        from jose import JWTError

        with patch("backend.services.oauth_service.settings") as mock_settings, \
             patch("backend.services.oauth_service.httpx.AsyncClient") as mock_client_cls, \
             patch("backend.services.oauth_service.jwt") as mock_jwt:

            mock_settings.google_client_id = "test-client-id"
            mock_resp = MagicMock()
            mock_resp.json.return_value = _GOOGLE_CERTS
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            mock_jwt.get_unverified_header.return_value = {"kid": "google-kid-123"}
            mock_jwt.decode.side_effect = JWTError("invalid signature")

            with pytest.raises(ValueError, match="검증 실패"):
                await verify_google_token("fake-id-token")

    @pytest.mark.asyncio
    async def test_no_name_uses_email_prefix(self):
        """name 필드 없으면 email 접두어를 display_name으로."""
        with patch("backend.services.oauth_service.settings") as mock_settings, \
             patch("backend.services.oauth_service.httpx.AsyncClient") as mock_client_cls, \
             patch("backend.services.oauth_service.jwt") as mock_jwt:

            mock_settings.google_client_id = "test-client-id"
            mock_resp = MagicMock()
            mock_resp.json.return_value = _GOOGLE_CERTS
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            mock_jwt.get_unverified_header.return_value = {"kid": "google-kid-123"}
            mock_jwt.decode.return_value = {
                "sub": "user-1",
                "email": "myname@gmail.com",
            }

            result = await verify_google_token("fake-id-token")
            assert result.display_name == "myname"


# ---------------------------------------------------------------------------
# verify_apple_token
# ---------------------------------------------------------------------------


class TestVerifyAppleToken:
    """Apple ID token 검증."""

    @pytest.mark.asyncio
    async def test_successful_verification(self):
        """정상 Apple 토큰 → OAuthUserInfo."""
        with patch("backend.services.oauth_service.settings") as mock_settings, \
             patch("backend.services.oauth_service.httpx.AsyncClient") as mock_client_cls, \
             patch("backend.services.oauth_service.jwt") as mock_jwt:

            mock_settings.apple_client_id = "com.test.app"
            mock_settings.apple_team_id = "TEAM123"

            mock_resp = MagicMock()
            mock_resp.json.return_value = _APPLE_CERTS
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            mock_jwt.get_unverified_header.return_value = {"kid": "apple-kid-456"}
            mock_jwt.decode.return_value = _APPLE_PAYLOAD

            result = await verify_apple_token("fake-apple-token")

        assert result.provider == "apple"
        assert result.provider_id == "apple-user-456"
        assert result.email == "test@icloud.com"
        assert result.avatar_url is None

    @pytest.mark.asyncio
    async def test_no_settings_raises(self):
        """Apple 설정 누락 시 ValueError."""
        with patch("backend.services.oauth_service.settings") as mock_settings:
            mock_settings.apple_client_id = None
            mock_settings.apple_team_id = None
            with pytest.raises(ValueError, match="Apple"):
                await verify_apple_token("token")

    @pytest.mark.asyncio
    async def test_no_sub_raises(self):
        """sub 없으면 ValueError."""
        with patch("backend.services.oauth_service.settings") as mock_settings, \
             patch("backend.services.oauth_service.httpx.AsyncClient") as mock_client_cls, \
             patch("backend.services.oauth_service.jwt") as mock_jwt:

            mock_settings.apple_client_id = "com.test.app"
            mock_settings.apple_team_id = "TEAM123"

            mock_resp = MagicMock()
            mock_resp.json.return_value = _APPLE_CERTS
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            mock_jwt.get_unverified_header.return_value = {"kid": "apple-kid-456"}
            mock_jwt.decode.return_value = {"sub": None}

            with pytest.raises(ValueError, match="필수 필드"):
                await verify_apple_token("fake-token")

    @pytest.mark.asyncio
    async def test_no_email_uses_private_relay(self):
        """email 없으면 private relay 주소 생성."""
        with patch("backend.services.oauth_service.settings") as mock_settings, \
             patch("backend.services.oauth_service.httpx.AsyncClient") as mock_client_cls, \
             patch("backend.services.oauth_service.jwt") as mock_jwt:

            mock_settings.apple_client_id = "com.test.app"
            mock_settings.apple_team_id = "TEAM123"

            mock_resp = MagicMock()
            mock_resp.json.return_value = _APPLE_CERTS
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            mock_jwt.get_unverified_header.return_value = {"kid": "apple-kid-456"}
            mock_jwt.decode.return_value = {"sub": "abc12345xyz", "email": None}

            result = await verify_apple_token("fake-token")
            assert "apple.privaterelay" in result.email
            assert result.display_name.startswith("apple_")


# ---------------------------------------------------------------------------
# verify_apple_code_callback
# ---------------------------------------------------------------------------


class TestVerifyAppleCodeCallback:
    """Apple authorization code 콜백 (미구현)."""

    def test_returns_empty_dict(self):
        result = verify_apple_code_callback("some-code")
        assert result == {}
