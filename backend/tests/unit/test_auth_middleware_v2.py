"""
인증 미들웨어 추가 테스트 - 게스트 토큰 및 JWT 액세스 토큰
미커버 라인: 48-86 (_verify_guest_token), 104-129 (_verify_access_token), 154-161, 166-167
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.asyncio as aioredis
from fastapi import Request
from jose import JWTError

from backend.app.middleware.auth import (
    _verify_access_token,
    _verify_guest_token,
    verify_api_key,
)

# ==========================================================================
# _verify_guest_token 함수 테스트 (48-86행)
# ==========================================================================


class TestVerifyGuestToken:
    """게스트 토큰 검증 함수 테스트"""

    @pytest.mark.asyncio
    async def test_verify_guest_token_success(self):
        """유효한 게스트 토큰 검증 성공"""
        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()
        mock_request.state = mock_state

        mock_redis = AsyncMock(spec=aioredis.Redis)
        mock_redis.exists = AsyncMock(return_value=1)  # 세션 존재

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
                mock_decode.return_value = {
                    "type": "guest",
                    "sub": "guest-session-123"
                }

                result = await _verify_guest_token(
                    mock_request, "valid-token", mock_redis
                )

                assert result == "guest-session-123"
                assert mock_request.state.is_guest is True
                assert mock_request.state.guest_session_id == "guest-session-123"

    @pytest.mark.asyncio
    async def test_verify_guest_token_jwt_decode_error(self):
        """JWT 디코딩 실패 시 401 예외"""
        mock_request = MagicMock(spec=Request)
        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth.jwt.decode", side_effect=JWTError):
                with pytest.raises(Exception) as exc_info:
                    await _verify_guest_token(
                        mock_request, "invalid-token", mock_redis
                    )

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_guest_token_wrong_type_claim(self):
        """type 클레임이 'guest'가 아닌 경우 401"""
        mock_request = MagicMock(spec=Request)
        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
                mock_decode.return_value = {"type": "access", "sub": "123"}

                with pytest.raises(Exception) as exc_info:
                    await _verify_guest_token(
                        mock_request, "token", mock_redis
                    )

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_guest_token_missing_sub_claim(self):
        """sub 클레임 누락 시 401"""
        mock_request = MagicMock(spec=Request)
        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
                mock_decode.return_value = {"type": "guest"}

                with pytest.raises(Exception) as exc_info:
                    await _verify_guest_token(
                        mock_request, "token", mock_redis
                    )

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_guest_token_session_expired(self):
        """Redis 세션 만료 시 401"""
        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()
        mock_request.state = mock_state

        mock_redis = AsyncMock(spec=aioredis.Redis)
        mock_redis.exists = AsyncMock(return_value=0)  # 세션 없음

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
                mock_decode.return_value = {
                    "type": "guest",
                    "sub": "expired-session"
                }

                with pytest.raises(Exception) as exc_info:
                    await _verify_guest_token(
                        mock_request, "token", mock_redis
                )

                assert exc_info.value.status_code == 401
                assert "만료" in exc_info.value.detail


# ==========================================================================
# _verify_access_token 함수 테스트 (104-129행)
# ==========================================================================


class TestVerifyAccessToken:
    """JWT 액세스 토큰 검증 함수 테스트"""

    @pytest.mark.asyncio
    async def test_verify_access_token_success(self):
        """유효한 액세스 토큰 검증 성공"""
        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()
        mock_request.state = mock_state

        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
                mock_decode.return_value = {
                    "type": "access",
                    "sub": "user-123",
                    "email": "user@example.com"
                }

                result = await _verify_access_token(
                    mock_request, "valid-token", mock_redis
                )

                assert result == "user-123"
                assert mock_request.state.is_guest is False
                assert mock_request.state.user_id == "user-123"
                assert mock_request.state.user_email == "user@example.com"

    @pytest.mark.asyncio
    async def test_verify_access_token_jwt_decode_error(self):
        """JWT 디코딩 실패 시 401"""
        mock_request = MagicMock(spec=Request)
        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth.jwt.decode", side_effect=JWTError):
                with pytest.raises(Exception) as exc_info:
                    await _verify_access_token(
                        mock_request, "invalid-token", mock_redis
                    )

                assert exc_info.value.status_code == 401
                assert "유효하지 않거나 만료된" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_access_token_wrong_type(self):
        """type 클레임이 'access'가 아닌 경우"""
        mock_request = MagicMock(spec=Request)
        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
                mock_decode.return_value = {"type": "guest", "sub": "123"}

                with pytest.raises(Exception) as exc_info:
                    await _verify_access_token(
                        mock_request, "token", mock_redis
                    )

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_access_token_missing_sub(self):
        """sub 클레임 누락 시 401"""
        mock_request = MagicMock(spec=Request)
        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
                mock_decode.return_value = {"type": "access"}

                with pytest.raises(Exception) as exc_info:
                    await _verify_access_token(
                        mock_request, "token", mock_redis
                    )

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_access_token_missing_email_defaults(self):
        """email 클레임 없으면 빈 문자열 기본값"""
        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()
        mock_request.state = mock_state

        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
                mock_decode.return_value = {
                    "type": "access",
                    "sub": "user-456"
                }

                result = await _verify_access_token(
                    mock_request, "token", mock_redis
                )

                assert result == "user-456"
                assert mock_request.state.user_email == ""


# ==========================================================================
# verify_api_key 함수 추가 테스트 (154-161, 166-167행)
# ==========================================================================


class TestVerifyApiKeyBearerTokens:
    """Bearer 토큰 인증 경로 테스트"""

    @pytest.mark.asyncio
    async def test_verify_api_key_with_guest_token(self):
        """Bearer guest:<token> 형식 인증"""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer guest:guest-token-123"}
        mock_request.state = {}

        mock_redis = AsyncMock(spec=aioredis.Redis)
        mock_redis.exists = AsyncMock(return_value=1)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.api_keys = ["api-key-1"]
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth._verify_guest_token") as mock_verify_guest:
                mock_verify_guest.return_value = "guest-session-abc"

                result = await verify_api_key(
                    request=mock_request,
                    api_key_header=None,
                    redis_client=mock_redis
                )

                assert result == "guest-session-abc"
                mock_verify_guest.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_api_key_with_jwt_access_token(self):
        """Bearer <jwt> 형식 액세스 토큰 인증"""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer jwt-access-token"}
        mock_request.state = {}

        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.api_keys = ["api-key-1"]
            mock_settings.jwt_secret = "test-secret"

            with patch("backend.app.middleware.auth._verify_access_token") as mock_verify_access:
                mock_verify_access.return_value = "user-xyz"

                result = await verify_api_key(
                    request=mock_request,
                    api_key_header=None,
                    redis_client=mock_redis
                )

                assert result == "user-xyz"
                mock_verify_access.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_api_key_production_no_api_keys_raises_503(self):
        """프로덕션 환경에서 API_KEYS 미설정 시 503 에러"""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}
        mock_request.state = {}

        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.api_keys = []
            mock_settings.environment = "production"

            with pytest.raises(Exception) as exc_info:
                await verify_api_key(
                    request=mock_request,
                    api_key_header=None,
                    redis_client=mock_redis
                )

                assert exc_info.value.status_code == 503
                assert "인증 설정" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_api_key_dev_mode_no_keys_returns_dev_mode(self):
        """개발 모드에서 API_KEYS 미설정 시 'dev-mode' 반환"""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}
        mock_request.state = {}

        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.api_keys = []
            mock_settings.environment = "development"

            result = await verify_api_key(
                request=mock_request,
                api_key_header=None,
                redis_client=mock_redis
            )

            assert result == "dev-mode"

    @pytest.mark.asyncio
    async def test_verify_api_key_uses_secrets_compare_digest(self):
        """secrets.compare_digest로 타이밍 안전 공격 방지"""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}
        mock_request.state = {}

        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.api_keys = ["correct-key"]

            # secrets.compare_digest는 문자열 비교에 타이밍 안전성 제공
            result = await verify_api_key(
                request=mock_request,
                api_key_header="correct-key",
                redis_client=mock_redis
            )

            assert result == "correct-key"

    @pytest.mark.asyncio
    async def test_verify_api_key_bearer_without_prefix_falls_to_api_key(self):
        """Bearer 접두사 없으면 API Key 검증으로 폴백"""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer random-token"}
        mock_request.state = {}

        mock_redis = AsyncMock(spec=aioredis.Redis)

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.api_keys = ["valid-api-key"]

            with pytest.raises(Exception) as exc_info:
                await verify_api_key(
                    request=mock_request,
                    api_key_header="valid-api-key",
                    redis_client=mock_redis
                )

            # API Key 검증 실패 (random-token != valid-api-key)
            assert exc_info.value.status_code == 401
