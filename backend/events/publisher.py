"""
Redis Pub/Sub 이벤트 퍼블리셔
REQ-SSE-005: 태스크 상태 변경 시 Redis Pub/Sub 채널에 이벤트 발행
REQ-SSE-006: publish_task_event(task_id, event_type, data) 인터페이스
"""

import json

import redis
import redis.asyncio as aioredis

from backend.utils.logger import get_logger

logger = get_logger(__name__)


# @MX:ANCHOR: 이벤트 발행 공개 인터페이스 - 워커/API 레이어에서 호출
# @MX:REASON: Celery 워커와 API 핸들러 양쪽에서 사용되는 핵심 이벤트 발행 함수
async def publish_task_event(
    redis_client: aioredis.Redis,
    task_id: str,
    event_type: str,
    data: dict,
) -> None:
    """
    태스크 이벤트를 Redis Pub/Sub 채널에 발행 (비동기 버전)

    Args:
        redis_client: Redis 비동기 클라이언트
        task_id: 태스크 고유 식별자
        event_type: 이벤트 타입 (status_update, completed, failed)
        data: 이벤트 데이터 (status, progress, message 등)
    """
    channel = f"task:{task_id}:status"
    message = json.dumps({"event": event_type, "data": data})

    await redis_client.publish(channel, message)
    logger.debug("태스크 이벤트 발행", task_id=task_id, event_type=event_type, channel=channel)


def publish_task_event_sync(
    redis_client: redis.Redis,
    task_id: str,
    event_type: str,
    data: dict,
) -> None:
    """
    태스크 이벤트를 Redis Pub/Sub 채널에 발행 (동기 버전 - Celery 워커용)

    Args:
        redis_client: Redis 동기 클라이언트
        task_id: 태스크 고유 식별자
        event_type: 이벤트 타입 (status_update, completed, failed)
        data: 이벤트 데이터 (status, progress, message 등)
    """
    channel = f"task:{task_id}:status"
    message = json.dumps({"event": event_type, "data": data})

    try:
        redis_client.publish(channel, message)
        logger.debug("태스크 이벤트 발행(동기)", task_id=task_id, event_type=event_type)
    except Exception:
        # Pub/Sub 발행 실패는 무시 (폴링 폴백으로 처리 가능)
        logger.warning("태스크 이벤트 발행 실패", task_id=task_id, event_type=event_type)

    # SPEC-WEBHOOK-001: 작업 완료/실패 시 등록된 웹훅 URL로 best-effort 알림
    if event_type in ("completed", "failed"):
        try:
            from backend.services.webhook_notifier import notify_webhooks_sync
            task_type = data.get("task_type", "unknown")
            notify_webhooks_sync(
                task_id=task_id,
                event_type=event_type,
                task_type=task_type,
                data=data,
            )
        except Exception:
            logger.warning("웹훅 알림 호출 실패 (무시)", task_id=task_id, event_type=event_type)
