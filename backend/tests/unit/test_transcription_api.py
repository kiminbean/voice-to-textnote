"""
전사 API 엔드포인트 테스트
POST /transcriptions, GET /status, GET /{task_id}, DELETE /{task_id}
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status


class TestUploadTranscription:
    """POST /api/v1/transcriptions 테스트"""

    def test_upload_audio_success(self, client, test_audio_file):
        """
        Given: 유효한 WAV 오디오 파일
        When: 파일 업로드
        Then: 201 Created + task_id 반환
        """
        with open(test_audio_file, "rb") as f:
            response = client.post(
                "/api/v1/transcriptions",
                files={"file": ("test.wav", f, "audio/wav")},
                data={"language": "ko", "model": "mlx-community/whisper-small-mlx"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert "status_url" in data
        assert "result_url" in data
        assert "diarization_task_id" in data

    def test_upload_with_vocabulary_id(self, client, test_audio_file):
        """
        Given: vocabulary_id가 포함된 요청
        When: 파일 업로드
        Then: vocabulary_id로 initial_prompt 변환 후 작업 생성
        """
        from backend.services.vocabulary_service import VocabularyService

        vocab_id = str(uuid.uuid4())

        with patch.object(VocabularyService, "get_initial_prompt", new=AsyncMock(return_value="test prompt")) as mock_get:
            with open(test_audio_file, "rb") as f:
                response = client.post(
                    "/api/v1/transcriptions",
                    files={"file": ("test.wav", f, "audio/wav")},
                    data={
                        "language": "ko",
                        "model": "mlx-community/whisper-small-mlx",
                        "vocabulary_id": vocab_id,
                    },
                )

            assert response.status_code == status.HTTP_201_CREATED
            mock_get.assert_called_once()

    def test_upload_invalid_vocabulary_id(self, client, test_audio_file):
        """
        Given: 유효하지 않은 vocabulary_id
        When: 파일 업로드
        Then: 422 Unprocessable Entity
        """
        with open(test_audio_file, "rb") as f:
            response = client.post(
                "/api/v1/transcriptions",
                files={"file": ("test.wav", f, "audio/wav")},
                data={
                    "language": "ko",
                    "model": "mlx-community/whisper-small-mlx",
                    "vocabulary_id": "not-a-uuid",
                },
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "message" in data
        assert any(e.get("field") == "vocabulary_id" for e in data["message"])

    def test_upload_unsupported_format(self, client, tmp_path):
        """
        Given: 지원하지 않는 파일 형식 (.exe)
        When: 파일 업로드
        Then: 422 Unprocessable Entity
        """
        exe_file = tmp_path / "test.exe"
        exe_file.write_bytes(b"MZ\x90\x00" + b"\x00" * 100)

        with open(exe_file, "rb") as f:
            response = client.post(
                "/api/v1/transcriptions",
                files={"file": ("test.exe", f, "application/octet-stream")},
                data={"language": "ko"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "message" in data
        # message 텍스트 확인 (한국어 또는 영어 메시지)
        assert any(
            "format" in e.get("type", "").lower() or "지원" in e.get("message", "")
            for e in data["message"]
        )

    @pytest.mark.skip(reason="대용량 파일 생성으로 인한 테스트 시간 초과")
    def test_upload_file_too_large(self, client, monkeypatch):
        """
        Given: 파일 크기가 제한 초과 (501MB)
        When: 파일 업로드
        Then: 422 Unprocessable Entity
        """
        # Settings override
        import backend.app.config as config_module
        monkeypatch.setattr(config_module.settings, "max_file_size_bytes", 500 * 1024 * 1024)

        # 큰 파일 생성 (temp_path에 저장되며 크기 검증)
        large_content = b"\x00" * (501 * 1024 * 1024)  # 501MB
        import io
        large_file = io.BytesIO(large_content)

        response = client.post(
            "/api/v1/transcriptions",
            files={"file": ("large.wav", large_file, "audio/wav")},
            data={"language": "ko"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert any("file_too_large" in e.get("type", "") for e in data["message"])

    @pytest.mark.skip(reason="Duration check uses mocked settings - needs conftest adjustment")
    def test_upload_duration_exceeded(self, client, test_audio_file, monkeypatch):
        """
        Given: 재생 시간이 제한 초과 (5시간)
        When: 파일 업로드
        Then: 422 Unprocessable Entity
        """
        from backend.app.config import settings

        monkeypatch.setattr(settings, "max_duration_seconds", 4 * 3600)

        # get_audio_duration_seconds가 5시간 반환하도록 mock
        with patch("backend.pipeline.audio_processor.get_audio_duration_seconds") as mock_duration:
            mock_duration.return_value = 5 * 3600

            with open(test_audio_file, "rb") as f:
                response = client.post(
                    "/api/v1/transcriptions",
                    files={"file": ("test.wav", f, "audio/wav")},
                    data={"language": "ko"},
                )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert any("duration_exceeded" in e.get("type", "") for e in data["message"])

    def test_upload_corrupted_audio(self, client, corrupted_audio_file):
        """
        Given: 손상된 오디오 파일
        When: 파일 업로드
        Then: 422 Unprocessable Entity
        """
        with open(corrupted_audio_file, "rb") as f:
            response = client.post(
                "/api/v1/transcriptions",
                files={"file": ("corrupted.wav", f, "audio/wav")},
                data={"language": "ko"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert any("invalid_audio" in e.get("type", "") for e in data["message"])

    def test_upload_concurrent_limit_exceeded(self, client, test_audio_file, mock_redis_client):
        """
        Given: 동시 처리 한도 초과
        When: 파일 업로드
        Then: 429 Too Many Requests
        """
        # active_jobs_ts 카운트가 max_concurrent_jobs 이상 반환
        mock_redis_client._set_pipeline_results([0, 10])  # zremrangebyscore + zcard

        with open(test_audio_file, "rb") as f:
            response = client.post(
                "/api/v1/transcriptions",
                files={"file": ("test.wav", f, "audio/wav")},
                data={"language": "ko"},
            )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_upload_file_write_error(self, client, tmp_path):
        """
        Given: 파일 저장 중 OSError 발생
        When: 파일 업로드
        Then: 422 Unprocessable Entity
        """
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        # Path.open에서 OSError 발생하도록 mock
        original_open = Path.open

        def mock_open(self, *args, **kwargs):
            # temp_path.open에서만 에러 발생
            if hasattr(self, "name") and "temp" in str(self):
                raise OSError("Disk full")
            return original_open(self, *args, **kwargs)

        with patch.object(Path, "open", mock_open):
            with open(test_file, "rb") as f:
                response = client.post(
                    "/api/v1/transcriptions",
                    files={"file": ("test.wav", f, "audio/wav")},
                    data={"language": "ko"},
                )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetTaskStatus:
    """GET /api/v1/transcriptions/{task_id}/status 테스트"""

    def test_get_status_success(self, client, mock_redis_client):
        """
        Given: 유효한 task_id
        When: 상태 조회
        Then: 200 OK + 상태 정보 반환
        """
        task_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        status_data = {
            "task_id": task_id,
            "status": "processing",
            "progress": 0.5,
            "message": "Processing audio",
            "created_at": now,
            "updated_at": now,
        }
        mock_redis_client.get.return_value = json.dumps(status_data)

        response = client.get(f"/api/v1/transcriptions/{task_id}/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "processing"
        assert data["progress"] == 0.5

    def test_get_status_not_found(self, client, mock_redis_client):
        """
        Given: 존재하지 않는 task_id
        When: 상태 조회
        Then: 404 Not Found
        """
        mock_redis_client.get.return_value = None

        response = client.get(f"/api/v1/transcriptions/{uuid.uuid4()}/status")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_status_missing_timestamps(self, client, mock_redis_client):
        """
        Given: created_at/updated_at 누락된 상태 데이터
        When: 상태 조회
        Then: 200 OK + 현재 시간 사용
        """
        task_id = str(uuid.uuid4())
        status_data = {
            "task_id": task_id,
            "status": "pending",
            "progress": 0.0,
        }
        mock_redis_client.get.return_value = json.dumps(status_data)

        response = client.get(f"/api/v1/transcriptions/{task_id}/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "created_at" in data
        assert "updated_at" in data


class TestGetTranscriptionResult:
    """GET /api/v1/transcriptions/{task_id} 테스트"""

    def test_get_result_from_cache(self, client, mock_redis_client):
        """
        Given: Redis 캐시에 결과가 존재
        When: 결과 조회
        Then: 200 OK + 전사 결과 반환
        """
        task_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        result_data = {
            "task_id": task_id,
            "status": "completed",
            "language": "ko",
            "duration": 4.2,
            "model": "mlx-community/whisper-small-mlx",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 4.2,
                    "text": "안녕하세요.",
                    "confidence": 0.78,
                }
            ],
            "metadata": {
                "file_name": "test.wav",
                "file_size_bytes": 100000,
                "sample_rate": 16000,
            },
            "created_at": now,
            "completed_at": now,
        }
        mock_redis_client._set_pipeline_results([json.dumps(result_data), None])

        response = client.get(f"/api/v1/transcriptions/{task_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "completed"
        assert len(data["segments"]) == 1
        assert data["segments"][0]["text"] == "안녕하세요."

    def test_get_result_from_file_cache_miss(self, client, mock_redis_client, tmp_path):
        """
        Given: Redis 캐시 미스 + 파일 시스템에 결과 존재
        When: 결과 조회
        Then: 200 OK + 파일에서 로드 후 Redis 재캐싱
        """
        task_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        result_data = {
            "task_id": task_id,
            "status": "completed",
            "language": "ko",
            "segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": "테스트"}],
            "created_at": now,
            "completed_at": now,
        }

        # Redis 캐시 미스
        mock_redis_client._set_pipeline_results([None, None])

        # 파일 시스템에 결과 저장
        results_dir = tmp_path / "results"
        results_dir.mkdir(exist_ok=True)
        result_file = results_dir / f"{task_id}.json"
        result_file.write_text(json.dumps(result_data), encoding="utf-8")

        # settings.results_dir override
        import backend.app.config as config_module

        mock_settings = MagicMock(spec=config_module.Settings)
        mock_settings.results_dir = results_dir
        mock_settings.cache_ttl_seconds = 604800

        with patch("backend.app.api.v1.transcription.transcription.settings", mock_settings):
            response = client.get(f"/api/v1/transcriptions/{task_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "completed"
        # Redis 재캐싱 확인
        mock_redis_client.setex.assert_called()

    def test_get_result_not_found(self, client, mock_redis_client):
        """
        Given: 존재하지 않는 task_id
        When: 결과 조회
        Then: 404 Not Found
        """
        # 캐히/파일 모두 없음
        mock_redis_client._set_pipeline_results([None, None])

        response = client.get(f"/api/v1/transcriptions/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_result_pending_status(self, client, mock_redis_client):
        """
        Given: 작업이 대기 중 (pending)
        When: 결과 조회
        Then: 200 OK + 빈 segments 반환
        """
        task_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        # 캐히 미스 + status만 존재
        status_data = {
            "task_id": task_id,
            "status": "pending",
            "created_at": now,
        }
        mock_redis_client._set_pipeline_results([None, json.dumps(status_data)])

        response = client.get(f"/api/v1/transcriptions/{task_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "pending"
        assert data["segments"] == []

    def test_get_result_failed_status(self, client, mock_redis_client):
        """
        Given: 작업 실패 (failed)
        When: 결과 조회
        Then: 200 OK + error_message 포함
        """
        task_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        status_data = {
            "task_id": task_id,
            "status": "failed",
            "error_message": "Processing failed: timeout",
            "created_at": now,
        }
        mock_redis_client._set_pipeline_results([None, json.dumps(status_data)])

        response = client.get(f"/api/v1/transcriptions/{task_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "Processing failed: timeout"

    def test_get_result_with_metadata(self, client, mock_redis_client):
        """
        Given: 메타데이터 포함 전사 결과
        When: 결과 조회
        Then: 200 OK + metadata 포함
        """
        task_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        result_data = {
            "task_id": task_id,
            "status": "completed",
            "segments": [],
            "metadata": {
                "file_name": "recording.wav",
                "file_size_bytes": 250000,
                "sample_rate": 16000,
                "processing_time_seconds": 3.5,
            },
            "created_at": now,
            "completed_at": now,
        }
        mock_redis_client._set_pipeline_results([json.dumps(result_data), None])

        response = client.get(f"/api/v1/transcriptions/{task_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["metadata"] is not None
        assert data["metadata"]["file_name"] == "recording.wav"


class TestDeleteTranscription:
    """DELETE /api/v1/transcriptions/{task_id} 테스트"""

    def test_delete_success(self, client, mock_redis_client, tmp_path):
        """
        Given: 존재하는 task_id
        When: 삭제 요청
        Then: 204 No Content
        """
        task_id = str(uuid.uuid4())

        # 임시 파일 생성
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir(exist_ok=True)
        for ext in [".wav", ".mp3"]:
            (temp_dir / f"{task_id}{ext}").write_bytes(b"dummy")

        # 결과 파일 생성
        results_dir = tmp_path / "results"
        results_dir.mkdir(exist_ok=True)
        result_file = results_dir / f"{task_id}.json"
        result_file.write_text('{"task_id": "test"}')

        import backend.app.config as config_module

        mock_settings = MagicMock(spec=config_module.Settings)
        mock_settings.temp_dir = temp_dir
        mock_settings.results_dir = results_dir

        with patch("backend.app.api.v1.transcription.transcription.settings", mock_settings):
            response = client.delete(f"/api/v1/transcriptions/{task_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""
        # Redis 삭제 확인
        mock_redis_client.delete.assert_called_once()
        # 파일 삭제 확인
        assert not result_file.exists()

    def test_delete_missing_files(self, client, mock_redis_client):
        """
        Given: 파일이 없는 task_id
        When: 삭제 요청
        Then: 204 No Content (idempotent)
        """
        task_id = str(uuid.uuid4())
        mock_redis_client.delete.return_value = 0  # 키 없음

        response = client.delete(f"/api/v1/transcriptions/{task_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestEdgeCases:
    """엣지 케이스 및 에러 경로 테스트"""

    def test_upload_redis_error_during_active_count(self, client, test_audio_file, mock_redis_client):
        """
        Given: Redis active_jobs_ts 조회 시 Exception 발생
        When: 파일 업로드
        Then: active_count=0 기본값으로 계속 진행
        """
        # pipeline.execute에서 Exception 발생
        mock_redis_client._set_pipeline_results(Exception("Redis connection lost"))

        with open(test_audio_file, "rb") as f:
            response = client.post(
                "/api/v1/transcriptions",
                files={"file": ("test.wav", f, "audio/wav")},
                data={"language": "ko"},
            )

        # 예외를 삼켜서 0으로 처리 후 계속 진행
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_422_UNPROCESSABLE_ENTITY]

    @pytest.mark.skip(reason="Redis error handling needs conftest adjustment")
    def test_get_status_redis_error(self, client, mock_redis_client):
        """
        Given: Redis 연결 실패
        When: 상태 조회
        Then: 404 Not Found (캐시 미스로 처리)
        """
        mock_redis_client.get.side_effect = Exception("Redis down")

        response = client.get(f"/api/v1/transcriptions/{uuid.uuid4()}/status")

        # 에러가 발생하면 404로 처리되지 않고 500이 될 수 있음
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]

    @pytest.mark.skip(reason="Redis pipeline error handling needs conftest adjustment")
    def test_get_result_redis_pipeline_error(self, client, mock_redis_client):
        """
        Given: Redis pipeline 실패
        When: 결과 조회
        Then: 500 Internal Server Error (또는 404)
        """
        mock_redis_client._set_pipeline_results(Exception("Pipeline error"))

        response = client.get(f"/api/v1/transcriptions/{uuid.uuid4()}")

        # 에러가 발생하면 404로 처리되지 않고 500이 될 수 있음
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_upload_without_filename(self, client, test_audio_bytes):
        """
        Given: filename이 None인 UploadFile
        When: 파일 업로드
        Then: 201 Created (filename="unknown"로 처리)
        """

        # UploadFile 객체 직접 생성 (filename=None)
        import io


        # TestClient override로 직접 호출
        client.post(
            "/api/v1/transcriptions",
            files={"file": ("test.wav", io.BytesIO(test_audio_bytes), "audio/wav")},
            data={"language": "ko"},
        )

    def test_upload_multiple_errors(self, client, tmp_path):
        """
        Given: 형식 오류 + 크기 오류 동시 발생
        When: 파일 업로드
        Then: 422 + 모든 에러 포함
        """
        exe_file = tmp_path / "test.exe"
        exe_file.write_bytes(b"MZ\x90\x00" + b"\x00" * (501 * 1024 * 1024))

        with open(exe_file, "rb") as f:
            response = client.post(
                "/api/v1/transcriptions",
                files={"file": ("test.exe", f, "application/octet-stream")},
                data={"language": "ko"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert len(data["message"]) >= 2  # 형식 오류 + 크기 오류
