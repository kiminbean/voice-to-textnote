"""
TagService 단위 테스트
SPEC-TAG-001: 회의록 태그 CRUD 서비스
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.db.tag_models import MeetingTag
from backend.services.tag_service import TagService
from backend.schemas.tag import TagCreate, TagUpdate


@pytest.fixture
def tag_service():
    """TagService 인스턴스 fixture"""
    return TagService()


@pytest.fixture
def mock_session():
    """AsyncSession mock fixture"""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def sample_user_id():
    """테스트용 사용자 ID"""
    return uuid.uuid4()


@pytest.fixture
def sample_task_id():
    """테스트용 task_id"""
    return "test-task-123"


@pytest.fixture
def sample_tag_id():
    """테스트용 tag_id"""
    return uuid.uuid4()


@pytest.fixture
def sample_tag_create_payload(sample_task_id):
    """태그 생성 payload"""
    return TagCreate(
        task_id=sample_task_id,
        tag_type="topic",
        tag_value="AI",
        source="manual",
        confidence=0.9,
        note="Important topic"
    )


@pytest.fixture
def sample_tag_update_payload():
    """태그 수정 payload"""
    return TagUpdate(
        tag_type="category",
        tag_value="Updated",
        note="Updated note"
    )


@pytest.fixture
def sample_meeting_tag(sample_user_id, sample_task_id, sample_tag_id):
    """MeetingTag ORM 객체 mock"""
    tag = MagicMock(spec=MeetingTag)
    tag.id = sample_tag_id
    tag.user_id = sample_user_id
    tag.task_id = sample_task_id
    tag.tag_type = "topic"
    tag.tag_value = "AI"
    tag.source = "manual"
    tag.confidence = 0.9
    tag.note = "Important topic"
    return tag


# _enforce_meeting_limit 테스트

class TestEnforceMeetingLimit:
    """_enforce_meeting_limit 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_under_limit_passes(
        self, tag_service, mock_session, sample_user_id, sample_task_id
    ):
        """태그 개수가 제한 미만인 경우 통과"""
        # Setup: count = 50 (< 100)
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 50
        mock_session.execute.return_value = mock_result

        # Execute
        await tag_service._enforce_meeting_limit(mock_session, sample_user_id, sample_task_id)

        # Assert: 예외 없이 통과
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_at_limit_fails(
        self, tag_service, mock_session, sample_user_id, sample_task_id
    ):
        """태그 개수가 제한과 같은 경우 예외 발생"""
        # Setup: count = 100
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 100
        mock_session.execute.return_value = mock_result

        # Execute & Assert
        with pytest.raises(Exception) as exc_info:
            await tag_service._enforce_meeting_limit(mock_session, sample_user_id, sample_task_id)

        assert exc_info.value.status_code == 409
        assert "최대 100개까지" in exc_info.value.detail


# _get_tag_or_404 테스트

class TestGetTagOr404:
    """_get_tag_or_404 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_tag_found(
        self, tag_service, mock_session, sample_tag_id, sample_meeting_tag
    ):
        """태그 조회 성공"""
        # Setup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_meeting_tag
        mock_session.execute.return_value = mock_result

        # Execute
        result = await tag_service._get_tag_or_404(mock_session, sample_tag_id, sample_meeting_tag.user_id)

        # Assert
        assert result == sample_meeting_tag

    @pytest.mark.asyncio
    async def test_tag_not_found(
        self, tag_service, mock_session, sample_tag_id, sample_user_id
    ):
        """태그 조회 실패 - 존재하지 않음"""
        # Setup: None 반환
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Execute & Assert
        with pytest.raises(Exception) as exc_info:
            await tag_service._get_tag_or_404(mock_session, sample_tag_id, sample_user_id)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_tag_wrong_user(
        self, tag_service, mock_session, sample_tag_id, sample_meeting_tag
    ):
        """태그 조회 실패 - 사용자 불일치"""
        # Setup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_meeting_tag
        mock_session.execute.return_value = mock_result

        # Execute & Assert (다른 사용자 ID로 조회)
        with pytest.raises(Exception) as exc_info:
            await tag_service._get_tag_or_404(mock_session, sample_tag_id, uuid.uuid4())

        assert exc_info.value.status_code == 404


# create 테스트

class TestCreate:
    """create 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_create_success(
        self, tag_service, mock_session, sample_user_id, sample_tag_create_payload
    ):
        """태그 생성 성공"""
        # Setup: _enforce_meeting_limit 통과
        with patch.object(tag_service, "_enforce_meeting_limit", AsyncMock()):
            # Execute
            result = await tag_service.create(mock_session, sample_user_id, sample_tag_create_payload)

            # Assert
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()
            assert isinstance(result, MeetingTag)

    @pytest.mark.asyncio
    async def test_create_invalid_tag_type(
        self, tag_service, mock_session, sample_user_id, sample_task_id
    ):
        """잘못된 태그 타입으로 생성 시도"""
        # Setup: 유효하지 않은 태그 타입
        payload = TagCreate(
            task_id=sample_task_id,
            tag_type="invalid_type",
            tag_value="test"
        )

        # Execute & Assert
        with pytest.raises(Exception) as exc_info:
            await tag_service.create(mock_session, sample_user_id, payload)

        assert exc_info.value.status_code == 422
        assert "유효하지 않은 태그 타입" in exc_info.value.detail


