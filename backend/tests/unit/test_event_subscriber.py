"""
SPEC-SSE-001 이벤트 구독자 단위 테스트
REQ-SSE-003: completed/failed 이벤트 수신 시 스트림 자동 종료
REQ-SSE-004: 클라이언트 연결 해제 시 리소스 해제
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


def make_redis_mock_with_pubsub(pubsub_mock: AsyncMock) -> MagicMock:
    """
    pubsub()이 동기 메서드이므로 MagicMock으로 래핑된 Redis mock 반환
    pubsub()은 코루틴이 아닌 일반 객체를 반환해야 함
    """
    redis_mock = MagicMock()
    redis_mock.pubsub.return_value = pubsub_mock
    # Redis 직접 조회용 mock (상태 조회 폴백)
    redis_mock.get = AsyncMock(return_value=None)
    return redis_mock


class TestSubscribeTaskEvents:
    """subscribe_task_events 비동기 제너레이터 테스트"""

    @pytest.mark.asyncio
    async def test_subscribe_yields_messages(self):
        """Redis Pub/Sub 메시지를 이벤트 딕셔너리로 변환하여 yield 하는지 확인"""
        from backend.events.subscriber import subscribe_task_events

        # Arrange - pubsub mock 설정
        pubsub_mock = AsyncMock()
        pubsub_mock.subscribe = AsyncMock()
        pubsub_mock.unsubscribe = AsyncMock()
        pubsub_mock.close = AsyncMock()

        # get_message가 순차적으로 메시지 반환 후 None(타임아웃) 반환
        test_event = {"event": "status_update", "data": {"status": "processing"}}
        completed_event = {"event": "completed", "data": {"status": "completed"}}

        call_count = 0

        async def mock_get_message(ignore_subscribe_messages=True, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "type": "message",
                    "data": json.dumps(test_event),
                }
            if call_count == 2:
                return {
                    "type": "message",
                    "data": json.dumps(completed_event),
                }
            return None

        pubsub_mock.get_message = mock_get_message
        redis_mock = make_redis_mock_with_pubsub(pubsub_mock)

        # Act - 메시지 수집
        received = []
        async for msg in subscribe_task_events(redis_mock, "test-task"):
            received.append(msg)

        # Assert
        assert len(received) == 2
        assert received[0]["event"] == "status_update"
        assert received[0]["data"]["status"] == "processing"
        assert received[1]["event"] == "completed"

    @pytest.mark.asyncio
    async def test_subscribe_terminates_on_completed(self):
        """completed 이벤트 수신 시 제너레이터가 종료되는지 확인"""
        from backend.events.subscriber import subscribe_task_events

        # Arrange
        pubsub_mock = AsyncMock()
        pubsub_mock.subscribe = AsyncMock()
        pubsub_mock.unsubscribe = AsyncMock()
        pubsub_mock.close = AsyncMock()

        completed_event = {"event": "completed", "data": {"status": "completed"}}
        extra_event = {"event": "status_update", "data": {"status": "processing"}}

        call_count = 0

        async def mock_get_message(ignore_subscribe_messages=True, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"type": "message", "data": json.dumps(completed_event)}
            # 이 메시지는 도달하면 안 됨
            return {"type": "message", "data": json.dumps(extra_event)}  # pragma: no cover

        pubsub_mock.get_message = mock_get_message
        redis_mock = make_redis_mock_with_pubsub(pubsub_mock)

        # Act
        received = []
        async for msg in subscribe_task_events(redis_mock, "test-task"):
            received.append(msg)

        # Assert - completed 이벤트만 받고 종료
        assert len(received) == 1
        assert received[0]["event"] == "completed"

    @pytest.mark.asyncio
    async def test_subscribe_terminates_on_failed(self):
        """failed 이벤트 수신 시 제너레이터가 종료되는지 확인"""
        from backend.events.subscriber import subscribe_task_events

        # Arrange
        pubsub_mock = AsyncMock()
        pubsub_mock.subscribe = AsyncMock()
        pubsub_mock.unsubscribe = AsyncMock()
        pubsub_mock.close = AsyncMock()

        failed_event = {"event": "failed", "data": {"status": "failed", "error": "test"}}

        async def mock_get_message(ignore_subscribe_messages=True, timeout=None):
            return {"type": "message", "data": json.dumps(failed_event)}

        pubsub_mock.get_message = mock_get_message
        redis_mock = make_redis_mock_with_pubsub(pubsub_mock)

        # Act
        received = []
        async for msg in subscribe_task_events(redis_mock, "test-task"):
            received.append(msg)

        # Assert - failed 이벤트 후 종료
        assert len(received) == 1
        assert received[0]["event"] == "failed"

    @pytest.mark.asyncio
    async def test_subscribe_falls_back_to_direct_check(self):
        """Pub/Sub 타임아웃 시 Redis 직접 조회로 폴백하는지 확인"""
        from backend.events.subscriber import subscribe_task_events

        # Arrange
        pubsub_mock = AsyncMock()
        pubsub_mock.subscribe = AsyncMock()
        pubsub_mock.unsubscribe = AsyncMock()
        pubsub_mock.close = AsyncMock()

        # get_message가 항상 None 반환 (타임아웃)
        pubsub_mock.get_message = AsyncMock(return_value=None)
        redis_mock = make_redis_mock_with_pubsub(pubsub_mock)

        # Redis 직접 조회에서 completed 상태 반환
        completed_data = json.dumps({
            "task_id": "test-task",
            "status": "completed",
            "progress": 1.0,
        })
        redis_mock.get = AsyncMock(return_value=completed_data)

        # Act
        received = []
        async for msg in subscribe_task_events(redis_mock, "test-task"):
            received.append(msg)

        # Assert - 폴백으로 완료 이벤트 수신
        assert len(received) == 1
        assert received[0]["event"] == "completed"

    @pytest.mark.asyncio
    async def test_subscribe_uses_correct_channel(self):
        """올바른 채널명으로 구독하는지 확인"""
        from backend.events.subscriber import subscribe_task_events

        # Arrange
        pubsub_mock = AsyncMock()
        pubsub_mock.subscribe = AsyncMock()
        pubsub_mock.unsubscribe = AsyncMock()
        pubsub_mock.close = AsyncMock()

        # 즉시 completed 반환하여 종료
        completed_event = {"event": "completed", "data": {"status": "completed"}}
        pubsub_mock.get_message = AsyncMock(
            return_value={"type": "message", "data": json.dumps(completed_event)}
        )
        redis_mock = make_redis_mock_with_pubsub(pubsub_mock)

        # Act
        task_id = "my-special-task"
        async for _ in subscribe_task_events(redis_mock, task_id):
            pass

        # Assert - 올바른 채널명으로 구독
        pubsub_mock.subscribe.assert_called_once_with(f"task:{task_id}:status")

    @pytest.mark.asyncio
    async def test_subscribe_cleanup_on_exit(self):
        """제너레이터 종료 시 unsubscribe와 close 호출되는지 확인"""
        from backend.events.subscriber import subscribe_task_events

        # Arrange
        pubsub_mock = AsyncMock()
        pubsub_mock.subscribe = AsyncMock()
        pubsub_mock.unsubscribe = AsyncMock()
        pubsub_mock.close = AsyncMock()

        completed_event = {"event": "completed", "data": {"status": "completed"}}
        pubsub_mock.get_message = AsyncMock(
            return_value={"type": "message", "data": json.dumps(completed_event)}
        )
        redis_mock = make_redis_mock_with_pubsub(pubsub_mock)

        # Act - 제너레이터 완전히 소비
        async for _ in subscribe_task_events(redis_mock, "cleanup-task"):
            pass

        # Assert - 리소스 정리 확인
        pubsub_mock.unsubscribe.assert_called_once()
        pubsub_mock.close.assert_called_once()
