"""
AI 요약 API 엔드포인트 단위 테스트

테스트 대상:
- POST /api/v1/summaries                    AI 요약 생성 작업 요청
- POST /api/v1/summaries/{id}/mind-map      마인드맵 생성 작업 요청
- GET  /api/v1/summaries/{id}/status        요약 작업 상태 조회
- GET  /api/v1/summaries/{id}               요약 결과 전체 조회
- GET  /api/v1/summaries/mind-map/{id}/status  마인드맵 작업 상태 조회
- GET  /api/v1/summaries/mind-map/{id}         마인드맵 결과 조회
- DELETE /api/v1/summaries/{id}             요약 작업 및 결과 삭제
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# TestClient 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def summary_client():
    """
    요약 API 테스트용 TestClient
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
# POST /api/v1/summaries 테스트
# ---------------------------------------------------------------------------


class TestCreateSummaryAPI:
    """POST /api/v1/summaries 엔드포인트 테스트"""

    def test_create_summary_success(self, summary_client):
        """요약 생성 작업 요청 성공"""
        client, mock_redis = summary_client

        # Mock 설정
        mock_redis.scard = AsyncMock(return_value=0)  # 활성 작업 0개
        mock_redis.setex = AsyncMock()

        with patch("backend.workers.tasks.summary_task.summary_celery_task") as mock_task:
            mock_task.delay = MagicMock()

            response = client.post(
                "/api/v1/summaries",
                json={
                    "minutes_task_id": "minutes-123",
                    "max_tokens": 1000,
                    "template_id": "template-1",
                },
            )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert data["minutes_task_id"] == "minutes-123"
        assert data["status"] == "pending"
        assert "/status" in data["status_url"]
        assert data["result_url"] == f"/api/v1/summaries/{data['task_id']}"

    def test_create_summary_concurrent_limit_exceeded(self, summary_client):
        """동시 처리 한도 초과 (429)"""
        client, mock_redis = summary_client

        # 활성 작업이 이미 한도에 도달
        mock_redis.scard = AsyncMock(return_value=10)

        response = client.post(
            "/api/v1/summaries",
            json={
                "minutes_task_id": "minutes-123",
            },
        )

        assert response.status_code == 429
        data = response.json()
        assert "message" in data
        assert "한도" in data["message"] or "초과" in data["message"]

    def test_create_summary_default_params(self, summary_client):
        """기본 파라미터로 요약 생성"""
        client, mock_redis = summary_client

        mock_redis.scard = AsyncMock(return_value=0)
        mock_redis.setex = AsyncMock()

        with patch("backend.workers.tasks.summary_task.summary_celery_task") as mock_task:
            mock_task.delay = MagicMock()

            response = client.post(
                "/api/v1/summaries",
                json={
                    "minutes_task_id": "minutes-456",
                },
            )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"

    def test_create_summary_missing_minutes_task_id(self, summary_client):
        """minutes_task_id 필드 누락"""
        client, _ = summary_client

        response = client.post(
            "/api/v1/summaries",
            json={
                "max_tokens": 1000,
            },
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/summaries/{id}/mind-map 테스트
# ---------------------------------------------------------------------------


class TestCreateMindMapAPI:
    """POST /api/v1/summaries/{summary_task_id}/mind-map 엔드포인트 테스트"""

    def test_create_mind_map_success(self, summary_client):
        """마인드맵 생성 성공"""
        client, mock_redis = summary_client

        # 완료된 요약 결과
        summary_result = {
            "task_id": "sum-123",
            "status": "completed",
            "summary_text": "요약 내용",
            "action_items": [],
            "key_decisions": [],
            "next_steps": [],
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(summary_result))
        mock_redis.setex = AsyncMock()

        with patch("backend.workers.tasks.mind_map_task.mind_map_celery_task") as mock_task:
            mock_task.delay = MagicMock()

            response = client.post(
                "/api/v1/summaries/sum-123/mind-map",
                json={
                    "max_tokens": 1024,  # 512 이상이어야 함
                },
            )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert data["summary_task_id"] == "sum-123"
        assert data["status"] == "pending"

    def test_create_mind_map_not_found(self, summary_client):
        """요약 결과를 찾을 수 없음 (404)"""
        client, mock_redis = summary_client

        mock_redis.get = AsyncMock(return_value=None)

        response = client.post(
            "/api/v1/summaries/non-existent/mind-map",
            json={},
        )

        assert response.status_code == 404
        data = response.json()
        assert "message" in data
        assert "찾을 수 없습니다" in data["message"]

    def test_create_mind_map_summary_not_completed(self, summary_client):
        """요약이 완료되지 않음 (409)"""
        client, mock_redis = summary_client

        # 진행 중인 요약
        summary_result = {
            "task_id": "sum-123",
            "status": "processing",
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(summary_result))

        response = client.post(
            "/api/v1/summaries/sum-123/mind-map",
            json={},
        )

        assert response.status_code == 409
        data = response.json()
        assert "message" in data
        assert "완료된 요약" in data["message"] or "completed" in data["message"]

    def test_create_mind_map_default_request(self, summary_client):
        """기본 요청 본문 (None)로 마인드맵 생성"""
        client, mock_redis = summary_client

        summary_result = {
            "task_id": "sum-123",
            "status": "completed",
            "summary_text": "요약",
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(summary_result))
        mock_redis.setex = AsyncMock()

        with patch("backend.workers.tasks.mind_map_task.mind_map_celery_task") as mock_task:
            mock_task.delay = MagicMock()

            response = client.post(
                "/api/v1/summaries/sum-123/mind-map",
                json=None,
            )

        assert response.status_code == 202


# ---------------------------------------------------------------------------
# GET /api/v1/summaries/{task_id}/status 테스트
# ---------------------------------------------------------------------------


class TestGetSummaryStatusAPI:
    """GET /api/v1/summaries/{task_id}/status 엔드포인트 테스트"""

    def test_get_summary_status_success(self, summary_client):
        """요약 작업 상태 조회 성공"""
        client, mock_redis = summary_client

        status_data = {
            "task_id": "sum-123",
            "status": "processing",
            "progress": 0.5,
            "message": "처리 중",
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(status_data))

        response = client.get("/api/v1/summaries/sum-123/status")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "sum-123"
        assert data["status"] == "processing"
        assert data["progress"] == 0.5
        assert data["message"] == "처리 중"

    def test_get_summary_status_not_found(self, summary_client):
        """요약 작업을 찾을 수 없음 (404)"""
        client, mock_redis = summary_client

        mock_redis.get = AsyncMock(return_value=None)

        response = client.get("/api/v1/summaries/non-existent/status")

        assert response.status_code == 404
        data = response.json()
        assert "message" in data
        assert "찾을 수 없습니다" in data["message"]

    def test_get_summary_status_with_error(self, summary_client):
        """에러 상태 조회"""
        client, mock_redis = summary_client

        status_data = {
            "task_id": "sum-123",
            "status": "failed",
            "error_message": "처리 실패",
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(status_data))

        response = client.get("/api/v1/summaries/sum-123/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "처리 실패"


# ---------------------------------------------------------------------------
# GET /api/v1/summaries/{task_id} 테스트
# ---------------------------------------------------------------------------


class TestGetSummaryResultAPI:
    """GET /api/v1/summaries/{task_id} 엔드포인트 테스트"""

    def test_get_summary_result_success(self, summary_client):
        """요약 결과 전체 조회 성공"""
        client, mock_redis = summary_client

        result_data = {
            "task_id": "sum-123",
            "status": "completed",
            "minutes_task_id": "minutes-456",
            "summary_text": "회의 요약 내용",
            "action_items": [
                {
                    "assignee": "김대리",
                    "task": "보고서 작성",
                    "deadline": "내일",
                    "priority": "high",
                }
            ],
            "key_decisions": ["결정 1"],
            "next_steps": ["다음 단계"],
            "sections": {},
            "tokens_used": {"prompt_tokens": 400, "completion_tokens": 100},
            "generation_time_seconds": 2.5,
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(result_data))

        response = client.get("/api/v1/summaries/sum-123")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "sum-123"
        assert data["status"] == "completed"
        assert data["summary_text"] == "회의 요약 내용"
        assert len(data["action_items"]) == 1
        assert data["action_items"][0]["assignee"] == "김대리"
        assert data["action_items"][0]["task"] == "보고서 작성"
        assert data["tokens_used"]["prompt_tokens"] == 400
        assert data["generation_time_seconds"] == 2.5

    def test_get_summary_result_not_found(self, summary_client):
        """요약 작업을 찾을 수 없음 (404)"""
        client, mock_redis = summary_client

        # 결과와 상태 모두 없음
        mock_redis.get = AsyncMock(return_value=None)

        response = client.get("/api/v1/summaries/non-existent")

        assert response.status_code == 404
        data = response.json()
        assert "message" in data
        assert "찾을 수 없습니다" in data["message"]

    def test_get_summary_result_still_processing(self, summary_client):
        """아직 처리 중인 경우 (빈 결과 반환)"""
        client, mock_redis = summary_client

        # 결과는 없지만 상태는 있음 (처리 중)
        mock_redis.get = AsyncMock(
            side_effect=[
                None,  # result_key 조회
                json.dumps({  # status_key 조회
                    "task_id": "sum-123",
                    "status": "processing",
                    "minutes_task_id": "minutes-456",
                })
            ]
        )

        response = client.get("/api/v1/summaries/sum-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["summary_text"] == ""
        assert data["action_items"] == []
        assert data["key_decisions"] == []

    def test_get_summary_result_failed(self, summary_client):
        """실패한 요약 결과 조회"""
        client, mock_redis = summary_client

        result_data = {
            "task_id": "sum-123",
            "status": "failed",
            "error_message": "처리 중 오류 발생",
            "minutes_task_id": "minutes-456",
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(result_data))

        response = client.get("/api/v1/summaries/sum-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "처리 중 오류 발생"

    def test_get_summary_result_with_sections(self, summary_client):
        """섹션 포함 요약 결과 조회"""
        client, mock_redis = summary_client

        result_data = {
            "task_id": "sum-123",
            "status": "completed",
            "summary_text": "요약",
            "action_items": [],
            "key_decisions": [],
            "next_steps": [],
            "sections": {
                "agenda": "안건",
                "discussion": "토의 내용",
            },
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(result_data))

        response = client.get("/api/v1/summaries/sum-123")

        assert response.status_code == 200
        data = response.json()
        assert "sections" in data
        assert data["sections"]["agenda"] == "안건"


# ---------------------------------------------------------------------------
# GET /api/v1/summaries/mind-map/{task_id}/status 테스트
# ---------------------------------------------------------------------------


class TestGetMindMapStatusAPI:
    """GET /api/v1/summaries/mind-map/{task_id}/status 엔드포인트 테스트"""

    def test_get_mind_map_status_success(self, summary_client):
        """마인드맵 작업 상태 조회 성공"""
        client, mock_redis = summary_client

        status_data = {
            "task_id": "mind-123",
            "status": "processing",
            "progress": 0.7,
            "message": "마인드맵 생성 중",
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(status_data))

        response = client.get("/api/v1/summaries/mind-map/mind-123/status")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "mind-123"
        assert data["status"] == "processing"
        assert data["progress"] == 0.7

    def test_get_mind_map_status_not_found(self, summary_client):
        """마인드맵 작업을 찾을 수 없음 (404)"""
        client, mock_redis = summary_client

        mock_redis.get = AsyncMock(return_value=None)

        response = client.get("/api/v1/summaries/mind-map/non-existent/status")

        assert response.status_code == 404
        data = response.json()
        assert "message" in data
        assert "찾을 수 없습니다" in data["message"]


# ---------------------------------------------------------------------------
# GET /api/v1/summaries/mind-map/{task_id} 테스트
# ---------------------------------------------------------------------------


class TestGetMindMapResultAPI:
    """GET /api/v1/summaries/mind-map/{task_id} 엔드포인트 테스트"""

    def test_get_mind_map_result_success(self, summary_client):
        """마인드맵 결과 조회 성공"""
        client, mock_redis = summary_client

        result_data = {
            "task_id": "mind-123",
            "status": "completed",
            "summary_task_id": "sum-456",
            "root": {
                "id": "root",
                "title": "주제",  # title 필드 추가
                "summary": "주제 설명",
                "children": [],
            },
            "edges": [
                {
                    "source": "root",
                    "target": "child-1",
                    "relation": "관계",
                }
            ],
            "generation_time_seconds": 1.5,
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(result_data))

        response = client.get("/api/v1/summaries/mind-map/mind-123")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "mind-123"
        assert data["status"] == "completed"
        assert data["summary_task_id"] == "sum-456"
        assert data["root"] is not None
        assert data["root"]["title"] == "주제"
        assert len(data["edges"]) == 1
        assert data["generation_time_seconds"] == 1.5

    def test_get_mind_map_result_not_found(self, summary_client):
        """마인드맵 작업을 찾을 수 없음 (404)"""
        client, mock_redis = summary_client

        # 결과와 상태 모두 없음
        mock_redis.get = AsyncMock(return_value=None)

        response = client.get("/api/v1/summaries/mind-map/non-existent")

        assert response.status_code == 404
        data = response.json()
        assert "message" in data
        assert "찾을 수 없습니다" in data["message"]

    def test_get_mind_map_result_still_processing(self, summary_client):
        """아직 처리 중인 마인드맵 (빈 결과 반환)"""
        client, mock_redis = summary_client

        # 결과는 없지만 상태는 있음
        mock_redis.get = AsyncMock(
            side_effect=[
                None,  # result 조회
                json.dumps({  # status 조회
                    "task_id": "mind-123",
                    "status": "processing",
                    "summary_task_id": "sum-456",
                })
            ]
        )

        response = client.get("/api/v1/summaries/mind-map/mind-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["root"] is None
        assert data["edges"] == []

    def test_get_mind_map_result_failed(self, summary_client):
        """실패한 마인드맵 결과 조회"""
        client, mock_redis = summary_client

        result_data = {
            "task_id": "mind-123",
            "status": "failed",
            "error_message": "마인드맵 생성 실패",
            "summary_task_id": "sum-456",
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(result_data))

        response = client.get("/api/v1/summaries/mind-map/mind-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "마인드맵 생성 실패"


# ---------------------------------------------------------------------------
# DELETE /api/v1/summaries/{task_id} 테스트
# ---------------------------------------------------------------------------


class TestDeleteSummaryAPI:
    """DELETE /api/v1/summaries/{task_id} 엔드포인트 테스트"""

    def test_delete_summary_success(self, summary_client):
        """요약 작업 삭제 성공"""
        client, mock_redis = summary_client

        mock_redis.delete = AsyncMock(return_value=2)  # 삭제된 키 수

        response = client.delete("/api/v1/summaries/sum-123")

        assert response.status_code == 204
        # 204는 응답 본문 없음
        assert response.content == b""

    def test_delete_summary_removes_both_keys(self, summary_client):
        """상태와 결과 키 모두 삭제 확인"""
        client, mock_redis = summary_client

        deleted_keys = []

        def mock_delete(*keys):
            deleted_keys.extend(keys)
            return len(keys)

        mock_redis.delete = AsyncMock(side_effect=mock_delete)

        response = client.delete("/api/v1/summaries/sum-123")

        assert response.status_code == 204
        assert "task:sum:status:sum-123" in deleted_keys
        assert "task:sum:result:sum-123" in deleted_keys
