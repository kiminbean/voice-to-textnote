"""
FastAPI 의존성 주입 - Redis 클라이언트, STT 엔진, 화자 분리 엔진, DB 세션
"""

from collections.abc import AsyncGenerator
from functools import lru_cache

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.engine import create_engine, get_session_factory
from backend.ml.diarization_engine import DiarizationEngine
from backend.ml.stt_engine import WhisperEngine
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# DB 엔진 싱글톤 (설정 기반)
_db_engine = create_engine(database_url=settings.database_url or None)
_session_factory = get_session_factory(_db_engine)


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


@lru_cache
def get_diarization_engine() -> DiarizationEngine:
    """DiarizationEngine 싱글톤 반환"""
    return DiarizationEngine.get_instance()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    REQ-DB-012: FastAPI DB 세션 의존성

    엔드포인트에 DB 세션을 주입합니다.
    요청 완료 후 세션을 자동으로 닫습니다.

    사용 예:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with _session_factory() as session:
        yield session
