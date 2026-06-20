"""
VersionService 단위 테스트
SPEC-VERSION-001: 회의록 버전 관리 서비스
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from backend.db.version_models import MinutesVersion
from backend.schemas.version import VersionCreate
from backend.services.version_service import VersionService


@pytest.fixture
def version_service():
    """VersionService 인스턴스 fixture"""
    return VersionService()


@pytest.fixture
def mock_session():
    """AsyncSession mock fixture"""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def sample_task_id():
    """테스트용 task_id"""
    return "test-task-123"


@pytest.fixture
def sample_version_id():
    """테스트용 version_id"""
    return uuid.uuid4()


@pytest.fixture
def sample_author_id():
    """테스트용 author_id"""
    return uuid.uuid4()


@pytest.fixture
def sample_version_create_payload():
    """버전 생성 payload"""
    return VersionCreate(
        content={"summary_text": "Test summary", "sections": [], "action_items": []},
        change_summary="Initial version",
    )


@pytest.fixture
def sample_minutes_version(sample_task_id, sample_version_id, sample_author_id):
    """MinutesVersion ORM 객체 mock"""
    version = MagicMock(spec=MinutesVersion)
    version.id = sample_version_id
    version.task_id = sample_task_id
    version.version_number = 1
    version.content = {"summary_text": "Test summary"}
    version.change_summary = "Initial version"
    version.author_id = sample_author_id
    return version


# _ensure_task_exists 테스트


class TestEnsureTaskExists:
    """_ensure_task_exists 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_task_exists_passes(self, version_service, mock_session, sample_task_id):
        """task가 존재하는 경우 통과"""
        # Setup: first()가 truthy 반환
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock()  # None이 아님
        mock_session.execute.return_value = mock_result

        # Execute
        await version_service._ensure_task_exists(mock_session, sample_task_id)

        # Assert: 예외 없이 통과
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_not_found_raises(self, version_service, mock_session, sample_task_id):
        """task가 존재하지 않는 경우 404 예외 발생"""
        # Setup: first()가 None 반환
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result

        # Execute & Assert
        with pytest.raises(Exception) as exc_info:
            await version_service._ensure_task_exists(mock_session, sample_task_id)

        assert exc_info.value.status_code == 404
        assert "회의록을 찾을 수 없습니다" in exc_info.value.detail


# _next_version_number 테스트


