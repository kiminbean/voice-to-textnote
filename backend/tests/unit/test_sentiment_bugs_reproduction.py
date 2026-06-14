"""
SPEC-SENTIMENT-001 재현 테스트 (TDD RED phase)
REQ-SEN-001/002: Celery sentiment_task 등록
REQ-SEN-005/006: SSE stream prefix 인식
REQ-SEN-004: max_concurrent_sentiment 설정 이관

이 테스트들은 버그가 존재할 때 FAIL 해야 하고, 수정 후 PASS 해야 한다.
"""


class TestCelerySentimentRegistration:
    """REQ-SEN-001/002: Celery가 sentiment_task를 발견할 수 있어야 한다"""

    def test_sentiment_task_module_in_celery_include(self):
        """celery_app.conf.include에 sentiment_task 모듈이 포함되어야 한다."""
        from backend.workers.celery_app import celery_app

        include_list = list(celery_app.conf.include)
        assert "backend.workers.tasks.sentiment_task" in include_list, (
            f"sentiment_task 모듈이 Celery include 목록에 없습니다: {include_list}"
        )

    def test_sentiment_celery_task_is_registered(self):
        """sentiment_celery_task가 Celery에 등록되어야 한다.

        Celery는 lazy loading을 사용하므로, 모듈을 import한 후 확인해야 한다.
        실제 워커는 include 목록을 보고 모듈을 import한다.
        """
        # 모듈을 명시적으로 import (Celery 워커가 include를 통해 수행하는 동작)
        import backend.workers.tasks.sentiment_task  # noqa: F401
        from backend.workers.celery_app import celery_app

        # sentiment_task.py에서 name="sentiment_task"로 정의됨
        assert "sentiment_task" in celery_app.tasks, (
            "sentiment_task가 Celery에 등록되지 않았습니다. "
            "Celery 워커가 sentiment_celery_task를 발견하지 못해 작업이 pending에 머무릅니다."
        )


class TestSSEStreamSentimentPrefix:
    """REQ-SEN-005/006: SSE stream이 sentiment 태스크를 인식해야 한다"""

    def test_stream_recognizes_sentiment_status_prefix(self):
        """stream_task_status가 task:sentiment:status: prefix를 확인해야 한다.

        버그: sentiment task가 진행 중일 때 GET /api/v1/tasks/{task_id}/stream이 404 반환.
        원인: stream.py의 prefix 튜플에 task:sentiment:status: 가 없음.
        """
        # stream_task_status 함수의 소스 코드를 읽어 prefix 확인
        import inspect

        from backend.app.api.v1.transcription.stream import stream_task_status

        source = inspect.getsource(stream_task_status)
        assert "task:sentiment:status:" in source, (
            "stream_task_status가 task:sentiment:status: prefix를 인식하지 못합니다. "
            "감정 분석 태스크 진행 중 SSE 엔드포인트가 404를 반환합니다."
        )

    def test_stream_does_not_404_for_sentiment_task(self):
        """sentiment status 키가 존재할 때 stream 엔드포인트가 404가 아닌 200을 반환해야 한다."""
        from unittest.mock import AsyncMock

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.app.api.v1.transcription.stream import router
        from backend.app.dependencies import get_redis_client
        from backend.app.error_handlers import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(router, prefix="/api/v1")

        # Redis: sentiment status 키만 존재 (다른 prefix는 없음)
        redis_mock = AsyncMock()

        async def mock_exists(key):
            # sentiment status 키가 존재한다고 응답
            if key.startswith("task:sentiment:status:"):
                return 1
            return 0

        redis_mock.exists = mock_exists

        async def override_redis():
            return redis_mock

        app.dependency_overrides[get_redis_client] = override_redis

        client = TestClient(app, raise_server_exceptions=False)
        with client.stream("GET", "/api/v1/tasks/sentiment-task-id/stream") as response:
            # 버그가 있으면 404, 수정되면 200
            assert response.status_code != 404, (
                "sentiment 태스크에 대해 SSE 엔드포인트가 404를 반환합니다. "
                "task:sentiment:status: prefix가 stream.py에 추가되어야 합니다."
            )


class TestSentimentConcurrencyConfig:
    """REQ-SEN-004: max_concurrent_sentiment이 config.py에 설정으로 존재해야 한다"""

    def test_max_concurrent_sentiment_exists_in_settings(self):
        """Settings에 max_concurrent_sentiment 항목이 있어야 한다."""
        from backend.app.config import settings

        assert hasattr(settings, "max_concurrent_sentiment"), (
            "settings.max_concurrent_sentiment이 존재하지 않습니다. "
            "config.py에 설정 항목을 추가해야 합니다."
        )

    def test_max_concurrent_sentiment_default_is_3(self):
        """기본값이 3이어야 한다 (기존 하드코딩값과 동일)."""
        from backend.app.config import settings

        assert settings.max_concurrent_sentiment == 3, (
            f"기본값이 3이어야 합니다. 현재값: {settings.max_concurrent_sentiment}"
        )

    def test_sentiment_task_uses_settings_not_module_constant(self):
        """sentiment_task.py에서 MAX_CONCURRENT_SENTIMENT 모듈 상수를 제거해야 한다."""
        import backend.workers.tasks.sentiment_task as sentiment_task_module

        # 버그: 모듈 수준 MAX_CONCURRENT_SENTIMENT 상수가 존재하면 안 됨
        assert not hasattr(sentiment_task_module, "MAX_CONCURRENT_SENTIMENT"), (
            "MAX_CONCURRENT_SENTIMENT 모듈 상수가 아직 존재합니다. "
            "settings.max_concurrent_sentiment를 사용하도록 변경해야 합니다."
        )
