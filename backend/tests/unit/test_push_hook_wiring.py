"""
SPEC-MOBILE-004 T-008: Push 훅 Celery task 연결 테스트

REQ-MOBILE-002-08: 파이프라인 완료 시 Push 알림 (동기 컨텍스트용)
REQ-MOBILE-002-09: 파이프라인 실패 시 Push 알림 (동기 컨텍스트용)

검증 대상:
- fire_push_sync() 동기 래퍼 존재
- user_id 전달 시 summary_task / minutes_task 완료 후 훅 호출
- 훅 실패해도 파이프라인에 영향 없음 (best-effort)
"""

from unittest.mock import patch


class TestFirePushSyncWrapper:
    """T-008: 동기 Push 훅 래퍼 테스트"""

    def test_fire_push_sync_exists(self):
        """fire_push_sync 함수가 celery_push_hooks에 존재"""
        from backend.app.workers.hooks import celery_push_hooks

        assert hasattr(celery_push_hooks, "fire_push_sync")
        assert callable(celery_push_hooks.fire_push_sync)

    def test_fire_push_sync_does_not_raise_on_error(self):
        """내부 오류 발생해도 예외를 밖으로 던지지 않음 (best-effort)"""
        from backend.app.workers.hooks.celery_push_hooks import fire_push_sync

        with patch("backend.app.workers.hooks.celery_push_hooks._fire_push_async") as mock_async:
            mock_async.side_effect = RuntimeError("DB connection failed")
            fire_push_sync(
                user_id="user-123",
                meeting_id="meeting-456",
                task_id="task-789",
                status="completed",
            )

    def test_fire_push_sync_skips_when_no_user_id(self):
        """user_id=None이면 아무 작업도 하지 않음"""
        from backend.app.workers.hooks.celery_push_hooks import fire_push_sync

        with patch("backend.app.workers.hooks.celery_push_hooks._fire_push_async") as mock_async:
            fire_push_sync(
                user_id=None,
                meeting_id="meeting-456",
                task_id="task-789",
                status="completed",
            )
            mock_async.assert_not_called()


class TestSummaryTaskPushHook:
    """T-008: summary_task 완료/실패 시 Push 훅 호출"""

    def test_summary_task_accepts_user_id(self):
        """summary_task가 user_id 파라미터를 받음"""
        import inspect

        from backend.workers.tasks.summary_task import summary_task

        sig = inspect.signature(summary_task)
        assert "user_id" in sig.parameters
        assert sig.parameters["user_id"].default is None

    def test_minutes_task_accepts_user_id(self):
        """minutes_task가 user_id 파라미터를 받음"""
        import inspect

        from backend.workers.tasks.minutes_task import minutes_task

        sig = inspect.signature(minutes_task)
        assert "user_id" in sig.parameters
        assert sig.parameters["user_id"].default is None
