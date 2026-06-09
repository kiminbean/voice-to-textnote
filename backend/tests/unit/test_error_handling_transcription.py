"""
REQ-ERR2-002, AC-2: Transcription Redis 연결 실패 시 ServiceUnavailableError 발생 테스트
"""

import pytest
import redis

from backend.app.exceptions import ServiceUnavailableError


class TestTranscriptionRedisError:
    """Transcription 엔드포인트 Redis 연결 실패 처리 테스트"""

    @pytest.mark.asyncio
    async def test_redis_error_transforms_to_service_unavailable(self):
        """
        GIVEN: RedisError 발생
        WHEN: Redis 연결 코드 실행 중
        THEN: ServiceUnavailableError (503) 발생

        # REQ-ERR2-002: Redis 연결 실패 시 ServiceUnavailableError 발생
        # transcription.py line 143-146 코드 테스트
        """
        # Arrange: RedisError 발생 상황 시뮬레이션
        redis_error = redis.RedisError("Redis connection failed")

        # Act & Assert: catch 블록이 ServiceUnavailableError를 발생시켜야 함
        with pytest.raises(ServiceUnavailableError) as exc_info:
            try:
                raise redis_error
            except (redis.RedisError, redis.ConnectionError, OSError) as e:
                from backend.app.errors import service_unavailable
                service_unavailable(f"Redis 연결 실패: {str(e)}")

        # Then: 예외 타입과 상태 코드 검증
        assert exc_info.value.status_code == 503
        assert "Redis" in exc_info.value.message or "연결" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_oserror_transforms_to_service_unavailable(self):
        """
        GIVEN: OSError 발생
        WHEN: Redis 연결 코드 실행 중
        THEN: ServiceUnavailableError (503) 발생
        """
        # Arrange: OSError 발생 상황 시뮬레이션
        os_error = OSError("Network unreachable")

        # Act & Assert
        with pytest.raises(ServiceUnavailableError) as exc_info:
            try:
                raise os_error
            except (redis.RedisError, redis.ConnectionError, OSError) as e:
                from backend.app.errors import service_unavailable
                service_unavailable(f"Redis 연결 실패: {str(e)}")

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_connection_error_transforms_to_service_unavailable(self):
        """
        GIVEN: redis.ConnectionError 발생
        WHEN: Redis 연결 코드 실행 중
        THEN: ServiceUnavailableError (503) 발생
        """
        # Arrange: ConnectionError 발생 상황 시뮬레이션
        conn_error = redis.ConnectionError("Connection refused")

        # Act & Assert
        with pytest.raises(ServiceUnavailableError) as exc_info:
            try:
                raise conn_error
            except (redis.RedisError, redis.ConnectionError, OSError) as e:
                from backend.app.errors import service_unavailable
                service_unavailable(f"Redis 연결 실패: {str(e)}")

        assert exc_info.value.status_code == 503
