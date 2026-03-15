"""
FastAPI 의존성 주입 - Redis 클라이언트, STT 엔진
"""

from functools import lru_cache

import redis.asyncio as aioredis

from backend.app.config import settings
from backend.ml.stt_engine import WhisperEngine
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@lru_cache
def get_redis_client() -> aioredis.Redis:
    """Redis 비동기 클라이언트 (싱글톤)"""
    return aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )


@lru_cache
def get_whisper_engine() -> WhisperEngine:
    """WhisperEngine 싱글톤 반환"""
    return WhisperEngine.get_instance()
