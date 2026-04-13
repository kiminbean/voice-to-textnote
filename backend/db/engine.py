"""
DB 엔진 모듈 - 비동기 SQLAlchemy 엔진/세션 팩토리

REQ-DB-001: PostgreSQL 비동기 세션 팩토리
REQ-DB-002: DATABASE_URL 미설정 시 SQLite 폴백 (개발/테스트 모드)
REQ-DB-003: 커넥션 풀 min 5, max 20 (pool_size=5, max_overflow=15)
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.config import settings

# 개발/테스트 모드 기본 SQLite URL
DEFAULT_DB_URL = "sqlite+aiosqlite:///./voice_to_textnote.db"


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """
    비동기 SQLAlchemy 엔진 생성

    Args:
        database_url: 데이터베이스 URL.
            None 또는 빈 문자열이면 SQLite 폴백(REQ-DB-002).
            PostgreSQL URL이면 커넥션 풀 설정 적용(REQ-DB-003).

    Returns:
        AsyncEngine 인스턴스
    """
    # None 또는 빈 문자열이면 SQLite 폴백
    url = database_url if database_url else DEFAULT_DB_URL

    if "sqlite" in url:
        # SQLite: 커넥션 풀 옵션 없음 (동시성 제한)
        return create_async_engine(url, echo=False)

    # PostgreSQL: REQ-DB-003 커넥션 풀 설정
    # pool_size=5 (최소), max_overflow=15 → 총 최대 20 연결
    return create_async_engine(
        url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        echo=False,
    )


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """
    비동기 세션 팩토리 생성

    Args:
        engine: AsyncEngine 인스턴스

    Returns:
        async_sessionmaker 인스턴스
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