# bulk_create 테스트

class TestBulkCreate:
    """bulk_create 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_bulk_create_success(
        self, tag_service, mock_session, sample_user_id, sample_task_id
    ):
        """일괄 태그 생성 성공"""
        # Setup
        tags = [
            TagCreate(task_id=sample_task_id, tag_type="topic", tag_value=f"Tag {i}")
            for i in range(3)
        ]

        # Execute
        result = await tag_service.bulk_create(mock_session, sample_user_id, sample_task_id, tags)

        # Assert
        assert len(result) == 3
        assert mock_session.add.call_count == 3
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_create_exceeds_limit(
        self, tag_service, mock_session, sample_user_id, sample_task_id
    ):
        """일괄 생성 개수 초과 시 예외 발생"""
        # Setup: 101개 태그 (최대 100개)
        tags = [
            TagCreate(task_id=sample_task_id, tag_type="topic", tag_value=f"Tag {i}")
            for i in range(101)
        ]

        # Execute & Assert
        with pytest.raises(Exception) as exc_info:
            await tag_service.bulk_create(mock_session, sample_user_id, sample_task_id, tags)

        assert exc_info.value.status_code == 422
        assert "최대 100개 태그까지" in exc_info.value.detail


# get_by_id 테스트

class TestGetById:
    """get_by_id 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_by_id_success(
        self, tag_service, mock_session, sample_tag_id, sample_meeting_tag
    ):
        """ID로 태그 조회 성공"""
        # Setup: _get_tag_or_404가 태그를 반환
        with patch.object(tag_service, "_get_tag_or_404", AsyncMock(return_value=sample_meeting_tag)):
            # Execute
            result = await tag_service.get_by_id(mock_session, sample_tag_id, sample_meeting_tag.user_id)

            # Assert
            assert result == sample_meeting_tag


# list_for_meeting 테스트

