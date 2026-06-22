"""
SPEC-OPS-001 헬스체크 강화 단위 테스트
REQ-OPS-008: /api/v1/health/ready 엔드포인트 (Kubernetes readiness probe)
REQ-OPS-009: readiness 체크에서 Redis 연결 및 Celery 워커 가용성 확인
"""

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
def mock_redis_unhealthy():
    """비정상 상태 Redis mock (연결 실패)"""
    redis_mock = AsyncMock()
    redis_mock.ping.side_effect = Exception("Connection refused")
    return redis_mock


@pytest.fixture
def client_with_healthy_redis(mock_redis_healthy):
    """정상 Redis가 있는 테스트 클라이언트"""
    from backend.app.dependencies import get_redis_client
    from backend.app.main import app

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


@pytest.fixture
def client_with_unhealthy_redis(mock_redis_unhealthy):
    """비정상 Redis가 있는 테스트 클라이언트"""
    from backend.app.dependencies import get_redis_client
    from backend.app.main import app

    async def override_redis():
        return mock_redis_unhealthy

    app.dependency_overrides[get_redis_client] = override_redis

    with patch("backend.app.main.WhisperEngine") as mock_engine_cls:
        mock_engine_inst = MagicMock()
        mock_engine_inst.is_loaded = True
        mock_engine_inst.load.return_value = None
        mock_engine_cls.get_instance.return_value = mock_engine_inst

        yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# REQ-OPS-008: /api/v1/health/ready 엔드포인트
# ---------------------------------------------------------------------------


class TestReadinessEndpoint:
    """Readiness probe 엔드포인트 테스트"""

    def test_readiness_endpoint_exists(self, client_with_healthy_redis):
        """REQ-OPS-008: /api/v1/health/ready 엔드포인트 존재"""
        response = client_with_healthy_redis.get("/api/v1/health/ready")
        # 404가 아니어야 함
        assert response.status_code != 404

    def test_readiness_returns_200_when_healthy(self, client_with_healthy_redis):
        """REQ-OPS-008: Redis 정상 시 200 응답"""
        response = client_with_healthy_redis.get("/api/v1/health/ready")
        assert response.status_code == 200

    def test_readiness_returns_json_response(self, client_with_healthy_redis):
        """REQ-OPS-008: JSON 형식 응답 반환"""
        response = client_with_healthy_redis.get("/api/v1/health/ready")
        data = response.json()
        assert isinstance(data, dict)

    def test_readiness_response_has_status_field(self, client_with_healthy_redis):
        """REQ-OPS-008: 응답에 status 필드 포함"""
        response = client_with_healthy_redis.get("/api/v1/health/ready")
        data = response.json()
        assert "status" in data

    def test_readiness_response_has_redis_field(self, client_with_healthy_redis):
        """REQ-OPS-009: 응답에 redis 상태 필드 포함"""
        response = client_with_healthy_redis.get("/api/v1/health/ready")
        data = response.json()
        assert "redis" in data

    def test_readiness_response_has_workers_field(self, client_with_healthy_redis):
        """REQ-OPS-009: 응답에 workers 상태 필드 포함"""
        response = client_with_healthy_redis.get("/api/v1/health/ready")
        data = response.json()
        assert "workers" in data


# ---------------------------------------------------------------------------
# REQ-OPS-009: Redis 연결 확인
# ---------------------------------------------------------------------------


class TestReadinessRedisCheck:
    """Readiness probe Redis 연결 확인 테스트"""

    def test_readiness_redis_healthy_status(self, client_with_healthy_redis):
        """REQ-OPS-009: Redis 정상 시 redis 상태가 true"""
        response = client_with_healthy_redis.get("/api/v1/health/ready")
        data = response.json()
        assert data["redis"] is True

    def test_readiness_returns_503_when_redis_down(self, client_with_unhealthy_redis):
        """REQ-OPS-009: Redis 비정상 시 503 응답"""
        response = client_with_unhealthy_redis.get("/api/v1/health/ready")
        assert response.status_code == 503

    def test_readiness_redis_unhealthy_status(self, client_with_unhealthy_redis):
        """REQ-OPS-009: Redis 비정상 시 redis 상태가 false"""
        response = client_with_unhealthy_redis.get("/api/v1/health/ready")
        data = response.json()
        assert data["redis"] is False

    def test_readiness_status_not_ready_when_redis_down(self, client_with_unhealthy_redis):
        """REQ-OPS-009: Redis 비정상 시 status가 'not_ready'"""
        response = client_with_unhealthy_redis.get("/api/v1/health/ready")
        data = response.json()
        assert data["status"] == "not_ready"


# ---------------------------------------------------------------------------
# REQ-OPS-009: Celery 워커 가용성 확인
# ---------------------------------------------------------------------------


class TestReadinessCeleryCheck:
    """Readiness probe Celery 워커 확인 테스트"""

    def test_readiness_workers_false_when_no_celery(self, client_with_healthy_redis):
        """REQ-OPS-009: Celery 워커 없을 때 workers가 false (개발환경 허용)"""
        # Celery inspect를 mock하여 워커 없음 시뮬레이션
        with patch("backend.app.api.v1.admin.health.celery_app.control.inspect") as mock_inspect:
            mock_inspect_instance = MagicMock()
            mock_inspect_instance.ping.return_value = None  # 워커 없음
            mock_inspect.return_value = mock_inspect_instance

            response = client_with_healthy_redis.get("/api/v1/health/ready")
            data = response.json()
            # 워커 없어도 200 반환 (개발 환경 허용)
            assert response.status_code == 200
            assert data["workers"] is False

    def test_readiness_workers_true_when_celery_available(self, client_with_healthy_redis):
        """REQ-OPS-009: Celery 워커 존재 시 workers가 true"""
        with patch("backend.app.api.v1.admin.health.celery_app.control.inspect") as mock_inspect:
            mock_inspect_instance = MagicMock()
            mock_inspect_instance.ping.return_value = {"celery@worker1": {"ok": "pong"}}
            mock_inspect.return_value = mock_inspect_instance

            response = client_with_healthy_redis.get("/api/v1/health/ready")
            data = response.json()
            assert response.status_code == 200
            assert data["workers"] is True

    def test_readiness_still_200_when_workers_unavailable(self, client_with_healthy_redis):
        """REQ-OPS-009: Celery 워커 없어도 Redis 정상이면 200 반환 (개발 환경 대응)"""
        with patch("backend.app.api.v1.admin.health.celery_app.control.inspect") as mock_inspect:
            mock_inspect.side_effect = Exception("Celery not running")

            response = client_with_healthy_redis.get("/api/v1/health/ready")
            # Redis 정상이면 200, workers는 false
            assert response.status_code == 200

    def test_readiness_returns_503_without_workers_in_production(
        self, client_with_healthy_redis
    ):
        """프로덕션에서는 Celery 워커가 없으면 트래픽 ready가 아니다."""
        with (
            patch("backend.app.api.v1.admin.health.settings") as mock_settings,
            patch("backend.app.api.v1.admin.health.celery_app.control.inspect") as mock_inspect,
        ):
            mock_settings.environment = "production"
            mock_inspect_instance = MagicMock()
            mock_inspect_instance.ping.return_value = None
            mock_inspect.return_value = mock_inspect_instance

            response = client_with_healthy_redis.get("/api/v1/health/ready")

        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "redis": True,
            "workers": False,
        }
