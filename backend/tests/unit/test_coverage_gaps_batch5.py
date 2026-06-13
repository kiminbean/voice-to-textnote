"""커버리지 gap 보충 배치5: remaining 200 lines"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/analytics/keyword_search.py — remaining lines 35, 59, 92, 121, 130-135
# ═══════════════════════════════════════════════════════════════════
class TestKeywordSearchEdgeCases:
    @pytest.mark.asyncio
    async def test_search_empty_q_stripped(self):
        from backend.app.api.v1.analytics.keyword_search import search_keywords
        from backend.app.exceptions import UnprocessableEntityError
        svc = MagicMock()
        db = AsyncMock()

        with pytest.raises(UnprocessableEntityError):
            await search_keywords(q="   ", page=1, page_size=20, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_suggest_short_context(self):
        from backend.app.api.v1.analytics.keyword_search import suggest_keywords
        from backend.app.exceptions import UnprocessableEntityError
        svc = MagicMock()
        db = AsyncMock()

        with pytest.raises(UnprocessableEntityError):
            await suggest_keywords(context="ab", limit=5, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_get_keyword_stats_hours(self):
        from backend.app.api.v1.analytics.keyword_search import get_keyword_statistics
        svc = MagicMock()
        svc.get_keyword_stats = AsyncMock(return_value=MagicMock(
            period="2h", top_keywords=[], total_searches=0,
        ))
        db = AsyncMock()
        resp = await get_keyword_statistics(period="2h", top_n=20, db=db, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_get_keyword_stats_weeks(self):
        from backend.app.api.v1.analytics.keyword_search import get_keyword_statistics
        svc = MagicMock()
        svc.get_keyword_stats = AsyncMock(return_value=MagicMock(
            period="3w", top_keywords=[], total_searches=0,
        ))
        db = AsyncMock()
        resp = await get_keyword_statistics(period="3w", top_n=20, db=db, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_get_keyword_stats_months(self):
        from backend.app.api.v1.analytics.keyword_search import get_keyword_statistics
        svc = MagicMock()
        svc.get_keyword_stats = AsyncMock(return_value=MagicMock(
            period="2m", top_keywords=[], total_searches=0,
        ))
        db = AsyncMock()
        resp = await get_keyword_statistics(period="2m", top_n=20, db=db, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_get_keyword_stats_invalid_period(self):
        from backend.app.api.v1.analytics.keyword_search import get_keyword_statistics
        from backend.app.exceptions import UnprocessableEntityError
        svc = MagicMock()
        db = AsyncMock()

        with pytest.raises(UnprocessableEntityError):
            await get_keyword_statistics(period="invalid", top_n=20, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_search_multi_keyword_split(self):
        from backend.app.api.v1.analytics.keyword_search import search_keywords
        svc = MagicMock()
        svc.search_keywords = AsyncMock(return_value=MagicMock(
            keywords=["hello", "world"], total_hits=0, total_documents=0,
            results=[], page=1, page_size=20, total_pages=0,
        ))
        db = AsyncMock()
        resp = await search_keywords(q="hello, world", page=1, page_size=20, db=db, svc=svc)
        assert resp is not None
        call_args = svc.search_keywords.call_args
        assert "hello" in call_args.kwargs["keywords"]
        assert "world" in call_args.kwargs["keywords"]


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/analytics/export.py — lines 27, 93, 96, 103, 106
# ═══════════════════════════════════════════════════════════════════
class TestExportEdgeCases:
    @pytest.mark.asyncio
    async def test_export_meeting_not_found_in_batch(self):
        from backend.app.api.v1.analytics.export import export_batch_meetings
        from backend.app.exceptions import NotFoundError
        from backend.schemas.export import ExportFormat, ExportRequest
        db = AsyncMock()
        db.get.return_value = None
        svc = MagicMock()

        req = ExportRequest(task_ids=["missing"], format=ExportFormat.pdf)
        with pytest.raises(NotFoundError):
            await export_batch_meetings(request=req, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_export_meeting_not_completed_in_batch(self):
        from backend.app.api.v1.analytics.export import export_batch_meetings
        from backend.app.exceptions import UnprocessableEntityError
        from backend.schemas.export import ExportFormat, ExportRequest
        db = AsyncMock()
        task = MagicMock()
        task.status = "processing"
        db.get.return_value = task
        svc = MagicMock()

        req = ExportRequest(task_ids=["t1"], format=ExportFormat.pdf)
        with pytest.raises(UnprocessableEntityError):
            await export_batch_meetings(request=req, db=db, svc=svc)


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/collaboration/bookmarks.py — line 63 (create_bookmark)
# ═══════════════════════════════════════════════════════════════════
class TestBookmarkCreate:
    @pytest.mark.asyncio
    async def test_create_bookmark(self):
        from backend.app.api.v1.collaboration.bookmarks import create_bookmark
        svc = MagicMock()
        bookmark = SimpleNamespace(
            id=uuid.uuid4(), task_id="t1", user_id=uuid.uuid4(),
            segment_start=0.0, segment_end=10.0, text_snippet="text",
            note="note", color="#FF0000", category="note", priority="medium",
            tags=[], is_private=True, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        )
        svc.create = AsyncMock(return_value=bookmark)
        db = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()
        payload = MagicMock()

        resp = await create_bookmark(payload=payload, db=db, user=user, svc=svc)
        assert resp is not None


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/collaboration/speakers.py — line 61 (create_speaker)
# ═══════════════════════════════════════════════════════════════════
class TestSpeakerCreate:
    @pytest.mark.asyncio
    async def test_create_speaker(self):
        from backend.app.api.v1.collaboration.speakers import create_speaker
        svc = MagicMock()
        profile = SimpleNamespace(
            id=uuid.uuid4(), user_id=uuid.uuid4(), speaker_label="SPEAKER_00",
            display_name="Speaker 0", role=None, note=None, task_id=None,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        )
        svc.create = AsyncMock(return_value=profile)
        db = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()
        payload = MagicMock()

        resp = await create_speaker(payload=payload, db=db, user=user, svc=svc)
        assert resp is not None


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/auth/devices.py — line 33 (_get_push)
# ═══════════════════════════════════════════════════════════════════
class TestDeviceHelpers:
    def test_get_push(self):
        from backend.app.api.v1.auth.devices import _get_push
        from backend.services.push_service import PushService
        result = _get_push()
        assert isinstance(result, PushService)


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/minutes/keywords.py — lines 27, 40
# ═══════════════════════════════════════════════════════════════════
class TestMinutesKeywordsExtract:
    @pytest.mark.asyncio
    async def test_extract_keywords_from_text(self):
        from backend.app.api.v1.minutes.keywords import extract_keywords
        svc = MagicMock()
        svc.extract_from_text = MagicMock(return_value=MagicMock(keywords=[], total=0))

        payload = MagicMock()
        payload.text = "테스트 회의 내용입니다"
        payload.language = "ko"
        payload.max_keywords = 10
        payload.min_score = 0.0

        resp = extract_keywords(payload=payload, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_extract_keywords_route(self):
        from backend.app.api.v1.minutes.keywords import extract_keywords
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        from backend.schemas.keyword import KeywordExtractRequest
        payload = KeywordExtractRequest(text="회의 내용 분석 키워드 추출 테스트")
        resp = extract_keywords(payload=payload, svc=svc)
        assert resp is not None


# ═══════════════════════════════════════════════════════════════════
# conftest.py — lines 294, 350, 353-354
# ═══════════════════════════════════════════════════════════════════
class TestConftestClientFixture:
    def test_client_fixture(self, client):
        assert client is not None

    def test_client_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code in (200, 503)


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/audio/quality_assessment.py — remaining route handlers
# ═══════════════════════════════════════════════════════════════════
class TestQualityAssessmentLoadMinutes:
    @pytest.mark.asyncio
    async def test_load_minutes_text_or_404_not_found(self):
        from backend.app.api.v1.audio.quality_assessment import _load_minutes_text_or_404
        from backend.app.exceptions import NotFoundError
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        with pytest.raises(NotFoundError):
            await _load_minutes_text_or_404(db, "missing_task")

    @pytest.mark.asyncio
    async def test_load_minutes_text_or_404_no_content(self):
        from backend.app.api.v1.audio.quality_assessment import _load_minutes_text_or_404
        from backend.app.exceptions import NotFoundError
        db = AsyncMock()
        task = MagicMock()
        task.result_data = {}
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=task))

        with pytest.raises(NotFoundError):
            await _load_minutes_text_or_404(db, "t1")

    @pytest.mark.asyncio
    async def test_load_minutes_text_or_404_success(self):
        from backend.app.api.v1.audio.quality_assessment import _load_minutes_text_or_404
        db = AsyncMock()
        task = MagicMock()
        task.result_data = {"markdown": "회의 내용입니다", "title": "테스트 회의"}
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=task))

        result = await _load_minutes_text_or_404(db, "t1")
        assert "회의 내용입니다" in result


# ═══════════════════════════════════════════════════════════════════
# services/keyword_service.py — lines 184, 195-196 (search loop branches)
# ═══════════════════════════════════════════════════════════════════
class TestKeywordServiceSearchLoop:
    def test_extract_text_from_minutes_string(self):
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        text = svc._extract_text_from_result({"minutes": "회의 내용입니다"})
        assert "회의 내용입니다" in text

    def test_extract_text_from_minutes_dict(self):
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        text = svc._extract_text_from_result({"minutes": {"content": "회의 내용", "summary": "요약"}})
        assert "회의 내용" in text

    def test_extract_text_from_summary_string(self):
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        text = svc._extract_text_from_result({"summary": "요약 내용"})
        assert "요약 내용" in text


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/collaboration/collab.py — broadcast failure + send failure
# ═══════════════════════════════════════════════════════════════════
class TestCollabErrorPaths:
    @pytest.mark.asyncio
    async def test_broadcast_send_failure(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()
        ws = AsyncMock()
        ws.send_json.side_effect = RuntimeError("connection closed")
        user = CollabUser(user_id="u1", display_name="User1", color="#000")
        await mgr.connect("room1", user, ws)

        await mgr.broadcast("room1", {"type": "test"})

    @pytest.mark.asyncio
    async def test_send_to_user_failure(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()
        ws = AsyncMock()
        ws.send_json.side_effect = RuntimeError("connection closed")
        user = CollabUser(user_id="u1", display_name="User1", color="#000")
        await mgr.connect("room1", user, ws)

        await mgr.send_to_user("u1", {"type": "test"})

    @pytest.mark.asyncio
    async def test_connect_same_user_reconnect(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        user = CollabUser(user_id="u1", display_name="User1", color="#000")
        await mgr.connect("room1", user, ws1)
        accepted = await mgr.connect("room1", user, ws2)
        assert accepted is True

    def test_get_collab_service_existing(self):
        import backend.app.api.v1.collaboration.collab as mod
        old = mod._service
        svc = MagicMock()
        mod._service = svc
        result = mod.get_collab_service()
        assert result is svc
        mod._service = old

    def test_get_collab_manager_existing(self):
        import backend.app.api.v1.collaboration.collab as mod
        old = mod._manager
        mgr = MagicMock()
        mod._manager = mgr
        result = mod.get_collab_manager()
        assert result is mgr
        mod._manager = old
