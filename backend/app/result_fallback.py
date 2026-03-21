"""
결과 조회 폴백 모듈 - Redis 캐시 미스 시 DB 조회

REQ-PERSIST-009: Redis 캐시 미스 시 DB 폴백 조회
REQ-PERSIST-010: DB에서 찾으면 Redis 캐시 복원

API 엔드포인트에서 Redis 캐시 미스 발생 시 DB에서 조회하고,
찾은 경우 Redis 캐시를 복원하여 다음 요청의 성능을 보장합니다.
"""

import json

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.service import ResultService


async def get_result_with_fallback(
    redis_client: aioredis.Redis,
    task_id: str,
    redis_key: str,
    db_session: AsyncSession,
) -> dict | None:
    """
    Redis 캐시 우선 조회, 미스 시 DB 폴백

    1단계: Redis에서 redis_key로 조회
    2단계: 캐시 미스 시 DB에서 task_id로 조회 (REQ-PERSIST-009)
    3단계: DB에서 찾으면 Redis 캐시 복원 (REQ-PERSIST-010)

    Args:
        redis_client: 비동기 Redis 클라이언트
        task_id: 작업 ID (DB 조회에 사용)
        redis_key: Redis 캐시 키 (Redis 조회 및 복원에 사용)
        db_session: 비동기 DB 세션

    Returns:
        결과 딕셔너리 또는 None (없으면)
    """
    # 1단계: Redis 캐시 조회
    cached = await redis_client.get(redis_key)
    if cached:
        return json.loads(cached)

    # 2단계: DB 폴백 조회 (REQ-PERSIST-009)
    service = ResultService()
    record = await service.get_result(db_session, task_id)

    if record and record.result_data:
        # 3단계: Redis 캐시 복원 (REQ-PERSIST-010)
        await redis_client.setex(
            redis_key,
            settings.cache_ttl_seconds,
            json.dumps(record.result_data),
        )
        return record.result_data

    return None
