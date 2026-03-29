"""
화자 분리 API 통합 테스트 (RED phase)
SPEC-DIA-001 인수 시나리오 검증
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_dia_redis_client():
    """Redis 비동기 클라이언트 mock (화자 분리 전용)"""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.ping.return_value = True
    redis_mock.scard.return_value = 0
    return redis_mock


@pytest.fixture
def dia_client(mock_dia_redis_client, tmp_path):
    """
    화자 분리 API TestClient
    - DiarizationEngine.load()를 mock
    - Redis를 mock
    - Celery를 mock
    """
    from fastapi.testclient import TestClient

    from backend.app.config import Settings
    from backend.app.dependencies import get_redis_client
    from backend.app.main import app

    # 임시 디렉토리를 스토리지로 사용
    test_settings = MagicMock(spec=Settings)
    test_settings.max_file_size_bytes = 500 * 1024 * 1024
    test_settings.max_file_size_mb = 500
    test_settings.max_duration_seconds = 4 * 3600
    test_settings.max_duration_hours = 4
    test_settings.max_concurrent_jobs = 3
    test_settings.max_concurrent_diarizations = 2
    test_settings.temp_dir = tmp_path / "temp"
    test_settings.results_dir = tmp_path / "results"
    test_settings.cache_ttl_seconds = 604800
    test_settings.diarization_result_ttl = 604800
    test_settings.whisper_model = "mlx-community/whisper-large-v3-turbo"
    test_settings.whisper_language = "ko"
    test_settings.chunk_duration_ms = 30 * 60 * 1000
    test_settings.chunk_overlap_ms = 5000
    test_settings.memory_warning_threshold_mb = 19660
    test_settings.huggingface_token = "hf_testtoken"
    test_settings.diarization_model = "pyannote/speaker-diarization-3.1"
    test_settings.temp_dir.mkdir(parents=True, exist_ok=True)
    test_settings.results_dir.mkdir(parents=True, exist_ok=True)

    async def override_redis():
        return mock_dia_redis_client

    app.dependency_overrides[get_redis_client] = override_redis

    with patch("backend.app.main.WhisperEngine") as mock_whisper_cls:
        mock_whisper_inst = MagicMock()
        mock_whisper_inst.is_loaded = True
        mock_whisper_inst.load.return_value = None
        mock_whisper_cls.get_instance.return_value = mock_whisper_inst

        with patch("backend.app.main.DiarizationEngine") as mock_dia_cls:
            mock_dia_inst = MagicMock()
            mock_dia_inst.is_loaded = True
            mock_dia_inst.load.return_value = None
            mock_dia_cls.get_instance.return_value = mock_dia_inst

            with patch("backend.app.api.v1.diarization.settings", test_settings):
                with patch(
                    "backend.workers.tasks.diarization_task.diarization_celery_task.delay"
                ) as mock_delay:
                    mock_task_result = MagicMock()
                    mock_task_result.id = "mock-dia-task-id"
                    mock_delay.return_value = mock_task_result

                    yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()


@pytest.fixture
def completed_dia_task_data():
    """완료된 화자 분리 작업 데이터"""
    task_id = str(uuid.uuid4())
    stt_task_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    return {
        "task_id": task_id,
        "stt_task_id": stt_task_id,
        "status": "completed",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 5.0,
                "text": "안녕하세요.",
                "confidence": 0.9,
                "speaker_id": "SPEAKER_00",
                "speaker_confidence": 1.0,
            },
            {
                "id": 1,
                "start": 6.0,
                "end": 10.0,
                "text": "반갑습니다.",
                "confidence": 0.85,
                "speaker_id": "SPEAKER_01",
                "speaker_confidence": 0.95,
            },
        ],
        "speakers": [
            {"speaker_id": "SPEAKER_00", "total_speaking_time": 5.0, "segment_count": 1},
            {"speaker_id": "SPEAKER_01", "total_speaking_time": 4.0, "segment_count": 1},
        ],
        "num_speakers": 2,
        "created_at": now,
        "completed_at": now,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/diarizations 테스트
# ---------------------------------------------------------------------------


class TestDiarizationCreate:
    """POST /api/v1/diarizations → 202 + task_id"""

    def test_create_returns_202(self, dia_client: TestClient):
        """POST → 202 Accepted + task_id 반환"""
        stt_task_id = str(uuid.uuid4())
        response = dia_client.post(
            "/api/v1/diarizations",
            json={"stt_task_id": stt_task_id},
        )
        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data

    def test_create_returns_status_pending(self, dia_client: TestClient):
        """POST 응답에 status=pending 포함"""
        stt_task_id = str(uuid.uuid4())
        response = dia_client.post(
            "/api/v1/diarizations",
            json={"stt_task_id": stt_task_id},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"

    def test_create_with_num_speakers(self, dia_client: TestClient):
        """num_speakers 파라미터 전달 가능"""
        stt_task_id = str(uuid.uuid4())
        response = dia_client.post(
            "/api/v1/diarizations",
            json={"stt_task_id": stt_task_id, "num_speakers": 2},
        )
        assert response.status_code == 202

    def test_create_response_has_status_url(self, dia_client: TestClient):
        """응답에 status_url 포함"""
        stt_task_id = str(uuid.uuid4())
        response = dia_client.post(
            "/api/v1/diarizations",
            json={"stt_task_id": stt_task_id},
        )
        assert response.status_code == 202
        data = response.json()
        assert "status_url" in data or "task_id" in data


# ---------------------------------------------------------------------------
# GET /api/v1/diarizations/{task_id}/status 테스트
# ---------------------------------------------------------------------------


class TestDiarizationStatus:
    """GET /api/v1/diarizations/{task_id}/status"""

    def test_status_returns_200(self, dia_client: TestClient, mock_dia_redis_client: AsyncMock):
        """존재하는 task_id → 200 + 상태 반환"""
        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        mock_dia_redis_client.get.return_value = json.dumps(
            {
                "task_id": task_id,
                "stt_task_id": stt_task_id,
                "status": "processing",
                "progress": 0.5,
                "created_at": now,
                "updated_at": now,
            }
        )

        response = dia_client.get(f"/api/v1/diarizations/{task_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"

    def test_status_has_required_fields(
        self, dia_client: TestClient, mock_dia_redis_client: AsyncMock
    ):
        """상태 응답에 task_id, status, created_at, updated_at 포함"""
        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        mock_dia_redis_client.get.return_value = json.dumps(
            {
                "task_id": task_id,
                "stt_task_id": stt_task_id,
                "status": "pending",
                "progress": 0.0,
                "created_at": now,
                "updated_at": now,
            }
        )

        response = dia_client.get(f"/api/v1/diarizations/{task_id}/status")
        assert response.status_code == 200
        data = response.json()
        for field in ("task_id", "status"):
            assert field in data, f"응답에 '{field}' 필드 누락"

    def test_nonexistent_task_returns_404(
        self, dia_client: TestClient, mock_dia_redis_client: AsyncMock
    ):
        """존재하지 않는 task_id → 404"""
        mock_dia_redis_client.get.return_value = None
        response = dia_client.get(f"/api/v1/diarizations/{uuid.uuid4()}/status")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/diarizations/{task_id} 테스트
# ---------------------------------------------------------------------------


class TestDiarizationResult:
    """GET /api/v1/diarizations/{task_id} - 완료 결과 조회"""

    def test_result_returns_200(
        self,
        dia_client: TestClient,
        mock_dia_redis_client: AsyncMock,
        completed_dia_task_data: dict,
    ):
        """완료 결과 조회 → 200 + 결과 반환"""
        task_id = completed_dia_task_data["task_id"]
        mock_dia_redis_client.get.return_value = json.dumps(completed_dia_task_data)

        response = dia_client.get(f"/api/v1/diarizations/{task_id}")
        assert response.status_code == 200

    def test_result_has_segments_with_speaker_id(
        self,
        dia_client: TestClient,
        mock_dia_redis_client: AsyncMock,
        completed_dia_task_data: dict,
    ):
        """결과에 speaker_id 포함된 세그먼트 반환"""
        task_id = completed_dia_task_data["task_id"]
        mock_dia_redis_client.get.return_value = json.dumps(completed_dia_task_data)

        response = dia_client.get(f"/api/v1/diarizations/{task_id}")
        assert response.status_code == 200
        data = response.json()

        assert "segments" in data
        assert len(data["segments"]) > 0
        segment = data["segments"][0]
        assert "speaker_id" in segment
        assert "speaker_confidence" in segment

    def test_result_has_speakers_info(
        self,
        dia_client: TestClient,
        mock_dia_redis_client: AsyncMock,
        completed_dia_task_data: dict,
    ):
        """결과에 speakers 통계 포함"""
        task_id = completed_dia_task_data["task_id"]
        mock_dia_redis_client.get.return_value = json.dumps(completed_dia_task_data)

        response = dia_client.get(f"/api/v1/diarizations/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert "speakers" in data

    def test_result_nonexistent_returns_404(
        self, dia_client: TestClient, mock_dia_redis_client: AsyncMock
    ):
        """존재하지 않는 task_id → 404"""
        mock_dia_redis_client.get.return_value = None
        response = dia_client.get(f"/api/v1/diarizations/{uuid.uuid4()}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/diarizations/{task_id} 테스트
# ---------------------------------------------------------------------------


class TestDiarizationDelete:
    """DELETE /api/v1/diarizations/{task_id} → 204"""

    def test_delete_returns_204(self, dia_client: TestClient, mock_dia_redis_client: AsyncMock):
        """DELETE → 204 No Content"""
        task_id = str(uuid.uuid4())
        mock_dia_redis_client.delete.return_value = 2

        response = dia_client.delete(f"/api/v1/diarizations/{task_id}")
        assert response.status_code == 204

    def test_delete_clears_redis_cache(
        self, dia_client: TestClient, mock_dia_redis_client: AsyncMock
    ):
        """DELETE 후 Redis 캐시 삭제됨"""
        task_id = str(uuid.uuid4())
        mock_dia_redis_client.delete.return_value = 2

        dia_client.delete(f"/api/v1/diarizations/{task_id}")

        mock_dia_redis_client.delete.assert_called_once()
        delete_call_args = str(mock_dia_redis_client.delete.call_args)
        assert task_id in delete_call_args

    def test_get_after_delete_returns_404(
        self, dia_client: TestClient, mock_dia_redis_client: AsyncMock
    ):
        """삭제 후 조회 시 404"""
        task_id = str(uuid.uuid4())
        mock_dia_redis_client.delete.return_value = 2
        mock_dia_redis_client.get.return_value = None

        dia_client.delete(f"/api/v1/diarizations/{task_id}")
        response = dia_client.get(f"/api/v1/diarizations/{task_id}/status")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/health/diarization 테스트
# ---------------------------------------------------------------------------


class TestDiarizationHealth:
    """GET /api/v1/health/diarization - 화자 분리 모델 상태"""

    def test_health_returns_200(self, dia_client: TestClient):
        """GET /health/diarization → 200"""
        from backend.app.dependencies import get_diarization_engine
        from backend.app.main import app

        mock_engine = MagicMock()
        mock_engine.model_name = "pyannote/speaker-diarization-3.1"
        mock_engine.is_loaded = True
        mock_engine.load_time_seconds = 5.0

        app.dependency_overrides[get_diarization_engine] = lambda: mock_engine

        try:
            response = dia_client.get("/api/v1/health/diarization")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_diarization_engine, None)

    def test_health_has_model_info(self, dia_client: TestClient):
        """헬스 응답에 model_name, model_loaded 포함"""
        from backend.app.dependencies import get_diarization_engine
        from backend.app.main import app

        mock_engine = MagicMock()
        mock_engine.model_name = "pyannote/speaker-diarization-3.1"
        mock_engine.is_loaded = True
        mock_engine.load_time_seconds = 5.0

        app.dependency_overrides[get_diarization_engine] = lambda: mock_engine

        try:
            response = dia_client.get("/api/v1/health/diarization")
            assert response.status_code == 200
            data = response.json()
            assert "model_loaded" in data
            assert "model_name" in data
        finally:
            app.dependency_overrides.pop(get_diarization_engine, None)
