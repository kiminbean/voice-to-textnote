"""
Redis 클라이언트 단위 테스트
테스트 대상: backend.workers.redis_client.get_worker_redis
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_pool():
    """테스트 간 전역 연결 풀 초기화"""
    from backend.workers import redis_client
    redis_client._pool = None
    yield
    redis_client._pool = None


class TestGetWorkerRedis:
    """get_worker_redis 함수 테스트"""

    @patch("backend.workers.redis_client.ConnectionPool")
    @patch("backend.workers.redis_client.redis")
    def test_creates_connection_pool_on_first_call(self, mock_redis, mock_connection_pool):
        """첫 호출 시 연결 풀 생성 검증"""
        # Arrange
        mock_pool = MagicMock()
        mock_connection_pool.from_url.return_value = mock_pool
        mock_redis_instance = MagicMock()
        mock_redis.Redis.return_value = mock_redis_instance

        with patch("backend.workers.redis_client.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            # Act
            from backend.workers.redis_client import get_worker_redis
            result = get_worker_redis()

            # Assert
            mock_connection_pool.from_url.assert_called_once_with(
                "redis://localhost:6379/0",
                max_connections=10,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            mock_redis.Redis.assert_called_once_with(connection_pool=mock_pool)
            assert result == mock_redis_instance

    @patch("backend.workers.redis_client.ConnectionPool")
    @patch("backend.workers.redis_client.redis")
    def test_reuses_existing_connection_pool(self, mock_redis, mock_connection_pool):
        """이후 호출 시 기존 연결 풀 재사용 검증"""
        # Arrange
        mock_pool = MagicMock()
        mock_connection_pool.from_url.return_value = mock_pool

        with patch("backend.workers.redis_client.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            from backend.workers.redis_client import get_worker_redis

            # Act - 첫 번째 호출
            get_worker_redis()

            # Act - 두 번째 호출
            get_worker_redis()

            # Assert
            assert mock_redis.Redis.call_count == 2  # Redis 인스턴스는 매번 생성
            # 연결 풀은 한 번만 생성되어야 함
            mock_connection_pool.from_url.assert_called_once()

    @patch("backend.workers.redis_client.ConnectionPool")
    @patch("backend.workers.redis_client.redis")
    def test_uses_correct_pool_parameters(self, mock_redis, mock_connection_pool):
        """연결 풀 파라미터 검증"""
        # Arrange
        with patch("backend.workers.redis_client.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            from backend.workers.redis_client import get_worker_redis

            # Act
            get_worker_redis()

            # Assert
            mock_connection_pool.from_url.assert_called_once()
            call_kwargs = mock_connection_pool.from_url.call_args[1]
            assert call_kwargs["max_connections"] == 10
            assert call_kwargs["decode_responses"] is True
            assert call_kwargs["socket_timeout"] == 5
            assert call_kwargs["socket_connect_timeout"] == 5

    @patch("backend.workers.redis_client.ConnectionPool")
    @patch("backend.workers.redis_client.redis")
    def test_returns_redis_instance_with_pool(self, mock_redis, mock_connection_pool):
        """Redis 인스턴스가 연결 풀과 함께 반환되는지 검증"""
        # Arrange
        mock_pool = MagicMock()
        mock_connection_pool.from_url.return_value = mock_pool
        mock_redis_instance = MagicMock()
        mock_redis.Redis.return_value = mock_redis_instance

        with patch("backend.workers.redis_client.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            from backend.workers.redis_client import get_worker_redis

            # Act
            result = get_worker_redis()

            # Assert
            mock_redis.Redis.assert_called_once()
            assert result == mock_redis_instance

    @patch("backend.workers.redis_client.ConnectionPool")
    @patch("backend.workers.redis_client.redis")
    def test_handles_different_redis_urls(self, mock_redis, mock_connection_pool):
        """다양한 Redis URL 처리 검증"""
        # Arrange
        test_urls = [
            "redis://localhost:6379/0",
            "redis://localhost:6379/1",
            "redis://redis.example.com:6380/2",
            "rediss://secure.redis.example.com:6380/0",
        ]

        for url in test_urls:
            # Reset
            from backend.workers import redis_client
            redis_client._pool = None
            mock_connection_pool.from_url.reset_mock()

            with patch("backend.workers.redis_client.settings") as mock_settings:
                mock_settings.redis_url = url

                # Act
                from backend.workers.redis_client import get_worker_redis
                get_worker_redis()

                # Assert
                mock_connection_pool.from_url.assert_called_once()
                call_args = mock_connection_pool.from_url.call_args[0]
                assert call_args[0] == url


class TestGlobalPoolState:
    """전역 연결 풀 상태 테스트"""

    @patch("backend.workers.redis_client.ConnectionPool")
    @patch("backend.workers.redis_client.redis")
    def test_global_pool_initialized_after_first_call(self, mock_redis, mock_connection_pool):
        """첫 호출 후 전역 _pool이 초기화되는지 검증"""
        # Arrange
        mock_pool = MagicMock()
        mock_connection_pool.from_url.return_value = mock_pool

        with patch("backend.workers.redis_client.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            from backend.workers import redis_client

            # Act
            assert redis_client._pool is None  # 초기 상태
            redis_client.get_worker_redis()

            # Assert
            assert redis_client._pool is not None
            assert redis_client._pool == mock_pool

    @patch("backend.workers.redis_client.ConnectionPool")
    @patch("backend.workers.redis_client.redis")
    def test_global_pool_persists_across_calls(self, mock_redis, mock_connection_pool):
        """여러 호출 간 전역 _pool이 유지되는지 검증"""
        # Arrange
        mock_pool = MagicMock()
        mock_connection_pool.from_url.return_value = mock_pool

        with patch("backend.workers.redis_client.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            from backend.workers import redis_client

            # Act
            redis_client.get_worker_redis()
            first_pool = redis_client._pool
            redis_client.get_worker_redis()
            second_pool = redis_client._pool

            # Assert
            assert first_pool is not None
            assert second_pool is not None
            assert first_pool is second_pool  # 동일 인스턴스
