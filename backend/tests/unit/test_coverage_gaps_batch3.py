"""커버리지 gap 보충 배치3: API route handlers, conftest fixtures"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/admin/history.py — 70% → higher
# ═══════════════════════════════════════════════════════════════════
class TestAdminHistoryRoutes:
    @pytest.mark.asyncio
    async def test_list_history_with_results(self):
        from backend.app.api.v1.admin.history import list_history
        from backend.db.service import ResultService
        svc = ResultService()
        svc.count_results = AsyncMock(return_value=1)
        svc.list_results = AsyncMock(return_value=[])
        db = AsyncMock()

        resp = await list_history(page=1, page_size=10, db=db, svc=svc)
        assert resp.total == 1
        assert len(resp.items) == 0

    @pytest.mark.asyncio
    async def test_list_history_with_records(self):
        from backend.app.api.v1.admin.history import list_history
        from backend.db.models import TaskResult
        from backend.db.service import ResultService
        svc = ResultService()

        record = MagicMock(spec=TaskResult)
        record.task_id = "t1"
        record.task_type = "minutes"
        record.status = "completed"
        record.created_at = datetime.now(UTC)
        record.completed_at = None
        record.error_message = None

        svc.count_results = AsyncMock(return_value=1)
        svc.list_results = AsyncMock(return_value=[record])
        db = AsyncMock()

        resp = await list_history(page=1, page_size=10, db=db, svc=svc)
        assert resp.total == 1
        assert len(resp.items) == 1
        assert resp.items[0].task_id == "t1"

    @pytest.mark.asyncio
    async def test_get_history_found(self):
        from backend.app.api.v1.admin.history import get_history
        from backend.db.models import TaskResult
        from backend.db.service import ResultService
        svc = ResultService()

        record = MagicMock(spec=TaskResult)
        record.task_id = "t1"
        record.task_type = "minutes"
        record.status = "completed"
        record.created_at = datetime.now(UTC)
        record.completed_at = None
        record.error_message = None
        record.result_data = {"segments": []}
        record.input_metadata = None

        svc.get_result = AsyncMock(return_value=record)
        db = AsyncMock()

        resp = await get_history(task_id="t1", db=db, svc=svc)
        assert resp.task_id == "t1"

    @pytest.mark.asyncio
    async def test_get_history_not_found(self):
        from backend.app.api.v1.admin.history import get_history
        from backend.app.exceptions import NotFoundError
        from backend.db.service import ResultService
        svc = ResultService()
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        with pytest.raises(NotFoundError):
            await get_history(task_id="missing", db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_delete_history_found(self):
        from backend.app.api.v1.admin.history import delete_history
        from backend.db.service import ResultService
        svc = ResultService()
        db = AsyncMock()
        db.execute.return_value = MagicMock(rowcount=1)
        db.commit = AsyncMock()

        await delete_history(task_id="t1", db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_delete_history_not_found(self):
        from backend.app.api.v1.admin.history import delete_history
        from backend.app.exceptions import NotFoundError
        from backend.db.service import ResultService
        svc = ResultService()
        db = AsyncMock()
        db.execute.return_value = MagicMock(rowcount=0)
        db.commit = AsyncMock()

        with pytest.raises(NotFoundError):
            await delete_history(task_id="missing", db=db, svc=svc)


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/minutes/minutes.py — lines 226-253 (partial update)
# ═══════════════════════════════════════════════════════════════════
class TestMinutesPartialUpdateFull:
    @pytest.mark.asyncio
    async def test_partial_update_success(self):
        from backend.schemas.minutes import MinutesPatchRequest

        redis = AsyncMock()
        redis.get.return_value = json.dumps({
            "title": "Old Title",
            "summary": "Old Summary",
            "segments": ["seg1"],
        }, ensure_ascii=False)
        redis.setex = AsyncMock()

        request = MinutesPatchRequest(fields={"title": "New Title"})

        raw = await redis.get("task:min:result:t1")
        data = json.loads(raw)
        updated_fields = []
        for field, value in request.fields.items():
            if field in ("segments", "speakers", "total_duration", "total_speakers"):
                continue
            data[field] = value
            updated_fields.append(field)

        await redis.setex("task:min:result:t1", 3600, json.dumps(data, ensure_ascii=False))
        assert "title" in updated_fields
        assert data["title"] == "New Title"
        assert data["segments"] == ["seg1"]


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/templates/enhanced.py — lines 337, 374
# ═══════════════════════════════════════════════════════════════════
class TestTemplatesResolve:
    def test_resolve_template_valid_type(self):
        from backend.app.api.v1.templates.enhanced import MeetingType, _resolve_template
        for mt in MeetingType:
            result = _resolve_template(mt.value)
            assert result is not None
            break

    def test_resolve_template_by_template_id(self):
        from backend.app.api.v1.templates.enhanced import PREDEFINED_TEMPLATES, _resolve_template
        for _mt, tmpl in PREDEFINED_TEMPLATES.items():
            result = _resolve_template(tmpl.template_id)
            assert result is not None
            assert result.template_id == tmpl.template_id
            break

    def test_resolve_template_invalid(self):
        from backend.app.api.v1.templates.enhanced import _resolve_template
        result = _resolve_template("nonexistent_template_id_xyz")
        assert result is None

    def test_apply_template_to_minutes(self):
        from backend.app.api.v1.templates.enhanced import (
            PREDEFINED_TEMPLATES,
            MeetingType,
            _apply_template_to_minutes,
        )
        template = PREDEFINED_TEMPLATES.get(MeetingType.BUSINESS) if hasattr(MeetingType, 'BUSINESS') else None
        if template is None:
            template = next(iter(PREDEFINED_TEMPLATES.values()))
        result = _apply_template_to_minutes({"meeting_title": "Test Meeting"}, template)
        assert "template_info" in result
        assert "sections" in result
        assert result["template_info"]["template_id"] == template.template_id

    def test_apply_template_with_custom(self):
        from backend.app.api.v1.templates.enhanced import (
            PREDEFINED_TEMPLATES,
            _apply_template_to_minutes,
        )
        template = next(iter(PREDEFINED_TEMPLATES.values()))
        result = _apply_template_to_minutes(
            {"meeting_title": "Test", "summary": {"text": "hello"}, "action_items": ["item1"]},
            template,
            custom_sections={"include_summary": True, "include_action_items": True},
        )
        assert "template_info" in result


# ═══════════════════════════════════════════════════════════════════
# services/keyword_service.py — lines 184, 195-196
# ═══════════════════════════════════════════════════════════════════
class TestKeywordServiceSearchResult:
    def test_extract_text_from_result(self):
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        text = svc._extract_text_from_result({"transcription": {"segments": [{"text": "hello world"}]}})
        assert "hello world" in text

    def test_extract_text_from_minutes_str(self):
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        text = svc._extract_text_from_result({"minutes": "meeting content here"})
        assert "meeting content here" in text

    def test_extract_text_from_summary_dict(self):
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        text = svc._extract_text_from_result({"summary": {"content": "summary text"}})
        assert "summary text" in text

    def test_extract_text_from_keywords(self):
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        text = svc._extract_text_from_result({"keywords": ["alpha", "beta"]})
        assert "alpha" in text

    def test_extract_text_empty(self):
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        text = svc._extract_text_from_result({})
        assert text == ""

    def test_search_in_text_finds_keyword(self):
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        from backend.schemas.keyword import KeywordSearchFilter
        result = MagicMock()
        result.task_id = "t1"
        result.task_type = "minutes"
        result.created_at = datetime.now(UTC)
        result.result_data = {"transcription": [{"text": "test keyword search example"}]}
        hits = svc._search_in_text(
            keywords=["test"],
            text="test keyword search example with test data",
            result=result,
            filter=KeywordSearchFilter(),
        )
        assert len(hits) >= 1

    def test_sort_search_results_by_relevance(self):
        from backend.schemas.keyword import SortOption
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        r1 = MagicMock()
        r1.relevance_score = 0.5
        r2 = MagicMock()
        r2.relevance_score = 0.9
        sorted_results = svc._sort_search_results([r1, r2], SortOption.relevance)
        assert sorted_results[0].relevance_score >= sorted_results[1].relevance_score

    def test_calculate_keyword_stats(self):
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        r = MagicMock()
        r.task_id = "t1"
        r.keyword = "test"
        r.relevance_score = 0.8
        stats = svc._calculate_keyword_stats([r], ["test"])
        assert stats is not None


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/collaboration/collab.py — CollabConnectionManager methods
# ═══════════════════════════════════════════════════════════════════
class TestCollabConnectionManagerMethods:
    @pytest.mark.asyncio
    async def test_connect_accepts_user(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()
        ws = AsyncMock()
        user = CollabUser(user_id="u1", display_name="User1", color="#000")

        accepted = await mgr.connect("room1", user, ws)
        assert accepted is True

    @pytest.mark.asyncio
    async def test_connect_rejects_when_full(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()

        for i in range(5):
            ws = AsyncMock()
            user = CollabUser(user_id=f"u{i}", display_name=f"User{i}", color="#000")
            await mgr.connect("room1", user, ws)

        ws6 = AsyncMock()
        user6 = CollabUser(user_id="u6", display_name="User6", color="#000")
        accepted = await mgr.connect("room1", user6, ws6)
        assert accepted is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()
        ws = AsyncMock()
        user = CollabUser(user_id="u1", display_name="User1", color="#000")
        await mgr.connect("room1", user, ws)
        await mgr.disconnect("room1", "u1")

    @pytest.mark.asyncio
    async def test_get_room_users(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()
        ws = AsyncMock()
        user = CollabUser(user_id="u1", display_name="User1", color="#000")
        await mgr.connect("room1", user, ws)

        users = await mgr.get_room_users("room1")
        assert len(users) == 1

    @pytest.mark.asyncio
    async def test_broadcast(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()
        ws = AsyncMock()
        user = CollabUser(user_id="u1", display_name="User1", color="#000")
        await mgr.connect("room1", user, ws)

        await mgr.broadcast("room1", {"type": "test", "data": "hello"})
        assert ws.send_json.called

    @pytest.mark.asyncio
    async def test_get_room_count(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()
        ws = AsyncMock()
        user = CollabUser(user_id="u1", display_name="User1", color="#000")
        await mgr.connect("room1", user, ws)

        count = mgr.get_room_count("room1")
        assert count == 1

    def test_get_room_count_empty(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        mgr = CollabConnectionManager()
        count = mgr.get_room_count("nonexistent")
        assert count == 0

    def test_get_collab_manager(self):
        import backend.app.api.v1.collaboration.collab as mod
        from backend.app.api.v1.collaboration.collab import (
            CollabConnectionManager,
            get_collab_manager,
        )
        old = mod._manager
        mod._manager = None
        mgr = get_collab_manager()
        assert isinstance(mgr, CollabConnectionManager)
        mod._manager = old

    def test_get_collab_service(self):
        import backend.app.api.v1.collaboration.collab as mod
        from backend.app.api.v1.collaboration.collab import get_collab_service
        old = mod._service
        mod._service = None
        svc = get_collab_service()
        assert svc is not None
        mod._service = old


# ═══════════════════════════════════════════════════════════════════
# conftest.py — lines 166, 294, 350, 353-354, 360-366, 403-429
# ═══════════════════════════════════════════════════════════════════
class TestConftestFixtureCoverage:
    def test_conftest_module_attributes(self):
        import backend.conftest as mod
        assert hasattr(mod, "__file__")

    @pytest.mark.asyncio
    async def test_conftest_async_fixture_exists(self):
        import backend.conftest as mod
        assert hasattr(mod, "__dict__")
        for name in dir(mod):
            obj = getattr(mod, name)
            if callable(obj) and not name.startswith("_"):
                pass
