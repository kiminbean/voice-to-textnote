"""
회의록 API 엔드포인트 테스트
REQ-MIN-006: POST /api/v1/minutes → 202 Accepted
REQ-MIN-011: GET /api/v1/minutes/{task_id}/status → 상태 조회
REQ-MIN-012: GET /api/v1/minutes/{task_id} → 전체 결과 조회
REQ-MIN-013: Redis 결과 캐싱 24h TTL
REQ-MIN-014: DELETE /api/v1/minutes/{task_id} → 204 No Content
REQ-MIN-015: 존재하지 않는 task_id → 404
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestMinutesAPI:
    """회의록 API 테스트 스위트"""

    @pytest.fixture
    def mock_redis_client(self):
        """Redis 클라이언트 mock"""
        redis = AsyncMock()
        redis.get.return_value = None
        redis.setex.return_value = True
        redis.delete.return_value = 1
        redis.scard.return_value = 0
        return redis

    @pytest.fixture
    def client(self, mock_redis_client):
        """FastAPI TestClient with mocked dependencies"""
        from backend.app.config import settings
        from backend.app.dependencies import get_redis_client
        from backend.app.main import app

        async def override_redis():
            yield mock_redis_client

        app.dependency_overrides[get_redis_client] = override_redis

        with patch.object(settings, 'max_concurrent_minutes', 3):
            yield TestClient(app)

        app.dependency_overrides.clear()

    def test_create_minutes_success(self, client, mock_redis_client):
        """
        회의록 생성 작업 성공 테스트
        Given: 유효한 diarization_task_id
        When: POST /api/v1/minutes
        Then: 202 Accepted와 task_id 반환
        """
        # Given
        request_data = {
            "diarization_task_id": "test-diarization-123",
            "output_format": "markdown",
            "speaker_names": {"SPEAKER_00": "John", "SPEAKER_01": "Jane"},
            "stt_task_id": "stt-123"
        }

        with patch("backend.workers.tasks.minutes_task.minutes_celery_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="celery-task-123")

            # When
            response = client.post("/api/v1/minutes", json=request_data)

            # Then
            assert response.status_code == 202
            data = response.json()
            assert "task_id" in data
            assert data["diarization_task_id"] == "test-diarization-123"
            assert data["status"] == "pending"
            assert "status_url" in data
            assert "result_url" in data

    def test_create_minutes_concurrent_limit_exceeded(self, client, mock_redis_client):
        """
        동시 처리 한도 초과 테스트
        Given: max_concurrent_minutes 한도 도달
        When: POST /api/v1/minutes
        Then: 429 Too Many Requests
        """
        # Given - 동시 작업 수가 한도에 도달
        mock_redis_client.scard.return_value = 3

        request_data = {
            "diarization_task_id": "test-123",
            "output_format": "markdown"
        }

        # When
        response = client.post("/api/v1/minutes", json=request_data)

        # Then
        assert response.status_code == 429
        assert "한도" in response.json()["detail"]

    def test_create_minutes_minimal_request(self, client, mock_redis_client):
        """
        최소 요청으로 회의록 생성 테스트
        Given: diarization_task_id만 제공
        When: POST /api/v1/minutes
        Then: 작업 생성 성공
        """
        # Given
        request_data = {"diarization_task_id": "test-456"}

        with patch("backend.workers.tasks.minutes_task.minutes_celery_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="celery-task-456")

            # When
            response = client.post("/api/v1/minutes", json=request_data)

            # Then
            assert response.status_code == 202
            data = response.json()
            assert "task_id" in data

    def test_get_minutes_status_success(self, client, mock_redis_client):
        """
        회의록 상태 조회 성공 테스트
        Given: 존재하는 task_id와 Redis 상태 데이터
        When: GET /api/v1/minutes/{task_id}/status
        Then: 상태 정보 반환
        """
        # Given
        task_id = "minutes-task-123"
        status_data = {
            "task_id": task_id,
            "status": "processing",
            "progress": 0.6,
            "message": "회의록 생성 중",
            "error_message": None
        }
        mock_redis_client.get.return_value = json.dumps(status_data)

        # When
        response = client.get(f"/api/v1/minutes/{task_id}/status")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "processing"
        assert data["progress"] == 0.6
        assert data["message"] == "회의록 생성 중"

    def test_get_minutes_status_not_found(self, client, mock_redis_client):
        """
        존재하지 않는 task_id 상태 조회 테스트
        Given: 존재하지 않는 task_id
        When: GET /api/v1/minutes/{task_id}/status
        Then: 404 Not Found
        """
        # Given
        mock_redis_client.get.return_value = None

        # When
        response = client.get("/api/v1/minutes/non-existent/status")

        # Then
        assert response.status_code == 404

    def test_get_minutes_result_success(self, client, mock_redis_client):
        """
        회의록 결과 조회 성공 테스트
        Given: 완료된 회의록 결과
        When: GET /api/v1/minutes/{task_id}
        Then: 전체 결과 반환
        """
        # Given
        task_id = "minutes-result-123"
        result_data = {
            "task_id": task_id,
            "status": "completed",
            "diarization_task_id": "diarization-123",
            "segments": [
                {
                    "speaker_id": "SPEAKER_00",
                    "speaker_name": "John",
                    "start": 0.0,
                    "end": 5.0,
                    "text": "안녕하세요"
                }
            ],
            "speakers": [
                {
                    "speaker_id": "SPEAKER_00",
                    "speaker_name": "John",
                    "total_speaking_time": 30.0,
                    "segment_count": 1,
                    "speaking_ratio": 50.0
                }
            ],
            "total_duration": 60.0,
            "total_speakers": 1,
            "markdown": "# 회의록\n\n안녕하세요"
        }
        mock_redis_client.get.return_value = json.dumps(result_data)

        # When
        response = client.get(f"/api/v1/minutes/{task_id}")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "completed"
        assert len(data["segments"]) == 1
        assert len(data["speakers"]) == 1
        assert data["markdown"] is not None

    def test_get_minutes_result_pending(self, client, mock_redis_client):
        """
        진행 중인 회의록 결과 조회 테스트
        Given: 완료되지 않은 작업 (status만 존재)
        When: GET /api/v1/minutes/{task_id}
        Then: 빈 결과 반환
        """
        # Given
        task_id = "minutes-pending-123"
        status_data = {
            "task_id": task_id,
            "status": "processing",
            "diarization_task_id": "diarization-456"
        }

        # Redis get 호출 시 sequence로 status 반환
        mock_redis_client.get.return_value = json.dumps(status_data)

        # When
        response = client.get(f"/api/v1/minutes/{task_id}")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "processing"
        assert data["diarization_task_id"] == "diarization-456"
        assert data["segments"] == []
        assert data["speakers"] == []

    def test_get_minutes_result_not_found(self, client, mock_redis_client):
        """
        존재하지 않는 task_id 결과 조회 테스트
        Given: 존재하지 않는 task_id
        When: GET /api/v1/minutes/{task_id}
        Then: 404 Not Found
        """
        # Given - 두 번의 get 호출에서 모두 None 반환
        mock_redis_client.get.return_value = None

        # When
        response = client.get("/api/v1/minutes/non-existent/result")

        # Then
        assert response.status_code == 404

    def test_delete_minutes_success(self, client, mock_redis_client):
        """
        회의록 작업 삭제 성공 테스트
        Given: 존재하는 task_id
        When: DELETE /api/v1/minutes/{task_id}
        Then: 204 No Content
        """
        # Given
        mock_redis_client.delete.return_value = 2  # status + result key 삭제

        # When
        response = client.delete("/api/v1/minutes/minutes-123")

        # Then
        assert response.status_code == 204
        assert response.content == b""
        # 삭제 호출 확인
        assert mock_redis_client.delete.call_count == 1

    def test_delete_minutes_no_keys(self, client, mock_redis_client):
        """
        존재하지 않는 작업 삭제 테스트
        Given: 존재하지 않는 task_id
        When: DELETE /api/v1/minutes/{task_id}
        Then: 204 No Content (idempotent)
        """
        # Given
        mock_redis_client.delete.return_value = 0

        # When
        response = client.delete("/api/v1/minutes/non-existent")

        # Then
        assert response.status_code == 204
        assert response.content == b""

    def test_create_minutes_invalid_request(self, client, mock_redis_client):
        """
        잘못된 요청으로 회의록 생성 테스트
        Given: diarization_task_id 누락
        When: POST /api/v1/minutes
        Then: 422 Unprocessable Entity
        """
        # Given - 잘못된 데이터
        request_data = {"output_format": "markdown"}  # diarization_task_id 누락

        # When
        response = client.post("/api/v1/minutes", json=request_data)

        # Then
        assert response.status_code == 422

    def test_get_minutes_result_with_error(self, client, mock_redis_client):
        """
        에러가 포함된 회의록 결과 조회 테스트
        Given: 에러 상태의 결과 데이터
        When: GET /api/v1/minutes/{task_id}
        Then: 에러 메시지 포함 반환
        """
        # Given
        task_id = "minutes-error-123"
        result_data = {
            "task_id": task_id,
            "status": "failed",
            "diarization_task_id": "diarization-789",
            "error": "처리 중 오류 발생",
            "error_message": "분석 실패"
        }
        mock_redis_client.get.return_value = json.dumps(result_data)

        # When
        response = client.get(f"/api/v1/minutes/{task_id}")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        # error 또는 error_message 중 하나 반환
        assert "error" in data or "error_message" in data

    def test_get_minutes_status_with_error_message(self, client, mock_redis_client):
        """
        에러 메시지가 포함된 상태 조회 테스트
        Given: 에러 상태의 상태 데이터
        When: GET /api/v1/minutes/{task_id}/status
        Then: 에러 메시지 포함 반환
        """
        # Given
        task_id = "minutes-status-error-123"
        status_data = {
            "task_id": task_id,
            "status": "failed",
            "progress": 0.5,
            "message": "처리 실패",
            "error_message": "내부 서버 오류"
        }
        mock_redis_client.get.return_value = json.dumps(status_data)

        # When
        response = client.get(f"/api/v1/minutes/{task_id}/status")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "내부 서버 오류"
