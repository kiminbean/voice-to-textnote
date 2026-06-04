"""
SPEC-TAG-001: 회의록 태그 API 유닛 테스트
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.schemas.tag import TagCreate, TagUpdate


@pytest.fixture
def mock_db():
    """Mock async DB session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def task_id():
    return "test-task-123"


class TestTagService:
    """TagService 단위 테스트."""

    async def test_create_tag(self, mock_db, user_id, task_id):
        """태그 생성 테스트."""
        from backend.services.tag_service import TagService

        service = TagService()

        # mock count query (limit check) — scalar_one은 이미 값 반환
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_db.execute = AsyncMock(return_value=mock_result)

        payload = TagCreate(
            task_id=task_id,
            tag_type="topic",
            tag_value="프로젝트A",
        )

        await service.create(mock_db, user_id, payload)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    async def test_create_tag_invalid_type(self, mock_db, user_id, task_id):
        """유효하지 않은 태그 타입 테스트."""
        from fastapi import HTTPException

        from backend.services.tag_service import TagService

        service = TagService()

        payload = TagCreate(
            task_id=task_id,
            tag_type="invalid_type",
            tag_value="test",
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create(mock_db, user_id, payload)
        assert exc_info.value.status_code == 422

    async def test_list_tags_for_meeting(self, mock_db, user_id, task_id):
        """회의록 태그 목록 조회 테스트."""
        from backend.services.tag_service import TagService

        service = TagService()

        # mock count result
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 2

        # mock list result
        mock_list_result = MagicMock()
        mock_tag1 = MagicMock()
        mock_tag2 = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = [mock_tag1, mock_tag2]

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        items, total = await service.list_for_meeting(mock_db, user_id, task_id)
        assert total == 2
        assert len(items) == 2


class TestTaggingEngine:
    """자동 태깅 엔진 테스트."""

    async def test_shared_http_client_can_be_created_and_closed(self):
        """공유 httpx 클라이언트는 lazy init 후 명시적으로 닫힌다."""
        from backend.ml import tagging_engine

        client = tagging_engine._get_http_client()
        assert client.is_closed is False

        await tagging_engine.close_http_client()

        assert tagging_engine._http_client is None

    def test_rule_based_tags_basic(self):
        """규칙 기반 태깅 기본 테스트."""
        from backend.ml.tagging_engine import _rule_based_tags

        content = "오늘 스프린트 회의에서 프로젝트 진행 상황을 리뷰했습니다. 긴급하게 처리해야 할 버그가 발견되었습니다."
        tags = _rule_based_tags(content, 10)

        # 최소 카테고리 + 중요도 + 주제 포함
        assert len(tags) >= 2

        types = {t["tag_type"] for t in tags}
        assert "category" in types
        assert "priority" in types

    def test_rule_based_tags_urgent(self):
        """긴급 감지 테스트."""
        from backend.ml.tagging_engine import _rule_based_tags

        content = "이것은 긴급 사항입니다. 즉시 처리가 필요합니다."
        tags = _rule_based_tags(content, 5)

        priority_tags = [t for t in tags if t["tag_type"] == "priority"]
        assert len(priority_tags) == 1
        assert priority_tags[0]["tag_value"] == "긴급"

    def test_rule_based_tags_sprint_category(self):
        """스프린트 카테고리 감지 테스트."""
        from backend.ml.tagging_engine import _rule_based_tags

        content = "스프린트 백로그를 정리하고 다음 스프린트 계획을 세웠습니다."
        tags = _rule_based_tags(content, 5)

        category_tags = [t for t in tags if t["tag_type"] == "category"]
        assert len(category_tags) == 1
        assert category_tags[0]["tag_value"] == "스프린트"


class TestTagSchemas:
    """태그 스키마 유효성 테스트."""

    def test_tag_create_valid(self):
        """유효한 태그 생성 스키마."""
        tag = TagCreate(
            task_id="task-123",
            tag_type="topic",
            tag_value="프로젝트A",
            source="manual",
            confidence=0.9,
        )
        assert tag.task_id == "task-123"
        assert tag.confidence == 0.9

    def test_tag_create_confidence_range(self):
        """confidence 범위 검증."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            TagCreate(
                task_id="task-123",
                tag_type="topic",
                tag_value="test",
                confidence=1.5,  # 범위 초과
            )

    def test_tag_update_partial(self):
        """부분 업데이트 스키마."""
        update = TagUpdate(tag_value="새값")
        assert update.tag_type is None
        assert update.tag_value == "새값"

    def test_auto_tag_request_max_tags_validation(self):
        """자동 태깅 요청 max_tags 검증."""
        import pydantic

        from backend.schemas.tag import AutoTagRequest

        # 유효
        req = AutoTagRequest(task_id="t1", content="some content", max_tags=15)
        assert req.max_tags == 15

        # 범위 초과
        with pytest.raises(pydantic.ValidationError):
            AutoTagRequest(task_id="t1", content="some content", max_tags=50)
