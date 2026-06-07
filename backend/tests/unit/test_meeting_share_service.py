"""
SPEC-TEAM-001 REQ-TEAM-005: MeetingShareService 단위 테스트

- test_share_meeting_success: 회의록 팀 공유 성공
- test_share_meeting_duplicate_conflict: 중복 공유 409 Conflict
- test_unshare_meeting_success: 공유 해제 성공
- test_list_team_meetings: 팀 회의록 목록
- test_list_user_meetings: 사용자 회의록 목록
- test_get_or_create_ownership: 소유권 레코드 조회/생성
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.auth_models import MeetingOwnership
from backend.db.models import TaskResult

# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def meeting_service():
    """MeetingShareService 인스턴스"""
    from backend.services.meeting_share_service import MeetingShareService

    return MeetingShareService()


@pytest.fixture
def mock_session():
    """SQLAlchemy AsyncSession mock"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_task_id() -> str:
    """테스트용 task_id"""
    return "test-task-id-001"


@pytest.fixture
def sample_owner_id() -> uuid.UUID:
    """테스트용 owner UUID"""
    return uuid.uuid4()


@pytest.fixture
def sample_team_id() -> uuid.UUID:
    """테스트용 team UUID"""
    return uuid.uuid4()


@pytest.fixture
def sample_ownership(sample_task_id, sample_owner_id, sample_team_id) -> MeetingOwnership:
    """테스트용 MeetingOwnership"""
    ownership = MeetingOwnership()
    ownership.id = uuid.uuid4()
    ownership.task_id = sample_task_id
    ownership.owner_id = sample_owner_id
    ownership.team_id = sample_team_id
    ownership.shared_at = datetime.now(UTC).replace(tzinfo=None)
    ownership.created_at = datetime.now(UTC).replace(tzinfo=None)
    return ownership


@pytest.fixture
def sample_task_result(sample_task_id) -> TaskResult:
    """테스트용 TaskResult"""
    task = TaskResult()
    task.id = uuid.uuid4()
    task.task_id = sample_task_id
    task.task_type = "transcription"
    task.status = "completed"
    task.created_at = datetime.now(UTC).replace(tzinfo=None)
    task.updated_at = datetime.now(UTC).replace(tzinfo=None)
    return task


# ---------------------------------------------------------------------------
# share_meeting 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_share_meeting_success(
    meeting_service, mock_session, sample_task_id, sample_owner_id, sample_team_id
):
    """
    회의록 팀 공유 성공
    REQ-TEAM-005
    """
    # 중복 공유 없음 (None 반환)
    mock_existing_result = MagicMock()
    mock_existing_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_existing_result

    ownership = await meeting_service.share_meeting(
        session=mock_session,
        task_id=sample_task_id,
        owner_id=sample_owner_id,
        team_id=sample_team_id,
    )

    assert isinstance(ownership, MeetingOwnership)
    assert ownership.task_id == sample_task_id
    assert ownership.owner_id == sample_owner_id
    assert ownership.team_id == sample_team_id
    assert ownership.shared_at is not None
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_share_meeting_duplicate_conflict(
    meeting_service, mock_session, sample_task_id, sample_owner_id, sample_team_id, sample_ownership
):
    """
    동일 팀에 중복 공유 시 409 Conflict
    REQ-TEAM-005
    """
    # 이미 공유된 레코드 존재
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_ownership
    mock_session.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await meeting_service.share_meeting(
            session=mock_session,
            task_id=sample_task_id,
            owner_id=sample_owner_id,
            team_id=sample_team_id,
        )

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# unshare_meeting 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unshare_meeting_success(
    meeting_service, mock_session, sample_task_id, sample_team_id, sample_ownership
):
    """
    회의록 공유 해제 성공 시 True 반환
    REQ-TEAM-005
    """
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_ownership
    mock_session.execute.return_value = mock_result

    result = await meeting_service.unshare_meeting(
        session=mock_session,
        task_id=sample_task_id,
        team_id=sample_team_id,
    )

    assert result is True
    mock_session.delete.assert_called_once_with(sample_ownership)
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_unshare_meeting_not_found(
    meeting_service, mock_session, sample_task_id, sample_team_id
):
    """
    공유 레코드 없을 때 False 반환
    """
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await meeting_service.unshare_meeting(
        session=mock_session,
        task_id=sample_task_id,
        team_id=sample_team_id,
    )

    assert result is False


