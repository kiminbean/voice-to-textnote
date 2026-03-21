"""
결과 폴백 테스트 - SPEC-PERSIST-001

테스트 범위:
- REQ-PERSIST-009: Redis 캐시 미스 시 DB 폴백 조회
- REQ-PERSIST-010: DB에서 찾은 경우 Redis 캐시 복원
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestGetResultWithFallback:
    """REQ-PERSIST-009~010: Redis 캐시 미스 + DB 폴백 + 캐시 복원"""

    @pytest.mark.asyncio
    async def test_returns_cached_result_when_redis_hit(self):
        """Redis에 캐시가 있으면 바로 반환해야 함"""
        from backend.app.result_fallback import get_result_with_fallback

        cached_data = {"task_id": "test-001", "status": "completed", "text": "안녕하세요"}
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(cached_data)
        mock_db_session = AsyncMock()

        result = await get_result_with_fallback(
            redis_client=mock_redis,
            task_id="test-001",
            redis_key="task:result:test-001",
            db_session=mock_db_session,
        )

        assert result == cached_data
        # Redis hit이면 DB 조회 없어야 함
        mock_db_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_db_when_redis_miss(self):
        """Redis 캐시 미스 시 DB에서 조회해야 함 (REQ-PERSIST-009)"""
        from backend.app.result_fallback import get_result_with_fallback

        db_result_data = {"task_id": "test-002", "status": "completed", "segments": []}
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # 캐시 미스

        mock_task_result = MagicMock()
        mock_task_result.result_data = db_result_data

        mock_result_service = AsyncMock()
        mock_result_service.get_result.return_value = mock_task_result

        mock_db_session = AsyncMock()

        with patch("backend.app.result_fallback.ResultService", return_value=mock_result_service):
            result = await get_result_with_fallback(
                redis_client=mock_redis,
                task_id="test-002",
                redis_key="task:result:test-002",
                db_session=mock_db_session,
            )

        assert result == db_result_data
        mock_result_service.get_result.assert_called_once_with(mock_db_session, "test-002")

    @pytest.mark.asyncio
    async def test_restores_redis_cache_from_db(self):
        """DB에서 찾으면 Redis 캐시를 복원해야 함 (REQ-PERSIST-010)"""
        from backend.app.result_fallback import get_result_with_fallback

        db_result_data = {"task_id": "test-003", "status": "completed"}
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # 캐시 미스

        mock_task_result = MagicMock()
        mock_task_result.result_data = db_result_data

        mock_result_service = AsyncMock()
        mock_result_service.get_result.return_value = mock_task_result

        mock_db_session = AsyncMock()

        with patch("backend.app.result_fallback.ResultService", return_value=mock_result_service):
            with patch("backend.app.result_fallback.settings") as mock_settings:
                mock_settings.cache_ttl_seconds = 86400
                await get_result_with_fallback(
                    redis_client=mock_redis,
                    task_id="test-003",
                    redis_key="task:result:test-003",
                    db_session=mock_db_session,
                )

        # Redis setex 호출 확인 (캐시 복원)
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        # 첫 번째 인자는 키
        assert call_args[0][0] == "task:result:test-003"
        # 두 번째 인자는 TTL
        assert call_args[0][1] == 86400
        # 세 번째 인자는 JSON 직렬화된 결과
        restored_data = json.loads(call_args[0][2])
        assert restored_data == db_result_data

    @pytest.mark.asyncio
    async def test_returns_none_when_neither_cache_nor_db(self):
        """Redis와 DB 모두 없으면 None을 반환해야 함"""
        from backend.app.result_fallback import get_result_with_fallback

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # 캐시 미스

        mock_result_service = AsyncMock()
        mock_result_service.get_result.return_value = None  # DB 미스

        mock_db_session = AsyncMock()

        with patch("backend.app.result_fallback.ResultService", return_value=mock_result_service):
            result = await get_result_with_fallback(
                redis_client=mock_redis,
                task_id="test-004",
                redis_key="task:result:test-004",
                db_session=mock_db_session,
            )

        assert result is None
        # Redis setex 호출 없어야 함
        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_db_result_has_no_data(self):
        """DB에 레코드는 있지만 result_data가 None이면 None을 반환해야 함"""
        from backend.app.result_fallback import get_result_with_fallback

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_task_result = MagicMock()
        mock_task_result.result_data = None  # result_data 없음

        mock_result_service = AsyncMock()
        mock_result_service.get_result.return_value = mock_task_result

        mock_db_session = AsyncMock()

        with patch("backend.app.result_fallback.ResultService", return_value=mock_result_service):
            result = await get_result_with_fallback(
                redis_client=mock_redis,
                task_id="test-005",
                redis_key="task:result:test-005",
                db_session=mock_db_session,
            )

        assert result is None
        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_key_used_for_lookup(self):
        """redis_key 파라미터가 실제 조회에 사용되어야 함"""
        from backend.app.result_fallback import get_result_with_fallback

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_result_service = AsyncMock()
        mock_result_service.get_result.return_value = None

        mock_db_session = AsyncMock()
        custom_key = "task:dia:result:custom-key-999"

        with patch("backend.app.result_fallback.ResultService", return_value=mock_result_service):
            await get_result_with_fallback(
                redis_client=mock_redis,
                task_id="custom-key-999",
                redis_key=custom_key,
                db_session=mock_db_session,
            )

        # 지정된 키로 Redis 조회
        mock_redis.get.assert_called_once_with(custom_key)
