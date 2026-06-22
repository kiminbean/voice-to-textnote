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

from backend.db.auth_models import MeetingOwnership, Team
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
    meeting_service,
    mock_session,
    sample_task_id,
    sample_owner_id,
    sample_team_id,
    sample_task_result,
):
    """
    회의록 팀 공유 성공
    REQ-TEAM-005
    """
    # 회의록 존재
    mock_task_result = MagicMock()
    mock_task_result.scalar_one_or_none.return_value = sample_task_result

    # 중복 공유 없음 (None 반환)
    mock_existing_result = MagicMock()
    mock_existing_result.scalar_one_or_none.return_value = None
    mock_session.execute.side_effect = [mock_task_result, mock_existing_result]

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
    meeting_service,
    mock_session,
    sample_task_id,
    sample_owner_id,
    sample_team_id,
    sample_ownership,
    sample_task_result,
):
    """
    동일 팀에 중복 공유 시 409 Conflict
    REQ-TEAM-005
    """
    # 회의록 존재
    mock_task_result = MagicMock()
    mock_task_result.scalar_one_or_none.return_value = sample_task_result

    # 이미 공유된 레코드 존재
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_ownership
    mock_session.execute.side_effect = [mock_task_result, mock_result]

    with pytest.raises(HTTPException) as exc_info:
        await meeting_service.share_meeting(
            session=mock_session,
            task_id=sample_task_id,
            owner_id=sample_owner_id,
            team_id=sample_team_id,
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_share_meeting_missing_task_returns_404(
    meeting_service, mock_session, sample_task_id, sample_owner_id, sample_team_id
):
    """존재하지 않는 회의록은 공유 레코드를 만들지 않고 404를 반환한다."""
    missing_task_result = MagicMock()
    missing_task_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = missing_task_result

    with pytest.raises(HTTPException) as exc_info:
        await meeting_service.share_meeting(
            session=mock_session,
            task_id=sample_task_id,
            owner_id=sample_owner_id,
            team_id=sample_team_id,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "회의록을 찾을 수 없습니다"
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_apply_default_team_sharing_policy_creates_owner_and_team_default_share(
    meeting_service, mock_session, sample_task_id, sample_owner_id, sample_team_id
):
    """team_default 정책 팀은 새 task 생성 시 자동 공유 후보로 적용된다."""
    private_team_id = uuid.uuid4()
    default_team = Team()
    default_team.id = sample_team_id
    default_team.sharing_policy = {"default_visibility": "team_default"}
    private_team = Team()
    private_team.id = private_team_id
    private_team.sharing_policy = {"default_visibility": "private"}

    missing_owner_result = MagicMock()
    missing_owner_result.scalar_one_or_none.return_value = None
    team_result = MagicMock()
    team_result.scalars.return_value.all.return_value = [default_team, private_team]
    missing_share_result = MagicMock()
    missing_share_result.scalar_one_or_none.return_value = None
    mock_session.execute.side_effect = [
        missing_owner_result,
        team_result,
        missing_share_result,
    ]

    shared_team_ids = await meeting_service.apply_default_team_sharing_policy(
        session=mock_session,
        task_id=sample_task_id,
        owner_id=sample_owner_id,
    )

    assert shared_team_ids == [sample_team_id]
    assert mock_session.add.call_count == 2
    owner_record = mock_session.add.call_args_list[0].args[0]
    team_record = mock_session.add.call_args_list[1].args[0]
    assert owner_record.team_id is None
    assert owner_record.shared_at is None
    assert team_record.team_id == sample_team_id
    assert team_record.shared_at is not None
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_apply_default_team_sharing_policy_skips_existing_default_share(
    meeting_service, mock_session, sample_task_id, sample_owner_id, sample_team_id
):
    """이미 공유된 team_default 팀은 중복 공유하지 않는다."""
    default_team = Team()
    default_team.id = sample_team_id
    default_team.sharing_policy = {"default_visibility": "team_default"}
    existing_owner = MeetingOwnership()
    existing_owner.id = uuid.uuid4()
    existing_owner.task_id = sample_task_id
    existing_owner.owner_id = sample_owner_id
    existing_owner.team_id = None
    existing_share = MeetingOwnership()
    existing_share.id = uuid.uuid4()
    existing_share.task_id = sample_task_id
    existing_share.owner_id = sample_owner_id
    existing_share.team_id = sample_team_id

    owner_result = MagicMock()
    owner_result.scalar_one_or_none.return_value = existing_owner
    team_result = MagicMock()
    team_result.scalars.return_value.all.return_value = [default_team]
    existing_share_result = MagicMock()
    existing_share_result.scalar_one_or_none.return_value = existing_share
    mock_session.execute.side_effect = [
        owner_result,
        team_result,
        existing_share_result,
    ]

    shared_team_ids = await meeting_service.apply_default_team_sharing_policy(
        session=mock_session,
        task_id=sample_task_id,
        owner_id=sample_owner_id,
    )

    assert shared_team_ids == []
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_apply_default_team_sharing_policy_keeps_private_when_no_default_team(
    meeting_service, mock_session, sample_task_id, sample_owner_id
):
    """team_default 정책 팀이 없어도 새 task 소유권은 비공개로 기록한다."""
    missing_owner_result = MagicMock()
    missing_owner_result.scalar_one_or_none.return_value = None
    team_result = MagicMock()
    team_result.scalars.return_value.all.return_value = []
    mock_session.execute.side_effect = [missing_owner_result, team_result]

    shared_team_ids = await meeting_service.apply_default_team_sharing_policy(
        session=mock_session,
        task_id=sample_task_id,
        owner_id=sample_owner_id,
    )

    assert shared_team_ids == []
    mock_session.add.assert_called_once()
    owner_record = mock_session.add.call_args.args[0]
    assert owner_record.team_id is None
    assert owner_record.shared_at is None
    mock_session.commit.assert_called_once()


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
    meeting_service, mock_session, sample_task_id, sample_owner_id, sample_task_result
):
    """
    소유권 레코드가 있으면 기존 레코드를 반환한다
    """
    existing = MeetingOwnership()
    existing.id = uuid.uuid4()
    existing.task_id = sample_task_id
    existing.owner_id = sample_owner_id
    existing.team_id = None

    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = sample_task_result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.side_effect = [task_result, mock_result]

    ownership = await meeting_service.get_or_create_ownership(
        session=mock_session,
        task_id=sample_task_id,
        user_id=sample_owner_id,
    )

    assert ownership is existing
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_ownership_creates_new(
    meeting_service, mock_session, sample_task_id, sample_owner_id, sample_task_result
):
    """
    소유권 레코드가 없으면 새로 생성한다
    """
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = sample_task_result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.side_effect = [task_result, mock_result]

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


@pytest.mark.asyncio
async def test_get_or_create_ownership_missing_task_returns_404(
    meeting_service, mock_session, sample_task_id, sample_owner_id
):
    """존재하지 않는 회의록에는 소유권 레코드를 만들지 않는다."""
    missing_task_result = MagicMock()
    missing_task_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = missing_task_result

    with pytest.raises(HTTPException) as exc_info:
        await meeting_service.get_or_create_ownership(
            session=mock_session,
            task_id=sample_task_id,
            user_id=sample_owner_id,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "회의록을 찾을 수 없습니다"
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


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
    meeting_service, mock_session, sample_task_id, sample_owner_id, sample_task_result
):
    """소유권 레코드가 없어도 실제 회의록이 있으면 기존 최초 요청 정책을 유지한다."""
    # 첫 번째 execute: 소유권 레코드 없음
    mock_none_result = MagicMock()
    mock_none_result.scalar_one_or_none.return_value = None

    # 두 번째 execute: 전체 개수 0
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 0

    # 세 번째 execute: task_id가 실제 TaskResult에 존재
    mock_task_result = MagicMock()
    mock_task_result.scalar_one_or_none.return_value = sample_task_result

    mock_session.execute.side_effect = [
        mock_none_result,
        mock_count_result,
        mock_task_result,
    ]

    result = await meeting_service.is_meeting_owner(
        session=mock_session,
        task_id=sample_task_id,
        user_id=sample_owner_id,
    )

    assert result is True


@pytest.mark.asyncio
async def test_is_meeting_owner_no_ownership_records_missing_task_returns_false(
    meeting_service, mock_session, sample_task_id, sample_owner_id
):
    """소유권 레코드와 회의록이 모두 없으면 소유자로 인정하지 않는다."""
    mock_none_result = MagicMock()
    mock_none_result.scalar_one_or_none.return_value = None

    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 0

    mock_missing_task_result = MagicMock()
    mock_missing_task_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_none_result,
        mock_count_result,
        mock_missing_task_result,
    ]

    result = await meeting_service.is_meeting_owner(
        session=mock_session,
        task_id=sample_task_id,
        user_id=sample_owner_id,
    )

    assert result is False
