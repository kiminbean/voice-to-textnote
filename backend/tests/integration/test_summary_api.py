"""
요약 API 통합 테스트 (RED phase)
REQ-SUM-006: POST /api/v1/summaries → 202 Accepted
REQ-SUM-008: 최대 2개 동시 작업 한도 → 429
REQ-SUM-012: GET /api/v1/summaries/{task_id}/status
REQ-SUM-013: GET /api/v1/summaries/{task_id} 전체 결과
REQ-SUM-015: DELETE /api/v1/summaries/{task_id} → 204
REQ-SUM-016: 존재하지 않는 task_id → 404
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 테스트용 완료된 요약 데이터
# ---------------------------------------------------------------------------

COMPLETED_SUMMARY_RESULT = {
    "task_id": str(uuid.uuid4()),
    "minutes_task_id": str(uuid.uuid4()),
    "status": "completed",
    "summary_text": "오늘 회의에서 주요 안건을 논의했습니다.",
    "action_items": [
        {
            "assignee": "Speaker 1",
            "task": "보고서 작성",
            "deadline": "2025-01-15",
            "priority": "high",
        }
    ],
    "key_decisions": ["안건 1번 승인"],
    "next_steps": ["다음 주 후속 미팅"],
    "tokens_used": None,
    "generation_time_seconds": 3.14,
    "created_at": datetime.now(UTC).isoformat(),
    "completed_at": datetime.now(UTC).isoformat(),
}


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sum_redis_client():
    """Redis 비동기 클라이언트 mock (요약 API 전용)"""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.ping.return_value = True
    redis_mock.scard.return_value = 0
    return redis_mock


@pytest.fixture
def sum_client(mock_sum_redis_client, tmp_path):
    """
    요약 API TestClient
    - Redis mock
    - Celery mock
    - 모델 로드 mock
    """
    from backend.app.config import Settings
    from backend.app.dependencies import get_redis_client
    from backend.app.main import app

    # 테스트용 Settings mock
    test_settings = MagicMock(spec=Settings)
    test_settings.max_concurrent_summaries = 2
    test_settings.summary_result_ttl = 86400
    test_settings.max_concurrent_minutes = 3
    test_settings.minutes_result_ttl = 86400
    test_settings.max_concurrent_diarizations = 2
    test_settings.diarization_result_ttl = 86400
    test_settings.temp_dir = tmp_path / "temp"
    test_settings.results_dir = tmp_path / "results"
    test_settings.huggingface_token = "hf_testtoken"
    test_settings.diarization_model = "pyannote/speaker-diarization-3.1"
    test_settings.anthropic_api_key = "sk-test-key"
    test_settings.summary_model = "claude-sonnet-4-20250514"
    test_settings.summary_max_tokens = 2000
    test_settings.temp_dir.mkdir(parents=True, exist_ok=True)
    test_settings.results_dir.mkdir(parents=True, exist_ok=True)

    async def override_redis():
        return mock_sum_redis_client

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

            with patch("backend.app.api.v1.summary.settings", test_settings):
                with patch("backend.workers.tasks.summary_task.summary_celery_task") as mock_celery:
                    mock_task_result = MagicMock()
                    mock_task_result.id = "mock-summary-task-id"
                    mock_celery.delay.return_value = mock_task_result

                    yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/summaries 테스트 (REQ-SUM-006)
# ---------------------------------------------------------------------------


class TestPostSummaries:
    """POST /api/v1/summaries - 요약 생성 요청"""

    def test_create_summary_returns_202(self, sum_client):
        """정상 요청 → 202 Accepted"""
        response = sum_client.post(
            "/api/v1/summaries",
            json={"minutes_task_id": str(uuid.uuid4())},
        )
        assert response.status_code == 202

    def test_create_summary_returns_task_id(self, sum_client):
        """202 응답에 task_id 포함"""
        response = sum_client.post(
            "/api/v1/summaries",
            json={"minutes_task_id": str(uuid.uuid4())},
        )
        data = response.json()
        assert "task_id" in data

    def test_create_summary_returns_status_url(self, sum_client):
        """202 응답에 status_url 포함"""
        response = sum_client.post(
            "/api/v1/summaries",
            json={"minutes_task_id": str(uuid.uuid4())},
        )
        data = response.json()
        assert "status_url" in data

    def test_create_summary_with_max_tokens(self, sum_client):
        """max_tokens 커스텀 값으로 요청 수락"""
        response = sum_client.post(
            "/api/v1/summaries",
            json={
                "minutes_task_id": str(uuid.uuid4()),
                "max_tokens": 1000,
            },
        )
        assert response.status_code == 202

    def test_create_summary_missing_minutes_task_id_returns_422(self, sum_client):
        """minutes_task_id 없으면 422 Unprocessable Entity"""
        response = sum_client.post("/api/v1/summaries", json={})
        assert response.status_code == 422

    def test_create_summary_429_when_limit_exceeded(self, mock_sum_redis_client, tmp_path):
        """동시 작업 한도 초과 → 429 Too Many Requests (REQ-SUM-008)"""
        from backend.app.config import Settings
        from backend.app.dependencies import get_redis_client
        from backend.app.main import app

        # 이미 2개 활성 작업
        mock_sum_redis_client.scard.return_value = 2

        test_settings = MagicMock(spec=Settings)
        test_settings.max_concurrent_summaries = 2
        test_settings.summary_result_ttl = 86400

        async def override_redis():
            return mock_sum_redis_client

        app.dependency_overrides[get_redis_client] = override_redis

        with patch("backend.app.main.WhisperEngine") as mock_whisper_cls:
            mock_whisper_inst = MagicMock()
            mock_whisper_inst.is_loaded = True
            mock_whisper_cls.get_instance.return_value = mock_whisper_inst

            with patch("backend.app.main.DiarizationEngine") as mock_dia_cls:
                mock_dia_inst = MagicMock()
                mock_dia_inst.is_loaded = True
                mock_dia_cls.get_instance.return_value = mock_dia_inst

                with patch("backend.app.api.v1.summary.settings", test_settings):
                    client = TestClient(app, raise_server_exceptions=True)
                    response = client.post(
                        "/api/v1/summaries",
                        json={"minutes_task_id": str(uuid.uuid4())},
                    )

        app.dependency_overrides.clear()
        assert response.status_code == 429


# ---------------------------------------------------------------------------
# GET /api/v1/summaries/{task_id}/status 테스트 (REQ-SUM-012)
# ---------------------------------------------------------------------------


class TestGetSummaryStatus:
    """GET /api/v1/summaries/{task_id}/status - 상태 조회"""

    def test_get_status_returns_200(self, sum_client, mock_sum_redis_client):
        """존재하는 작업 상태 조회 → 200"""
        task_id = str(uuid.uuid4())
        status_data = {
            "task_id": task_id,
            "status": "processing",
            "progress": 0.5,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        mock_sum_redis_client.get.return_value = json.dumps(status_data)

        response = sum_client.get(f"/api/v1/summaries/{task_id}/status")
        assert response.status_code == 200

    def test_get_status_returns_correct_fields(self, sum_client, mock_sum_redis_client):
        """상태 응답에 task_id, status, progress 포함"""
        task_id = str(uuid.uuid4())
        status_data = {
            "task_id": task_id,
            "status": "processing",
            "progress": 0.5,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        mock_sum_redis_client.get.return_value = json.dumps(status_data)

        response = sum_client.get(f"/api/v1/summaries/{task_id}/status")
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "processing"
        assert data["progress"] == 0.5

    def test_get_status_404_for_nonexistent_task(self, sum_client, mock_sum_redis_client):
        """존재하지 않는 task_id → 404 (REQ-SUM-016)"""
        mock_sum_redis_client.get.return_value = None

        response = sum_client.get(f"/api/v1/summaries/{uuid.uuid4()}/status")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/summaries/{task_id} 테스트 (REQ-SUM-013)
# ---------------------------------------------------------------------------


class TestGetSummaryResult:
    """GET /api/v1/summaries/{task_id} - 전체 결과 조회"""

    def test_get_result_completed_returns_200(self, sum_client, mock_sum_redis_client):
        """완료된 작업 결과 조회 → 200"""
        task_id = str(uuid.uuid4())
        result_data = {**COMPLETED_SUMMARY_RESULT, "task_id": task_id}
        mock_sum_redis_client.get.return_value = json.dumps(result_data)

        response = sum_client.get(f"/api/v1/summaries/{task_id}")
        assert response.status_code == 200

    def test_get_result_has_summary_fields(self, sum_client, mock_sum_redis_client):
        """결과에 summary_text, action_items, key_decisions, next_steps 포함"""
        task_id = str(uuid.uuid4())
        result_data = {**COMPLETED_SUMMARY_RESULT, "task_id": task_id}
        mock_sum_redis_client.get.return_value = json.dumps(result_data)

        response = sum_client.get(f"/api/v1/summaries/{task_id}")
        data = response.json()
        assert "summary_text" in data
        assert "action_items" in data
        assert "key_decisions" in data
        assert "next_steps" in data

    def test_get_result_404_when_no_result_and_no_status(self, sum_client, mock_sum_redis_client):
        """결과도 없고 상태도 없으면 → 404 (REQ-SUM-016)"""
        mock_sum_redis_client.get.return_value = None

        response = sum_client.get(f"/api/v1/summaries/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_get_result_pending_status_when_no_result_but_status_exists(
        self, sum_client, mock_sum_redis_client
    ):
        """결과는 없지만 상태 존재 → 200 with pending status"""
        task_id = str(uuid.uuid4())
        status_data = {
            "task_id": task_id,
            "minutes_task_id": str(uuid.uuid4()),
            "status": "pending",
            "progress": 0.0,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        call_count = [0]

        async def side_effect(key):
            call_count[0] += 1
            if "result" in key:
                return None
            if "status" in key:
                return json.dumps(status_data)
            return None

        mock_sum_redis_client.get.side_effect = side_effect

        response = sum_client.get(f"/api/v1/summaries/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"


# ---------------------------------------------------------------------------
# DELETE /api/v1/summaries/{task_id} 테스트 (REQ-SUM-015)
# ---------------------------------------------------------------------------


class TestDeleteSummary:
    """DELETE /api/v1/summaries/{task_id} - 요약 삭제"""

    def test_delete_returns_204(self, sum_client, mock_sum_redis_client):
        """삭제 요청 → 204 No Content"""
        task_id = str(uuid.uuid4())
        response = sum_client.delete(f"/api/v1/summaries/{task_id}")
        assert response.status_code == 204

    def test_delete_removes_from_redis(self, sum_client, mock_sum_redis_client):
        """삭제 후 Redis에서 키 제거"""
        task_id = str(uuid.uuid4())
        sum_client.delete(f"/api/v1/summaries/{task_id}")
        assert mock_sum_redis_client.delete.called
