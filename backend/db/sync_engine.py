"""
동기 SQLAlchemy 엔진 모듈 - Celery 워커용

REQ-PERSIST-001: Celery 워커용 동기 DB 세션 팩토리
AC-DI-021 ~ AC-DI-024: 명시적 초기화 패턴으로 전환

Celery 워커는 동기 환경이므로 aiosqlite/asyncpg 대신
동기 SQLAlchemy 드라이버를 사용합니다.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import settings

# 명시적 초기화 상태 (AC-DI-021)
_initialized_engine: Engine | None = None
_initialized_session_factory: sessionmaker | None = None

# deprecated shim — Phase 5에서 제거 예정
_sync_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def init_sync_engine() -> tuple[Engine, sessionmaker]:
    """
    AC-DI-021: 명시적 동기 엔진 초기화

    Celery worker_init 시그널에서 호출.
    비동기 URL(+aiosqlite, +asyncpg)을 동기 URL로 자동 변환합니다.

    Returns:
        (Engine, sessionmaker) 튜플
    """
    global _initialized_engine, _initialized_session_factory

    if _initialized_engine is not None:
        return _initialized_engine, _initialized_session_factory  # type: ignore

    url = settings.database_url or "sqlite:///./voice_to_textnote.db"

    # 비동기 드라이버를 동기 드라이버로 변환
    sync_url = url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2") if "+" in url else url

    _initialized_engine = create_engine(sync_url, pool_pre_ping=True)
    _initialized_session_factory = sessionmaker(_initialized_engine)

    return _initialized_engine, _initialized_session_factory


def _get_sync_engine() -> tuple[Engine, sessionmaker]:
    """
    동기 엔진과 세션 팩토리를 반환

    우선순위: init_sync_engine()으로 초기화된 상태 → lazy init 폴백
    """
    global _sync_engine, _SessionLocal

    # 명시적 초기화가 된 경우 우선 사용
    if _initialized_engine is not None:
        return _initialized_engine, _initialized_session_factory  # type: ignore

    # 폴백: lazy init (기존 동작 보존)
    if _sync_engine is None:
        url = settings.database_url or "sqlite:///./voice_to_textnote.db"

        if "+" in url:
            sync_url = url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")
        else:
            sync_url = url

        _sync_engine = create_engine(sync_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(_sync_engine)

    return _sync_engine, _SessionLocal  # type: ignore


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """
    AC-DI-023: 동기 DB 세션 컨텍스트 매니저

    init_sync_engine() 호출 후 사용 가능.
    미초기화 시 lazy init 폴백 (AC-DI-024).

    사용 예:
        with get_sync_session() as session:
            session.add(record)
            session.commit()
    """
    _, session_factory = _get_sync_engine()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
