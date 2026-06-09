"""
REQ-ERR2-004, AC-4: auth.py HTTPException → Custom Exceptions 테스트
SPEC-ERR-002, TASK-003: 인증 미들웨어에서 HTTPException을 커스텀 예외로 변환
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.exceptions import ServiceUnavailableError, UnauthorizedError
from backend.app.middleware.auth import (
    _verify_access_token,
    _verify_guest_token,
    verify_api_key,
)


class TestGuestTokenExceptionTransformation:
    """게스트 토큰 검증 실패 시 UnauthorizedError 변환 테스트"""

    @pytest.mark.asyncio
    async def test_jwt_decode_failure_raises_unauthorized(self):
        """
        GIVEN: 유효하지 않은 JWT 토큰
        WHEN: _verify_guest_token 호출 시 JWT 디코딩 실패
        THEN: HTTPException(401) 대신 UnauthorizedError 발생

        # REQ-ERR2-004: HTTPException → 커스텀 예외
        # AC-4: status_code=401 → UnauthorizedError
        """
        # Arrange
        mock_request = MagicMock()
        mock_redis = AsyncMock()

        # Act & Assert
        with pytest.raises(UnauthorizedError) as exc_info:
            await _verify_guest_token(
                request=mock_request,
                token_str="invalid.jwt.token",
                redis_client=mock_redis,
            )

        # Then: 예외 메시지 검증
        assert "유효하지 않거나 만료된" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wrong_type_claim_raises_unauthorized(self):
        """
        GIVEN: type 클레임이 "guest"가 아닌 토큰
        WHEN: _verify_guest_token 호출
        THEN: UnauthorizedError 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_redis = AsyncMock()

        # 잘못된 type 클레임을 가진 토큰 디코딩 mock
        with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
            mock_decode.return_value = {"type": "access", "sub": "guest-123"}

            # Act & Assert
            with pytest.raises(UnauthorizedError) as exc_info:
                await _verify_guest_token(
                    request=mock_request,
                    token_str="valid.jwt.but.wrong.type",
                    redis_client=mock_redis,
                )

            assert "유효하지 않은 게스트 토큰" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_sub_claim_raises_unauthorized(self):
        """
        GIVEN: sub 클레임이 없는 토큰
        WHEN: _verify_guest_token 호출
        THEN: UnauthorizedError 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_redis = AsyncMock()

        with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
            mock_decode.return_value = {"type": "guest"}  # sub 없음

            # Act & Assert
            with pytest.raises(UnauthorizedError) as exc_info:
                await _verify_guest_token(
                    request=mock_request,
                    token_str="valid.jwt.no.sub",
                    redis_client=mock_redis,
                )

            assert "유효하지 않은 게스트 토큰" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_expired_redis_session_raises_unauthorized(self):
        """
        GIVEN: Redis에 세션이 만료된 토큰
        WHEN: _verify_guest_token 호출
        THEN: UnauthorizedError 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0  # 세션 만료

        with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
            mock_decode.return_value = {"type": "guest", "sub": "expired-session"}

            # Act & Assert
            with pytest.raises(UnauthorizedError) as exc_info:
                await _verify_guest_token(
                    request=mock_request,
                    token_str="valid.jwt.expired.session",
                    redis_client=mock_redis,
                )

            assert "세션이 만료되었거나" in str(exc_info.value)


