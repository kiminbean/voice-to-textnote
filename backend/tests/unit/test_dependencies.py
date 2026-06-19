"""
의존성 주입 함수 테스트
- get_redis_client(): Redis 클라이언트 싱글톤
- close_redis_client(): Redis 클라이언트 종료
- get_whisper_engine(): WhisperEngine 싱글톤
- get_diarization_engine(): DiarizationEngine 싱글톤
- get_db_session(): DB 세션 생성
- get_current_user(): JWT 인증 및 현재 사용자 반환
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession


class TestGetRedisClient:
    """get_redis_client() 싱글톤 테스트"""

    @pytest.mark.asyncio
    async def test_returns_redis_client(self):
        """Redis 클라이언트 인스턴스 반환 확인"""
        from backend.app.dependencies import get_redis_client

        # aioredis.from_url를 mock
        with patch("backend.app.dependencies.aioredis.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_from_url.return_value = mock_client

            client = get_redis_client()
            assert client is not None

    @pytest.mark.asyncio
    async def test_singleton_behavior(self):
        """싱글톤 동작 확인 - 여러 호출에서 같은 인스턴스 반환"""
        from backend.app.dependencies import get_redis_client

        with patch("backend.app.dependencies.aioredis.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_from_url.return_value = mock_client

            client1 = get_redis_client()
            client2 = get_redis_client()
            assert client1 is client2


class TestCloseRedisClient:
    """close_redis_client() 테스트"""

    @pytest.mark.asyncio
    async def test_close_when_cache_empty(self):
        """캐시가 비어있을 때 예외 없이 반환"""
        from backend.app.dependencies import close_redis_client, get_redis_client

        # 캐시 비우기
        get_redis_client.cache_clear()

        # 예외 없어야 함
        await close_redis_client()

    @pytest.mark.asyncio
    async def test_close_and_clear_cache(self):
        """클라이언트 종료 후 캐시 비워짐 확인"""
        from backend.app.dependencies import close_redis_client, get_redis_client

        with patch("backend.app.dependencies.aioredis.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_client.close = MagicMock()
            mock_client.aclose = MagicMock()
            mock_from_url.return_value = mock_client

            # 클라이언트 생성
            get_redis_client()
            assert get_redis_client.cache_info().currsize > 0

            # 종료
            await close_redis_client()

            # 캐시 비워짐 확인
            assert get_redis_client.cache_info().currsize == 0


class TestGetWhisperEngine:
    """get_whisper_engine() 싱글톤 테스트"""

    @pytest.mark.asyncio
    async def test_returns_engine_instance(self):
        """WhisperEngine 인스턴스 반환 확인"""
        from backend.app.dependencies import get_whisper_engine

        with patch("backend.ml.stt_engine.WhisperEngine.get_instance"):
            engine = get_whisper_engine()
            assert engine is not None

    @pytest.mark.asyncio
    async def test_singleton_behavior(self):
        """싱글톤 동작 확인"""
        from backend.app.dependencies import get_whisper_engine

        with patch("backend.ml.stt_engine.WhisperEngine.get_instance"):
            engine1 = get_whisper_engine()
            engine2 = get_whisper_engine()
            assert engine1 is engine2


class TestGetDiarizationEngine:
    """get_diarization_engine() 싱글톤 테스트"""

    @pytest.mark.asyncio
    async def test_returns_engine_instance(self):
        """DiarizationEngine 인스턴스 반환 확인"""
        from backend.app.dependencies import get_diarization_engine

        with patch("backend.ml.diarization_engine.DiarizationEngine.get_instance"):
            engine = get_diarization_engine()
            assert engine is not None

    @pytest.mark.asyncio
    async def test_singleton_behavior(self):
        """싱글톤 동작 확인"""
        from backend.app.dependencies import get_diarization_engine

        with patch("backend.ml.diarization_engine.DiarizationEngine.get_instance"):
            engine1 = get_diarization_engine()
            engine2 = get_diarization_engine()
            assert engine1 is engine2


class TestGetDbSession:
    """get_db_session() DB 세션 생성 테스트"""

    @pytest.mark.asyncio
    async def test_yields_async_session(self):
        """AsyncSession 인스턴스 yield 확인"""
        from backend.app.dependencies import get_db_session

        session_generator = get_db_session()
        try:
            session = await anext(session_generator)
            assert isinstance(session, AsyncSession)
        finally:
            await session_generator.aclose()

    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """세션 자동 정리 확인"""
        from backend.app.dependencies import get_db_session

        session = None
        async for s in get_db_session():
            session = s
            # 세션이 활성화되어 있어야 함
            assert session.is_active

        # 컨텍스트 종료 후 세션 정리됨


class TestGetCurrentUser:
    """get_current_user() JWT 인증 테스트"""

    @pytest.fixture
    def mock_request(self):
        """Mock Request 객체"""
        request = MagicMock(spec=Request)
        return request

    @pytest.fixture
    def mock_db_session(self):
        """Mock DB 세션"""
        session = AsyncMock(spec=AsyncSession)
        # execute 메서드는 비동기로 mock
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_no_authorization_header(self, mock_request, mock_db_session):
        """Authorization 헤더 없으면 401 에러"""
        from backend.app.dependencies import get_current_user

        mock_request.headers.get = MagicMock(return_value=None)

        with pytest.raises(HTTPException) as exc:
            await get_current_user(mock_request, mock_db_session)

        assert exc.value.status_code == 401
        assert "인증이 필요합니다" in exc.value.detail

    @pytest.mark.asyncio
    async def test_invalid_bearer_format(self, mock_request, mock_db_session):
        """Bearer 형식이 아니면 401 에러"""
        from backend.app.dependencies import get_current_user

        mock_request.headers.get = MagicMock(return_value="InvalidFormat")

        with pytest.raises(HTTPException) as exc:
            await get_current_user(mock_request, mock_db_session)

        assert exc.value.status_code == 401
        assert "인증이 필요합니다" in exc.value.detail

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self, mock_request, mock_db_session):
        """유효한 토큰으로 사용자 반환"""
        import uuid

        from backend.app.dependencies import get_current_user
        from backend.db.auth_models import User

        # Mock 설정
        mock_request.headers.get = MagicMock(return_value="Bearer valid_token")
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.is_active = True

        # AuthService mock - 지연 임포트되므로 경로 주의
        with patch("backend.services.auth_service.AuthService") as mock_auth_service_class:
            mock_auth_service = MagicMock()
            mock_auth_service.decode_access_token = MagicMock(
                return_value={"sub": str(mock_user.id)}
            )
            mock_auth_service_class.return_value = mock_auth_service

            # DB query mock
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
            mock_db_session.execute.return_value = mock_result

            user = await get_current_user(mock_request, mock_db_session)

            assert user is not None
            assert user.id == mock_user.id

    @pytest.mark.asyncio
    async def test_token_without_subject(self, mock_request, mock_db_session):
        """토큰에 sub 클레임 없으면 401 에러"""
        from backend.app.dependencies import get_current_user

        mock_request.headers.get = MagicMock(return_value="Bearer token")

        with patch("backend.services.auth_service.AuthService") as mock_auth_service_class:
            mock_auth_service = MagicMock()
            mock_auth_service.decode_access_token = MagicMock(return_value={})
            mock_auth_service_class.return_value = mock_auth_service

            with pytest.raises(HTTPException) as exc:
                await get_current_user(mock_request, mock_db_session)

            assert exc.value.status_code == 401
            assert "유효하지 않은 토큰입니다" in exc.value.detail

    @pytest.mark.asyncio
    async def test_invalid_uuid_format(self, mock_request, mock_db_session):
        """UUID 형식이 아니면 401 에러"""
        from backend.app.dependencies import get_current_user

        mock_request.headers.get = MagicMock(return_value="Bearer token")

        with patch("backend.services.auth_service.AuthService") as mock_auth_service_class:
            mock_auth_service = MagicMock()
            mock_auth_service.decode_access_token = MagicMock(return_value={"sub": "invalid-uuid"})
            mock_auth_service_class.return_value = mock_auth_service

            with pytest.raises(HTTPException) as exc:
                await get_current_user(mock_request, mock_db_session)

            assert exc.value.status_code == 401
            assert "유효하지 않은 토큰입니다" in exc.value.detail

    @pytest.mark.asyncio
    async def test_user_not_found(self, mock_request, mock_db_session):
        """사용자를 찾을 수 없으면 401 에러"""
        import uuid

        from backend.app.dependencies import get_current_user

        mock_request.headers.get = MagicMock(return_value="Bearer token")

        with patch("backend.services.auth_service.AuthService") as mock_auth_service_class:
            mock_auth_service = MagicMock()
            user_id = uuid.uuid4()
            mock_auth_service.decode_access_token = MagicMock(return_value={"sub": str(user_id)})
            mock_auth_service_class.return_value = mock_auth_service

            # DB에서 사용자 없음
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_db_session.execute.return_value = mock_result

            with pytest.raises(HTTPException) as exc:
                await get_current_user(mock_request, mock_db_session)

            assert exc.value.status_code == 401
            assert "사용자를 찾을 수 없습니다" in exc.value.detail

    @pytest.mark.asyncio
    async def test_inactive_user(self, mock_request, mock_db_session):
        """비활성 사용자면 401 에러"""
        import uuid

        from backend.app.dependencies import get_current_user
        from backend.db.auth_models import User

        mock_request.headers.get = MagicMock(return_value="Bearer token")

        with patch("backend.services.auth_service.AuthService") as mock_auth_service_class:
            mock_auth_service = MagicMock()
            user_id = uuid.uuid4()
            mock_auth_service.decode_access_token = MagicMock(return_value={"sub": str(user_id)})
            mock_auth_service_class.return_value = mock_auth_service

            # 비활성 사용자
            mock_user = MagicMock(spec=User)
            mock_user.id = user_id
            mock_user.is_active = False

            mock_result = AsyncMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
            mock_db_session.execute.return_value = mock_result

            with pytest.raises(HTTPException) as exc:
                await get_current_user(mock_request, mock_db_session)

            assert exc.value.status_code == 401
            assert "사용자를 찾을 수 없습니다" in exc.value.detail
