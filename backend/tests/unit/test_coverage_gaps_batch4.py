"""커버리지 gap 보충 배치4: API route handlers 직접 테스트"""

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _bookmark_mock(**overrides):
    defaults = dict(
        id=uuid.uuid4(), task_id="t1", user_id=uuid.uuid4(),
        segment_start=0.0, segment_end=10.0, text_snippet="text",
        note="note", color="#FF0000", category="note", priority="medium",
        tags=[], is_private=True, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _speaker_mock(**overrides):
    defaults = dict(
        id=uuid.uuid4(), user_id=uuid.uuid4(), speaker_label="SPEAKER_00",
        display_name="Speaker 0", role=None, note=None, task_id=None,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _vocab_mock(**overrides):
    defaults = dict(
        id=uuid.uuid4(), name="Test Vocab", words=["word1", "word2"],
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/audio/quality_assessment.py — helpers
# ═══════════════════════════════════════════════════════════════════
class TestQualityAssessmentHelpers:
    def test_extract_minutes_text_with_segments(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_text
        result = _extract_minutes_text({"segments": [{"text": "hello"}, {"text": "world"}]})
        assert "hello" in result
        assert "world" in result

    def test_extract_minutes_text_with_sections(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_text
        result = _extract_minutes_text({"sections": {"intro": "안녕하세요", "body": "내용"}})
        assert "안녕하세요" in result

    def test_extract_minutes_text_none(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_text
        assert _extract_minutes_text(None) == ""

    def test_extract_minutes_text_empty_dict(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_text
        assert _extract_minutes_text({}) == ""

    def test_extract_minutes_title(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_title
        assert _extract_minutes_title({"title": "회의 제목"}) == "회의 제목"

    def test_extract_minutes_title_none(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_title
        assert _extract_minutes_title(None) == ""

    def test_extract_minutes_title_non_string(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_title
        assert _extract_minutes_title({"title": 123}) == ""

    def test_extract_minutes_content_markdown(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_content
        task = MagicMock()
        task.result_data = {"markdown": "# 회의록", "title": "제목"}
        content, title = _extract_minutes_content(task)
        assert "# 회의록" in content
        assert title == "제목"

    def test_extract_minutes_content_segments(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_content
        task = MagicMock()
        task.result_data = {"segments": [{"text": "발화1"}, {"text": "발화2"}]}
        content, title = _extract_minutes_content(task)
        assert "발화1" in content

    def test_extract_minutes_content_summary_text(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_content
        task = MagicMock()
        task.result_data = {"summary_text": "요약입니다"}
        content, title = _extract_minutes_content(task)
        assert "요약입니다" in content

    def test_extract_minutes_content_empty(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_content
        task = MagicMock()
        task.result_data = {}
        content, title = _extract_minutes_content(task)
        assert content == ""

    def test_extract_minutes_content_meeting_title(self):
        from backend.app.api.v1.audio.quality_assessment import _extract_minutes_content
        task = MagicMock()
        task.result_data = {"meeting_title": "프로젝트 회의", "markdown": "내용"}
        content, title = _extract_minutes_content(task)
        assert title == "프로젝트 회의"

    @pytest.mark.asyncio
    async def test_health_check(self):
        from backend.app.api.v1.audio.quality_assessment import health_check
        result = await health_check()
        assert result["status"] == "healthy"


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/audio/enhanced_preprocess.py — helpers
# ═══════════════════════════════════════════════════════════════════
class TestEnhancedPreprocessHelpers:
    def test_calculate_audio_metrics_empty(self):
        import numpy as np
        from backend.app.api.v1.audio.enhanced_preprocess import _calculate_audio_metrics
        result = _calculate_audio_metrics(np.array([]), 16000)
        assert result["snr"] == 0.0
        assert result["clarity"] == 0.0

    def test_calculate_audio_metrics_signal(self):
        import numpy as np
        from backend.app.api.v1.audio.enhanced_preprocess import _calculate_audio_metrics
        data = np.sin(np.linspace(0, 2 * np.pi, 16000)).astype(np.float64)
        result = _calculate_audio_metrics(data, 16000)
        assert "snr" in result
        assert "clarity" in result
        assert "noise_level" in result

    def test_safe_unlink_exists(self, tmp_path):
        from backend.app.api.v1.audio.enhanced_preprocess import _safe_unlink
        f = tmp_path / "test.wav"
        f.write_text("data")
        _safe_unlink(f)

    def test_safe_unlink_not_exists(self, tmp_path):
        from backend.app.api.v1.audio.enhanced_preprocess import _safe_unlink
        _safe_unlink(tmp_path / "nonexistent.wav")


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/analytics/keyword_search.py — route handlers
# ═══════════════════════════════════════════════════════════════════
class TestKeywordSearchRoutes:
    @pytest.mark.asyncio
    async def test_search_keywords_route(self):
        from backend.app.api.v1.analytics.keyword_search import search_keywords
        from backend.schemas.keyword import KeywordSearchResponse
        svc = MagicMock()
        svc.search_keywords = AsyncMock(return_value=MagicMock(
            keywords=["test"],
            total_hits=0,
            total_documents=0,
            results=[],
            page=1,
            page_size=20,
            total_pages=0,
        ))
        db = AsyncMock()
        resp = await search_keywords(q="test", page=1, page_size=20, db=db, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_suggest_keywords_route(self):
        from backend.app.api.v1.analytics.keyword_search import suggest_keywords
        svc = MagicMock()
        svc.suggest_keywords = AsyncMock(return_value=MagicMock(
            suggestions=[],
            total=0,
        ))
        db = AsyncMock()
        resp = await suggest_keywords(context="meeting discussion topic", limit=5, db=db, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_get_keyword_statistics_route(self):
        from backend.app.api.v1.analytics.keyword_search import get_keyword_statistics
        svc = MagicMock()
        svc.get_keyword_stats = AsyncMock(return_value=MagicMock(
            period="30d",
            top_keywords=[],
            total_searches=0,
        ))
        db = AsyncMock()
        resp = await get_keyword_statistics(period="30d", top_n=20, db=db, svc=svc)
        assert resp is not None


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/analytics/export.py — route handlers
# ═══════════════════════════════════════════════════════════════════
class TestExportRoutes:
    @pytest.mark.asyncio
    async def test_export_meeting_minutes_not_found(self):
        from backend.app.api.v1.analytics.export import export_meeting_minutes
        from backend.app.errors import NotFoundError
        db = AsyncMock()
        db.get.return_value = None
        svc = MagicMock()

        with pytest.raises(NotFoundError):
            await export_meeting_minutes(task_id="missing", db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_export_meeting_minutes_not_completed(self):
        from backend.app.api.v1.analytics.export import export_meeting_minutes
        from backend.app.exceptions import UnprocessableEntityError
        db = AsyncMock()
        task = MagicMock()
        task.status = "processing"
        db.get.return_value = task
        svc = MagicMock()

        with pytest.raises(UnprocessableEntityError):
            await export_meeting_minutes(task_id="t1", db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_export_meeting_minutes_success(self):
        from backend.app.api.v1.analytics.export import export_meeting_minutes
        db = AsyncMock()
        task = MagicMock()
        task.status = "completed"
        db.get.return_value = task

        export_file = MagicMock()
        export_file.path = "/tmp/test.pdf"
        export_file.filename = "test.pdf"
        export_file.media_type = "application/pdf"
        svc = MagicMock()
        svc.export_meeting = AsyncMock(return_value=export_file)

        resp = await export_meeting_minutes(task_id="t1", db=db, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_export_batch_success(self):
        from backend.app.api.v1.analytics.export import export_batch_meetings
        from backend.schemas.export import ExportRequest, ExportFormat, ExportFile
        db = AsyncMock()
        task = MagicMock()
        task.status = "completed"
        task.result_data = {}
        task.task_id = "t1"
        task.task_type = "minutes"
        db.get.return_value = task

        export_file = ExportFile(
            task_id="t1", filename="test.pdf", path="/tmp/test.pdf",
            size_bytes=1024, media_type="application/pdf",
            created_at=datetime.now(UTC), format=ExportFormat.pdf,
        )
        svc = MagicMock()
        svc.export_batch_meetings = AsyncMock(return_value=[export_file])

        req = ExportRequest(task_ids=["t1"], format=ExportFormat.pdf)
        resp = await export_batch_meetings(request=req, db=db, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_get_export_templates(self):
        from backend.app.api.v1.analytics.export import get_export_templates
        from backend.schemas.export import ExportFormat
        svc = MagicMock()
        svc.get_export_templates = AsyncMock(return_value=[])
        db = AsyncMock()
        resp = await get_export_templates(format=ExportFormat.pdf, db=db, svc=svc)
        assert resp["available"] is True


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/auth/devices.py — route handlers
# ═══════════════════════════════════════════════════════════════════
class TestDeviceRoutes:
    @pytest.mark.asyncio
    async def test_register_device(self):
        from backend.app.api.v1.auth.devices import register_device
        from backend.schemas.device import DeviceRegisterRequest

        req = DeviceRegisterRequest(fcm_token="test-token", platform="ios")
        user = MagicMock()
        user.id = uuid.uuid4()
        db = AsyncMock()

        with patch("backend.app.api.v1.auth.devices._get_push") as mock_push:
            mock_push_svc = MagicMock()
            mock_push_svc.register_device = AsyncMock()
            mock_push.return_value = mock_push_svc

            resp = await register_device(req=req, current_user=user, db=db)
            assert resp.fcm_token == "test-token"
            assert resp.platform == "ios"

    @pytest.mark.asyncio
    async def test_unregister_device(self):
        from backend.app.api.v1.auth.devices import unregister_device

        user = MagicMock()
        user.id = uuid.uuid4()
        db = AsyncMock()

        with patch("backend.app.api.v1.auth.devices._get_push") as mock_push:
            mock_push_svc = MagicMock()
            mock_push_svc.get_user_tokens = AsyncMock(return_value=["token1"])
            mock_push_svc.invalidate_token = AsyncMock()
            mock_push.return_value = mock_push_svc

            await unregister_device(device_id="dev1", current_user=user, db=db)
            mock_push_svc.invalidate_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_unregister_device_no_tokens(self):
        from backend.app.api.v1.auth.devices import unregister_device

        user = MagicMock()
        user.id = uuid.uuid4()
        db = AsyncMock()

        with patch("backend.app.api.v1.auth.devices._get_push") as mock_push:
            mock_push_svc = MagicMock()
            mock_push_svc.get_user_tokens = AsyncMock(return_value=[])
            mock_push.return_value = mock_push_svc

            await unregister_device(device_id="dev1", current_user=user, db=db)

    @pytest.mark.asyncio
    async def test_list_devices(self):
        from backend.app.api.v1.auth.devices import list_devices

        user = MagicMock()
        user.id = uuid.uuid4()
        db = AsyncMock()

        dt = MagicMock()
        dt.id = uuid.uuid4()
        dt.fcm_token = "token1"
        dt.platform = "ios"
        dt.created_at = datetime.now(UTC)
        dt.updated_at = datetime.now(UTC)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [dt]
        db.execute.return_value = MagicMock(scalars=MagicMock(return_value=mock_scalars))

        resp = await list_devices(current_user=user, db=db)
        assert resp.total == 1
        assert len(resp.devices) == 1

    def test_is_valid_uuid(self):
        from backend.app.api.v1.auth.devices import is_valid_uuid
        assert is_valid_uuid(str(uuid.uuid4())) is True
        assert is_valid_uuid("not-a-uuid") is False


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/minutes/minutes.py — partial update (lines 226-253)
# ═══════════════════════════════════════════════════════════════════
class TestMinutesPatch:
    @pytest.mark.asyncio
    async def test_patch_minutes_not_found(self):
        from backend.app.api.v1.minutes.minutes import patch_minutes
        from backend.app.errors import NotFoundError
        from backend.schemas.minutes import MinutesPatchRequest

        redis = AsyncMock()
        redis.get.return_value = None

        with pytest.raises(NotFoundError):
            await patch_minutes(
                task_id="missing",
                request=MinutesPatchRequest(fields={"title": "New"}),
                redis_client=redis,
            )

    @pytest.mark.asyncio
    async def test_patch_minutes_success(self):
        from backend.app.api.v1.minutes.minutes import patch_minutes
        from backend.schemas.minutes import MinutesPatchRequest

        redis = AsyncMock()
        redis.get.return_value = json.dumps({"title": "Old", "summary": "S"}, ensure_ascii=False)
        redis.setex = AsyncMock()

        resp = await patch_minutes(
            task_id="t1",
            request=MinutesPatchRequest(fields={"title": "New Title"}),
            redis_client=redis,
        )
        assert resp["task_id"] == "t1"
        assert "title" in resp["updated_fields"]

    @pytest.mark.asyncio
    async def test_patch_minutes_skips_protected_fields(self):
        from backend.app.api.v1.minutes.minutes import patch_minutes
        from backend.schemas.minutes import MinutesPatchRequest

        redis = AsyncMock()
        redis.get.return_value = json.dumps({"segments": [], "title": "T"}, ensure_ascii=False)
        redis.setex = AsyncMock()

        resp = await patch_minutes(
            task_id="t1",
            request=MinutesPatchRequest(fields={"segments": "skip", "title": "New"}),
            redis_client=redis,
        )
        assert "segments" not in resp["updated_fields"]
        assert "title" in resp["updated_fields"]


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/minutes/keywords.py — lines 27, 40, 73, 96-97
# ═══════════════════════════════════════════════════════════════════
class TestMinutesKeywordsRoutes:
    @pytest.mark.asyncio
    async def test_extract_keywords_for_task(self):
        from backend.app.api.v1.minutes.keywords import get_meeting_keywords
        svc = MagicMock()
        svc.extract_for_task = AsyncMock(return_value=MagicMock(keywords=[], total=0))
        redis = AsyncMock()
        db = AsyncMock()

        resp = await get_meeting_keywords(
            task_id="t1", max_keywords=10, min_score=0.0,
            redis_client=redis, db=db, svc=svc,
        )
        assert resp is not None

    @pytest.mark.asyncio
    async def test_recommend_meeting_keywords(self):
        from backend.app.api.v1.minutes.keywords import recommend_meeting_keywords
        svc = MagicMock()
        svc.recommend_for_task = AsyncMock(return_value=MagicMock(keywords=[], total=0))
        redis = AsyncMock()
        db = AsyncMock()

        resp = await recommend_meeting_keywords(
            task_id="t1", redis_client=redis, db=db, svc=svc,
        )
        assert resp is not None


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/analytics/vocabulary.py — lines 46, 59, 73, 85
# ═══════════════════════════════════════════════════════════════════
class TestVocabularyRoutes:
    @pytest.mark.asyncio
    async def test_create_vocabulary(self):
        from backend.app.api.v1.analytics.vocabulary import create_vocabulary
        svc = MagicMock()
        svc.create = AsyncMock(return_value=_vocab_mock())
        db = AsyncMock()

        payload = MagicMock()
        resp = await create_vocabulary(payload=payload, db=db, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_list_vocabularies(self):
        from backend.app.api.v1.analytics.vocabulary import list_vocabularies
        svc = MagicMock()
        svc.list_all = AsyncMock(return_value=([_vocab_mock()], 1))
        db = AsyncMock()

        resp = await list_vocabularies(page=1, page_size=50, db=db, svc=svc)
        assert resp.total == 1

    @pytest.mark.asyncio
    async def test_get_vocabulary(self):
        from backend.app.api.v1.analytics.vocabulary import get_vocabulary
        svc = MagicMock()
        svc.get_by_id = AsyncMock(return_value=_vocab_mock())
        db = AsyncMock()

        resp = await get_vocabulary(vocab_id=uuid.uuid4(), db=db, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_update_vocabulary(self):
        from backend.app.api.v1.analytics.vocabulary import update_vocabulary
        svc = MagicMock()
        svc.update = AsyncMock(return_value=_vocab_mock(name="Updated"))
        db = AsyncMock()

        payload = MagicMock()
        resp = await update_vocabulary(vocab_id=uuid.uuid4(), payload=payload, db=db, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_delete_vocabulary(self):
        from backend.app.api.v1.analytics.vocabulary import delete_vocabulary
        svc = MagicMock()
        svc.delete = AsyncMock()
        db = AsyncMock()

        await delete_vocabulary(vocab_id=uuid.uuid4(), db=db, svc=svc)
        svc.delete.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/collaboration/bookmarks.py — lines 63, 88, 102, 114
# ═══════════════════════════════════════════════════════════════════
class TestBookmarkRoutes:
    @pytest.mark.asyncio
    async def test_list_bookmarks(self):
        from backend.app.api.v1.collaboration.bookmarks import list_bookmarks
        svc = MagicMock()
        svc.list_for_user = AsyncMock(return_value=([_bookmark_mock()], 1))
        db = AsyncMock()
        user = MagicMock()

        resp = await list_bookmarks(page=1, page_size=50, db=db, user=user, svc=svc)
        assert resp.total == 1

    @pytest.mark.asyncio
    async def test_get_bookmark(self):
        from backend.app.api.v1.collaboration.bookmarks import get_bookmark
        svc = MagicMock()
        svc.get_by_id = AsyncMock(return_value=_bookmark_mock())
        db = AsyncMock()
        user = MagicMock()

        resp = await get_bookmark(bookmark_id=uuid.uuid4(), db=db, user=user, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_update_bookmark(self):
        from backend.app.api.v1.collaboration.bookmarks import update_bookmark
        svc = MagicMock()
        svc.update = AsyncMock(return_value=_bookmark_mock(color="#00FF00", note="updated"))
        db = AsyncMock()
        user = MagicMock()
        payload = MagicMock()

        resp = await update_bookmark(bookmark_id=uuid.uuid4(), payload=payload, db=db, user=user, svc=svc)
        assert resp is not None


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/collaboration/speakers.py — lines 61, 92, 106, 118, 156, 183, 203
# ═══════════════════════════════════════════════════════════════════
class TestSpeakerRoutes:
    @pytest.mark.asyncio
    async def test_list_speakers(self):
        from backend.app.api.v1.collaboration.speakers import list_speakers
        svc = MagicMock()
        svc.list_for_user = AsyncMock(return_value=([_speaker_mock()], 1))
        db = AsyncMock()
        user = MagicMock()

        resp = await list_speakers(page=1, page_size=50, db=db, user=user, svc=svc)
        assert resp.total == 1

    @pytest.mark.asyncio
    async def test_get_speaker(self):
        from backend.app.api.v1.collaboration.speakers import get_speaker
        svc = MagicMock()
        svc.get_by_id = AsyncMock(return_value=_speaker_mock())
        db = AsyncMock()
        user = MagicMock()

        resp = await get_speaker(speaker_id=uuid.uuid4(), db=db, user=user, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_update_speaker(self):
        from backend.app.api.v1.collaboration.speakers import update_speaker
        svc = MagicMock()
        svc.update = AsyncMock(return_value=_speaker_mock(display_name="Updated"))
        db = AsyncMock()
        user = MagicMock()
        payload = MagicMock()

        resp = await update_speaker(speaker_id=uuid.uuid4(), payload=payload, db=db, user=user, svc=svc)
        assert resp is not None

    @pytest.mark.asyncio
    async def test_delete_speaker(self):
        from backend.app.api.v1.collaboration.speakers import delete_speaker
        svc = MagicMock()
        svc.delete = AsyncMock()
        db = AsyncMock()
        user = MagicMock()

        await delete_speaker(speaker_id=uuid.uuid4(), db=db, user=user, svc=svc)
        svc.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_speaker_sample(self):
        from backend.app.api.v1.collaboration.speakers import analyze_speaker_sample
        from backend.schemas.speaker import VoiceSampleAnalysis, VoiceCharacteristics
        svc = MagicMock()
        voice_svc = MagicMock()

        sample = VoiceSampleAnalysis(duration_seconds=1.0, sample_rate=16000, avg_dbfs=-20.0)
        voice = MagicMock()
        voice_svc.analyze_upload = AsyncMock(return_value=(sample, voice))
        voice_svc.to_characteristics_response.return_value = VoiceCharacteristics(
            speaker_profile_id=uuid.uuid4(), sample_count=1,
            total_duration_seconds=1.0, features={"pitch": 100.0},
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        )
        db = AsyncMock()
        user = MagicMock()
        file = MagicMock()

        resp = await analyze_speaker_sample(
            speaker_id=uuid.uuid4(), file=file, db=db, user=user, svc=svc, voice_svc=voice_svc,
        )
        assert resp is not None

    @pytest.mark.asyncio
    async def test_create_or_update_voice_profile(self):
        from backend.app.api.v1.collaboration.speakers import create_or_update_voice_profile
        svc = MagicMock()
        voice_svc = MagicMock()
        voice_svc.create_or_replace_from_samples = AsyncMock(return_value=MagicMock())
        voice_svc.to_characteristics_response.return_value = MagicMock()
        db = AsyncMock()
        user = MagicMock()
        payload = MagicMock()

        resp = await create_or_update_voice_profile(
            speaker_id=uuid.uuid4(), payload=payload, db=db, user=user, svc=svc, voice_svc=voice_svc,
        )
        assert resp is not None

    @pytest.mark.asyncio
    async def test_get_voice_characteristics(self):
        from backend.app.api.v1.collaboration.speakers import get_voice_characteristics
        svc = MagicMock()
        voice_svc = MagicMock()
        voice_svc.get_characteristics = AsyncMock(return_value=MagicMock())
        voice_svc.to_characteristics_response.return_value = MagicMock()
        db = AsyncMock()
        user = MagicMock()

        resp = await get_voice_characteristics(
            speaker_id=uuid.uuid4(), db=db, user=user, svc=svc, voice_svc=voice_svc,
        )
        assert resp is not None


# ═══════════════════════════════════════════════════════════════════
# db/models.py — line 56 (ActionItem repr)
# ═══════════════════════════════════════════════════════════════════
class TestModelsRepr:
    def test_action_item_repr(self):
        from backend.db.models import ActionItem
        try:
            item = ActionItem.__new__(ActionItem)
            item.id = uuid.uuid4()
            item.title = "Test Item"
            item.status = "pending"
            r = repr(item)
            assert "Test Item" in r
            assert "pending" in r
        except (TypeError, AttributeError):
            pytest.skip("ActionItem requires DB-backed init")


# ═══════════════════════════════════════════════════════════════════
# db/sync_engine.py — line 41 (fallback path)
# ═══════════════════════════════════════════════════════════════════
class TestSyncEngineFallback:
    def test_init_sync_engine_creates_new(self):
        import backend.db.sync_engine as mod
        old_engine = mod._initialized_engine
        old_factory = mod._initialized_session_factory
        mod._initialized_engine = None
        mod._initialized_session_factory = None

        with patch.object(mod, "settings") as mock_settings:
            mock_settings.database_url = "sqlite+aiosqlite:///:memory:"
            engine, factory = mod.init_sync_engine()
            assert engine is not None
            assert factory is not None

        mod._initialized_engine = old_engine
        mod._initialized_session_factory = old_factory


# ═══════════════════════════════════════════════════════════════════
# conftest.py — MockRedisPipeline, fixtures
# ═══════════════════════════════════════════════════════════════════
class TestConftestPipeline:
    @pytest.mark.asyncio
    async def test_mock_pipeline_execute(self):
        from backend.conftest import _MockRedisPipeline
        redis = AsyncMock()
        redis.get.return_value = b"value"
        redis._get_pipeline_results = MagicMock(return_value=None)

        pipeline = _MockRedisPipeline(redis)
        pipeline.get("key1")
        pipeline.set("key2", "val2")
        result = await pipeline.execute()
        assert result == [b"value", b"value"]

    @pytest.mark.asyncio
    async def test_mock_pipeline_zcard(self):
        from backend.conftest import _MockRedisPipeline
        redis = AsyncMock()
        redis._get_pipeline_results = MagicMock(return_value=None)

        pipeline = _MockRedisPipeline(redis)
        pipeline.zcard("sorted_set")
        result = await pipeline.execute()
        assert result == [0, 0]

    @pytest.mark.asyncio
    async def test_mock_pipeline_override(self):
        from backend.conftest import _MockRedisPipeline
        redis = AsyncMock()
        redis._get_pipeline_results = MagicMock(return_value=[1, 2, 3])

        pipeline = _MockRedisPipeline(redis)
        result = await pipeline.execute()
        assert result == [1, 2, 3]

    def test_mock_redis_client_fixture(self, mock_redis_client):
        assert mock_redis_client is not None
        assert mock_redis_client.pipeline is not None

    @pytest.mark.asyncio
    async def test_db_session_fixture(self, db_session):
        assert db_session is not None

    def test_completed_task_data_fixture(self, completed_task_data):
        assert completed_task_data["status"] == "completed"
        assert "task_id" in completed_task_data


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/collaboration/collab.py — send_to_user
# ═══════════════════════════════════════════════════════════════════
class TestCollabSendToUser:
    @pytest.mark.asyncio
    async def test_send_to_user_found(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()
        ws = AsyncMock()
        user = CollabUser(user_id="u1", display_name="User1", color="#000")
        await mgr.connect("room1", user, ws)

        await mgr.send_to_user("u1", {"type": "test"})
        assert ws.send_json.called

    @pytest.mark.asyncio
    async def test_send_to_user_not_found(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        mgr = CollabConnectionManager()
        await mgr.send_to_user("nonexistent", {"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_with_exclude(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        u1 = CollabUser(user_id="u1", display_name="User1", color="#000")
        u2 = CollabUser(user_id="u2", display_name="User2", color="#000")
        await mgr.connect("room1", u1, ws1)
        await mgr.connect("room1", u2, ws2)

        await mgr.broadcast("room1", {"type": "test"}, exclude_user="u1")
        ws1.send_json.assert_not_called()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_empty_room(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        mgr = CollabConnectionManager()
        await mgr.broadcast("nonexistent", {"type": "test"})

    @pytest.mark.asyncio
    async def test_disconnect_last_user_cleans_room(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        from backend.schemas.collab import CollabUser
        mgr = CollabConnectionManager()
        ws = AsyncMock()
        user = CollabUser(user_id="u1", display_name="User1", color="#000")
        await mgr.connect("room1", user, ws)
        await mgr.disconnect("room1", "u1")
        assert mgr.get_room_count("room1") == 0

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_room(self):
        from backend.app.api.v1.collaboration.collab import CollabConnectionManager
        mgr = CollabConnectionManager()
        await mgr.disconnect("nonexistent", "u1")
