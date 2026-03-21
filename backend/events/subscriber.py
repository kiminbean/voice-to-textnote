"""
Redis Pub/Sub 이벤트 구독자
REQ-SSE-003: completed/failed 이벤트 수신 시 스트림 자동 종료
REQ-SSE-004: 클라이언트 연결 해제 시 리소스 해제
"""

import asyncio
import json
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Pub/Sub 메시지 대기 타임아웃 (초) - 이 간격마다 Redis 직접 조회로 상태 확인
POLL_TIMEOUT_SECONDS = 5.0

# Redis 직접 상태 조회용 key prefix 목록
STATUS_KEY_PREFIXES = (
    "task:status:",      # transcription
    "task:dia:status:",  # diarization
    "task:min:status:",  # minutes
    "task:sum:status:",  # summary
)


async def _check_task_status_directly(
    redis_client: aioredis.Redis,
    task_id: str,
) -> dict | None:
    """Redis에서 태스크 상태를 직접 조회 (Pub/Sub 폴백)"""
    for prefix in STATUS_KEY_PREFIXES:
        raw = await redis_client.get(f"{prefix}{task_id}")
        if raw:
            data = json.loads(raw)
            status = data.get("status")
            if status in ("completed", "failed"):
                event_type = status
                return {"event": event_type, "data": data}
    return None


async def subscribe_task_events(
    redis_client: aioredis.Redis,
    task_id: str,
) -> AsyncGenerator[dict, None]:
    """
    Redis Pub/Sub 채널에서 태스크 이벤트를 구독하는 비동기 제너레이터
    타임아웃 시 Redis 직접 조회로 상태를 확인하여 무한 대기 방지

    Args:
        redis_client: Redis 비동기 클라이언트
        task_id: 구독할 태스크 고유 식별자

    Yields:
        이벤트 딕셔너리 {"event": str, "data": dict}
    """
    channel = f"task:{task_id}:status"
    pubsub = redis_client.pubsub()

    await pubsub.subscribe(channel)
    logger.debug("태스크 이벤트 구독 시작", task_id=task_id, channel=channel)

    try:
        while True:
            # 타임아웃 포함 메시지 수신 - None이면 타임아웃
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=POLL_TIMEOUT_SECONDS,
            )

            if message is not None and message["type"] == "message":
                event_data = json.loads(message["data"])
                yield event_data

                # 종료 이벤트면 루프 탈출
                if event_data.get("event") in ("completed", "failed"):
                    return
            else:
                # 타임아웃 - Redis 직접 조회로 상태 확인 (Pub/Sub 메시지 유실 대비)
                direct_result = await _check_task_status_directly(redis_client, task_id)
                if direct_result:
                    yield direct_result
                    return

            # 짧은 대기 후 다음 메시지 확인
            await asyncio.sleep(0.1)

    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        logger.debug("태스크 이벤트 구독 종료", task_id=task_id, channel=channel)