class TestAccessTokenExceptionTransformation:
    """JWT 액세스 토큰 검증 실패 시 UnauthorizedError 변환 테스트"""

    @pytest.mark.asyncio
    async def test_invalid_jwt_raises_unauthorized(self):
        """
        GIVEN: 유효하지 않은 JWT 액세스 토큰
        WHEN: _verify_access_token 호출
        THEN: UnauthorizedError 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_redis = AsyncMock()

        # Act & Assert
        with pytest.raises(UnauthorizedError) as exc_info:
            await _verify_access_token(
                request=mock_request,
                token_str="invalid.token",
                redis_client=mock_redis,
            )

        assert "유효하지 않거나 만료된" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wrong_access_type_raises_unauthorized(self):
        """
        GIVEN: type 클레임이 "access"가 아닌 토큰
        WHEN: _verify_access_token 호출
        THEN: UnauthorizedError 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_redis = AsyncMock()

        with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
            mock_decode.return_value = {"type": "refresh", "sub": "user-123"}

            # Act & Assert
            with pytest.raises(UnauthorizedError) as exc_info:
                await _verify_access_token(
                    request=mock_request,
                    token_str="valid.jwt.refresh.type",
                    redis_client=mock_redis,
                )

            assert "유효하지 않은 토큰" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_sub_in_access_token_raises_unauthorized(self):
        """
        GIVEN: sub 클레임이 없는 액세스 토큰
        WHEN: _verify_access_token 호출
        THEN: UnauthorizedError 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_redis = AsyncMock()

        with patch("backend.app.middleware.auth.jwt.decode") as mock_decode:
            mock_decode.return_value = {"type": "access"}  # sub 없음

            # Act & Assert
            with pytest.raises(UnauthorizedError) as exc_info:
                await _verify_access_token(
                    request=mock_request,
                    token_str="valid.access.no.sub",
                    redis_client=mock_redis,
                )

            assert "유효하지 않은 토큰" in str(exc_info.value)


class TestAPIKeyVerificationExceptionTransformation:
    """API Key 검증 실패 시 커스텀 예외 변환 테스트"""

    @pytest.mark.asyncio
    async def test_missing_api_key_in_production_raises_service_unavailable(self):
        """
        GIVEN: 프로덕션 환경에서 API_KEYS 미설정
        WHEN: verify_api_key 호출
        THEN: ServiceUnavailableError(503) 발생

        # REQ-ERR2-004: status_code=503 → ServiceUnavailableError
        """
        # Arrange
        mock_request = MagicMock()
        mock_request.headers = {}  # Authorization 헤더 없음
        mock_redis = AsyncMock()

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.api_keys = []
            mock_settings.environment = "production"

            # Act & Assert
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await verify_api_key(
                    request=mock_request,
                    api_key_header=None,
                    redis_client=mock_redis,
                )

            assert "서버 인증 설정" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_api_key_header_raises_unauthorized(self):
        """
        GIVEN: API_KEYS 설정되어 있으나 헤더 누락
        WHEN: verify_api_key 호출
        THEN: UnauthorizedError(401) 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_redis = AsyncMock()

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.api_keys = ["valid-key-123"]

            # Act & Assert
            with pytest.raises(UnauthorizedError) as exc_info:
                await verify_api_key(
                    request=mock_request,
                    api_key_header=None,
                    redis_client=mock_redis,
                )

            assert "API Key가 필요합니다" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises_unauthorized(self):
        """
        GIVEN: 잘못된 API Key 헤더
        WHEN: verify_api_key 호출
        THEN: UnauthorizedError(401) 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_redis = AsyncMock()

        with patch("backend.app.middleware.auth.settings") as mock_settings:
            mock_settings.api_keys = ["valid-key-123"]

            # Act & Assert
            with pytest.raises(UnauthorizedError) as exc_info:
                await verify_api_key(
                    request=mock_request,
                    api_key_header="invalid-key",
                    redis_client=mock_redis,
                )

            assert "유효하지 않은 API Key" in str(exc_info.value)


class TestDependenciesExceptionTransformation:
    """dependencies.py get_current_user HTTPException → Custom 변환 테스트"""

    @pytest.mark.asyncio
    async def test_missing_auth_header_raises_unauthorized(self):
        """
        GIVEN: Authorization 헤더 누락
        WHEN: get_current_user 호출
        THEN: UnauthorizedError(401) 발생

        # REQ-ERR2-004: dependencies.py HTTPException → 커스텀 예외
        # AC-4: status_code=401 → UnauthorizedError
        """
        # Arrange
        mock_request = MagicMock()
        mock_request.headers = {}  # Authorization 헤더 없음

        mock_db = AsyncMock()

        # Act & Assert
        with pytest.raises(UnauthorizedError) as exc_info:
            from backend.app.dependencies import get_current_user
            await get_current_user(request=mock_request, db=mock_db)

        assert "인증이 필요합니다" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_bearer_format_raises_unauthorized(self):
        """
        GIVEN: Authorization 헤더가 "Bearer "로 시작하지 않음
        WHEN: get_current_user 호출
        THEN: UnauthorizedError 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "InvalidFormat token"}
        mock_db = AsyncMock()

        # Act & Assert
        with pytest.raises(UnauthorizedError) as exc_info:
            from backend.app.dependencies import get_current_user
            await get_current_user(request=mock_request, db=mock_db)

        assert "인증이 필요합니다" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_token_raises_unauthorized(self):
        """
        GIVEN: 유효하지 않은 JWT 토큰
        WHEN: get_current_user 호출 시 AuthService.decode_access_token 실패
        THEN: UnauthorizedError 발생 (AuthService HTTPException catch 후 변환)

        # REQ-ERR2-004: dependencies.py HTTPException → 커스텀 예외
        # AC-4: status_code=401 → UnauthorizedError
        """
        # Arrange
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer invalid.token"}
        mock_db = AsyncMock()

        # Act & Assert
        with pytest.raises(UnauthorizedError) as exc_info:
            from backend.app.dependencies import get_current_user
            await get_current_user(request=mock_request, db=mock_db)

        assert "유효하지 않거나 만료된" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_user_id_raises_unauthorized(self):
        """
        GIVEN: JWT 디코딩 성공했으나 sub 클레임 누락
        WHEN: get_current_user 호출
        THEN: UnauthorizedError 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid.but.no.sub"}

        mock_db = AsyncMock()

        # AuthService mock: sub 없는 payload 반환
        with patch("backend.services.auth_service.AuthService") as mock_auth_service:
            mock_instance = MagicMock()
            mock_instance.decode_access_token.return_value = {}  # sub 없음
            mock_auth_service.return_value = mock_instance

            # Act & Assert
            with pytest.raises(UnauthorizedError) as exc_info:
                from backend.app.dependencies import get_current_user
                await get_current_user(request=mock_request, db=mock_db)

            assert "유효하지 않은 토큰입니다" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises_unauthorized(self):
        """
        GIVEN: JWT의 sub 클레임이 유효하지 않은 UUID
        WHEN: get_current_user 호출
        THEN: UnauthorizedError 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid.but.bad.uuid"}

        mock_db = AsyncMock()

        with patch("backend.services.auth_service.AuthService") as mock_auth_service:
            mock_instance = MagicMock()
            mock_instance.decode_access_token.return_value = {"sub": "not-a-uuid"}
            mock_auth_service.return_value = mock_instance

            # Act & Assert
            with pytest.raises(UnauthorizedError) as exc_info:
                from backend.app.dependencies import get_current_user
                await get_current_user(request=mock_request, db=mock_db)

            assert "유효하지 않은 토큰입니다" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_user_not_found_raises_unauthorized(self):
        """
        GIVEN: JWT 유효하나 DB에 사용자 없음
        WHEN: get_current_user 호출
        THEN: UnauthorizedError 발생
        """
        # Arrange
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid.token"}

        mock_db = AsyncMock()
        # DB에서 사용자 찾지 못함 (scalar_one_or_none() → None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        import uuid as _uuid
        test_user_id = _uuid.uuid4()

        with patch("backend.services.auth_service.AuthService") as mock_auth_service:
            mock_instance = MagicMock()
            mock_instance.decode_access_token.return_value = {"sub": str(test_user_id)}
            mock_auth_service.return_value = mock_instance

            # Act & Assert
            with pytest.raises(UnauthorizedError) as exc_info:
                from backend.app.dependencies import get_current_user
                await get_current_user(request=mock_request, db=mock_db)

            assert "사용자를 찾을 수 없습니다" in str(exc_info.value)


