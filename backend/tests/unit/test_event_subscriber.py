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
    return redis_mock


class TestSubscribeTaskEvents:
    """subscribe_task_events 비동기 제너레이터 테스트"""

    @pytest.mark.asyncio
    async def test_subscribe_yields_messages(self):
        """Redis 메시지를 이벤트 딕셔너리로 변환하여 yield 하는지 확인"""
        from backend.events.subscriber import subscribe_task_events

        # Arrange - pubsub mock 설정
        pubsub_mock = AsyncMock()
        pubsub_mock.subscribe = AsyncMock()
        pubsub_mock.unsubscribe = AsyncMock()
        pubsub_mock.close = AsyncMock()

        # 테스트 메시지
        test_message = {
            "type": "message",
            "data": json.dumps({"event": "status_update", "data": {"status": "processing"}}),
        }

        # listen()이 async generator 반환하도록 설정
        async def mock_listen():
            yield {"type": "subscribe", "data": 1}  # 구독 확인 메시지
            yield test_message  # 실제 메시지

        pubsub_mock.listen = mock_listen

        # pubsub()은 동기 메서드이므로 MagicMock 사용
        redis_mock = make_redis_mock_with_pubsub(pubsub_mock)

        # Act - 메시지 수집
        received = []
        async for msg in subscribe_task_events(redis_mock, "test-task"):
            received.append(msg)
            break  # 첫 번째 메시지만 받고 종료

        # Assert
        assert len(received) == 1
        assert received[0]["event"] == "status_update"
        assert received[0]["data"]["status"] == "processing"

    @pytest.mark.asyncio
    async def test_subscribe_skips_non_message_types(self):
        """type != 'message'인 메시지는 yield 하지 않는지 확인"""
        from backend.events.subscriber import subscribe_task_events

        # Arrange
        pubsub_mock = AsyncMock()
        pubsub_mock.subscribe = AsyncMock()
        pubsub_mock.unsubscribe = AsyncMock()
        pubsub_mock.close = AsyncMock()

        real_message = {
            "type": "message",
            "data": json.dumps({"event": "completed", "data": {"status": "completed"}}),
        }

        async def mock_listen():
            yield {"type": "subscribe", "data": 1}  # 건너뛰어야 함
            yield {"type": "psubscribe", "data": 1}  # 건너뛰어야 함
            yield real_message  # 이것만 yield 되어야 함

        pubsub_mock.listen = mock_listen
        redis_mock = make_redis_mock_with_pubsub(pubsub_mock)

        # Act
        received = []
        async for msg in subscribe_task_events(redis_mock, "test-task"):
            received.append(msg)
            break

        # Assert - subscribe 메시지는 건너뛰고 실제 메시지만 수신
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

        async def mock_listen():
            # 즉시 종료 (채널 구독 확인만)
            return
            yield  # 제너레이터 표시

        pubsub_mock.listen = mock_listen
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

        async def mock_listen():
            return
            yield

        pubsub_mock.listen = mock_listen
        redis_mock = make_redis_mock_with_pubsub(pubsub_mock)

        # Act - 제너레이터 완전히 소비
        async for _ in subscribe_task_events(redis_mock, "cleanup-task"):
            pass

        # Assert - 리소스 정리 확인
        pubsub_mock.unsubscribe.assert_called_once()
        pubsub_mock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_cleanup_on_exception(self):
        """예외 발생 시에도 cleanup이 호출되는지 확인"""
        from backend.events.subscriber import subscribe_task_events

        # Arrange
        pubsub_mock = AsyncMock()
        pubsub_mock.subscribe = AsyncMock()
        pubsub_mock.unsubscribe = AsyncMock()
        pubsub_mock.close = AsyncMock()

        async def mock_listen():
            raise RuntimeError("연결 끊김")
            yield

        pubsub_mock.listen = mock_listen
        redis_mock = make_redis_mock_with_pubsub(pubsub_mock)

        # Act - 예외 발생해도 cleanup 실행
        with pytest.raises(RuntimeError):
            async for _ in subscribe_task_events(redis_mock, "error-task"):
                pass

        # Assert
        pubsub_mock.unsubscribe.assert_called_once()
        pubsub_mock.close.assert_called_once()
