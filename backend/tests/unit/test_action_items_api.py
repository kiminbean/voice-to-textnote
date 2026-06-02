"""
SPEC-ACTION-001: 액션 아이템 추출 API 단위 테스트

테스트 대상:
- POST /api/v1/action-items/extract    텍스트에서 액션 아이템 추출
- POST /api/v1/action-items/meeting     기존 회의록에서 액션 아이템 추출
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# TestClient 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def action_items_client():
    """
    액션 아이템 API 테스트용 TestClient
    - DB 세션 mock
    - Redis 클라이언트 mock
    - 모델 로드 없이 앱 생성
    """
    from backend.app.dependencies import get_db_session, get_redis_client
    from backend.app.main import app

    async def mock_db_session():
        yield AsyncMock()

    async def mock_redis():
        yield AsyncMock()

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_redis_client] = mock_redis

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/action-items/extract 테스트
# ---------------------------------------------------------------------------


class TestExtractActionItemsAPI:
    """POST /api/v1/action-items/extract 엔드포인트 테스트"""

    def test_extract_action_items_success_korean(self, action_items_client):
        """한국어 텍스트에서 액션 아이템 추출 성공"""
        response = action_items_client.post(
            "/api/v1/action-items/extract",
            json={
                "text": "회의 내용입니다. 김대리가 내일까지 보고서를 작성해 주세요. "
                "박과장이 이번 주 금요일까지 검토하겠습니다.",
                "language": "ko",
                "include_deadlines": True,
                "include_assignees": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "task_id" in data
        assert "action_items" in data
        assert "total_count" in data
        assert "extracted_at" in data
        assert data["total_count"] >= 1

    def test_extract_action_items_success_english(self, action_items_client):
        """영어 텍스트에서 액션 아이템 추출 성공"""
        response = action_items_client.post(
            "/api/v1/action-items/extract",
            json={
                "text": "Meeting notes: John will prepare the presentation by Friday. "
                "We need to review the API design.",
                "language": "en",
                "include_deadlines": True,
                "include_assignees": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["total_count"] >= 1

    def test_extract_action_items_default_language(self, action_items_client):
        """기본 언어(ko)로 액션 아이템 추출"""
        response = action_items_client.post(
            "/api/v1/action-items/extract",
            json={
                "text": "김대리가 보고서를 작성해 주세요.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_extract_action_items_without_deadlines(self, action_items_client):
        """기한 추출 비활성화"""
        response = action_items_client.post(
            "/api/v1/action-items/extract",
            json={
                "text": "김대리가 내일까지 보고서를 작성해 주세요.",
                "language": "ko",
                "include_deadlines": False,
                "include_assignees": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # 기한이 None이어야 함
        if data["total_count"] > 0:
            for item in data["action_items"]:
                assert item.get("deadline") is None or item.get("deadline") == ""

    def test_extract_action_items_without_assignees(self, action_items_client):
        """담당자 추출 비활성화"""
        response = action_items_client.post(
            "/api/v1/action-items/extract",
            json={
                "text": "김대리가 보고서를 작성해 주세요.",
                "language": "ko",
                "include_deadlines": True,
                "include_assignees": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_extract_action_items_short_text(self, action_items_client):
        """짧은 텍스트 (액션 아이템 없음)"""
        # 10자 이상이어야 Pydantic validation 통과
        response = action_items_client.post(
            "/api/v1/action-items/extract",
            json={
                "text": "안녕하세요 반갑습니다",  # 10자 이상
                "language": "ko",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # 액션 아이템이 없거나 매우 적음
        assert data["total_count"] >= 0

    def test_extract_action_items_empty_text(self, action_items_client):
        """빈 텍스트 처리 (공백만 있는 경우 Pydantic validation 실패)"""
        # 공백만 있으면 Pydantic min_length=10 validation 실패
        response = action_items_client.post(
            "/api/v1/action-items/extract",
            json={
                "text": "   ",  # 3자 (공백) - min_length=10 실패
                "language": "ko",
            },
        )

        # Pydantic validation 에러 (422)
        assert response.status_code == 422

    def test_extract_action_items_text_too_short(self, action_items_client):
        """텍스트가 너무 짧음 (10자 미만)"""
        response = action_items_client.post(
            "/api/v1/action-items/extract",
            json={
                "text": "짧음",
            },
        )

        # Pydantic validation 에러
        assert response.status_code == 422

    def test_extract_action_items_missing_text(self, action_items_client):
        """텍스트 필드 누락"""
        response = action_items_client.post(
            "/api/v1/action-items/extract",
            json={
                "language": "ko",
            },
        )

        assert response.status_code == 422

    def test_extract_action_items_response_structure(self, action_items_client):
        """응답 구조 검증"""
        response = action_items_client.post(
            "/api/v1/action-items/extract",
            json={
                "text": "김대리가 내일까지 보고서를 작성해 주세요.",
                "language": "ko",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # 필수 필드 확인
        assert "task_id" in data
        assert isinstance(data["task_id"], str)

        assert "status" in data
        assert data["status"] == "completed"

        assert "action_items" in data
        assert isinstance(data["action_items"], list)

        assert "total_count" in data
        assert isinstance(data["total_count"], int)
        assert data["total_count"] == len(data["action_items"])

        assert "extracted_at" in data
        assert isinstance(data["extracted_at"], str)

        # ActionItem 필드 확인 (아이템이 있는 경우)
        if data["total_count"] > 0:
            item = data["action_items"][0]
            assert "id" in item
            assert "task" in item
            assert "assignee" in item
            assert "deadline" in item
            assert "priority" in item
            assert "context" in item


# ---------------------------------------------------------------------------
# POST /api/v1/action-items/meeting 테스트
# ---------------------------------------------------------------------------


class TestExtractFromMeetingAPI:
    """POST /api/v1/action-items/meeting 엔드포인트 테스트"""

    @pytest.fixture
    def meeting_client_with_redis(self):
        """Redis mock이 적용된 TestClient"""
        from backend.app.dependencies import get_db_session, get_redis_client
        from backend.app.main import app

        async def mock_db_session():
            yield AsyncMock()

        # Redis mock 생성
        mock_redis_instance = AsyncMock()
        mock_redis_instance.get = AsyncMock(return_value=None)

        async def mock_redis():
            return mock_redis_instance

        app.dependency_overrides[get_db_session] = mock_db_session
        app.dependency_overrides[get_redis_client] = mock_redis

        with patch("backend.app.main.WhisperEngine"):
            with patch("backend.app.main.DiarizationEngine"):
                with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                    with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                        client = TestClient(app, raise_server_exceptions=False)
                        yield client, mock_redis_instance

        app.dependency_overrides.clear()

    def test_extract_from_meeting_success(self, meeting_client_with_redis):
        """회의록에서 액션 아이템 추출 성공"""
        client, mock_redis = meeting_client_with_redis
        minutes_task_id = "test-task-123"

        # Redis mock 설정
        mock_redis.get = AsyncMock(
            return_value=json.dumps(
                {
                    "transcription": "회의록 전사 내용입니다. "
                    "김대리가 내일까지 보고서를 작성해 주세요. "
                    "박과장이 금요일까지 검토하겠습니다.",
                    "segments": [
                        {"text": "김대리가 내일까지 보고서를 작성해 주세요."},
                        {"text": "박과장이 금요일까지 검토하겠습니다."},
                    ],
                }
            )
        )

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": minutes_task_id,
                "include_deadlines": True,
                "include_assignees": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["total_count"] >= 1

    def test_extract_from_meeting_not_found(self, meeting_client_with_redis):
        """회의록 결과를 찾을 수 없음 (404)"""
        client, mock_redis = meeting_client_with_redis

        mock_redis.get = AsyncMock(return_value=None)

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": "non-existent-task",
            },
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "찾을 수 없습니다" in data["detail"]

    def test_extract_from_meeting_invalid_json(self, meeting_client_with_redis):
        """회의록 데이터 JSON 파싱 실패"""
        client, mock_redis = meeting_client_with_redis

        mock_redis.get = AsyncMock(return_value="invalid json{{{")

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": "test-task",
            },
        )

        assert response.status_code == 500

    def test_extract_from_meeting_text_too_short(self, meeting_client_with_redis):
        """회의록 내용이 너무 짧음"""
        client, mock_redis = meeting_client_with_redis

        mock_redis.get = AsyncMock(
            return_value=json.dumps({"transcription": "짧음"})
        )

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": "test-task",
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "너무 짧아" in data["detail"]

    def test_extract_from_meeting_transcription_field(self, meeting_client_with_redis):
        """transcription 필드에서 텍스트 추출"""
        client, mock_redis = meeting_client_with_redis

        mock_redis.get = AsyncMock(
            return_value=json.dumps({
                "transcription": "김대리가 보고서를 작성해 주세요."
            })
        )

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": "test-task",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_extract_from_meeting_text_field(self, meeting_client_with_redis):
        """text 필드에서 텍스트 추출"""
        client, mock_redis = meeting_client_with_redis

        mock_redis.get = AsyncMock(
            return_value=json.dumps({
                "text": "박과장이 검토해 주세요."
            })
        )

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": "test-task",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_extract_from_meeting_segments_field(self, meeting_client_with_redis):
        """segments 필드에서 텍스트 추출"""
        client, mock_redis = meeting_client_with_redis

        mock_redis.get = AsyncMock(
            return_value=json.dumps({
                "segments": [
                    {"text": "김대리가 보고서 작성"},
                    {"text": "박과장이 검토"},
                ]
            })
        )

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": "test-task",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_extract_from_meeting_minutes_string(self, meeting_client_with_redis):
        """minutes 필드 (문자열)에서 텍스트 추출"""
        client, mock_redis = meeting_client_with_redis

        mock_redis.get = AsyncMock(
            return_value=json.dumps({
                "minutes": "회의록 본문입니다. 김대리가 보고서를 작성해 주세요."
            })
        )

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": "test-task",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_extract_from_meeting_minutes_dict(self, meeting_client_with_redis):
        """minutes 필드 (딕셔너리)에서 텍스트 추출"""
        client, mock_redis = meeting_client_with_redis

        mock_redis.get = AsyncMock(
            return_value=json.dumps({
                "minutes": {
                    "content": "회의록 내용입니다. 박과장이 검토하겠습니다."
                }
            })
        )

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": "test-task",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_extract_from_meeting_missing_task_id(self, meeting_client_with_redis):
        """minutes_task_id 필드 누락"""
        client, _ = meeting_client_with_redis

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "include_deadlines": True,
            },
        )

        assert response.status_code == 422

    def test_extract_from_meeting_without_deadlines(self, meeting_client_with_redis):
        """기한 추출 비활성화"""
        client, mock_redis = meeting_client_with_redis

        mock_redis.get = AsyncMock(
            return_value=json.dumps({
                "transcription": "김대리가 내일까지 보고서를 작성해 주세요."
            })
        )

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": "test-task",
                "include_deadlines": False,
                "include_assignees": True,
            },
        )

        assert response.status_code == 200

    def test_extract_from_meeting_language_detection_korean(
        self, meeting_client_with_redis
    ):
        """한국어 자동 감지 (10% 이상 한글)"""
        client, mock_redis = meeting_client_with_redis

        mock_redis.get = AsyncMock(
            return_value=json.dumps({
                "transcription": "회의록입니다. 김대리가 보고서를 작성해 주세요."
            })
        )

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": "test-task",
            },
        )

        assert response.status_code == 200

    def test_extract_from_meeting_language_detection_english(
        self, meeting_client_with_redis
    ):
        """영어 자동 감지 (한글 10% 미만)"""
        client, mock_redis = meeting_client_with_redis

        mock_redis.get = AsyncMock(
            return_value=json.dumps({
                "transcription": "Meeting notes. John will prepare the report."
            })
        )

        response = client.post(
            "/api/v1/action-items/meeting",
            json={
                "minutes_task_id": "test-task",
            },
        )

        assert response.status_code == 200
