"""
FastAPI 의존성 주입 - Redis 클라이언트, STT 엔진, 화자 분리 엔진, DB 세션, JWT 인증
"""

import inspect
from collections.abc import AsyncGenerator
from functools import lru_cache

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
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


async def close_redis_client() -> None:
    """캐시된 Redis 클라이언트를 종료하고 싱글톤 캐시를 비운다."""
    if get_redis_client.cache_info().currsize == 0:
        return

    client = get_redis_client()
    close = getattr(client, "aclose", None) or getattr(client, "close", None)
    if close is not None:
        result = close()
        if inspect.isawaitable(result):
            await result
    get_redis_client.cache_clear()


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


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    SPEC-TEAM-001: JWT Bearer 토큰으로 현재 사용자를 반환하는 의존성

    Authorization: Bearer <access_token> 헤더 필수.

    Raises:
        HTTPException(401): 토큰 없음, 만료, 또는 사용자 없음
    """
    # 지연 임포트로 순환 참조 방지
    from backend.db.auth_models import User
    from backend.services.auth_service import AuthService

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    token = auth_header.split(" ", 1)[1]
    auth_service = AuthService()
    payload = auth_service.decode_access_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    import uuid as _uuid

    try:
        user_uuid = _uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    return user
