"""그룹2: collaboration (collab/bookmarks/speakers) + services 커버리지 테스트"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.schemas.bookmark import BookmarkCreate, BookmarkUpdate
from backend.schemas.collab import CollabUser, EditMessage, FieldState
from backend.schemas.speaker import SpeakerProfileCreate, SpeakerProfileUpdate
from backend.services.bookmark_service import BookmarkService
from backend.services.collab_service import CollabService
from backend.services.speaker_service import SpeakerService


# ═══════════════════════════════════════════════════════════════════
# CollabService
# ═══════════════════════════════════════════════════════════════════
class TestCollabService:
    @pytest.mark.asyncio
    async def test_apply_edit_in_memory(self):
        svc = CollabService(redis_client=None)
        user = CollabUser(user_id="u1", display_name="User1")
        edit = EditMessage(field="title", value="New Title")
        broadcast = await svc.apply_edit("r1", user, edit)
        assert broadcast["field"] == "title"
        assert broadcast["value"] == "New Title"

    @pytest.mark.asyncio
    async def test_apply_edit_lww_older_edit_ignored(self):
        svc = CollabService(redis_client=None)
        user1 = CollabUser(user_id="u1", display_name="User1")
        user2 = CollabUser(user_id="u2", display_name="User2")
        edit1 = EditMessage(field="title", value="Second")
        await svc.apply_edit("r1", user1, edit1)
        edit2 = EditMessage(field="title", value="First")
        result = await svc.apply_edit("r1", user2, edit2)
        assert result["value"] == "First"

    @pytest.mark.asyncio
    async def test_apply_edit_with_redis_save_failure(self):
        redis = AsyncMock()
        redis.hset = AsyncMock(side_effect=Exception("Redis down"))
        redis.expire = AsyncMock()
        svc = CollabService(redis_client=redis)
        user = CollabUser(user_id="u1", display_name="User1")
        edit = EditMessage(field="title", value="Value")
        result = await svc.apply_edit("r1", user, edit)
        assert result is not None
        assert result["value"] == "Value"

    @pytest.mark.asyncio
    async def test_get_sync_state(self):
        svc = CollabService(redis_client=None)
        user = CollabUser(user_id="u1", display_name="User1")
        edit = EditMessage(field="title", value="Hello")
        await svc.apply_edit("r1", user, edit)
        state = await svc.get_sync_state("r1")
        assert "title" in state

    @pytest.mark.asyncio
    async def test_get_dirty_fields(self):
        svc = CollabService(redis_client=None)
        user = CollabUser(user_id="u1", display_name="User1")
        edit = EditMessage(field="title", value="Hello")
        await svc.apply_edit("r1", user, edit)
        dirty = svc.get_dirty_fields("r1")
        assert "title" in dirty

    def test_clear_dirty_fields(self):
        svc = CollabService(redis_client=None)
        svc._dirty["r1"] = {"title": "val"}
        svc.clear_dirty_fields("r1")
        assert svc._dirty.get("r1", {}) == {}

    def test_has_unpersisted_changes_true(self):
        svc = CollabService(redis_client=None)
        svc._dirty["r1"] = {"title": "val"}
        assert svc.has_unpersisted_changes("r1") is True

    def test_has_unpersisted_changes_false(self):
        svc = CollabService(redis_client=None)
        assert svc.has_unpersisted_changes("r1") is False

    @pytest.mark.asyncio
    async def test_flush_room(self):
        svc = CollabService(redis_client=None)
        user = CollabUser(user_id="u1", display_name="User1")
        edit = EditMessage(field="title", value="Flushed")
        await svc.apply_edit("r1", user, edit)
        flushed = await svc.flush_room("r1")
        assert flushed is not None
        assert "title" in flushed

    @pytest.mark.asyncio
    async def test_flush_room_no_changes(self):
        svc = CollabService(redis_client=None)
        result = await svc.flush_room("r1")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# BookmarkService
# ═══════════════════════════════════════════════════════════════════
def _mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


class TestBookmarkService:
    @pytest.mark.asyncio
    async def test_ensure_task_exists_not_found(self):
        svc = BookmarkService()
        session = _mock_session()
        session.execute.return_value = MagicMock(first=MagicMock(return_value=None))
        with pytest.raises(HTTPException) as exc_info:
            await svc._ensure_task_exists(session, "missing-task")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_ensure_task_exists_found(self):
        svc = BookmarkService()
        session = _mock_session()
        session.execute.return_value = MagicMock(first=MagicMock(return_value=("row",)))
        # 예외 없이 통과
        await svc._ensure_task_exists(session, "existing-task")

    @pytest.mark.asyncio
    async def test_enforce_per_meeting_limit_exceeded(self):
        from unittest.mock import patch
        svc = BookmarkService()
        session = _mock_session()
        session.execute.return_value = MagicMock(scalar_one=MagicMock(return_value=999))
        with patch("backend.services.bookmark_service.settings") as mock_settings:
            mock_settings.bookmark_max_per_meeting = 5
            with pytest.raises(HTTPException) as exc_info:
                await svc._enforce_per_meeting_limit(session, uuid.uuid4(), "t1")
            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_enforce_per_meeting_limit_ok(self):
        from unittest.mock import patch
        svc = BookmarkService()
        session = _mock_session()
        session.execute.return_value = MagicMock(scalar_one=MagicMock(return_value=2))
        with patch("backend.services.bookmark_service.settings") as mock_settings:
            mock_settings.bookmark_max_per_meeting = 5
            await svc._enforce_per_meeting_limit(session, uuid.uuid4(), "t1")

    def test_validate_segment_range_invalid(self):
        svc = BookmarkService()
        with pytest.raises(HTTPException) as exc_info:
            svc._validate_segment_range(10.0, 5.0)
        assert exc_info.value.status_code == 422

    def test_validate_segment_range_valid(self):
        svc = BookmarkService()
        svc._validate_segment_range(1.0, 5.0)

    def test_validate_note_length_too_long(self):
        from unittest.mock import patch
        svc = BookmarkService()
        with patch("backend.services.bookmark_service.settings") as mock_settings:
            mock_settings.bookmark_note_max_length = 10
            with pytest.raises(HTTPException) as exc_info:
                svc._validate_note_length("a" * 20)
            assert exc_info.value.status_code == 422

    def test_validate_note_length_none_ok(self):
        svc = BookmarkService()
        svc._validate_note_length(None)

    def test_validate_note_length_valid(self):
        from unittest.mock import patch
        svc = BookmarkService()
        with patch("backend.services.bookmark_service.settings") as mock_settings:
            mock_settings.bookmark_note_max_length = 100
            svc._validate_note_length("short note")

    @pytest.mark.asyncio
    async def test_create_success(self):
        svc = BookmarkService()
        session = _mock_session()
        # _ensure_task_exists → found
        # _enforce_per_meeting_limit → ok
        session.execute.side_effect = [
            MagicMock(first=MagicMock(return_value=("exists",))),
            MagicMock(scalar_one=MagicMock(return_value=0)),
        ]
        bookmark = MagicMock()
        session.refresh.return_value = bookmark

        payload = BookmarkCreate(
            task_id="t1", segment_start=0.0, segment_end=5.0,
            text_snippet="hello", note="note", color="#fff",
        )
        result = await svc.create(session, uuid.uuid4(), payload)
        assert session.add.called
        assert session.commit.called

    @pytest.mark.asyncio
    async def test_get_by_id_found(self):
        svc = BookmarkService()
        session = _mock_session()
        uid = uuid.uuid4()
        bm = MagicMock()
        bm.user_id = uid
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=bm))

        result = await svc.get_by_id(session, uuid.uuid4(), uid)
        assert result == bm

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        svc = BookmarkService()
        session = _mock_session()
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        with pytest.raises(HTTPException) as exc_info:
            await svc.get_by_id(session, uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_by_id_wrong_user(self):
        svc = BookmarkService()
        session = _mock_session()
        bm = MagicMock()
        bm.user_id = uuid.uuid4()
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=bm))
        with pytest.raises(HTTPException) as exc_info:
            await svc.get_by_id(session, uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_for_user(self):
        svc = BookmarkService()
        session = _mock_session()
        bm = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [bm]
        session.execute.side_effect = [
            MagicMock(scalar_one=MagicMock(return_value=1)),
            MagicMock(scalars=MagicMock(return_value=scalars_mock)),
        ]
        items, total = await svc.list_for_user(session, uuid.uuid4(), None, 10, 0)
        assert total == 1

    @pytest.mark.asyncio
    async def test_update_success(self):
        svc = BookmarkService()
        session = _mock_session()
        uid = uuid.uuid4()
        bm = MagicMock()
        bm.user_id = uid
        bm.segment_start = 0.0
        bm.segment_end = 10.0
        # get_by_id 내부 execute
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=bm))

        payload = BookmarkUpdate(segment_start=1.0, segment_end=9.0, note="updated")
        result = await svc.update(session, uuid.uuid4(), uid, payload)
        assert session.commit.called

    @pytest.mark.asyncio
    async def test_delete_success(self):
        svc = BookmarkService()
        session = _mock_session()
        uid = uuid.uuid4()
        bm = MagicMock()
        bm.user_id = uid
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=bm))

        await svc.delete(session, uuid.uuid4(), uid)
        assert session.delete.called


# ═══════════════════════════════════════════════════════════════════
# SpeakerService
# ═══════════════════════════════════════════════════════════════════
class TestSpeakerService:
    @pytest.mark.asyncio
    async def test_ensure_no_duplicate_found(self):
        svc = SpeakerService()
        session = _mock_session()
        session.execute.return_value = MagicMock(first=MagicMock(return_value=("id",)))
        with pytest.raises(HTTPException) as exc_info:
            await svc._ensure_no_duplicate(session, uuid.uuid4(), "label", None)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_ensure_no_duplicate_ok(self):
        svc = SpeakerService()
        session = _mock_session()
        session.execute.return_value = MagicMock(first=MagicMock(return_value=None))
        await svc._ensure_no_duplicate(session, uuid.uuid4(), "label", None)

    @pytest.mark.asyncio
    async def test_ensure_no_duplicate_with_exclude(self):
        svc = SpeakerService()
        session = _mock_session()
        session.execute.return_value = MagicMock(first=MagicMock(return_value=None))
        await svc._ensure_no_duplicate(session, uuid.uuid4(), "label", None, exclude_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_enforce_user_limit_exceeded(self):
        svc = SpeakerService()
        session = _mock_session()
        session.execute.return_value = MagicMock(scalar_one=MagicMock(return_value=600))
        with pytest.raises(HTTPException) as exc_info:
            await svc._enforce_user_limit(session, uuid.uuid4())
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_enforce_user_limit_ok(self):
        svc = SpeakerService()
        session = _mock_session()
        session.execute.return_value = MagicMock(scalar_one=MagicMock(return_value=10))
        await svc._enforce_user_limit(session, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_create_success(self):
        svc = SpeakerService()
        session = _mock_session()
        session.execute.side_effect = [
            MagicMock(scalar_one=MagicMock(return_value=0)),  # _enforce_user_limit
            MagicMock(first=MagicMock(return_value=None)),    # _ensure_no_duplicate
        ]
        profile = MagicMock()
        session.refresh.return_value = profile

        payload = SpeakerProfileCreate(
            speaker_label="SPK1", display_name="Alice", role="PM", note="test", task_id=None,
        )
        result = await svc.create(session, uuid.uuid4(), payload)
        assert session.add.called

    @pytest.mark.asyncio
    async def test_get_by_id_found(self):
        svc = SpeakerService()
        session = _mock_session()
        uid = uuid.uuid4()
        profile = MagicMock()
        profile.user_id = uid
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=profile))

        result = await svc.get_by_id(session, uuid.uuid4(), uid)
        assert result == profile

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        svc = SpeakerService()
        session = _mock_session()
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        with pytest.raises(HTTPException) as exc_info:
            await svc.get_by_id(session, uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_by_id_wrong_user(self):
        svc = SpeakerService()
        session = _mock_session()
        profile = MagicMock()
        profile.user_id = uuid.uuid4()
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=profile))
        with pytest.raises(HTTPException) as exc_info:
            await svc.get_by_id(session, uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_for_user(self):
        svc = SpeakerService()
        session = _mock_session()
        profile = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [profile]
        session.execute.side_effect = [
            MagicMock(scalar_one=MagicMock(return_value=1)),
            MagicMock(scalars=MagicMock(return_value=scalars_mock)),
        ]
        items, total = await svc.list_for_user(session, uuid.uuid4(), None, None, 10, 0)
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_for_user_with_filters(self):
        svc = SpeakerService()
        session = _mock_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        session.execute.side_effect = [
            MagicMock(scalar_one=MagicMock(return_value=0)),
            MagicMock(scalars=MagicMock(return_value=scalars_mock)),
        ]
        items, total = await svc.list_for_user(session, uuid.uuid4(), "task1", "SPK1", 10, 0)
        assert total == 0

    @pytest.mark.asyncio
    async def test_update_success(self):
        svc = SpeakerService()
        session = _mock_session()
        uid = uuid.uuid4()
        profile = MagicMock()
        profile.user_id = uid
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=profile))

        payload = SpeakerProfileUpdate(display_name="Bob", role="Dev", note="updated")
        result = await svc.update(session, uuid.uuid4(), uid, payload)
        assert session.commit.called

    @pytest.mark.asyncio
    async def test_delete_success(self):
        svc = SpeakerService()
        session = _mock_session()
        uid = uuid.uuid4()
        profile = MagicMock()
        profile.user_id = uid
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=profile))

        await svc.delete(session, uuid.uuid4(), uid)
        assert session.delete.called
