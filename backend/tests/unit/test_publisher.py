"""
Redis Pub/Sub 이벤트 퍼블리셔 유닛 테스트
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis
import redis.asyncio as aioredis


class TestPublishTaskEvent:
    """publish_task_event (비동기) 테스트"""

    @pytest.mark.asyncio
    async def test_publish_task_event_success(self):
        """태스크 이벤트 발행 성공"""
        # Arrange
        mock_redis = AsyncMock(spec=aioredis.Redis)
        mock_redis.publish = AsyncMock(return_value=1)

        # Act
        from backend.events.publisher import publish_task_event

        await publish_task_event(
            redis_client=mock_redis,
            task_id="task-123",
            event_type="status_update",
            data={"status": "processing", "progress": 50}
        )

        # Assert
        mock_redis.publish.assert_called_once_with(
            "task:task-123:status",
            '{"event": "status_update", "data": {"status": "processing", "progress": 50}}'
        )

    @pytest.mark.asyncio
    async def test_publish_task_event_with_completed_event(self):
        """completed 이벤트 발행"""
        mock_redis = AsyncMock(spec=aioredis.Redis)
        mock_redis.publish = AsyncMock(return_value=1)

        from backend.events.publisher import publish_task_event

        await publish_task_event(
            redis_client=mock_redis,
            task_id="task-456",
            event_type="completed",
            data={"status": "completed", "result": "success"}
        )

        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert "task:task-456:status" in str(call_args)
        assert "completed" in str(call_args)

    @pytest.mark.asyncio
    async def test_publish_task_event_with_failed_event(self):
        """failed 이벤트 발행"""
        mock_redis = AsyncMock(spec=aioredis.Redis)
        mock_redis.publish = AsyncMock(return_value=1)

        from backend.events.publisher import publish_task_event

        await publish_task_event(
            redis_client=mock_redis,
            task_id="task-789",
            event_type="failed",
            data={"status": "failed", "error": "Processing timeout"}
        )

        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert "task:task-789:status" in str(call_args)
        assert "failed" in str(call_args)


class TestPublishTaskEventSync:
    """publish_task_event_sync (동기) 테스트"""

    def test_publish_sync_success(self):
        """동기 버전 태스크 이벤트 발행 성공"""
        # Arrange
        mock_redis = MagicMock(spec=redis.Redis)
        mock_redis.publish = MagicMock(return_value=1)

        # Act
        from backend.events.publisher import publish_task_event_sync

        publish_task_event_sync(
            redis_client=mock_redis,
            task_id="task-sync-123",
            event_type="status_update",
            data={"status": "processing", "progress": 75}
        )

        # Assert
        mock_redis.publish.assert_called_once_with(
            "task:task-sync-123:status",
            '{"event": "status_update", "data": {"status": "processing", "progress": 75}}'
        )

    def test_publish_sync_with_exception(self):
        """Redis 발행 실패 시 예외 처리 및 로깅"""
        mock_redis = MagicMock(spec=redis.Redis)
        mock_redis.publish = MagicMock(side_effect=Exception("Redis connection error"))

        from backend.events.publisher import publish_task_event_sync

        # 예외가 발생하지 않고 처리되어야 함
        publish_task_event_sync(
            redis_client=mock_redis,
            task_id="task-sync-456",
            event_type="status_update",
            data={"status": "processing"}
        )

        # 호출은 시도되었음
        mock_redis.publish.assert_called_once()

    def test_publish_sync_completed_event_triggers_webhook(self):
        """completed 이벤트 시 웹훅 알림 호출"""
        mock_redis = MagicMock(spec=redis.Redis)
        mock_redis.publish = MagicMock(return_value=1)

        from backend.events.publisher import publish_task_event_sync

        with patch("backend.services.webhook_notifier.notify_webhooks_sync") as mock_notify:
            publish_task_event_sync(
                redis_client=mock_redis,
                task_id="task-sync-789",
                event_type="completed",
                data={"status": "completed", "task_type": "transcription"}
            )

            # 웹훅 알림 호출 확인
            mock_notify.assert_called_once_with(
                task_id="task-sync-789",
                event_type="completed",
                task_type="transcription",
                data={"status": "completed", "task_type": "transcription"}
            )

    def test_publish_sync_failed_event_triggers_webhook(self):
        """failed 이벤트 시 웹훅 알림 호출"""
        mock_redis = MagicMock(spec=redis.Redis)
        mock_redis.publish = MagicMock(return_value=1)

        from backend.events.publisher import publish_task_event_sync

        with patch("backend.services.webhook_notifier.notify_webhooks_sync") as mock_notify:
            publish_task_event_sync(
                redis_client=mock_redis,
                task_id="task-sync-999",
                event_type="failed",
                data={"status": "failed", "error": "Timeout", "task_type": "diarization"}
            )

            # 웹훅 알림 호출 확인
            mock_notify.assert_called_once_with(
                task_id="task-sync-999",
                event_type="failed",
                task_type="diarization",
                data={"status": "failed", "error": "Timeout", "task_type": "diarization"}
            )

    def test_publish_sync_status_update_does_not_trigger_webhook(self):
        """status_update 이벤트는 웹훅 알림을 호출하지 않음"""
        mock_redis = MagicMock(spec=redis.Redis)
        mock_redis.publish = MagicMock(return_value=1)

        from backend.events.publisher import publish_task_event_sync

        with patch("backend.services.webhook_notifier.notify_webhooks_sync") as mock_notify:
            publish_task_event_sync(
                redis_client=mock_redis,
                task_id="task-sync-111",
                event_type="status_update",
                data={"status": "processing", "progress": 50}
            )

            # 웹훅 알림 호출되지 않음
            mock_notify.assert_not_called()

    def test_publish_sync_webhook_notification_failure(self):
        """웹훅 알림 호출 실패 시 예외 처리"""
        mock_redis = MagicMock(spec=redis.Redis)
        mock_redis.publish = MagicMock(return_value=1)

        from backend.events.publisher import publish_task_event_sync

        with patch("backend.services.webhook_notifier.notify_webhooks_sync", side_effect=Exception("Webhook error")):
            # 예외가 발생하지 않고 처리되어야 함
            publish_task_event_sync(
                redis_client=mock_redis,
                task_id="task-sync-222",
                event_type="completed",
                data={"status": "completed"}
            )

            # Redis 발행은 성공
            mock_redis.publish.assert_called_once()

    def test_publish_sync_with_unknown_task_type(self):
        """task_type이 없는 경우 기본값 'unknown' 사용"""
        mock_redis = MagicMock(spec=redis.Redis)
        mock_redis.publish = MagicMock(return_value=1)

        from backend.events.publisher import publish_task_event_sync

        with patch("backend.services.webhook_notifier.notify_webhooks_sync") as mock_notify:
            publish_task_event_sync(
                redis_client=mock_redis,
                task_id="task-sync-333",
                event_type="completed",
                data={"status": "completed"}  # task_type 없음
            )

            # task_type 기본값 확인
            mock_notify.assert_called_once()
            call_kwargs = mock_notify.call_args.kwargs
            assert call_kwargs["task_type"] == "unknown"
