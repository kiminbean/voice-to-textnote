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


@pytest.fixture
def tags_client():
    from backend.app.dependencies import get_current_user, get_db_session
    from backend.app.api.v1.tags import get_tag_service
    from backend.app.main import app

    async def mock_db_session():
        yield AsyncMock()

    async def mock_current_user():
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        yield mock_user

    svc_mock = AsyncMock()

    async def override_svc():
        return svc_mock

    app.dependency_overrides[get_db_session] = mock_db_session
    app.dependency_overrides[get_current_user] = mock_current_user
    app.dependency_overrides[get_tag_service] = override_svc

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield TestClient(app, raise_server_exceptions=False), svc_mock

    app.dependency_overrides.clear()


class TestAutoTagMeetingEndpoint:
    def test_auto_tag_meeting_success(self, tags_client) -> None:
        client, mock_svc = tags_client

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
                created_at="2024-01-01T00:00:00Z",
            ),
            MagicMock(
                id=uuid.uuid4(),
                task_id="task-123",
                tag_type="category",
                tag_value="Planning",
                source="auto",
                confidence=0.88,
                note=None,
                created_at="2024-01-01T00:00:00Z",
            ),
        ]

        from backend.app.api.v1 import tags as tags_mod

        with patch.object(tags_mod, "generate_auto_tags", return_value=mock_tags):
            mock_svc.bulk_create = AsyncMock(return_value=mock_created_tags)
            response = client.post(
                "/api/v1/tags/auto",
                json={
                    "task_id": "task-123",
                    "content": "Discuss strategy for Q4 planning",
                    "max_tags": 5,
                },
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["task_id"] == "task-123"
        assert data["total"] == 2
        assert len(data["tags"]) == 2

    def test_auto_tag_meeting_empty_tags(self, tags_client) -> None:
        client, mock_svc = tags_client

        from backend.app.api.v1 import tags as tags_mod

        with patch.object(tags_mod, "generate_auto_tags", return_value=[]):
            mock_svc.bulk_create = AsyncMock(return_value=[])
            response = client.post(
                "/api/v1/tags/auto",
                json={"task_id": "task-123", "content": "Short content", "max_tags": 5},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["total"] == 0
        assert data["tags"] == []


class TestCreateTagEndpoint:
    def test_create_tag_success(self, tags_client) -> None:
        client, mock_svc = tags_client

        mock_tag = MagicMock(
            id=uuid.uuid4(),
            task_id="task-123",
            tag_type="topic",
            tag_value="Important",
            source="manual",
            confidence=None,
            note=None,
            created_at="2024-01-01T00:00:00Z",
        )

        mock_svc.create = AsyncMock(return_value=mock_tag)
        response = client.post(
            "/api/v1/tags",
            json={"task_id": "task-123", "tag_type": "topic", "tag_value": "Important"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["task_id"] == "task-123"
        assert data["tag_value"] == "Important"


class TestListTagsEndpoint:
    def test_list_tags_success(self, tags_client) -> None:
        client, mock_svc = tags_client

        mock_tags = [
            MagicMock(
                id=uuid.uuid4(),
                task_id="task-123",
                tag_type="topic",
                tag_value="Strategy",
                source="manual",
                confidence=None,
                note=None,
                created_at="2024-01-01T00:00:00Z",
            ),
        ]

        mock_svc.list_for_meeting = AsyncMock(return_value=(mock_tags, 1))
        response = client.get("/api/v1/tags?task_id=task-123&page=1&page_size=100")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["task_id"] == "task-123"
        assert len(data["items"]) == 1


class TestGetTagEndpoint:
    def test_get_tag_success(self, tags_client) -> None:
        client, mock_svc = tags_client

        mock_tag = MagicMock(
            id=uuid.uuid4(),
            task_id="task-123",
            tag_type="topic",
            tag_value="Strategy",
            source="manual",
            confidence=None,
            note=None,
            created_at="2024-01-01T00:00:00Z",
        )

        tag_id = uuid.uuid4()
        mock_svc.get_by_id = AsyncMock(return_value=mock_tag)
        response = client.get(f"/api/v1/tags/{tag_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["tag_value"] == "Strategy"


class TestUpdateTagEndpoint:
    def test_update_tag_success(self, tags_client) -> None:
        client, mock_svc = tags_client

        mock_tag = MagicMock(
            id=uuid.uuid4(),
            task_id="task-123",
            tag_type="topic",
            tag_value="Updated Strategy",
            source="manual",
            confidence=None,
            note=None,
            created_at="2024-01-01T00:00:00Z",
        )

        tag_id = uuid.uuid4()
        mock_svc.update = AsyncMock(return_value=mock_tag)
        response = client.patch(f"/api/v1/tags/{tag_id}", json={"tag_value": "Updated Strategy"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["tag_value"] == "Updated Strategy"


class TestDeleteTagEndpoint:
    def test_delete_tag_success(self, tags_client) -> None:
        client, mock_svc = tags_client

        tag_id = uuid.uuid4()
        mock_svc.delete = AsyncMock(return_value=None)
        response = client.delete(f"/api/v1/tags/{tag_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