class TestListForMeeting:
    """list_for_meeting 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_list_success(
        self, tag_service, mock_session, sample_user_id, sample_task_id
    ):
        """태그 목록 조회 성공"""
        # Setup
        mock_tags = [MagicMock(spec=MeetingTag) for _ in range(3)]

        # count 쿼리 mock
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 3

        # list 쿼리 mock
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = mock_tags

        mock_session.execute.side_effect = [mock_count_result, mock_list_result]

        # Execute
        items, total = await tag_service.list_for_meeting(mock_session, sample_user_id, sample_task_id)

        # Assert
        assert items == mock_tags
        assert total == 3

    @pytest.mark.asyncio
    async def test_list_with_filters(
        self, tag_service, mock_session, sample_user_id, sample_task_id
    ):
        """필터 적용한 태그 목록 조회"""
        # Setup
        mock_tags = [MagicMock(spec=MeetingTag)]

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = mock_tags

        mock_session.execute.side_effect = [mock_count_result, mock_list_result]

        # Execute (tag_type과 source 필터 적용)
        items, total = await tag_service.list_for_meeting(
            mock_session, sample_user_id, sample_task_id, tag_type="topic", source="auto"
        )

        # Assert
        assert total == 1
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_list_empty(
        self, tag_service, mock_session, sample_user_id, sample_task_id
    ):
        """빈 태그 목록 조회"""
        # Setup
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [mock_count_result, mock_list_result]

        # Execute
        items, total = await tag_service.list_for_meeting(mock_session, sample_user_id, sample_task_id)

        # Assert
        assert items == []
        assert total == 0


# update 테스트

class TestUpdate:
    """update 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_update_success(
        self,
        tag_service,
        mock_session,
        sample_meeting_tag,
        sample_tag_update_payload,
    ):
        """태그 수정 성공"""
        # Setup: _get_tag_or_404가 태그를 반환
        with patch.object(tag_service, "_get_tag_or_404", AsyncMock(return_value=sample_meeting_tag)):
            # Execute
            result = await tag_service.update(
                mock_session, sample_meeting_tag.id, sample_meeting_tag.user_id, sample_tag_update_payload
            )

            # Assert
            assert result.tag_type == sample_tag_update_payload.tag_type
            assert result.tag_value == sample_tag_update_payload.tag_value
            assert result.note == sample_tag_update_payload.note
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_invalid_tag_type(
        self, tag_service, mock_session, sample_meeting_tag
    ):
        """잘못된 태그 타입으로 수정 시도"""
        # Setup
        payload = TagUpdate(tag_type="invalid_type")

        with patch.object(tag_service, "_get_tag_or_404", AsyncMock(return_value=sample_meeting_tag)):
            # Execute & Assert
            with pytest.raises(Exception) as exc_info:
                await tag_service.update(
                    mock_session, sample_meeting_tag.id, sample_meeting_tag.user_id, payload
                )

            assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_update_partial(
        self, tag_service, mock_session, sample_meeting_tag
    ):
        """부분 수정 (tag_value만)"""
        # Setup
        payload = TagUpdate(tag_value="Updated only")

        with patch.object(tag_service, "_get_tag_or_404", AsyncMock(return_value=sample_meeting_tag)):
            # Execute
            result = await tag_service.update(
                mock_session, sample_meeting_tag.id, sample_meeting_tag.user_id, payload
            )

            # Assert
            assert result.tag_value == "Updated only"
            # tag_type은 변경되지 않음
            assert result.tag_type == sample_meeting_tag.tag_type


# delete 테스트

class TestDelete:
    """delete 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_delete_success(
        self, tag_service, mock_session, sample_meeting_tag
    ):
        """태그 삭제 성공"""
        # Setup: _get_tag_or_404가 태그를 반환
        with patch.object(tag_service, "_get_tag_or_404", AsyncMock(return_value=sample_meeting_tag)):
            # Execute
            await tag_service.delete(mock_session, sample_meeting_tag.id, sample_meeting_tag.user_id)

            # Assert
            mock_session.delete.assert_called_once_with(sample_meeting_tag)
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, tag_service, mock_session, sample_tag_id, sample_user_id
    ):
        """존재하지 않는 태그 삭제 시도"""
        # Setup: _get_tag_or_404가 404 예외 발생
        from fastapi import HTTPException

        http_exc = HTTPException(status_code=404, detail="Not found")

        with patch.object(tag_service, "_get_tag_or_404", AsyncMock(side_effect=http_exc)):
            # Execute & Assert
            with pytest.raises(HTTPException) as exc_info:
                await tag_service.delete(mock_session, sample_tag_id, sample_user_id)

            assert exc_info.value.status_code == 404


# delete_all_for_meeting 테스트

class TestDeleteAllForMeeting:
    """delete_all_for_meeting 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_delete_all_success(
        self, tag_service, mock_session, sample_user_id, sample_task_id
    ):
        """회의록 태그 전체 삭제 성공"""
        # Setup
        mock_tags = [MagicMock(spec=MeetingTag) for _ in range(3)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_tags
        mock_session.execute.return_value = mock_result

        # Execute
        count = await tag_service.delete_all_for_meeting(mock_session, sample_user_id, sample_task_id)

        # Assert
        assert count == 3
        assert mock_session.delete.call_count == 3
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_with_source_filter(
        self, tag_service, mock_session, sample_user_id, sample_task_id
    ):
        """소스 필터 적용하여 삭제"""
        # Setup
        mock_tags = [MagicMock(spec=MeetingTag)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_tags
        mock_session.execute.return_value = mock_result

        # Execute (source="auto" 필터)
        count = await tag_service.delete_all_for_meeting(
            mock_session, sample_user_id, sample_task_id, source="auto"
        )

        # Assert
        assert count == 1

    @pytest.mark.asyncio
    async def test_delete_all_empty(
        self, tag_service, mock_session, sample_user_id, sample_task_id
    ):
        """삭제할 태그가 없는 경우"""
        # Setup: 빈 목록
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        # Execute
        count = await tag_service.delete_all_for_meeting(mock_session, sample_user_id, sample_task_id)

        # Assert
        assert count == 0
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_called_once()
