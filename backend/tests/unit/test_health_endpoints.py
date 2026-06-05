"""
SPEC-OPS-001 헬스체크 엔드포인트 추가 테스트

테스트 범위:
- model_health: /api/v1/health/model
- diarization_model_health: /api/v1/health/diarization
- health_check Redis 장애 시 degraded 응답
- health_check ffmpeg 미설치 시 degraded 응답
- _check_celery_status 예외 처리
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis_healthy():
    """정상 Redis mock"""
    redis_mock = AsyncMock()
    redis_mock.ping.return_value = True
    redis_mock.get.return_value = None
    return redis_mock


@pytest.fixture
def mock_whisper_engine():
    """WhisperEngine mock"""
    engine = MagicMock()
    engine.is_loaded = True
    engine.model_name = "whisper-large-v3"
    engine.device = "cpu"
    engine.load_time_seconds = 3.5
    engine.get_memory_info.return_value = {
        "used_mb": 1024.0,
        "total_mb": 8192.0,
        "available_mb": 7168.0,
    }
    return engine


@pytest.fixture
def mock_diarization_engine():
    """DiarizationEngine mock"""
    engine = MagicMock()
    engine.is_loaded = True
    engine.model_name = "pyannote/speaker-diarization"
    engine.load_time_seconds = 5.2
    return engine


@pytest.fixture
def client_full_deps(
    mock_redis_healthy, mock_whisper_engine, mock_diarization_engine
):
    """모든 의존성이 오버라이드된 테스트 클라이언트"""
    from backend.app.dependencies import (
        get_diarization_engine,
        get_redis_client,
        get_whisper_engine,
    )
    from backend.app.main import app

    async def override_redis():
        return mock_redis_healthy

    async def override_whisper():
        return mock_whisper_engine

    async def override_diarization():
        return mock_diarization_engine

    app.dependency_overrides[get_redis_client] = override_redis
    app.dependency_overrides[get_whisper_engine] = override_whisper
    app.dependency_overrides[get_diarization_engine] = override_diarization

    with patch("backend.app.main.WhisperEngine") as mock_engine_cls:
        mock_inst = MagicMock()
        mock_inst.is_loaded = True
        mock_inst.load.return_value = None
        mock_engine_cls.get_instance.return_value = mock_inst

        with patch("backend.app.api.v1.admin.health.celery_app"):
            yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /api/v1/health/model 테스트
# ---------------------------------------------------------------------------


class TestModelHealth:
    """모델 상태 조회 엔드포인트 테스트"""

    def test_returns_200(self, client_full_deps):
        """/health/model이 200 응답"""
        response = client_full_deps.get("/api/v1/health/model")
        assert response.status_code == 200

    def test_includes_model_name(self, client_full_deps):
        """model_name 필드 포함"""
        response = client_full_deps.get("/api/v1/health/model")
        data = response.json()
        assert data["model_name"] == "whisper-large-v3"

    def test_includes_model_loaded(self, client_full_deps):
        """model_loaded 필드 포함"""
        response = client_full_deps.get("/api/v1/health/model")
        data = response.json()
        assert data["model_loaded"] is True

    def test_includes_device(self, client_full_deps):
        """device 필드 포함"""
        response = client_full_deps.get("/api/v1/health/model")
        data = response.json()
        assert data["device"] == "cpu"

    def test_includes_memory_info(self, client_full_deps):
        """메모리 정보 필드 포함"""
        response = client_full_deps.get("/api/v1/health/model")
        data = response.json()
        assert "memory_usage_mb" in data
        assert "total_system_memory_mb" in data
        assert "available_memory_mb" in data

    def test_includes_version(self, client_full_deps):
        """version 필드 포함"""
        response = client_full_deps.get("/api/v1/health/model")
        data = response.json()
        assert "version" in data


# ---------------------------------------------------------------------------
# /api/v1/health/diarization 테스트
# ---------------------------------------------------------------------------


class TestDiarizationModelHealth:
    """화자 분리 모델 상태 조회 테스트"""

    def test_returns_200(self, client_full_deps):
        """/health/diarization이 200 응답"""
        response = client_full_deps.get("/api/v1/health/diarization")
        assert response.status_code == 200

    def test_includes_model_name(self, client_full_deps):
        """model_name 필드 포함"""
        response = client_full_deps.get("/api/v1/health/diarization")
        data = response.json()
        assert data["model_name"] == "pyannote/speaker-diarization"

    def test_includes_model_loaded(self, client_full_deps):
        """model_loaded 필드 포함"""
        response = client_full_deps.get("/api/v1/health/diarization")
        data = response.json()
        assert data["model_loaded"] is True

    def test_includes_load_time(self, client_full_deps):
        """load_time_seconds 필드 포함"""
        response = client_full_deps.get("/api/v1/health/diarization")
        data = response.json()
        assert data["load_time_seconds"] == 5.2


# ---------------------------------------------------------------------------
# health_check 예외 상황 테스트
# ---------------------------------------------------------------------------


class TestHealthCheckDegraded:
    """health_check 장애 상황 테스트"""

    def test_degraded_when_redis_down(self):
        """Redis 장애 시 status가 degraded"""
        from backend.app.dependencies import get_redis_client, get_whisper_engine
        from backend.app.main import app

        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection refused")
        mock_redis.get.return_value = None

        async def override_redis():
            return mock_redis

        async def override_whisper():
            engine = MagicMock()
            engine.is_loaded = True
            return engine

        app.dependency_overrides[get_redis_client] = override_redis
        app.dependency_overrides[get_whisper_engine] = override_whisper

        with patch("backend.app.main.WhisperEngine") as mock_engine_cls:
            mock_inst = MagicMock()
            mock_inst.is_loaded = True
            mock_inst.load.return_value = None
            mock_engine_cls.get_instance.return_value = mock_inst

            with patch("backend.app.api.v1.admin.health.celery_app"):
                client = TestClient(app, raise_server_exceptions=True)
                response = client.get("/api/v1/health")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert "unhealthy" in data["components"]["redis"]

    def test_degraded_when_ffmpeg_missing(self):
        """ffmpeg 미설치 시 status가 degraded"""
        from backend.app.dependencies import get_redis_client, get_whisper_engine
        from backend.app.main import app

        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = None

        async def override_redis():
            return mock_redis

        async def override_whisper():
            engine = MagicMock()
            engine.is_loaded = True
            return engine

        app.dependency_overrides[get_redis_client] = override_redis
        app.dependency_overrides[get_whisper_engine] = override_whisper

        with patch("backend.app.main.WhisperEngine") as mock_engine_cls:
            mock_inst = MagicMock()
            mock_inst.is_loaded = True
            mock_inst.load.return_value = None
            mock_engine_cls.get_instance.return_value = mock_inst

            with patch("backend.app.api.v1.admin.health.shutil.which", return_value=None):
                with patch("backend.app.api.v1.admin.health.celery_app"):
                    client = TestClient(app, raise_server_exceptions=True)
                    response = client.get("/api/v1/health")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["ffmpeg"] == "unavailable"

    def test_celery_status_unknown_on_exception(self, client_full_deps):
        """Celery 상태 조회 실패 시 unknown 반환"""
        with patch(
            "backend.app.api.v1.admin.health.celery_app.control.inspect"
        ) as mock_inspect:
            mock_inspect.side_effect = Exception("broker error")

            response = client_full_deps.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert "unknown" in data["components"]["celery_workers"]["status"]
