"""
Redis Pub/Sub 이벤트 구독자
REQ-SSE-003: completed/failed 이벤트 수신 시 스트림 자동 종료
REQ-SSE-004: 클라이언트 연결 해제 시 리소스 해제
"""

import json
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def subscribe_task_events(
    redis_client: aioredis.Redis,
    task_id: str,
) -> AsyncGenerator[dict, None]:
    """
    Redis Pub/Sub 채널에서 태스크 이벤트를 구독하는 비동기 제너레이터

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
        async for message in pubsub.listen():
            # 구독 확인 메시지(type='subscribe') 등은 건너뜀
            if message["type"] != "message":
                continue

            # JSON 역직렬화 후 yield
            event_data = json.loads(message["data"])
            yield event_data

    finally:
        # 클라이언트 연결 해제 또는 정상 종료 시 리소스 정리
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        logger.debug("태스크 이벤트 구독 종료", task_id=task_id, channel=channel)
