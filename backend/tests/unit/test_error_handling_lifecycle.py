"""
REQ-ERR2-008, AC-5: Lifecycle degraded state 테스트
SPEC-ERR-002, TASK-006: Redis/DB 연결 실패 시 degraded=True 플래그 추가
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLifecycleDegradedState:
    """라이프사이클 degraded 상태 테스트"""

    @pytest.mark.asyncio
    async def test_redis_connection_failure_returns_degraded_true(self):
        """
        GIVEN: Redis 연결 실패
        WHEN: validate_startup 호출
        THEN: degraded=True 플래그 반환

        # REQ-ERR2-008: 시작 검증 실패 시 degraded 플래그
        # AC-5: Redis/DB 연결 실패 시 degraded=True
        """
        # Arrange: Redis ping 실패 mock
        with patch("backend.app.dependencies.get_redis_client") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.ping.side_effect = Exception("Redis connection failed")
            mock_get_redis.return_value = mock_redis

            # DB 엔진 mock (성공 가정)
            with patch("backend.app.dependencies._db_engine") as mock_engine:
                mock_conn = MagicMock()
                mock_engine.begin.return_value.__aenter__.return_value = mock_conn
                mock_conn.run_sync = MagicMock()

                # Act
                from backend.app.lifecycle import validate_startup
                result = await validate_startup()

            # Then: degraded 플래그 확인
            assert "degraded" in result
            assert result["degraded"] is True
            assert "redis" in result
            assert "warning" in result["redis"]

    @pytest.mark.asyncio
    async def test_database_connection_failure_returns_degraded_true(self):
        """
        GIVEN: DB 연결 실패
        WHEN: validate_startup 호출
        THEN: degraded=True 플래그 반환
        """
        # Arrange: Redis 성공, DB 실패 mock
        with patch("backend.app.dependencies.get_redis_client") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.ping.return_value = True  # Redis 성공
            mock_get_redis.return_value = mock_redis

            # DB 엔진 실패 mock
            with patch("backend.app.dependencies._db_engine") as mock_engine:
                mock_engine.begin.side_effect = Exception("DB connection failed")

                # Act
                from backend.app.lifecycle import validate_startup
                result = await validate_startup()

            # Then: degraded 플래그 확인
            assert "degraded" in result
            assert result["degraded"] is True
            assert "database" in result
            assert "warning" in result["database"]

    @pytest.mark.asyncio
    async def test_all_connections_success_no_degraded_flag(self):
        """
        GIVEN: 모든 연결 성공
        WHEN: validate_startup 호출
        THEN: degraded=False (또는 플래그 없음)
        """
        # Arrange: 모두 성공 mock
        with patch("backend.app.dependencies.get_redis_client") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.ping.return_value = True
            mock_get_redis.return_value = mock_redis

            # DB 엔진 mock - async context manager 제대로 설정
            async_mock = AsyncMock()
            async_mock.__aenter__ = AsyncMock()
            async_mock.__aexit__ = AsyncMock()

            with patch("backend.app.dependencies._db_engine") as mock_engine:
                mock_engine.begin = MagicMock(return_value=async_mock)

                # Act
                from backend.app.lifecycle import validate_startup
                result = await validate_startup()

            # Then: degraded 플래그 확인 (False이거나 없음)
            # 현재 구현에서는 성공 시 플래그가 없을 수 있음
            if "degraded" in result:
                assert result["degraded"] is False
