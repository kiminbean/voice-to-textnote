"""
SPEC-SSE-001 이벤트 퍼블리셔 단위 테스트
REQ-SSE-005: Redis Pub/Sub 채널에 태스크 상태 변경 이벤트 발행
REQ-SSE-006: publish_task_event(task_id, event_type, data) 인터페이스
"""

import json
from unittest.mock import AsyncMock

import pytest


class TestPublishTaskEvent:
    """publish_task_event 함수 테스트"""

    @pytest.mark.asyncio
    async def test_publish_event_calls_redis_publish(self):
        """Redis publish가 올바른 채널과 메시지로 호출되는지 확인"""
        from backend.events.publisher import publish_task_event

        # Arrange
        redis_mock = AsyncMock()
        task_id = "test-task-123"
        event_type = "status_update"
        data = {"status": "processing", "progress": 50}

        # Act
        await publish_task_event(redis_mock, task_id, event_type, data)

        # Assert - 올바른 채널로 publish 호출 확인
        redis_mock.publish.assert_called_once()
        call_args = redis_mock.publish.call_args
        channel = call_args[0][0]
        assert channel == f"task:{task_id}:status"

    @pytest.mark.asyncio
    async def test_publish_event_message_format(self):
        """발행 메시지가 올바른 JSON 형식인지 확인"""
        from backend.events.publisher import publish_task_event

        # Arrange
        redis_mock = AsyncMock()
        task_id = "test-task-456"
        event_type = "completed"
        data = {"status": "completed", "result": "success"}

        # Act
        await publish_task_event(redis_mock, task_id, event_type, data)

        # Assert - 메시지 형식 확인
        call_args = redis_mock.publish.call_args
        message_str = call_args[0][1]
        message = json.loads(message_str)

        assert message["event"] == event_type
        assert message["data"] == data

    @pytest.mark.asyncio
    async def test_publish_event_channel_format(self):
        """채널명이 task:{task_id}:status 형식인지 확인"""
        from backend.events.publisher import publish_task_event

        # Arrange
        redis_mock = AsyncMock()
        task_id = "abc-def-ghi"

        # Act
        await publish_task_event(redis_mock, task_id, "status_update", {})

        # Assert
        call_args = redis_mock.publish.call_args
        assert call_args[0][0] == "task:abc-def-ghi:status"

    @pytest.mark.asyncio
    async def test_publish_failed_event(self):
        """failed 이벤트 타입 발행 확인"""
        from backend.events.publisher import publish_task_event

        # Arrange
        redis_mock = AsyncMock()
        task_id = "failed-task-789"
        event_type = "failed"
        data = {"status": "failed", "error": "처리 오류 발생"}

        # Act
        await publish_task_event(redis_mock, task_id, event_type, data)

        # Assert
        redis_mock.publish.assert_called_once()
        call_args = redis_mock.publish.call_args
        message = json.loads(call_args[0][1])
        assert message["event"] == "failed"
        assert message["data"]["error"] == "처리 오류 발생"

    @pytest.mark.asyncio
    async def test_publish_with_empty_data(self):
        """빈 데이터로 이벤트 발행 가능한지 확인"""
        from backend.events.publisher import publish_task_event

        # Arrange
        redis_mock = AsyncMock()

        # Act - 예외 없이 실행되어야 함
        await publish_task_event(redis_mock, "task-1", "status_update", {})

        # Assert
        redis_mock.publish.assert_called_once()