class TestNextVersionNumber:
    """_next_version_number 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_no_existing_version(self, version_service, mock_session, sample_task_id):
        """기존 버전이 없는 경우 1 반환"""
        # Setup: scalar_one_or_none()가 None 반환
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Execute
        result = await version_service._next_version_number(mock_session, sample_task_id)

        # Assert
        assert result == 1

    @pytest.mark.asyncio
    async def test_with_existing_versions(self, version_service, mock_session, sample_task_id):
        """기존 최대 버전이 5인 경우 6 반환"""
        # Setup: scalar_one_or_none()가 5 반환
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 5
        mock_session.execute.return_value = mock_result

        # Execute
        result = await version_service._next_version_number(mock_session, sample_task_id)

        # Assert
        assert result == 6


# create_version 테스트


class TestCreateVersion:
    """create_version 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_create_success(
        self,
        version_service,
        mock_session,
        sample_task_id,
        sample_author_id,
        sample_version_create_payload,
    ):
        """버전 생성 성공"""
        # Setup: _ensure_task_exists, _next_version_number 통과
        with patch.object(version_service, "_ensure_task_exists", AsyncMock()):
            with patch.object(version_service, "_next_version_number", AsyncMock(return_value=1)):
                # Execute
                result = await version_service.create_version(
                    mock_session, sample_task_id, sample_version_create_payload, sample_author_id
                )

                # Assert
                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()
                mock_session.refresh.assert_called_once()
                assert isinstance(result, MinutesVersion)

    @pytest.mark.asyncio
    async def test_create_without_author(
        self,
        version_service,
        mock_session,
        sample_task_id,
        sample_version_create_payload,
    ):
        """author_id 없이 버전 생성"""
        with patch.object(version_service, "_ensure_task_exists", AsyncMock()):
            with patch.object(version_service, "_next_version_number", AsyncMock(return_value=1)):
                # Execute
                result = await version_service.create_version(
                    mock_session, sample_task_id, sample_version_create_payload
                )

                # Assert
                assert result.author_id is None

    @pytest.mark.asyncio
    async def test_create_retries_after_integrity_error(
        self,
        version_service,
        mock_session,
        sample_task_id,
        sample_version_create_payload,
    ):
        """버전 번호 충돌이 한 번 발생하면 rollback 후 다음 번호로 재시도한다."""
        integrity_error = IntegrityError("insert", {}, Exception("duplicate version"))
        mock_session.commit.side_effect = [integrity_error, None]

        with (
            patch.object(version_service, "_ensure_task_exists", AsyncMock()),
            patch.object(version_service, "_next_version_number", AsyncMock(side_effect=[1, 2])),
        ):
            result = await version_service.create_version(
                mock_session,
                sample_task_id,
                sample_version_create_payload,
            )

        assert isinstance(result, MinutesVersion)
        assert result.version_number == 2
        assert mock_session.commit.await_count == 2
        mock_session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_raises_conflict_after_three_integrity_errors(
        self,
        version_service,
        mock_session,
        sample_task_id,
        sample_version_create_payload,
    ):
        """버전 번호 충돌이 3회 반복되면 409 응답을 반환한다."""
        mock_session.commit.side_effect = [
            IntegrityError("insert", {}, Exception("duplicate version"))
            for _ in range(3)
        ]

        with (
            patch.object(version_service, "_ensure_task_exists", AsyncMock()),
            patch.object(version_service, "_next_version_number", AsyncMock(side_effect=[1, 2, 3])),
        ):
            with pytest.raises(Exception) as exc_info:
                await version_service.create_version(
                    mock_session,
                    sample_task_id,
                    sample_version_create_payload,
                )

        assert exc_info.value.status_code == 409
        assert "버전 생성 충돌" in exc_info.value.detail
        assert mock_session.commit.await_count == 3
        assert mock_session.rollback.await_count == 3


# list_versions 테스트


class TestListVersions:
    """list_versions 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_list_success(self, version_service, mock_session, sample_task_id):
        """버전 목록 조회 성공"""
        # Setup
        mock_versions = [MagicMock(spec=MinutesVersion) for _ in range(3)]

        # _ensure_task_exists 통과
        with patch.object(version_service, "_ensure_task_exists", AsyncMock()):
            # count 쿼리 mock
            mock_count_result = MagicMock()
            mock_count_result.scalar_one.return_value = 3

            # list 쿼리 mock
            mock_list_result = MagicMock()
            mock_list_result.scalars.return_value.all.return_value = mock_versions

            mock_session.execute.side_effect = [mock_count_result, mock_list_result]

            # Execute
            items, total = await version_service.list_versions(mock_session, sample_task_id)

            # Assert
            assert items == mock_versions
            assert total == 3

    @pytest.mark.asyncio
    async def test_list_empty(self, version_service, mock_session, sample_task_id):
        """빈 버전 목록 조회"""
        # Setup
        with patch.object(version_service, "_ensure_task_exists", AsyncMock()):
            mock_count_result = MagicMock()
            mock_count_result.scalar_one.return_value = 0

            mock_list_result = MagicMock()
            mock_list_result.scalars.return_value.all.return_value = []

            mock_session.execute.side_effect = [mock_count_result, mock_list_result]

            # Execute
            items, total = await version_service.list_versions(mock_session, sample_task_id)

            # Assert
            assert items == []
            assert total == 0


# get_version 테스트


class TestGetVersion:
    """get_version 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_found(
        self, version_service, mock_session, sample_task_id, sample_minutes_version
    ):
        """버전 조회 성공"""
        # Setup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_minutes_version
        mock_session.execute.return_value = mock_result

        # Execute
        result = await version_service.get_version(
            mock_session, sample_task_id, sample_minutes_version.id
        )

        # Assert
        assert result == sample_minutes_version

    @pytest.mark.asyncio
    async def test_get_not_found(
        self, version_service, mock_session, sample_task_id, sample_version_id
    ):
        """버전 조회 실패 - 존재하지 않음"""
        # Setup: None 반환
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Execute & Assert
        with pytest.raises(Exception) as exc_info:
            await version_service.get_version(mock_session, sample_task_id, sample_version_id)

        assert exc_info.value.status_code == 404


