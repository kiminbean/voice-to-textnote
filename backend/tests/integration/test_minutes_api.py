"""
회의록 API 통합 테스트 (RED phase)
REQ-MIN-006, REQ-MIN-011~015: REST API 엔드포인트 검증
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 테스트용 완료된 회의록 데이터
# ---------------------------------------------------------------------------

COMPLETED_MINUTES_RESULT = {
    "task_id": str(uuid.uuid4()),
    "diarization_task_id": str(uuid.uuid4()),
    "status": "completed",
    "segments": [
        {
            "speaker_id": "SPEAKER_00",
            "speaker_name": "Speaker 1",
            "text": "안녕하세요.",
            "start": 0.0,
            "end": 5.0,
        },
        {
            "speaker_id": "SPEAKER_01",
            "speaker_name": "Speaker 2",
            "text": "반갑습니다.",
            "start": 5.0,
            "end": 10.0,
        },
    ],
    "speakers": [
        {
            "speaker_id": "SPEAKER_00",
            "speaker_name": "Speaker 1",
            "total_speaking_time": 5.0,
            "segment_count": 1,
            "speaking_ratio": 50.0,
        },
        {
            "speaker_id": "SPEAKER_01",
            "speaker_name": "Speaker 2",
            "total_speaking_time": 5.0,
            "segment_count": 1,
            "speaking_ratio": 50.0,
        },
    ],
    "total_duration": 10.0,
    "total_speakers": 2,
    "markdown": None,
    "created_at": datetime.now(UTC).isoformat(),
    "completed_at": datetime.now(UTC).isoformat(),
}


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_min_redis_client():
    """Redis 비동기 클라이언트 mock (회의록 API 전용)"""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.ping.return_value = True
    redis_mock.scard.return_value = 0
    return redis_mock


@pytest.fixture
def min_client(mock_min_redis_client, tmp_path):
    """
    회의록 API TestClient
    - Redis mock
    - Celery mock
    - 모델 로드 mock
    """
    from backend.app.config import Settings
    from backend.app.dependencies import get_redis_client
    from backend.app.main import app
    from backend.app.middleware.auth import verify_api_key

    # 테스트용 Settings mock
    test_settings = MagicMock(spec=Settings)
    test_settings.max_concurrent_minutes = 3
    test_settings.minutes_result_ttl = 86400
    test_settings.max_concurrent_diarizations = 2
    test_settings.diarization_result_ttl = 86400
    test_settings.temp_dir = tmp_path / "temp"
    test_settings.results_dir = tmp_path / "results"
    test_settings.huggingface_token = "hf_testtoken"
    test_settings.diarization_model = "pyannote/speaker-diarization-3.1"
    test_settings.temp_dir.mkdir(parents=True, exist_ok=True)
    test_settings.results_dir.mkdir(parents=True, exist_ok=True)

    async def override_redis():
        return mock_min_redis_client

    app.dependency_overrides[get_redis_client] = override_redis

    async def override_verify_api_key():
        return "test-bypass"

    app.dependency_overrides[verify_api_key] = override_verify_api_key

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

            with patch("backend.app.api.v1.minutes.settings", test_settings):
                with patch("backend.workers.tasks.minutes_task.minutes_celery_task") as mock_celery:
                    mock_task_result = MagicMock()
                    mock_task_result.id = "mock-minutes-task-id"
                    mock_celery.delay.return_value = mock_task_result

                    yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/minutes 테스트 (REQ-MIN-006)
# ---------------------------------------------------------------------------


class TestPostMinutes:
    """POST /api/v1/minutes - 회의록 생성 요청"""

    def test_create_minutes_returns_202(self, min_client):
        """정상 요청 → 202 Accepted"""
        response = min_client.post(
            "/api/v1/minutes",
            json={"diarization_task_id": str(uuid.uuid4())},
        )
        assert response.status_code == 202

    def test_create_minutes_returns_task_id(self, min_client):
        """202 응답에 task_id 포함"""
        response = min_client.post(
            "/api/v1/minutes",
            json={"diarization_task_id": str(uuid.uuid4())},
        )
        data = response.json()
        assert "task_id" in data

    def test_create_minutes_returns_status_url(self, min_client):
        """202 응답에 status_url 포함"""
        response = min_client.post(
            "/api/v1/minutes",
            json={"diarization_task_id": str(uuid.uuid4())},
        )
        data = response.json()
        assert "status_url" in data

    def test_create_minutes_with_markdown_format(self, min_client):
        """output_format=markdown 요청 수락"""
        response = min_client.post(
            "/api/v1/minutes",
            json={
                "diarization_task_id": str(uuid.uuid4()),
                "output_format": "markdown",
            },
        )
        assert response.status_code == 202

    def test_create_minutes_with_speaker_names(self, min_client):
        """speaker_names 포함 요청 수락"""
        response = min_client.post(
            "/api/v1/minutes",
            json={
                "diarization_task_id": str(uuid.uuid4()),
                "speaker_names": {"SPEAKER_00": "김팀장"},
            },
        )
        assert response.status_code == 202

    def test_create_minutes_429_when_limit_exceeded(self, mock_min_redis_client, tmp_path):
        """동시 작업 한도 초과 → 429 Too Many Requests (REQ-MIN-008)"""
        from backend.app.config import Settings
        from backend.app.dependencies import get_redis_client
        from backend.app.main import app
        from backend.app.middleware.auth import verify_api_key

        # 이미 3개 활성 작업
        mock_min_redis_client.scard.return_value = 3

        test_settings = MagicMock(spec=Settings)
        test_settings.max_concurrent_minutes = 3
        test_settings.minutes_result_ttl = 86400

        async def override_redis():
            return mock_min_redis_client

        app.dependency_overrides[get_redis_client] = override_redis

        async def override_verify_api_key():
            return "test-bypass"

        app.dependency_overrides[verify_api_key] = override_verify_api_key

        with patch("backend.app.main.WhisperEngine") as mock_whisper_cls:
            mock_whisper_inst = MagicMock()
            mock_whisper_inst.is_loaded = True
            mock_whisper_cls.get_instance.return_value = mock_whisper_inst

            with patch("backend.app.main.DiarizationEngine") as mock_dia_cls:
                mock_dia_inst = MagicMock()
                mock_dia_inst.is_loaded = True
                mock_dia_cls.get_instance.return_value = mock_dia_inst

                with patch("backend.app.api.v1.minutes.settings", test_settings):
                    client = TestClient(app, raise_server_exceptions=True)
                    response = client.post(
                        "/api/v1/minutes",
                        json={"diarization_task_id": str(uuid.uuid4())},
                    )

        app.dependency_overrides.clear()
        assert response.status_code == 429

    def test_create_minutes_missing_diarization_task_id_returns_422(self, min_client):
        """diarization_task_id 없으면 422 Unprocessable Entity"""
        response = min_client.post("/api/v1/minutes", json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/minutes/{task_id}/status 테스트 (REQ-MIN-011)
# ---------------------------------------------------------------------------


class TestGetMinutesStatus:
    """GET /api/v1/minutes/{task_id}/status - 상태 조회"""

    def test_get_status_returns_200(self, min_client, mock_min_redis_client):
        """존재하는 작업 상태 조회 → 200"""
        task_id = str(uuid.uuid4())
        status_data = {
            "task_id": task_id,
            "status": "processing",
            "progress": 0.5,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        mock_min_redis_client.get.return_value = json.dumps(status_data)

        response = min_client.get(f"/api/v1/minutes/{task_id}/status")
        assert response.status_code == 200

    def test_get_status_returns_task_status_fields(self, min_client, mock_min_redis_client):
        """상태 응답에 task_id, status, progress 포함"""
        task_id = str(uuid.uuid4())
        status_data = {
            "task_id": task_id,
            "status": "processing",
            "progress": 0.5,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        mock_min_redis_client.get.return_value = json.dumps(status_data)

        response = min_client.get(f"/api/v1/minutes/{task_id}/status")
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "processing"
        assert data["progress"] == 0.5

    def test_get_status_404_for_nonexistent_task(self, min_client, mock_min_redis_client):
        """존재하지 않는 task_id → 404 (REQ-MIN-015)"""
        mock_min_redis_client.get.return_value = None

        response = min_client.get(f"/api/v1/minutes/{uuid.uuid4()}/status")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/minutes/{task_id} 테스트 (REQ-MIN-012)
# ---------------------------------------------------------------------------


class TestGetMinutesResult:
    """GET /api/v1/minutes/{task_id} - 전체 결과 조회"""

    def test_get_result_completed_returns_200(self, min_client, mock_min_redis_client):
        """완료된 작업 결과 조회 → 200"""
        task_id = str(uuid.uuid4())
        result_data = {**COMPLETED_MINUTES_RESULT, "task_id": task_id}
        mock_min_redis_client.get.return_value = json.dumps(result_data)

        response = min_client.get(f"/api/v1/minutes/{task_id}")
        assert response.status_code == 200

    def test_get_result_has_segments_and_speakers(self, min_client, mock_min_redis_client):
        """결과에 segments, speakers 포함"""
        task_id = str(uuid.uuid4())
        result_data = {**COMPLETED_MINUTES_RESULT, "task_id": task_id}
        mock_min_redis_client.get.return_value = json.dumps(result_data)

        response = min_client.get(f"/api/v1/minutes/{task_id}")
        data = response.json()
        assert "segments" in data
        assert "speakers" in data

    def test_get_result_404_when_no_result_and_no_status(self, min_client, mock_min_redis_client):
        """결과도 없고 상태도 없으면 → 404 (REQ-MIN-015)"""
        mock_min_redis_client.get.return_value = None

        response = min_client.get(f"/api/v1/minutes/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_get_result_pending_status_when_no_result_but_status_exists(
        self, min_client, mock_min_redis_client
    ):
        """결과는 없지만 상태 존재 → 200 with pending status"""
        task_id = str(uuid.uuid4())
        status_data = {
            "task_id": task_id,
            "diarization_task_id": str(uuid.uuid4()),
            "status": "pending",
            "progress": 0.0,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        # 결과 조회 없음, 상태 조회 있음
        call_count = [0]

        async def side_effect(key):
            call_count[0] += 1
            if "result" in key:
                return None
            if "status" in key:
                return json.dumps(status_data)
            return None

        mock_min_redis_client.get.side_effect = side_effect

        response = min_client.get(f"/api/v1/minutes/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"


# ---------------------------------------------------------------------------
# DELETE /api/v1/minutes/{task_id} 테스트 (REQ-MIN-014)
# ---------------------------------------------------------------------------


class TestDeleteMinutes:
    """DELETE /api/v1/minutes/{task_id} - 회의록 삭제"""

    def test_delete_returns_204(self, min_client, mock_min_redis_client):
        """삭제 요청 → 204 No Content"""
        task_id = str(uuid.uuid4())
        response = min_client.delete(f"/api/v1/minutes/{task_id}")
        assert response.status_code == 204

    def test_delete_removes_from_redis(self, min_client, mock_min_redis_client):
        """삭제 후 Redis에서 키 제거"""
        task_id = str(uuid.uuid4())
        min_client.delete(f"/api/v1/minutes/{task_id}")
        assert mock_min_redis_client.delete.called
