"""
감정 분석 API 엔드포인트 테스트
SPEC-SENTIMENT-001:
- POST /api/v1/sentiment → 감정 분석 작업 요청 (202 Accepted)
- GET /api/v1/sentiment/{task_id}/status → 상태 조회
- GET /api/v1/sentiment/{task_id} → 전체 결과 조회
- GET /api/v1/sentiment/meeting/{meeting_id} → 회의 ID로 감정 분석 결과 조회
- DELETE /api/v1/sentiment/{task_id} → 삭제
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestSentimentAPI:
    """감정 분석 API 테스트 스위트"""

    @pytest.fixture
    def mock_redis_client(self):
        """Redis 클라이언트 mock"""
        redis = AsyncMock()
        redis.get.return_value = None
        redis.setex.return_value = True
        redis.delete.return_value = 1
        return redis

    @pytest.fixture
    def client(self, mock_redis_client):
        """FastAPI TestClient with mocked dependencies"""
        from backend.app.dependencies import get_redis_client
        from backend.app.main import app

        async def override_redis():
            yield mock_redis_client

        app.dependency_overrides[get_redis_client] = override_redis

        yield TestClient(app)

        app.dependency_overrides.clear()

    def test_create_sentiment_success(self, client, mock_redis_client):
        """
        감정 분석 작업 생성 성공 테스트
        Given: 유효한 minutes_task_id
        When: POST /api/v1/sentiment
        Then: 202 Accepted와 task_id 반환
        """
        # Given
        request_data = {
            "minutes_task_id": "test-minutes-123",
            "max_tokens": 4000
        }

        with patch("backend.workers.tasks.sentiment_task.sentiment_celery_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="celery-task-123")

            # When
            response = client.post("/api/v1/sentiment", json=request_data)

            # Then
            assert response.status_code == 202
            data = response.json()
            assert "task_id" in data
            assert data["minutes_task_id"] == "test-minutes-123"
            assert data["status"] == "pending"
            assert "status_url" in data
            assert "result_url" in data

    def test_create_sentiment_with_defaults(self, client, mock_redis_client):
        """
        기본값 포함 감정 분석 작업 생성 테스트
        Given: max_tokens 없이 minutes_task_id만 제공
        When: POST /api/v1/sentiment
        Then: 작업 생성 성공
        """
        # Given
        request_data = {"minutes_task_id": "test-minutes-456"}

        with patch("backend.workers.tasks.sentiment_task.sentiment_celery_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="celery-task-456")

            # When
            response = client.post("/api/v1/sentiment", json=request_data)

            # Then
            assert response.status_code == 202
            data = response.json()
            assert "task_id" in data

    def test_get_sentiment_status_success(self, client, mock_redis_client):
        """
        감정 분석 상태 조회 성공 테스트
        Given: 존재하는 task_id와 Redis 상태 데이터
        When: GET /api/v1/sentiment/{task_id}/status
        Then: 상태 정보 반환
        """
        # Given
        task_id = "sentiment-task-123"
        status_data = {
            "task_id": task_id,
            "status": "processing",
            "progress": 0.5,
            "message": "감정 분석 중",
            "error_message": None
        }
        mock_redis_client.get.return_value = json.dumps(status_data)

        # When
        response = client.get(f"/api/v1/sentiment/{task_id}/status")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "processing"
        assert data["progress"] == 0.5
        assert data["message"] == "감정 분석 중"

    def test_get_sentiment_status_not_found(self, client, mock_redis_client):
        """
        존재하지 않는 task_id 상태 조회 테스트
        Given: 존재하지 않는 task_id
        When: GET /api/v1/sentiment/{task_id}/status
        Then: 404 Not Found
        """
        # Given
        mock_redis_client.get.return_value = None

        # When
        response = client.get("/api/v1/sentiment/non-existent/status")

        # Then
        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"] or "찾을 수 없습니다" in response.json()["detail"]

    def test_get_sentiment_result_success(self, client, mock_redis_client):
        """
        감정 분석 결과 조회 성공 테스트
        Given: 완료된 감정 분석 결과
        When: GET /api/v1/sentiment/{task_id}
        Then: 전체 결과 반환
        """
        # Given
        task_id = "sentiment-result-123"
        result_data = {
            "task_id": task_id,
            "status": "completed",
            "minutes_task_id": "minutes-123",
            "overall_sentiment": "positive",
            "overall_emotion": "happy",
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "speaker": "SPEAKER_00",
                    "text": "안녕하세요",
                    "sentiment": "positive",
                    "emotion": "joy",
                    "confidence": 0.9
                }
            ],
            "speakers": [
                {
                    "speaker": "SPEAKER_00",
                    "total_segments": 1,
                    "positive_ratio": 0.8,
                    "neutral_ratio": 0.2,
                    "negative_ratio": 0.0,
                    "dominant_emotion": "joy",
                    "emotion_distribution": {"joy": 1}
                }
            ],
            "emotional_timeline": [
                {"time": 0.0, "sentiment": "positive", "emotion": "joy", "speaker": "SPEAKER_00"}
            ],
            "generation_time_seconds": 2.5
        }
        mock_redis_client.get.return_value = json.dumps(result_data)

        # When
        response = client.get(f"/api/v1/sentiment/{task_id}")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "completed"
        assert data["overall_sentiment"] == "positive"
        assert len(data["segments"]) == 1

    def test_get_sentiment_result_pending(self, client, mock_redis_client):
        """
        진행 중인 감정 분석 결과 조회 테스트
        Given: 완료되지 않은 작업 (status만 존재)
        When: GET /api/v1/sentiment/{task_id}
        Then: 빈 결과 반환
        """
        # Given
        task_id = "sentiment-pending-123"
        status_data = {
            "task_id": task_id,
            "status": "processing",
            "minutes_task_id": "minutes-456"
        }

        # Redis get 호출 시 sequence로 status 반환
        mock_redis_client.get.return_value = json.dumps(status_data)

        # When
        response = client.get(f"/api/v1/sentiment/{task_id}")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "processing"
        assert data["minutes_task_id"] == "minutes-456"

    def test_get_sentiment_result_not_found(self, client, mock_redis_client):
        """
        존재하지 않는 task_id 결과 조회 테스트
        Given: 존재하지 않는 task_id
        When: GET /api/v1/sentiment/{task_id}
        Then: 404 Not Found
        """
        # Given - 두 번의 get 호출에서 모두 None 반환
        mock_redis_client.get.return_value = None

        # When
        response = client.get("/api/v1/sentiment/non-existent/result")

        # Then
        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"] or "찾을 수 없습니다" in response.json()["detail"]

    def test_delete_sentiment_success(self, client, mock_redis_client):
        """
        감정 분석 작업 삭제 성공 테스트
        Given: 존재하는 task_id
        When: DELETE /api/v1/sentiment/{task_id}
        Then: 204 No Content
        """
        # Given
        mock_redis_client.delete.return_value = 2  # status + result key 삭제

        # When
        response = client.delete("/api/v1/sentiment/sentiment-123")

        # Then
        assert response.status_code == 204
        assert response.content == b""
        # 삭제 호출 확인
        assert mock_redis_client.delete.call_count == 1

    def test_delete_sentiment_no_keys(self, client, mock_redis_client):
        """
        존재하지 않는 작업 삭제 테스트
        Given: 존재하지 않는 task_id
        When: DELETE /api/v1/sentiment/{task_id}
        Then: 204 No Content (idempotent)
        """
        # Given
        mock_redis_client.delete.return_value = 0

        # When
        response = client.delete("/api/v1/sentiment/non-existent")

        # Then
        assert response.status_code == 204
        assert response.content == b""

    def test_create_sentiment_invalid_request(self, client, mock_redis_client):
        """
        잘못된 요청으로 감정 분석 작업 생성 테스트
        Given: minutes_task_id 누락
        When: POST /api/v1/sentiment
        Then: 422 Unprocessable Entity
        """
        # Given - 잘못된 데이터
        request_data = {"max_tokens": 4000}  # minutes_task_id 누락

        # When
        response = client.post("/api/v1/sentiment", json=request_data)

        # Then
        assert response.status_code == 422
