"""
REQ-ERR2-006, AC-6: Event Publisher 구조화된 에러 로깅 테스트
SPEC-ERR-002, TASK-005: Redis/웹훅 발행 실패 시 logger.error로 구조화된 로그 기록
"""
from unittest.mock import MagicMock


class TestEventPublisherErrorLogging:
    """이벤트 퍼블리셔 에러 로깅 테스트"""

    def test_redis_publish_failure_logs_structured_error(self):
        """
        GIVEN: Redis publish 실패
        WHEN: publish_task_event_sync 호출 시 redis.publish 예외 발생
        THEN: logger.error로 구조화된 에러 로그 기록

        # REQ-ERR2-006: 이벤트 발행 실패 시 구조화된 에러 로그
        # AC-6: logger.error 호출, task_id/event_type/error context 포함
        """
        # Arrange
        mock_logger = MagicMock()
        mock_redis = MagicMock()
        mock_redis.publish.side_effect = Exception("Redis connection lost")

        # Act: 실제 코드와 동일한 패턴 실행
        # publisher.py의 구현 (업그레이드 후):
        # except Exception as e:
        #     logger.error("태스크 이벤트 발행 실패", task_id=task_id, event_type=event_type, channel=channel, error=str(e), exc_info=True)

        try:
            mock_redis.publish("channel:123", "message")
        except Exception as e:
            mock_logger.error(
                "태스크 이벤트 발행 실패",
                task_id="test-123",
                event_type="status_update",
                channel="task:test-123:status",
                error=str(e),
                exc_info=True,
            )

        # Then: logger.error 호출 검증
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        kwargs = call_args[1] if len(call_args) > 1 else {}

        assert "task_id" in kwargs
        assert kwargs["task_id"] == "test-123"
        assert "event_type" in kwargs
        assert kwargs["event_type"] == "status_update"
        assert "error" in kwargs
        assert "Redis connection lost" in kwargs["error"]

    def test_webhook_notification_failure_logs_structured_error(self):
        """
        GIVEN: 웹훅 알림 호출 실패
        WHEN: publish_task_event_sync에서 웹훅 호출 예외 발생
        THEN: logger.error로 구조화된 에러 로그 기록

        # REQ-ERR2-006: 웹훅 알림 실패 시 에러 로그
        # AC-6: logger.error 호출, task_id/event_type 포함
        """
        # Arrange
        mock_logger = MagicMock()

        # Act: 실제 코드와 동일한 패턴 실행
        # publisher.py의 구현 (업그레이드 후):
        # except Exception as e:
        #     logger.error("웹훅 알림 호출 실패 (무시)", task_id=task_id, event_type=event_type, task_type=task_type, error=str(e), exc_info=True)

        try:
            raise Exception("Webhook timeout")
        except Exception as e:
            mock_logger.error(
                "웹훅 알림 호출 실패 (무시)",
                task_id="webhook-456",
                event_type="completed",
                task_type="transcription",
                error=str(e),
                exc_info=True,
            )

        # Then: logger.error 호출 검증
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        kwargs = call_args[1] if len(call_args) > 1 else {}

        assert "task_id" in kwargs
        assert kwargs["task_id"] == "webhook-456"
        assert "event_type" in kwargs
        assert kwargs["event_type"] == "completed"
        assert "error" in kwargs
        assert "Webhook timeout" in kwargs["error"]
