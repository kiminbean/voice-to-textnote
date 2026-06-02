"""
SPEC-TAG-001: Tags API v5 테스트
커버되지 않은 라인을 위한 추가 테스트

커버되지 않은 라인:
- 52, 55, 56, 57: auto_tag_meeting 함수 내부 (AI 태그 추출 및 DB 저장)
- 67, 68, 70: bulk_create 호출 및 응답 생성
- 89: create_tag 반환
- 108: list_tags 반환
- 123: get_tag 반환
- 135: update_tag 반환
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.db.auth_models import User

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def tags_client():
    """태그 API 테스트용 TestClient"""
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.main import app

    async def mock_db_session():
        yield AsyncMock()

    async def mock_current_user():
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        yield mock_user

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_current_user

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# auto_tag_meeting 엔드포인트 테스트 (라인 40-74)
# ---------------------------------------------------------------------------


class TestAutoTagMeetingEndpoint:
    """AI 자동 태깅 엔드포인트 테스트"""

    def test_auto_tag_meeting_success(self, tags_client) -> None:
        """AI 자동 태깅 성공 (라인 52-70 커버)"""
        from backend.app.api.v1 import tags

        # Mock the AI tagging engine
        mock_tags = [
            {"tag_type": "topic", "tag_value": "Strategy", "confidence": 0.95},
            {"tag_type": "category", "tag_value": "Planning", "confidence": 0.88},
        ]

        mock_created_tags = [
            MagicMock(
                id=uuid.uuid4(),
                task_id="task-123",
                tag_type="topic",
                tag_value="Strategy",
                source="auto",
                confidence=0.95,
                note=None,
                created_at="2024-01-01T00:00:00Z"
            ),
            MagicMock(
                id=uuid.uuid4(),
                task_id="task-123",
                tag_type="category",
                tag_value="Planning",
                source="auto",
                confidence=0.88,
                note=None,
                created_at="2024-01-01T00:00:00Z"
            ),
        ]

        with patch.object(tags, "generate_auto_tags", return_value=mock_tags):
            with patch.object(tags._service, "bulk_create", return_value=mock_created_tags):
                response = tags_client.post(
                    "/api/v1/tags/auto",
                    json={
                        "task_id": "task-123",
                        "content": "Discuss strategy for Q4 planning",
                        "max_tags": 5
                    }
                )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["task_id"] == "task-123"
        assert data["total"] == 2
        assert len(data["tags"]) == 2

    def test_auto_tag_meeting_empty_tags(self, tags_client) -> None:
        """AI 자동 태깅 결과가 없는 경우"""
        from backend.app.api.v1 import tags

        with patch.object(tags, "generate_auto_tags", return_value=[]):
            with patch.object(tags._service, "bulk_create", return_value=[]):
                response = tags_client.post(
                    "/api/v1/tags/auto",
                    json={
                        "task_id": "task-123",
                        "content": "Short content",
                        "max_tags": 5
                    }
                )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["total"] == 0
        assert data["tags"] == []


# ---------------------------------------------------------------------------
# create_tag 엔드포인트 테스트 (라인 77-89)
# ---------------------------------------------------------------------------


class TestCreateTagEndpoint:
    """수동 태그 생성 엔드포인트 테스트"""

    def test_create_tag_success(self, tags_client) -> None:
        """수동 태그 생성 성공 (라인 89 커버)"""
        from backend.app.api.v1 import tags

        mock_tag = MagicMock(
            id=uuid.uuid4(),
            task_id="task-123",
            tag_type="topic",
            tag_value="Important",
            source="manual",
            confidence=None,
            note=None,
            created_at="2024-01-01T00:00:00Z"
        )

        with patch.object(tags._service, "create", return_value=mock_tag):
            response = tags_client.post(
                "/api/v1/tags",
                json={
                    "task_id": "task-123",
                    "tag_type": "topic",
                    "tag_value": "Important"
                }
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["task_id"] == "task-123"
        assert data["tag_value"] == "Important"


# ---------------------------------------------------------------------------
# list_tags 엔드포인트 테스트 (라인 92-112)
# ---------------------------------------------------------------------------


class TestListTagsEndpoint:
    """태그 목록 조회 엔드포인트 테스트"""

    def test_list_tags_success(self, tags_client) -> None:
        """태그 목록 조회 성공 (라인 108 커버)"""
        from backend.app.api.v1 import tags

        mock_tags = [
            MagicMock(
                id=uuid.uuid4(),
                task_id="task-123",
                tag_type="topic",
                tag_value="Strategy",
                source="manual",
                confidence=None,
                note=None,
                created_at="2024-01-01T00:00:00Z"
            ),
        ]

        with patch.object(tags._service, "list_for_meeting", return_value=(mock_tags, 1)):
            response = tags_client.get(
                "/api/v1/tags?task_id=task-123&page=1&page_size=100"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["task_id"] == "task-123"
        assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# get_tag 엔드포인트 테스트 (라인 115-123)
# ---------------------------------------------------------------------------


class TestGetTagEndpoint:
    """태그 단건 조회 엔드포인트 테스트"""

    def test_get_tag_success(self, tags_client) -> None:
        """태그 단건 조회 성공 (라인 123 커버)"""
        from backend.app.api.v1 import tags

        mock_tag = MagicMock(
            id=uuid.uuid4(),
            task_id="task-123",
            tag_type="topic",
            tag_value="Strategy",
            source="manual",
            confidence=None,
            note=None,
            created_at="2024-01-01T00:00:00Z"
        )

        tag_id = uuid.uuid4()
        with patch.object(tags._service, "get_by_id", return_value=mock_tag):
            response = tags_client.get(f"/api/v1/tags/{tag_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["tag_value"] == "Strategy"


# ---------------------------------------------------------------------------
# update_tag 엔드포인트 테스트 (라인 126-135)
# ---------------------------------------------------------------------------


class TestUpdateTagEndpoint:
    """태그 수정 엔드포인트 테스트"""

    def test_update_tag_success(self, tags_client) -> None:
        """태그 수정 성공 (라인 135 커버)"""
        from backend.app.api.v1 import tags

        mock_tag = MagicMock(
            id=uuid.uuid4(),
            task_id="task-123",
            tag_type="topic",
            tag_value="Updated Strategy",
            source="manual",
            confidence=None,
            note=None,
            created_at="2024-01-01T00:00:00Z"
        )

        tag_id = uuid.uuid4()
        with patch.object(tags._service, "update", return_value=mock_tag):
            response = tags_client.patch(
                f"/api/v1/tags/{tag_id}",
                json={"tag_value": "Updated Strategy"}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["tag_value"] == "Updated Strategy"


# ---------------------------------------------------------------------------
# delete_tag 엔드포인트 테스트 (라인 138-145)
# ---------------------------------------------------------------------------


class TestDeleteTagEndpoint:
    """태그 삭제 엔드포인트 테스트"""

    def test_delete_tag_success(self, tags_client) -> None:
        """태그 삭제 성공"""
        from backend.app.api.v1 import tags

        tag_id = uuid.uuid4()
        with patch.object(tags._service, "delete", new_callable=AsyncMock):
            response = tags_client.delete(f"/api/v1/tags/{tag_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
