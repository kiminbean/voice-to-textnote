"""
SPEC-LIFECYCLE-001 단위 테스트 - 앱 수명주기 관리
REQ-LIFE-001: 시작 시 Redis 연결 검증, 실패 시 warning 로그
REQ-LIFE-002: 시작 시 DB 연결 검증, 개발 모드에서 테이블 자동 생성
REQ-LIFE-003: 구조화된 JSON 시작 로그 출력 (서비스별 상태)
REQ-LIFE-004: 종료 시 DB 커넥션 풀 dispose
REQ-LIFE-005: 종료 완료 로그 출력
"""

from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_engine():
    """공통 mock DB 엔진 팩토리"""
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.run_sync = AsyncMock()

    @asynccontextmanager
    async def mock_begin():
        yield mock_conn

    mock_engine.begin = mock_begin
    mock_engine.dispose = AsyncMock()
    return mock_engine


def _mock_redis():
    """공통 mock Redis 클라이언트 팩토리"""
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True
    return mock_redis


@contextmanager
def _patches(mock_engine=None, mock_redis=None):
    """
    lifecycle 모듈의 의존성을 패치하는 컨텍스트 매니저.
    """
    redis_mock = mock_redis or _mock_redis()
    engine_mock = mock_engine or _mock_engine()
    with (
        patch("backend.app.dependencies.get_redis_client", return_value=redis_mock),
        patch("backend.app.dependencies._db_engine", engine_mock),
    ):
        yield


# ---------------------------------------------------------------------------
# REQ-LIFE-001: Redis 연결 검증
# ---------------------------------------------------------------------------


class TestValidateStartupRedis:
    """시작 시 Redis 연결 검증 테스트"""

    @pytest.mark.asyncio
    async def test_redis_ok_when_ping_succeeds(self):
        """REQ-LIFE-001: Redis ping 성공 시 status['redis'] == 'ok'"""
        with _patches():
            from backend.app.lifecycle import validate_startup

            status = await validate_startup()

        assert status["redis"] == "ok"

    @pytest.mark.asyncio
    async def test_redis_warning_when_ping_fails(self):
        """REQ-LIFE-001: Redis ping 실패 시 status['redis']에 'warning' 포함"""
        mock_redis = _mock_redis()
        mock_redis.ping.side_effect = Exception("Connection refused")

        with _patches(mock_redis=mock_redis):
            from backend.app.lifecycle import validate_startup

            status = await validate_startup()

        assert "warning" in status["redis"]

    @pytest.mark.asyncio
    async def test_redis_failure_does_not_raise(self):
        """REQ-LIFE-001: Redis 연결 실패해도 예외 발생하지 않음 (서버 계속 실행)"""
        mock_redis = _mock_redis()
        mock_redis.ping.side_effect = Exception("Connection refused")

        with _patches(mock_redis=mock_redis):
            from backend.app.lifecycle import validate_startup

            status = await validate_startup()

        assert isinstance(status, dict)


# ---------------------------------------------------------------------------
# REQ-LIFE-002: DB 연결 검증
# ---------------------------------------------------------------------------


class TestValidateStartupDatabase:
    """시작 시 DB 연결 검증 테스트"""

    @pytest.mark.asyncio
    async def test_database_ok_when_engine_created(self):
        """REQ-LIFE-002: DB 엔진 생성 성공 시 status['database'] == 'ok'"""
        with _patches():
            from backend.app.lifecycle import validate_startup

            status = await validate_startup()

        assert status["database"] == "ok"

    @pytest.mark.asyncio
    async def test_database_warning_when_engine_fails(self):
        """REQ-LIFE-002: DB 엔진 생성 실패 시 status['database']에 'warning' 포함"""
        mock_engine = MagicMock()
        mock_engine.begin = AsyncMock(side_effect=Exception("DB connection failed"))

        with _patches(mock_engine=mock_engine):
            from backend.app.lifecycle import validate_startup

            status = await validate_startup()

        assert "warning" in status["database"]

    @pytest.mark.asyncio
    async def test_database_failure_does_not_raise(self):
        """REQ-LIFE-002: DB 연결 실패해도 예외 발생하지 않음"""
        mock_engine = MagicMock()
        mock_engine.begin = AsyncMock(side_effect=Exception("DB connection failed"))

        with _patches(mock_engine=mock_engine):
            from backend.app.lifecycle import validate_startup

            status = await validate_startup()

        assert isinstance(status, dict)