class TestUnifiedErrorFormat:
    """통합 에러 형식 검증 테스트 (REQ-ERR2-005)"""

    @pytest.mark.asyncio
    async def test_unauthorized_error_produces_unified_format(self):
        """
        GIVEN: VoiceNoteError 계열 예외 발생
        WHEN: FastAPI 예외 핸들러 처리
        THEN: 통합 에러 형식 반환 {error_code, message, request_id}

        # REQ-ERR2-005: VoiceNoteError → 통합 형식
        """
        # Arrange: 실제 예외 발생
        from backend.app.exceptions import UnauthorizedError

        error = UnauthorizedError(message="테스트 인증 실패")

        # Act: 예외의 속성 검증
        # VoiceNoteError는 error_code와 status_code를 가짐
        assert hasattr(error, "error_code")
        assert hasattr(error, "status_code")
        assert error.status_code == 401
        assert error.error_code == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_service_unavailable_error_produces_unified_format(self):
        """
        GIVEN: ServiceUnavailableError 발생
        WHEN: FastAPI 예외 핸들러 처리
        THEN: 통합 에러 형식 반환
        """
        # Arrange
        from backend.app.exceptions import ServiceUnavailableError

        error = ServiceUnavailableError(message="서비스 일시 중단")

        # Act & Assert
        assert hasattr(error, "error_code")
        assert hasattr(error, "status_code")
        assert error.status_code == 503
        assert error.error_code == "SERVICE_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_all_custom_errors_have_required_attributes(self):
        """
        GIVEN: 모든 VoiceNoteError 서브클래스
        WHEN: 예외 인스턴스 생성
        THEN: error_code, status_code, message 속성 존재

        # REQ-ERR2-005: 모든 커스텀 예외는 통합 형식 준수
        """
        # Arrange: 모든 커스텀 예외 import
        from backend.app.exceptions import (
            ForbiddenError,
            NotFoundError,
            ServiceUnavailableError,
            UnauthorizedError,
        )

        errors_to_test = [
            (UnauthorizedError, "UNAUTHORIZED", 401),
            (ForbiddenError, "FORBIDDEN", 403),
            (NotFoundError, "NOT_FOUND", 404),
            (ServiceUnavailableError, "SERVICE_UNAVAILABLE", 503),
        ]

        # Act & Assert: 각 예외 검증
        for error_class, expected_code, expected_status in errors_to_test:
            error = error_class(message="테스트 메시지")

            assert error.error_code == expected_code, f"{error_class.__name__} error_code mismatch"
            assert error.status_code == expected_status, f"{error_class.__name__} status_code mismatch"
            assert str(error) == "테스트 메시지", f"{error_class.__name__} message format mismatch"