# ---------------------------------------------------------------------------
# list_team_meetings 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_team_meetings(
    meeting_service, mock_session, sample_team_id, sample_ownership, sample_task_result
):
    """
    팀 공유 회의록 목록 반환
    REQ-TEAM-005
    """
    # 개수 조회 mock
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 1

    # 목록 조회 mock (ownership + task_result 튜플)
    mock_list_result = MagicMock()
    mock_list_result.all.return_value = [(sample_ownership, sample_task_result)]

    mock_session.execute.side_effect = [mock_count_result, mock_list_result]

    result = await meeting_service.list_team_meetings(
        session=mock_session,
        team_id=sample_team_id,
        page=1,
        page_size=20,
    )

    assert result["total"] == 1
    assert result["page"] == 1
    assert result["page_size"] == 20
    assert len(result["items"]) == 1
    assert result["items"][0]["task_id"] == sample_ownership.task_id
    assert result["items"][0]["task_type"] == "transcription"
    assert result["items"][0]["status"] == "completed"


# ---------------------------------------------------------------------------
# list_user_meetings 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_user_meetings(
    meeting_service, mock_session, sample_owner_id, sample_ownership, sample_task_result
):
    """
    사용자 소유 회의록 목록 반환
    REQ-TEAM-005
    """
    # 개수 조회 mock
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 1

    # 목록 조회 mock
    mock_list_result = MagicMock()
    mock_list_result.all.return_value = [(sample_ownership, sample_task_result)]

    mock_session.execute.side_effect = [mock_count_result, mock_list_result]

    result = await meeting_service.list_user_meetings(
        session=mock_session,
        user_id=sample_owner_id,
        page=1,
        page_size=20,
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["owner_id"] == str(sample_owner_id)


# ---------------------------------------------------------------------------
# get_or_create_ownership 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_create_ownership_existing(
    meeting_service, mock_session, sample_task_id, sample_owner_id
):
    """
    소유권 레코드가 있으면 기존 레코드를 반환한다
    """
    existing = MeetingOwnership()
    existing.id = uuid.uuid4()
    existing.task_id = sample_task_id
    existing.owner_id = sample_owner_id
    existing.team_id = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result

    ownership = await meeting_service.get_or_create_ownership(
        session=mock_session,
        task_id=sample_task_id,
        user_id=sample_owner_id,
    )

    assert ownership is existing
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_ownership_creates_new(
    meeting_service, mock_session, sample_task_id, sample_owner_id
):
    """
    소유권 레코드가 없으면 새로 생성한다
    """
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    ownership = await meeting_service.get_or_create_ownership(
        session=mock_session,
        task_id=sample_task_id,
        user_id=sample_owner_id,
    )

    assert isinstance(ownership, MeetingOwnership)
    assert ownership.task_id == sample_task_id
    assert ownership.owner_id == sample_owner_id
    assert ownership.team_id is None
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# is_meeting_owner 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_meeting_owner_true(
    meeting_service, mock_session, sample_task_id, sample_owner_id, sample_ownership
):
    """소유권 레코드가 있으면 True"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_ownership
    mock_session.execute.return_value = mock_result

    result = await meeting_service.is_meeting_owner(
        session=mock_session,
        task_id=sample_task_id,
        user_id=sample_owner_id,
    )

    assert result is True


@pytest.mark.asyncio
async def test_is_meeting_owner_no_ownership_records(
    meeting_service, mock_session, sample_task_id, sample_owner_id
):
    """소유권 레코드가 아예 없으면 (최초 요청) True 반환"""
    # 첫 번째 execute: 소유권 레코드 없음
    mock_none_result = MagicMock()
    mock_none_result.scalar_one_or_none.return_value = None

    # 두 번째 execute: 전체 개수 0
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 0

    mock_session.execute.side_effect = [mock_none_result, mock_count_result]

    result = await meeting_service.is_meeting_owner(
        session=mock_session,
        task_id=sample_task_id,
        user_id=sample_owner_id,
    )

    assert result is True
