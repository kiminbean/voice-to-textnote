"""
동기 SQLAlchemy 엔진 모듈 - Celery 워커용

REQ-PERSIST-001: Celery 워커용 동기 DB 세션 팩토리

Celery 워커는 동기 환경이므로 aiosqlite/asyncpg 대신
동기 SQLAlchemy 드라이버를 사용합니다.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import settings

# 모듈 수준 싱글톤 (테스트 격리를 위해 None으로 초기화 가능)
_sync_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _get_sync_engine() -> tuple[Engine, sessionmaker]:
    """
    동기 엔진과 세션 팩토리를 싱글톤으로 반환

    비동기 URL(+aiosqlite, +asyncpg)을 동기 URL로 자동 변환합니다.
    """
    global _sync_engine, _SessionLocal

    if _sync_engine is None:
        # 설정에서 DB URL 가져오기 (없으면 SQLite 기본값)
        url = settings.database_url or "sqlite:///./voice_to_textnote.db"

        # 비동기 드라이버를 동기 드라이버로 변환
        # - sqlite+aiosqlite → sqlite
        # - postgresql+asyncpg → postgresql+psycopg2
        if "+" in url:
            sync_url = url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")
        else:
            sync_url = url

        _sync_engine = create_engine(sync_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(_sync_engine)

    assert _SessionLocal is not None
    return _sync_engine, _SessionLocal


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """
    동기 DB 세션 컨텍스트 매니저

    사용 예:
        with get_sync_session() as session:
            session.add(record)
            session.commit()
    """
    _, session_local = _get_sync_engine()
    session = session_local()
    try:
        yield session
    finally:
        session.close()