# compute_diff 테스트


class TestComputeDiff:
    """compute_diff 메서드 테스트"""

    def test_compute_diff_no_change(self, version_service):
        """변경 없는 경우 diff 계산"""
        old_content = {"summary_text": "Same content"}
        new_content = {"summary_text": "Same content"}

        result = version_service.compute_diff(old_content, new_content)

        assert result["changed"] is False
        assert result["added_lines"] == 0
        assert result["removed_lines"] == 0
        assert "---" not in result["unified_diff"]

    def test_compute_diff_with_change(self, version_service):
        """내용 변경 있는 경우 diff 계산"""
        old_content = {"summary_text": "Old content"}
        new_content = {"summary_text": "New content"}

        result = version_service.compute_diff(old_content, new_content)

        assert result["changed"] is True
        assert result["added_lines"] > 0
        assert result["removed_lines"] > 0

    def test_compute_diff_with_sections(self, version_service):
        """섹션 포함 diff 계산"""
        old_content = {
            "summary_text": "Summary",
            "sections": [{"title": "Section 1", "content": "Content 1"}],
        }
        new_content = {
            "summary_text": "Summary",
            "sections": [{"title": "Section 1", "content": "Content 2"}],
        }

        result = version_service.compute_diff(old_content, new_content)

        assert result["changed"] is True

    def test_compute_diff_with_action_items(self, version_service):
        """action items 포함 diff 계산"""
        old_content = {
            "summary_text": "Summary",
            "action_items": [{"text": "Task 1"}],
        }
        new_content = {
            "summary_text": "Summary",
            "action_items": [{"text": "Task 1"}, {"text": "Task 2"}],
        }

        result = version_service.compute_diff(old_content, new_content)

        assert result["changed"] is True


# compute_structured_diff 테스트


