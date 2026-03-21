"""
DB 엔진 모듈 테스트 - REQ-DB-001, REQ-DB-002, REQ-DB-003

테스트 범위:
- 비동기 SQLAlchemy 엔진/세션 팩토리 생성
- SQLite 폴백 동작 (DATABASE_URL 미설정 시)
- PostgreSQL 커넥션 풀 설정 (min 5, max 20)
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


class TestCreateEngine:
    """REQ-DB-001: 비동기 SQLAlchemy 엔진 팩토리 테스트"""

    def test_create_engine_returns_async_engine(self):
        """인자 없이 호출하면 AsyncEngine 반환"""
        from backend.db.engine import create_engine

        engine = create_engine()
        assert isinstance(engine, AsyncEngine)

    def test_create_engine_sqlite_fallback_when_no_url(self):
        """REQ-DB-002: DATABASE_URL 미설정 시 SQLite로 폴백"""
        from backend.db.engine import create_engine

        engine = create_engine(database_url=None)
        # SQLite 드라이버 확인
        assert "sqlite" in str(engine.url)

    def test_create_engine_sqlite_fallback_when_empty_string(self):
        """REQ-DB-002: 빈 문자열도 SQLite 폴백"""
        from backend.db.engine import create_engine

        engine = create_engine(database_url="")
        assert "sqlite" in str(engine.url)

    def test_create_engine_with_explicit_sqlite_url(self):
        """명시적 SQLite URL 사용"""
        from backend.db.engine import create_engine

        engine = create_engine(database_url="sqlite+aiosqlite:///:memory:")
        assert "sqlite" in str(engine.url)

    def test_create_engine_postgresql_pool_size(self):
        """REQ-DB-003: PostgreSQL 커넥션 풀 min 5, max 20 설정"""
        from unittest.mock import MagicMock, patch

        from backend.db.engine import create_engine

        # asyncpg 미설치 환경에서도 풀 설정 검증: create_async_engine 호출 인자 확인
        with patch("backend.db.engine.create_async_engine") as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine

            create_engine(
                database_url="postgresql+asyncpg://user:pass@localhost/testdb"
            )

            # pool_size=5, max_overflow=15 인자로 호출됐는지 검증
            _, kwargs = mock_create.call_args
            assert kwargs["pool_size"] == 5
            assert kwargs["max_overflow"] == 15


class TestGetSessionFactory:
    """세션 팩토리 생성 테스트"""

    def test_get_session_factory_returns_sessionmaker(self):
        """세션 팩토리 반환"""
        from backend.db.engine import create_engine, get_session_factory

        engine = create_engine()
        factory = get_session_factory(engine)
        assert isinstance(factory, async_sessionmaker)

    @pytest.mark.asyncio
    async def test_session_factory_creates_async_session(self):
        """세션 팩토리로 AsyncSession 생성"""
        from backend.db.engine import create_engine, get_session_factory
        from backend.db.models import Base

        engine = create_engine(database_url="sqlite+aiosqlite:///:memory:")

        # 테이블 생성
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        factory = get_session_factory(engine)
        async with factory() as session:
            assert isinstance(session, AsyncSession)

        await engine.dispose()


class TestDefaultDbUrl:
    """DEFAULT_DB_URL 상수 테스트"""

    def test_default_db_url_is_sqlite(self):
        """기본 DB URL이 SQLite"""
        from backend.db.engine import DEFAULT_DB_URL

        assert "sqlite+aiosqlite" in DEFAULT_DB_URL
