"""
SSE(Server-Sent Events) 스트림 엔드포인트
REQ-SSE-001: GET /api/v1/tasks/{task_id}/stream → text/event-stream
REQ-SSE-002: 이벤트에 event type, data (JSON), id 포함
REQ-SSE-003: completed/failed 이벤트에서 스트림 자동 종료
REQ-SSE-004: 클라이언트 연결 해제 시 리소스 해제
REQ-SSE-007: 15초마다 heartbeat ping 전송
"""

import json
from collections.abc import AsyncGenerator, Callable

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.app.dependencies import get_redis_client
from backend.events.subscriber import subscribe_task_events
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["stream"])

# heartbeat 전송 간격 (초)
HEARTBEAT_INTERVAL = 15

# 스트림 종료 이벤트 타입
TERMINAL_EVENTS = {"completed", "failed"}


async def create_sse_event_generator(
    redis_client: aioredis.Redis,
    task_id: str,
    subscriber_fn: Callable = subscribe_task_events,
) -> AsyncGenerator[dict, None]:
    """
    SSE 이벤트 제너레이터 - Redis 구독 이벤트를 SSE 형식으로 변환

    Args:
        redis_client: Redis 비동기 클라이언트
        task_id: 스트리밍할 태스크 ID
        subscriber_fn: 이벤트 구독 함수 (테스트 주입용)

    Yields:
        ServerSentEvent 형식 딕셔너리
    """
    event_counter = 0

    async for event_data in subscriber_fn(redis_client, task_id):
        event_counter += 1
        event_type = event_data.get("event", "status_update")
        data = event_data.get("data", {})

        # REQ-SSE-002: event type, data (JSON), id 포함
        yield {
            "event": event_type,
            "data": json.dumps(data),
            "id": str(event_counter),
        }

        # REQ-SSE-003: completed/failed 이벤트에서 스트림 자동 종료
        if event_type in TERMINAL_EVENTS:
            logger.info("스트림 자동 종료", task_id=task_id, event_type=event_type)
            return


# @MX:ANCHOR: SSE 스트림 공개 API 진입점 - 클라이언트와의 계약 변경 금지
# @MX:REASON: 이 엔드포인트는 Flutter 앱의 실시간 상태 업데이트 핵심 경로
@router.get("/{task_id}/stream")
async def stream_task_status(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> EventSourceResponse:
    """
    태스크 상태 실시간 스트리밍
    GET /api/v1/tasks/{task_id}/stream

    REQ-SSE-001: text/event-stream Content-Type으로 응답
    REQ-SSE-004: 클라이언트 연결 해제 시 리소스 해제
    REQ-SSE-007: 15초마다 heartbeat ping 전송
    """
    # 태스크 존재 여부 확인 (Redis에 태스크 데이터가 있는지)
    # 각 태스크 타입별 status key 패턴을 모두 확인
    task_exists = False
    for prefix in (
        "task:status:",
        "task:dia:status:",
        "task:min:status:",
        "task:sum:status:",
        "task:mind:status:",
    ):
        if await redis_client.exists(f"{prefix}{task_id}"):
            task_exists = True
            break

    if not task_exists:
        raise HTTPException(status_code=404, detail=f"태스크를 찾을 수 없습니다: {task_id}")

    logger.info("SSE 스트림 시작", task_id=task_id)

    # REQ-SSE-007: heartbeat 포함한 이벤트 소스 응답
    return EventSourceResponse(
        create_sse_event_generator(redis_client, task_id),
        ping=HEARTBEAT_INTERVAL,
        media_type="text/event-stream",
    )
