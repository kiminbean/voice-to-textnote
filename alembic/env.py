"""
Alembic 환경 설정 - SPEC-DB-001 (REQ-DB-007, REQ-DB-008)

비동기 SQLAlchemy 기반 마이그레이션 환경.
settings.database_url 또는 DEFAULT_DB_URL을 사용합니다.
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.db.engine import DEFAULT_DB_URL
from backend.db.models import Base

# alembic.ini 로깅 설정 적용
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 마이그레이션 대상 메타데이터
target_metadata = Base.metadata


def get_db_url() -> str:
    """
    마이그레이션에 사용할 DB URL 결정

    우선순위:
    1. DATABASE_URL 환경 변수
    2. settings.database_url (앱 설정)
    3. DEFAULT_DB_URL (SQLite 폴백)
    """
    # 환경 변수 우선
    env_url = os.environ.get("DATABASE_URL", "")
    if env_url:
        return env_url

    # 앱 설정 사용 시도
    try:
        from backend.app.config import settings

        if settings.database_url:
            return settings.database_url
    except Exception:
        pass

    return DEFAULT_DB_URL


def run_migrations_offline() -> None:
    """
    오프라인 모드 마이그레이션 (SQL 스크립트 생성)

    DB 연결 없이 SQL 파일을 생성합니다.
    """
    url = get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """동기 마이그레이션 실행 (비동기 래퍼에서 호출)"""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """비동기 온라인 마이그레이션"""
    url = get_db_url()

    # URL에 따라 드라이버 자동 선택
    # SQLite는 aiosqlite, PostgreSQL은 asyncpg 사용
    if "sqlite" in url and "+aiosqlite" not in url:
        url = url.replace("sqlite://", "sqlite+aiosqlite://")
    elif "postgresql" in url and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://")

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """온라인 모드 마이그레이션 (실제 DB 연결)"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