class TestComputeStructuredDiff:
    """compute_structured_diff 메서드 테스트"""

    def test_structured_diff_no_change(self, version_service):
        """변경 없는 경우 구조화 diff 계산"""
        old_content = {
            "summary_text": "Same summary",
            "sections": [],
            "action_items": [],
        }
        new_content = {
            "summary_text": "Same summary",
            "sections": [],
            "action_items": [],
        }

        result = version_service.compute_structured_diff(old_content, new_content)

        assert result["changed"] is False
        assert result["total_changes"] == 0

    def test_structured_diff_summary_changed(self, version_service):
        """요약 변경 있는 경우"""
        old_content = {
            "summary_text": "Old summary",
            "sections": [],
            "action_items": [],
        }
        new_content = {
            "summary_text": "New summary",
            "sections": [],
            "action_items": [],
        }

        result = version_service.compute_structured_diff(old_content, new_content)

        assert result["summary_text"]["changed"] is True
        assert result["summary_text"]["before"] == "Old summary"
        assert result["summary_text"]["after"] == "New summary"
        assert result["total_changes"] == 1

    def test_structured_diff_section_added(self, version_service):
        """섹션 추가"""
        old_content = {
            "summary_text": "Summary",
            "sections": [],
            "action_items": [],
        }
        new_content = {
            "summary_text": "Summary",
            "sections": [{"title": "New Section", "content": "Content"}],
            "action_items": [],
        }

        result = version_service.compute_structured_diff(old_content, new_content)

        assert len(result["sections"]["added"]) == 1
        assert result["sections"]["added"][0]["title"] == "New Section"
        assert result["total_changes"] == 1

    def test_structured_diff_section_removed(self, version_service):
        """섹션 삭제"""
        old_content = {
            "summary_text": "Summary",
            "sections": [{"title": "Old Section", "content": "Content"}],
            "action_items": [],
        }
        new_content = {
            "summary_text": "Summary",
            "sections": [],
            "action_items": [],
        }

        result = version_service.compute_structured_diff(old_content, new_content)

        assert len(result["sections"]["removed"]) == 1
        assert result["sections"]["removed"][0]["title"] == "Old Section"

    def test_structured_diff_section_modified(self, version_service):
        """섹션 수정"""
        old_content = {
            "summary_text": "Summary",
            "sections": [{"title": "Section", "content": "Old content"}],
            "action_items": [],
        }
        new_content = {
            "summary_text": "Summary",
            "sections": [{"title": "Section", "content": "New content"}],
            "action_items": [],
        }

        result = version_service.compute_structured_diff(old_content, new_content)

        assert len(result["sections"]["modified"]) == 1
        assert result["sections"]["modified"][0]["title"] == "Section"

    def test_structured_diff_action_item_added(self, version_service):
        """action item 추가"""
        old_content = {
            "summary_text": "Summary",
            "sections": [],
            "action_items": [],
        }
        new_content = {
            "summary_text": "Summary",
            "sections": [],
            "action_items": [{"id": "1", "text": "New task"}],
        }

        result = version_service.compute_structured_diff(old_content, new_content)

        assert len(result["action_items"]["added"]) == 1
        assert result["total_changes"] == 1

    def test_structured_diff_action_item_removed(self, version_service):
        """action item 삭제"""
        old_content = {
            "summary_text": "Summary",
            "sections": [],
            "action_items": [{"id": "1", "text": "Task"}],
        }
        new_content = {
            "summary_text": "Summary",
            "sections": [],
            "action_items": [],
        }

        result = version_service.compute_structured_diff(old_content, new_content)

        assert len(result["action_items"]["removed"]) == 1

    def test_structured_diff_action_item_modified(self, version_service):
        """action item 수정"""
        old_content = {
            "summary_text": "Summary",
            "sections": [],
            "action_items": [{"id": "1", "text": "Old task"}],
        }
        new_content = {
            "summary_text": "Summary",
            "sections": [],
            "action_items": [{"id": "1", "text": "New task"}],
        }

        result = version_service.compute_structured_diff(old_content, new_content)

        assert len(result["action_items"]["modified"]) == 1
        assert result["total_changes"] == 1

    def test_structured_diff_multiple_changes(self, version_service):
        """여러 변경사항 있는 경우"""
        old_content = {
            "summary_text": "Old",
            "sections": [{"title": "S1", "content": "C1"}],
            "action_items": [{"id": "1", "text": "T1"}],
        }
        new_content = {
            "summary_text": "New",
            "sections": [{"title": "S2", "content": "C2"}],
            "action_items": [{"id": "2", "text": "T2"}],
        }

        result = version_service.compute_structured_diff(old_content, new_content)

        assert result["summary_text"]["changed"] is True
        assert len(result["sections"]["removed"]) == 1  # S1 removed
        assert len(result["sections"]["added"]) == 1  # S2 added
        assert len(result["action_items"]["removed"]) == 1  # T1 removed
        assert len(result["action_items"]["added"]) == 1  # T2 added
        assert result["total_changes"] == 5


# delete_version 테스트


class TestDeleteVersion:
    """delete_version 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_delete_success(
        self, version_service, mock_session, sample_task_id, sample_minutes_version
    ):
        """버전 삭제 성공"""
        # Setup: get_version이 version을 반환
        with patch.object(
            version_service, "get_version", AsyncMock(return_value=sample_minutes_version)
        ):
            # Execute
            await version_service.delete_version(
                mock_session, sample_task_id, sample_minutes_version.id
            )

            # Assert
            mock_session.delete.assert_called_once_with(sample_minutes_version)
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, version_service, mock_session, sample_task_id, sample_version_id
    ):
        """존재하지 않는 버전 삭제 시도"""
        # Setup: get_version이 404 예외 발생
        from fastapi import HTTPException

        http_exc = HTTPException(status_code=404, detail="Not found")

        with patch.object(version_service, "get_version", AsyncMock(side_effect=http_exc)):
            # Execute & Assert
            with pytest.raises(HTTPException) as exc_info:
                await version_service.delete_version(
                    mock_session, sample_task_id, sample_version_id
                )

            assert exc_info.value.status_code == 404
