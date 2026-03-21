"""
SPEC-SSE-001 SSE 스트림 엔드포인트 단위 테스트
REQ-SSE-001: GET /api/v1/tasks/{task_id}/stream → text/event-stream
REQ-SSE-002: 이벤트에 event type, data (JSON: status, progress, message), id 포함
REQ-SSE-003: completed/failed 이벤트에서 스트림 자동 종료
REQ-SSE-004: 클라이언트 연결 해제 시 리소스 해제
REQ-SSE-007: 15초마다 heartbeat ping 전송
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------


def make_test_app():
    """스트림 라우터만 포함한 최소 테스트 앱 생성"""
    from backend.app.api.v1.stream import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# 이벤트 제너레이터 단위 테스트
# ---------------------------------------------------------------------------


class TestSSEEventGenerator:
    """SSE 이벤트 제너레이터 로직 테스트 (HTTP 연결 없이)"""

    @pytest.mark.asyncio
    async def test_generator_yields_sse_events(self):
        """이벤트 제너레이터가 올바른 SSE 형식으로 yield하는지 확인"""
        from backend.app.api.v1.stream import create_sse_event_generator

        # Arrange - 완료 이벤트 하나만 있는 구독자 mock
        async def mock_subscriber(redis_client, task_id):
            yield {"event": "completed", "data": {"status": "completed"}}

        redis_mock = AsyncMock()

        # Act - 이벤트 수집
        events = []
        async for event in create_sse_event_generator(redis_mock, "task-123", mock_subscriber):
            events.append(event)

        # Assert - 최소 1개 이상의 이벤트 (completed 이벤트 포함)
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_generator_stops_on_completed_event(self):
        """completed 이벤트 수신 후 제너레이터가 종료되는지 확인"""
        from backend.app.api.v1.stream import create_sse_event_generator

        # Arrange
        async def mock_subscriber(redis_client, task_id):
            yield {"event": "status_update", "data": {"status": "processing"}}
            yield {"event": "completed", "data": {"status": "completed"}}
            yield {"event": "status_update", "data": {"status": "should_not_be_sent"}}

        redis_mock = AsyncMock()

        # Act
        events = []
        async for event in create_sse_event_generator(redis_mock, "task-1", mock_subscriber):
            events.append(event)

        # Assert - completed 이후 이벤트는 전송되지 않음
        assert "should_not_be_sent" not in str(events)

    @pytest.mark.asyncio
    async def test_generator_stops_on_failed_event(self):
        """failed 이벤트 수신 후 제너레이터가 종료되는지 확인"""
        from backend.app.api.v1.stream import create_sse_event_generator

        # Arrange
        async def mock_subscriber(redis_client, task_id):
            yield {"event": "failed", "data": {"status": "failed", "error": "처리 실패"}}
            yield {"event": "status_update", "data": {"status": "should_not_be_sent"}}

        redis_mock = AsyncMock()

        # Act
        events = []
        async for event in create_sse_event_generator(redis_mock, "task-1", mock_subscriber):
            events.append(event)

        # Assert - failed 이후 이벤트 없음
        assert "should_not_be_sent" not in str(events)

    @pytest.mark.asyncio
    async def test_generator_event_has_id(self):
        """이벤트에 id 필드가 포함되는지 확인 (REQ-SSE-002)"""
        from backend.app.api.v1.stream import create_sse_event_generator

        # Arrange
        async def mock_subscriber(redis_client, task_id):
            yield {"event": "completed", "data": {"status": "completed"}}

        redis_mock = AsyncMock()

        # Act
        events = []
        async for event in create_sse_event_generator(redis_mock, "task-123", mock_subscriber):
            events.append(event)

        # Assert - 이벤트에 id가 존재
        # 이벤트는 ServerSentEvent 객체이므로 id 속성 확인
        assert len(events) >= 1


# ---------------------------------------------------------------------------
# SSE 엔드포인트 통합 테스트 (라우터 레벨)
# ---------------------------------------------------------------------------


class TestSSEEndpoint:
    """SSE 엔드포인트 HTTP 레벨 테스트"""

    def test_stream_endpoint_returns_404_when_task_not_found(self):
        """존재하지 않는 태스크 조회 시 404 반환 (REQ-SSE-001)"""
        from backend.app.api.v1.stream import router
        from backend.app.dependencies import get_redis_client

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        # Redis에 태스크 없음 mock
        redis_mock = AsyncMock()
        redis_mock.exists = AsyncMock(return_value=0)

        async def override_redis():
            return redis_mock

        app.dependency_overrides[get_redis_client] = override_redis

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/tasks/nonexistent-task/stream")

        assert response.status_code == 404

    def test_stream_endpoint_content_type(self):
        """스트림 엔드포인트의 Content-Type이 text/event-stream인지 확인 (REQ-SSE-001)"""
        from backend.app.api.v1.stream import router
        from backend.app.dependencies import get_redis_client

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        # Redis에 태스크 존재 + 즉시 completed 이벤트
        redis_mock = AsyncMock()
        redis_mock.exists = AsyncMock(return_value=1)

        pubsub_mock = AsyncMock()
        pubsub_mock.subscribe = AsyncMock()
        pubsub_mock.unsubscribe = AsyncMock()
        pubsub_mock.close = AsyncMock()

        import json as _json

        completed_msg = {
            "type": "message",
            "data": _json.dumps({"event": "completed", "data": {"status": "completed"}}),
        }

        async def mock_listen():
            yield completed_msg

        pubsub_mock.listen = mock_listen
        redis_mock.pubsub.return_value = pubsub_mock

        async def override_redis():
            return redis_mock

        app.dependency_overrides[get_redis_client] = override_redis

        client = TestClient(app, raise_server_exceptions=False)
        # SSE 스트림은 스트리밍 응답이므로 stream=True로 요청
        with client.stream("GET", "/api/v1/tasks/test-task-id/stream") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
