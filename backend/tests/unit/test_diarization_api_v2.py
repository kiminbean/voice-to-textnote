"""
화자 분리 API 엔드포인트 단위 테스트

테스트 대상:
- POST /api/v1/diarizations                    화자 분리 작업 생성
- GET  /api/v1/diarizations/{task_id}/status    화자 분리 작업 상태 조회
- GET  /api/v1/diarizations/{task_id}           화자 분리 결과 조회
- DELETE /api/v1/diarizations/{task_id}         화자 분리 작업 및 결과 삭제
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# TestClient 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def diarization_client():
    """
    화자 분리 API 테스트용 TestClient
    - DB 세션 mock
    - Redis 클라이언트 mock
    - 모델 로드 없이 앱 생성
    """
    from backend.app.dependencies import get_db_session, get_redis_client
    from backend.app.main import app

    async def mock_db_session():
        yield AsyncMock()

    # Redis mock 생성
    mock_redis_instance = AsyncMock()
    mock_redis_instance.get = AsyncMock(return_value=None)
    mock_redis_instance.setex = AsyncMock()
    mock_redis_instance.scard = AsyncMock(return_value=0)
    mock_redis_instance.delete = AsyncMock()

    async def mock_redis():
        return mock_redis_instance

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_redis_client] = mock_redis

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield TestClient(app, raise_server_exceptions=False), mock_redis_instance

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/diarizations 테스트
# ---------------------------------------------------------------------------


class TestCreateDiarizationAPI:
    """POST /api/v1/diarizations 엔드포인트 테스트"""

    def test_create_diarization_success(self, diarization_client):
        """화자 분리 작업 생성 성공"""
        client, mock_redis = diarization_client
        stt_task_id = uuid.uuid4()

        # Mock 설정
        mock_redis.scard = AsyncMock(return_value=0)  # 활성 작업 0개
        mock_redis.setex = AsyncMock()

        with patch("backend.workers.tasks.diarization_task.diarization_celery_task") as mock_task:
            mock_task.delay = MagicMock()

            response = client.post(
                "/api/v1/diarizations",
                json={
                    "stt_task_id": str(stt_task_id),
                    "num_speakers": 3,
                    "min_speakers": 2,
                    "max_speakers": 5,
                },
            )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert data["stt_task_id"] == str(stt_task_id)
        assert data["status"] == "pending"
        assert "/status" in data["status_url"]
        assert data["result_url"] == f"/api/v1/diarizations/{data['task_id']}"

    def test_create_diarization_concurrent_limit_exceeded(self, diarization_client):
        """동시 처리 한도 초과 (429)"""
        client, mock_redis = diarization_client

        # 활성 작업이 이미 한도에 도달
        mock_redis.scard = AsyncMock(return_value=10)

        stt_task_id = uuid.uuid4()

        response = client.post(
            "/api/v1/diarizations",
            json={
                "stt_task_id": str(stt_task_id),
            },
        )

        assert response.status_code == 429
        data = response.json()
        assert "message" in data
        assert "한도" in data["message"] or "초과" in data["message"]

    def test_create_diarization_default_params(self, diarization_client):
        """기본 파라미터로 화자 분리 생성"""
        client, mock_redis = diarization_client
        stt_task_id = uuid.uuid4()

        mock_redis.scard = AsyncMock(return_value=0)
        mock_redis.setex = AsyncMock()

        with patch("backend.workers.tasks.diarization_task.diarization_celery_task") as mock_task:
            mock_task.delay = MagicMock()

            response = client.post(
                "/api/v1/diarizations",
                json={
                    "stt_task_id": str(stt_task_id),
                },
            )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"

    def test_create_diarization_invalid_uuid(self, diarization_client):
        """잘못된 UUID 형식"""
        client, _ = diarization_client

        response = client.post(
            "/api/v1/diarizations",
            json={
                "stt_task_id": "invalid-uuid-format",
            },
        )

        assert response.status_code == 422

    def test_create_diarization_missing_stt_task_id(self, diarization_client):
        """stt_task_id 필드 누락"""
        client, _ = diarization_client

        response = client.post(
            "/api/v1/diarizations",
            json={
                "num_speakers": 3,
            },
        )

        assert response.status_code == 422

    def test_create_diarization_min_speakers_validation(self, diarization_client):
        """min_speakers 유효성 검사"""
        client, _ = diarization_client
        stt_task_id = uuid.uuid4()

        # min_speakers가 1 미만인 경우
        response = client.post(
            "/api/v1/diarizations",
            json={
                "stt_task_id": str(stt_task_id),
                "min_speakers": 0,  # 1 이상이어야 함
            },
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/diarizations/{task_id}/status 테스트
# ---------------------------------------------------------------------------


class TestGetDiarizationStatusAPI:
    """GET /api/v1/diarizations/{task_id}/status 엔드포인트 테스트"""

    def test_get_diarization_status_success(self, diarization_client):
        """화자 분리 작업 상태 조회 성공"""
        client, mock_redis = diarization_client
        task_id = str(uuid.uuid4())

        status_data = {
            "task_id": task_id,
            "stt_task_id": str(uuid.uuid4()),
            "status": "processing",
            "progress": 0.6,
            "message": "화자 분리 중",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(status_data))

        response = client.get(f"/api/v1/diarizations/{task_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "processing"
        assert data["progress"] == 0.6
        assert data["message"] == "화자 분리 중"

    def test_get_diarization_status_not_found(self, diarization_client):
        """화자 분리 작업을 찾을 수 없음 (404)"""
        client, mock_redis = diarization_client

        mock_redis.get = AsyncMock(return_value=None)

        task_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/diarizations/{task_id}/status")

        assert response.status_code == 404
        data = response.json()
        assert "message" in data
        assert "찾을 수 없습니다" in data["message"]

    def test_get_diarization_status_with_error(self, diarization_client):
        """에러 상태 조회"""
        client, mock_redis = diarization_client
        task_id = str(uuid.uuid4())

        status_data = {
            "task_id": task_id,
            "stt_task_id": str(uuid.uuid4()),
            "status": "failed",
            "error_message": "처리 실패",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(status_data))

        response = client.get(f"/api/v1/diarizations/{task_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "처리 실패"


# ---------------------------------------------------------------------------
# GET /api/v1/diarizations/{task_id} 테스트
# ---------------------------------------------------------------------------


class TestGetDiarizationResultAPI:
    """GET /api/v1/diarizations/{task_id} 엔드포인트 테스트"""

    def test_get_diarization_result_success(self, diarization_client):
        """화자 분리 결과 조회 성공"""
        client, mock_redis = diarization_client
        task_id = str(uuid.uuid4())

        result_data = {
            "task_id": task_id,
            "stt_task_id": str(uuid.uuid4()),
            "status": "completed",
            "segments": [
                {
                    "id": 1,
                    "start": 0.0,
                    "end": 2.5,
                    "text": "안녕하세요",
                    "confidence": 0.95,
                    "speaker_id": "SPEAKER_00",
                    "speaker_confidence": 0.9,
                },
                {
                    "id": 2,
                    "start": 2.5,
                    "end": 5.0,
                    "text": "반갑습니다",
                    "confidence": 0.92,
                    "speaker_id": "SPEAKER_01",
                    "speaker_confidence": 0.85,
                },
            ],
            "speakers": [
                {
                    "speaker_id": "SPEAKER_00",
                    "total_speaking_time": 2.5,
                    "segment_count": 1,
                },
                {
                    "speaker_id": "SPEAKER_01",
                    "total_speaking_time": 2.5,
                    "segment_count": 1,
                },
            ],
            "num_speakers": 2,
            "created_at": datetime.now(UTC).isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
        }

        # get_result_with_fallback mock
        mock_redis.get = AsyncMock(return_value=json.dumps(result_data))

        response = client.get(f"/api/v1/diarizations/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "completed"
        assert len(data["segments"]) == 2
        assert data["segments"][0]["speaker_id"] == "SPEAKER_00"
        assert len(data["speakers"]) == 2
        assert data["num_speakers"] == 2

    def test_get_diarization_result_not_found(self, diarization_client):
        """화자 분리 작업을 찾을 수 없음 (404)"""
        client, mock_redis = diarization_client
        task_id = str(uuid.uuid4())

        # get_result_with_fallback mock - None 반환
        with patch("backend.app.api.v1.transcription.diarization.get_result_with_fallback") as mock_fallback:
            mock_fallback.return_value = None

            response = client.get(f"/api/v1/diarizations/{task_id}")

        assert response.status_code == 404
        data = response.json()
        assert "message" in data
        assert "찾을 수 없습니다" in data["message"]

    def test_get_diarization_result_still_processing(self, diarization_client):
        """아직 처리 중인 화자 분리 (빈 결과 반환)"""
        client, mock_redis = diarization_client
        task_id = str(uuid.uuid4())

        # 결과는 없지만 상태는 있음 (처리 중)
        now = datetime.now(UTC).isoformat()

        # get_result_with_fallback mock - None 반환 (결과 없음)
        # 상태는 Redis에서 직접 조회
        with patch("backend.app.api.v1.transcription.diarization.get_result_with_fallback") as mock_fallback:
            mock_fallback.return_value = None

            # 두 번째 Redis 호출 (status 조회)
            call_count = [0]

            async def mock_get_with_count(key):
                call_count[0] += 1
                if call_count[0] == 1:  # status_key 조회
                    return json.dumps({
                        "task_id": task_id,
                        "stt_task_id": str(uuid.uuid4()),
                        "status": "processing",
                        "created_at": now,
                    })
                return None

            mock_redis.get = mock_get_with_count

            response = client.get(f"/api/v1/diarizations/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["segments"] == []
        assert data["speakers"] == []

    def test_get_diarization_result_failed(self, diarization_client):
        """실패한 화자 분리 결과 조회"""
        client, mock_redis = diarization_client
        task_id = str(uuid.uuid4())

        result_data = {
            "task_id": task_id,
            "stt_task_id": str(uuid.uuid4()),
            "status": "failed",
            "error_message": "화자 분리 실패",
            "segments": [],
            "speakers": [],
            "created_at": datetime.now(UTC).isoformat(),
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(result_data))

        response = client.get(f"/api/v1/diarizations/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "화자 분리 실패"

    def test_get_diarization_result_parallel_mode(self, diarization_client):
        """병렬 모드(matched=False) 세그먼트 결과 조회"""
        client, mock_redis = diarization_client
        task_id = str(uuid.uuid4())

        # 병렬 모드: id, text, confidence가 None일 수 있음
        result_data = {
            "task_id": task_id,
            "stt_task_id": str(uuid.uuid4()),
            "status": "completed",
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.5,
                    "text": "",
                    "confidence": 0.0,
                    "speaker_id": "SPEAKER_00",
                    "speaker_confidence": 0.9,
                },
            ],
            "speakers": [
                {
                    "speaker_id": "SPEAKER_00",
                    "total_speaking_time": 2.5,
                    "segment_count": 1,
                }
            ],
            "num_speakers": 1,
            "created_at": datetime.now(UTC).isoformat(),
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(result_data))

        response = client.get(f"/api/v1/diarizations/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert len(data["segments"]) == 1
        # 병렬 모드에서는 id가 None일 수 있음
        assert data["segments"][0]["id"] is None or isinstance(data["segments"][0]["id"], int)


# ---------------------------------------------------------------------------
# DELETE /api/v1/diarizations/{task_id} 테스트
# ---------------------------------------------------------------------------


class TestDeleteDiarizationAPI:
    """DELETE /api/v1/diarizations/{task_id} 엔드포인트 테스트"""

    def test_delete_diarization_success(self, diarization_client):
        """화자 분리 작업 삭제 성공"""
        client, mock_redis = diarization_client
        task_id = str(uuid.uuid4())

        mock_redis.delete = AsyncMock(return_value=2)  # 삭제된 키 수

        response = client.delete(f"/api/v1/diarizations/{task_id}")

        assert response.status_code == 204
        # 204는 응답 본문 없음
        assert response.content == b""

    def test_delete_diarization_removes_both_keys(self, diarization_client):
        """상태와 결과 키 모두 삭제 확인"""
        client, mock_redis = diarization_client
        task_id = str(uuid.uuid4())

        deleted_keys = []

        def mock_delete(*keys):
            deleted_keys.extend(keys)
            return len(keys)

        mock_redis.delete = AsyncMock(side_effect=mock_delete)

        response = client.delete(f"/api/v1/diarizations/{task_id}")

        assert response.status_code == 204
        assert "task:dia:status:" + task_id in deleted_keys
        assert "task:dia:result:" + task_id in deleted_keys
