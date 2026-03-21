"""
SPEC-LIFECYCLE-001 단위 테스트 - 헬스체크 버전 정보
REQ-LIFE-006: /api/v1/health 응답에 version, started_at, uptime_seconds 포함
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis_healthy():
    """정상 상태 Redis mock"""
    redis_mock = AsyncMock()
    redis_mock.ping.return_value = True
    return redis_mock


@pytest.fixture
def client_with_started_at(mock_redis_healthy):
    """started_at이 설정된 상태의 테스트 클라이언트"""
    import backend.app.lifecycle as lc
    from backend.app.dependencies import get_redis_client
    from backend.app.main import app

    # 시작 시각 설정 (10초 전)
    lc._app_started_at = datetime.now(UTC) - timedelta(seconds=10)

    async def override_redis():
        return mock_redis_healthy

    app.dependency_overrides[get_redis_client] = override_redis

    with patch("backend.app.main.WhisperEngine") as mock_engine_cls:
        mock_engine_inst = MagicMock()
        mock_engine_inst.is_loaded = True
        mock_engine_inst.load.return_value = None
        mock_engine_cls.get_instance.return_value = mock_engine_inst

        yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()
    # 테스트 후 초기화
    lc._app_started_at = None


@pytest.fixture
def client_with_no_started_at(mock_redis_healthy):
    """started_at이 설정되지 않은 상태의 테스트 클라이언트"""
    import backend.app.lifecycle as lc
    from backend.app.dependencies import get_redis_client
    from backend.app.main import app

    # 시작 시각 없음
    lc._app_started_at = None

    async def override_redis():
        return mock_redis_healthy

    app.dependency_overrides[get_redis_client] = override_redis

    with patch("backend.app.main.WhisperEngine") as mock_engine_cls:
        mock_engine_inst = MagicMock()
        mock_engine_inst.is_loaded = True
        mock_engine_inst.load.return_value = None
        mock_engine_cls.get_instance.return_value = mock_engine_inst

        yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# REQ-LIFE-006: version 필드
# ---------------------------------------------------------------------------


class TestHealthVersionField:
    """헬스체크 응답 version 필드 테스트"""

    def test_health_response_has_version_field(self, client_with_started_at):
        """REQ-LIFE-006: 헬스체크 응답에 version 필드 포함"""
        response = client_with_started_at.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data

    def test_health_version_is_string(self, client_with_started_at):
        """REQ-LIFE-006: version 값이 문자열"""
        response = client_with_started_at.get("/api/v1/health")
        data = response.json()
        assert isinstance(data["version"], str)

    def test_health_version_is_not_empty(self, client_with_started_at):
        """REQ-LIFE-006: version 값이 비어있지 않음"""
        response = client_with_started_at.get("/api/v1/health")
        data = response.json()
        assert len(data["version"]) > 0


# ---------------------------------------------------------------------------
# REQ-LIFE-006: started_at 필드
# ---------------------------------------------------------------------------


class TestHealthStartedAtField:
    """헬스체크 응답 started_at 필드 테스트"""

    def test_health_response_has_started_at_field(self, client_with_started_at):
        """REQ-LIFE-006: 헬스체크 응답에 started_at 필드 포함"""
        response = client_with_started_at.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "started_at" in data

    def test_health_started_at_is_not_none_when_app_started(self, client_with_started_at):
        """REQ-LIFE-006: 앱 시작 후 started_at이 None이 아님"""
        response = client_with_started_at.get("/api/v1/health")
        data = response.json()
        assert data["started_at"] is not None

    def test_health_started_at_is_none_before_app_started(self, client_with_no_started_at):
        """REQ-LIFE-006: 앱 미시작 시 started_at이 None"""
        response = client_with_no_started_at.get("/api/v1/health")
        data = response.json()
        assert data["started_at"] is None

    def test_health_started_at_is_iso_format(self, client_with_started_at):
        """REQ-LIFE-006: started_at 값이 ISO 8601 형식"""
        response = client_with_started_at.get("/api/v1/health")
        data = response.json()
        started_at_str = data["started_at"]
        # ISO 8601 파싱 가능해야 함
        parsed = datetime.fromisoformat(started_at_str)
        assert isinstance(parsed, datetime)


# ---------------------------------------------------------------------------
# REQ-LIFE-006: uptime_seconds 필드
# ---------------------------------------------------------------------------


class TestHealthUptimeField:
    """헬스체크 응답 uptime_seconds 필드 테스트"""

    def test_health_response_has_uptime_seconds_field(self, client_with_started_at):
        """REQ-LIFE-006: 헬스체크 응답에 uptime_seconds 필드 포함"""
        response = client_with_started_at.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "uptime_seconds" in data

    def test_health_uptime_seconds_is_positive_when_started(self, client_with_started_at):
        """REQ-LIFE-006: 앱 시작 후 uptime_seconds가 양수"""
        response = client_with_started_at.get("/api/v1/health")
        data = response.json()
        assert data["uptime_seconds"] > 0

    def test_health_uptime_seconds_is_zero_when_not_started(self, client_with_no_started_at):
        """REQ-LIFE-006: 앱 미시작 시 uptime_seconds가 0"""
        response = client_with_no_started_at.get("/api/v1/health")
        data = response.json()
        assert data["uptime_seconds"] == 0

    def test_health_uptime_seconds_is_numeric(self, client_with_started_at):
        """REQ-LIFE-006: uptime_seconds가 숫자형"""
        response = client_with_started_at.get("/api/v1/health")
        data = response.json()
        assert isinstance(data["uptime_seconds"], int | float)

    def test_health_uptime_seconds_approximately_correct(self, client_with_started_at):
        """REQ-LIFE-006: 10초 전 시작한 경우 uptime이 약 10초 이상"""
        response = client_with_started_at.get("/api/v1/health")
        data = response.json()
        # 10초 전에 시작했으므로 uptime이 최소 9초 이상이어야 함
        assert data["uptime_seconds"] >= 9