# ---------------------------------------------------------------------------
# REQ-LIFE-003: 구조화된 시작 로그
# ---------------------------------------------------------------------------


class TestValidateStartupLog:
    """구조화된 시작 로그 테스트"""

    @pytest.mark.asyncio
    async def test_validate_startup_returns_dict(self):
        """REQ-LIFE-003: validate_startup이 딕셔너리 반환"""
        with _patches():
            from backend.app.lifecycle import validate_startup

            result = await validate_startup()

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_validate_startup_status_has_redis_and_database_keys(self):
        """REQ-LIFE-003: 반환된 상태에 redis와 database 키 포함"""
        with _patches():
            from backend.app.lifecycle import validate_startup

            status = await validate_startup()

        assert "redis" in status
        assert "database" in status


# ---------------------------------------------------------------------------
# REQ-LIFE-004: DB 커넥션 풀 dispose
# ---------------------------------------------------------------------------


class TestCleanupShutdown:
    """종료 시 리소스 정리 테스트"""

    @pytest.mark.asyncio
    async def test_cleanup_shutdown_disposes_engine(self):
        """REQ-LIFE-004: 종료 시 DB 엔진 dispose 호출"""
        mock_engine = _mock_engine()

        with patch("backend.app.dependencies._db_engine", mock_engine):
            from backend.app.lifecycle import cleanup_shutdown

            await cleanup_shutdown()

        mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_shutdown_does_not_raise(self):
        """REQ-LIFE-004/005: 종료 정리 실패해도 예외 발생하지 않음"""
        with patch(
            "backend.app.dependencies._db_engine",
            side_effect=Exception("Engine error"),
        ):
            from backend.app.lifecycle import cleanup_shutdown

            await cleanup_shutdown()

    @pytest.mark.asyncio
    async def test_cleanup_shutdown_handles_dispose_error(self):
        """REQ-LIFE-004: dispose 실패해도 예외 발생하지 않음"""
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock(side_effect=Exception("Dispose failed"))

        with patch("backend.app.dependencies._db_engine", mock_engine):
            from backend.app.lifecycle import cleanup_shutdown

            await cleanup_shutdown()


# ---------------------------------------------------------------------------
# 앱 시작 시각 추적
# ---------------------------------------------------------------------------


class TestAppStartedAt:
    """앱 시작 시각 추적 테스트"""

    def setup_method(self):
        """각 테스트 전 _app_started_at 초기화"""
        import backend.app.lifecycle as lc

        lc._app_started_at = None

    @pytest.mark.asyncio
    async def test_app_started_at_set_on_validate_startup(self):
        """validate_startup 호출 시 _app_started_at 설정됨"""
        with _patches():
            from backend.app.lifecycle import get_app_started_at, validate_startup

            await validate_startup()
            started_at = get_app_started_at()

        assert started_at is not None
        assert isinstance(started_at, datetime)

    def test_get_app_started_at_returns_none_initially(self):
        """초기 상태에서 get_app_started_at() == None"""
        import backend.app.lifecycle as lc

        lc._app_started_at = None
        from backend.app.lifecycle import get_app_started_at

        assert get_app_started_at() is None

    @pytest.mark.asyncio
    async def test_started_at_is_utc_timezone(self):
        """validate_startup 호출 후 started_at이 UTC 타임존"""
        with _patches():
            from backend.app.lifecycle import get_app_started_at, validate_startup

            await validate_startup()
            started_at = get_app_started_at()

        assert started_at.tzinfo is not None
        assert started_at.tzinfo == UTC
