"""
Celery 워커용 공유 Redis 클라이언트
연결 풀을 공유하여 불필요한 연결 생성을 방지합니다.
"""

import redis
from redis.connection import ConnectionPool

from backend.app.config import settings

_pool: ConnectionPool | None = None


def get_worker_redis() -> redis.Redis:
    """
    워커 프로세스 전용 Redis 클라이언트 (연결 풀 공유)
    Celery 워커는 동기 환경이므로 redis-py 동기 클라이언트를 사용합니다.
    """
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=10,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
    return redis.Redis(connection_pool=_pool)
