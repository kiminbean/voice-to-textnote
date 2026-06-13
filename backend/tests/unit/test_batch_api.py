"""
배치 전사 API 단위 테스트

대상: app/api/v1/batch.py
  - POST /api/v1/transcriptions/batch (upload_batch_transcription)
  - GET  /api/v1/transcriptions/batch/{batch_id} (get_batch_status)
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_redis_client
from backend.app.error_handlers import register_exception_handlers

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
def app_client(tmp_path):
    """배치 라우터만 포함한 테스트 앱 + Redis mock."""
    from backend.app.api.v1.transcription.batch import router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    redis_mock = AsyncMock()
    redis_mock.setex = AsyncMock()

    async def override_redis():
        return redis_mock

    app.dependency_overrides[get_redis_client] = override_redis

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, redis_mock, tmp_path

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /batch — upload_batch_transcription
# ---------------------------------------------------------------------------


class TestUploadBatch:
    """다중 오디오 파일 일괄 업로드."""

    def test_no_files_returns_422(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/v1/transcriptions/batch", files=[])
        assert resp.status_code == 422

    def test_too_many_files_returns_422(self, app_client):
        """최대 10개 초과 시 422."""
        client, _, _ = app_client
        files = [("files", (f"test{i}.wav", b"data", "audio/wav")) for i in range(11)]
        resp = client.post("/api/v1/transcriptions/batch", files=files)
        assert resp.status_code == 422

    def test_single_valid_file(self, app_client):
        """정상 파일 1개 → 201 + accepted=1."""
        client, _redis_mock, tmp_path = app_client

        with (
            patch(
                "backend.app.api.v1.transcription.batch.validate_audio_format",
                return_value=(True, ""),
            ),
            patch(
                "backend.app.api.v1.transcription.batch.validate_file_size", return_value=(True, "")
            ),
            patch(
                "backend.app.api.v1.transcription.batch.get_audio_duration_seconds",
                return_value=60.0,
            ),
            patch("backend.app.api.v1.transcription.batch.settings") as mock_settings,
            patch("backend.workers.tasks.transcription_task.transcription_task") as mock_task,
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.cache_ttl_seconds = 86400
            mock_settings.max_file_size_bytes = 500 * 1024 * 1024
            mock_settings.max_duration_seconds = 4 * 3600
            mock_task.delay = MagicMock()

            resp = client.post(
                "/api/v1/transcriptions/batch",
                files=[("files", ("meeting.wav", b"fake-audio", "audio/wav"))],
                data={"language": "ko"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["total"] == 1
        assert body["accepted"] == 1
        assert body["batch_id"] is not None
        assert len(body["items"]) == 1
        assert body["items"][0]["status"] == "pending"

    def test_invalid_format_file_accepted_as_failed(self, app_client):
        """포맷 검증 실패 파일은 failed로 기록, 나머지는 계속."""
        client, _redis_mock, tmp_path = app_client

        with (
            patch("backend.app.api.v1.transcription.batch.validate_audio_format") as mock_validate,
            patch(
                "backend.app.api.v1.transcription.batch.validate_file_size", return_value=(True, "")
            ),
            patch(
                "backend.app.api.v1.transcription.batch.get_audio_duration_seconds",
                return_value=60.0,
            ),
            patch("backend.app.api.v1.transcription.batch.settings") as mock_settings,
            patch("backend.workers.tasks.transcription_task.transcription_task") as mock_task,
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.cache_ttl_seconds = 86400
            mock_settings.max_file_size_bytes = 500 * 1024 * 1024
            mock_settings.max_duration_seconds = 4 * 3600
            mock_task.delay = MagicMock()

            # 첫 번째 파일: 실패, 두 번째 파일: 성공
            mock_validate.side_effect = [(False, "지원하지 않는 포맷"), (True, "")]

            resp = client.post(
                "/api/v1/transcriptions/batch",
                files=[
                    ("files", ("bad.exe", b"data", "application/octet-stream")),
                    ("files", ("good.wav", b"audio-data", "audio/wav")),
                ],
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["total"] == 2
        assert body["accepted"] == 1
        assert body["items"][0]["status"] == "failed"
        assert body["items"][1]["status"] == "pending"

    def test_file_too_large_marked_failed(self, app_client):
        """파일 크기 초과 → failed."""
        client, _redis_mock, tmp_path = app_client

        with (
            patch(
                "backend.app.api.v1.transcription.batch.validate_audio_format",
                return_value=(True, ""),
            ),
            patch(
                "backend.app.api.v1.transcription.batch.validate_file_size",
                return_value=(False, "파일 크기 초과"),
            ),
            patch("backend.app.api.v1.transcription.batch.settings") as mock_settings,
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.cache_ttl_seconds = 86400

            resp = client.post(
                "/api/v1/transcriptions/batch",
                files=[("files", ("big.wav", b"x" * 100, "audio/wav"))],
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["accepted"] == 0
        assert body["items"][0]["status"] == "failed"

    def test_duration_exceeds_limit_marked_failed(self, app_client):
        """재생 시간 초과 → failed."""
        client, _redis_mock, tmp_path = app_client

        with (
            patch(
                "backend.app.api.v1.transcription.batch.validate_audio_format",
                return_value=(True, ""),
            ),
            patch(
                "backend.app.api.v1.transcription.batch.validate_file_size", return_value=(True, "")
            ),
            patch(
                "backend.app.api.v1.transcription.batch.get_audio_duration_seconds",
                return_value=99999.0,
            ),
            patch("backend.app.api.v1.transcription.batch.settings") as mock_settings,
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.cache_ttl_seconds = 86400
            mock_settings.max_file_size_bytes = 500 * 1024 * 1024
            mock_settings.max_duration_seconds = 14400  # 4h
            mock_settings.max_duration_hours = 4

            resp = client.post(
                "/api/v1/transcriptions/batch",
                files=[("files", ("long.wav", b"audio", "audio/wav"))],
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["items"][0]["status"] == "failed"
        assert "재생 시간" in body["items"][0]["error"]

    def test_audio_read_error_marked_failed(self, app_client):
        """오디오 읽기 실패 → failed."""
        client, _redis_mock, tmp_path = app_client

        with (
            patch(
                "backend.app.api.v1.transcription.batch.validate_audio_format",
                return_value=(True, ""),
            ),
            patch(
                "backend.app.api.v1.transcription.batch.validate_file_size", return_value=(True, "")
            ),
            patch(
                "backend.app.api.v1.transcription.batch.get_audio_duration_seconds",
                side_effect=Exception("corrupt"),
            ),
            patch("backend.app.api.v1.transcription.batch.settings") as mock_settings,
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.cache_ttl_seconds = 86400
            mock_settings.max_file_size_bytes = 500 * 1024 * 1024
            mock_settings.max_duration_seconds = 14400

            resp = client.post(
                "/api/v1/transcriptions/batch",
                files=[("files", ("broken.wav", b"data", "audio/wav"))],
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["items"][0]["status"] == "failed"


# ---------------------------------------------------------------------------
# GET /batch/{batch_id} — get_batch_status
# ---------------------------------------------------------------------------


class TestGetBatchStatus:
    """배치 처리 상태 일괄 조회."""

    def test_invalid_batch_id_returns_422(self, app_client):
        client, _, _ = app_client
        resp = client.get("/api/v1/transcriptions/batch/not-a-uuid")
        assert resp.status_code == 422

    def test_nonexistent_batch_returns_404(self, app_client):
        client, redis_mock, _ = app_client
        redis_mock.get.return_value = None
        batch_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/transcriptions/batch/{batch_id}")
        assert resp.status_code == 404

    def test_existing_batch_returns_status(self, app_client):
        client, redis_mock, _ = app_client

        task_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        batch_data = {
            "batch_id": batch_id,
            "task_ids": [task_id],
            "created_at": "2026-01-01T00:00:00",
        }

        task_status = {
            "status": "completed",
            "original_filename": "meeting.wav",
        }

        async def _redis_get(key):
            if f"batch:{batch_id}" == key:
                return json.dumps(batch_data)
            if f"task:status:{task_id}" == key:
                return json.dumps(task_status)
            return None

        redis_mock.get.side_effect = _redis_get

        # pipeline mock — MagicMock으로 sync 반환 (AsyncMock은 coroutine 반환)
        pipe_mock = MagicMock()
        pipe_mock.get.return_value = pipe_mock  # fluent API
        pipe_mock.execute = AsyncMock(return_value=[json.dumps(task_status)])
        redis_mock.pipeline = MagicMock(return_value=pipe_mock)

        resp = client.get(f"/api/v1/transcriptions/batch/{batch_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["completed"] == 1
        assert body["items"][0]["status"] == "completed"

    def test_batch_with_missing_task_status(self, app_client):
        """task status가 Redis에 없으면 failed 처리."""
        client, redis_mock, _ = app_client

        task_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        batch_data = {
            "batch_id": batch_id,
            "task_ids": [task_id],
            "created_at": "2026-01-01T00:00:00",
        }

        redis_mock.get.side_effect = lambda key: (
            json.dumps(batch_data) if f"batch:{batch_id}" == key else None
        )

        pipe_mock = MagicMock()
        pipe_mock.get.return_value = pipe_mock
        pipe_mock.execute = AsyncMock(return_value=[None])  # task status 없음
        redis_mock.pipeline = MagicMock(return_value=pipe_mock)

        resp = client.get(f"/api/v1/transcriptions/batch/{batch_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["failed"] == 1

    def test_invalid_task_status_falls_back_to_failed(self, app_client):
        """TaskStatus에 없는 문자열이면 failed로 폴백한다."""
        import json

        client, redis_mock, _ = app_client
        batch_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())

        batch_data = {
            "task_ids": [task_id],
            "created_at": "2026-01-01T00:00:00",
        }

        redis_mock.get.side_effect = lambda key: (
            json.dumps(batch_data)
            if f"batch:{batch_id}" == key
            else json.dumps({"status": "INVALID_STATUS", "original_filename": "test.wav"})
        )

        pipe_mock = MagicMock()
        pipe_mock.get.return_value = pipe_mock
        pipe_mock.execute = AsyncMock(
            return_value=[json.dumps({"status": "INVALID_STATUS", "original_filename": "test.wav"})]
        )
        redis_mock.pipeline = MagicMock(return_value=pipe_mock)

        resp = client.get(f"/api/v1/transcriptions/batch/{batch_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["failed"] == 1
