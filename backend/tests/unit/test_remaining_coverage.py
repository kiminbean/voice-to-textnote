"""
Final remaining coverage: 5 modules below 95%

- backend/app/api/v1/webhooks.py (88% -> lines 46,64,77,88)
- backend/app/api/v1/audio_preprocess.py (90% -> lines 149-152, 188-192)
- backend/app/api/v1/dashboard.py (90% -> lines 65,82,87,91-92)
- backend/app/api/v1/enhanced_statistics.py (93% -> line 77)
- backend/schemas/bookmark.py (93% -> lines 28,58,63)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# webhooks.py - lines 46, 64, 77, 88 (CRUD return paths)
# ---------------------------------------------------------------------------
class TestWebhooksCrudReturns:
    """Cover the return lines in webhooks CRUD endpoints."""

    @pytest.fixture
    def mock_endpoint_obj(self):
        obj = MagicMock()
        obj.id = uuid.uuid4()
        obj.url = "https://example.com/hook"
        obj.secret = "s3cret"
        obj.events = ["task.completed"]
        obj.is_active = True
        obj.created_at = "2026-01-01T00:00:00"
        obj.updated_at = "2026-01-01T00:00:00"
        return obj

    @pytest.mark.asyncio
    async def test_create_webhook_return(self, mock_endpoint_obj):
        """Line 46: return from create_webhook"""
        from backend.app.api.v1.webhooks import create_webhook
        from backend.schemas.webhook import WebhookEndpointCreate, WebhookEndpointResponse

        payload = WebhookEndpointCreate(url="https://example.com/hook", events=["transcription.completed"])
        db = AsyncMock()
        user = MagicMock(id=uuid.uuid4())

        fake_resp = MagicMock(spec=WebhookEndpointResponse)
        fake_resp.id = mock_endpoint_obj.id
        fake_resp.url = mock_endpoint_obj.url
        fake_resp.events = ["transcription.completed"]
        fake_resp.is_active = True
        fake_resp.has_secret = False
        fake_resp.description = None
        fake_resp.created_at = "2026-01-01T00:00:00"
        fake_resp.updated_at = "2026-01-01T00:00:00"

        with patch("backend.app.api.v1.webhooks._service") as svc:
            svc.create = AsyncMock(return_value=mock_endpoint_obj)
            with patch.object(WebhookEndpointResponse, "from_orm_masked", return_value=fake_resp):
                result = await create_webhook(payload, db, user)
                assert result is not None

    @pytest.mark.asyncio
    async def test_list_webhooks_return(self, mock_endpoint_obj):
        """Line 64: return from list_webhooks"""
        from backend.app.api.v1.webhooks import list_webhooks
        from backend.schemas.webhook import WebhookEndpointResponse

        db = AsyncMock()
        user = MagicMock(id=uuid.uuid4())

        fake_resp = MagicMock(spec=WebhookEndpointResponse)
        fake_resp.id = mock_endpoint_obj.id
        fake_resp.url = mock_endpoint_obj.url
        fake_resp.events = mock_endpoint_obj.events
        fake_resp.is_active = True
        fake_resp.has_secret = False
        fake_resp.description = None
        fake_resp.created_at = "2026-01-01T00:00:00"
        fake_resp.updated_at = "2026-01-01T00:00:00"

        with patch("backend.app.api.v1.webhooks._service") as svc:
            svc.list_for_user = AsyncMock(return_value=([mock_endpoint_obj], 1))
            with patch.object(WebhookEndpointResponse, "from_orm_masked", return_value=fake_resp):
                result = await list_webhooks(page=1, page_size=50, db=db, user=user)
                assert result is not None

    @pytest.mark.asyncio
    async def test_get_webhook_return(self, mock_endpoint_obj):
        """Line 77: return from get_webhook"""
        from backend.app.api.v1.webhooks import get_webhook
        from backend.schemas.webhook import WebhookEndpointResponse

        db = AsyncMock()
        user = MagicMock(id=uuid.uuid4())
        wid = uuid.uuid4()

        fake_resp = MagicMock(spec=WebhookEndpointResponse)
        fake_resp.id = mock_endpoint_obj.id

        with patch("backend.app.api.v1.webhooks._service") as svc:
            svc.get_by_id = AsyncMock(return_value=mock_endpoint_obj)
            with patch.object(WebhookEndpointResponse, "from_orm_masked", return_value=fake_resp):
                result = await get_webhook(wid, db, user)
                assert result is not None

    @pytest.mark.asyncio
    async def test_update_webhook_return(self, mock_endpoint_obj):
        """Line 88: return from update_webhook"""
        from backend.app.api.v1.webhooks import update_webhook
        from backend.schemas.webhook import WebhookEndpointResponse, WebhookEndpointUpdate

        payload = WebhookEndpointUpdate(is_active=False)
        db = AsyncMock()
        user = MagicMock(id=uuid.uuid4())
        wid = uuid.uuid4()

        fake_resp = MagicMock(spec=WebhookEndpointResponse)
        fake_resp.id = mock_endpoint_obj.id

        with patch("backend.app.api.v1.webhooks._service") as svc:
            svc.update = AsyncMock(return_value=mock_endpoint_obj)
            with patch.object(WebhookEndpointResponse, "from_orm_masked", return_value=fake_resp):
                result = await update_webhook(wid, payload, db, user)
                assert result is not None


# ---------------------------------------------------------------------------
# audio_preprocess.py - lines 149-152, 188-192
# ---------------------------------------------------------------------------
class TestAudioPreprocessRemaining:
    """Cover the two uncovered exception paths in preprocess_endpoint."""

    @pytest.mark.asyncio
    async def test_upload_generic_exception_returns_400(self):
        """Lines 149-152: generic Exception during file write triggers HTTPException(400)"""
        from backend.app.api.v1.audio_preprocess import preprocess_endpoint

        mock_file = MagicMock()
        mock_file.filename = "test.wav"
        # read raises IOError -> caught by except Exception at line 149
        mock_file.read = AsyncMock(side_effect=OSError("disk full"))

        with patch("backend.app.api.v1.audio_preprocess.settings") as mock_settings:
            mock_settings.audio_preprocess_enabled = True
            mock_settings.audio_preprocess_max_file_mb = 100
            mock_settings.audio_preprocess_default_high_pass_hz = 0

            with patch("backend.app.api.v1.audio_preprocess.validate_audio_format",
                       return_value=(True, "ok")):
                with patch("backend.app.api.v1.audio_preprocess._safe_unlink"):
                    with patch("backend.app.api.v1.audio_preprocess.logger"):
                        with pytest.raises(HTTPException) as exc_info:
                            await preprocess_endpoint(
                                file=mock_file,
                                convert_to_16k_mono=True,
                                normalize=True,
                                target_dbfs=-20.0,
                                high_pass_hz=None,
                                low_pass_hz=None,
                                trim_silence=False,
                                silence_threshold_db=-40.0,
                                silence_min_len_ms=700,
                            )
                        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_oserror_during_wave_metadata(self):
        """Lines 188-192: OSError during wave.open triggers HTTPException(500)"""
        from pathlib import Path as P  # noqa: N817
        from unittest.mock import mock_open

        from backend.app.api.v1.audio_preprocess import preprocess_endpoint

        mock_file = MagicMock()
        mock_file.filename = "test.wav"
        mock_file.read = AsyncMock(
            side_effect=[b"fake audio data", b""]  # First read returns data, second returns empty
        )

        with patch("backend.app.api.v1.audio_preprocess.settings") as mock_settings:
            mock_settings.audio_preprocess_enabled = True
            mock_settings.audio_preprocess_max_file_mb = 100
            mock_settings.audio_preprocess_default_high_pass_hz = 0

            with patch("backend.app.api.v1.audio_preprocess.validate_audio_format",
                       return_value=(True, "ok")):
                with patch("backend.app.api.v1.audio_preprocess._safe_unlink"):
                    with patch("backend.app.api.v1.audio_preprocess.logger"):
                        with patch("backend.app.api.v1.audio_preprocess.preprocess_audio",
                                   return_value=P("/fake/out.wav")):
                            # wave.open raises OSError (not wave.Error/EOFError)
                            with patch("backend.app.api.v1.audio_preprocess.wave.open",
                                       side_effect=OSError("file access error")):
                                with patch("backend.app.api.v1.audio_preprocess._preprocess_semaphore") as sema:
                                    sema.__aenter__ = AsyncMock(return_value=None)
                                    sema.__aexit__ = AsyncMock(return_value=None)
                                    with patch("backend.app.api.v1.audio_preprocess.tempfile.mkstemp",
                                               return_value=(99, "/tmp/preprocess_in_test.wav")):
                                        with patch("builtins.open", mock_open()):
                                            with pytest.raises(HTTPException) as exc_info:
                                                await preprocess_endpoint(
                                                    file=mock_file,
                                                    convert_to_16k_mono=True,
                                                    normalize=True,
                                                    target_dbfs=-20.0,
                                                    high_pass_hz=None,
                                                    low_pass_hz=None,
                                                    trim_silence=False,
                                                    silence_threshold_db=-40.0,
                                                    silence_min_len_ms=700,
                                                )
                                            assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# dashboard.py - lines 65, 82, 87, 91-92
# ---------------------------------------------------------------------------
class TestDashboardRemaining:
    """Cover all uncovered paths in dashboard.py."""

    @pytest.mark.asyncio
    async def test_empty_records_returns_zero_overview(self):
        """Line 65: return DashboardOverview with zeros when no records"""
        from backend.app.api.v1.dashboard import DashboardOverview, get_dashboard_overview

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        redis_client = AsyncMock()

        result = await get_dashboard_overview(
            limit=100, redis_client=redis_client, db=db
        )
        assert isinstance(result, DashboardOverview)
        assert result.total_meetings == 0
        assert result.total_duration_seconds == 0.0

    @pytest.mark.asyncio
    async def test_non_dict_data_and_segments_skipped(self):
        """Lines 82, 87, 91-92: skip non-dict data, segments, invalid timestamps"""
        from backend.app.api.v1.dashboard import DashboardOverview, get_dashboard_overview

        # Record with non-dict result_data -> line 82 continue
        rec1 = MagicMock()
        rec1.result_data = "not a dict"

        # Record with non-dict segments -> line 87 continue
        rec2 = MagicMock()
        rec2.result_data = {"segments": ["string_seg", None, 123]}

        # Record with invalid timestamps -> lines 91-92 continue
        rec3 = MagicMock()
        rec3.result_data = {"segments": [{"start": "bad", "end": 5.0}]}

        # Valid record
        rec4 = MagicMock()
        rec4.result_data = {"segments": [{"start": 0.0, "end": 10.0, "text": "hello", "speaker": "A"}]}

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rec1, rec2, rec3, rec4]
        db.execute.return_value = mock_result

        redis_client = AsyncMock()

        result = await get_dashboard_overview(
            limit=100, redis_client=redis_client, db=db
        )
        assert isinstance(result, DashboardOverview)
        assert result.total_meetings == 4
        assert result.total_duration_seconds == 10.0
        assert result.total_segments == 1


# ---------------------------------------------------------------------------
# enhanced_statistics.py - line 77
# ---------------------------------------------------------------------------
class TestEnhancedStatsRemaining:
    """Cover line 77: pass-through to service."""

    @pytest.mark.asyncio
    async def test_project_overview_endpoint(self):
        """Line 77: return await _service.get_project_overview(...)"""
        from backend.app.api.v1.enhanced_statistics import get_project_overview

        mock_response = MagicMock()

        with patch("backend.app.api.v1.enhanced_statistics._service") as svc:
            svc.get_project_overview = AsyncMock(return_value=mock_response)
            db = AsyncMock()
            redis_client = AsyncMock()

            result = await get_project_overview(
                period="7d", top_meetings=5, db=db, redis_client=redis_client
            )
            assert result is mock_response


# ---------------------------------------------------------------------------
# schemas/bookmark.py - lines 28, 58, 63
# ---------------------------------------------------------------------------
class TestBookmarkSchemaCoverage:
    """Cover bookmark schema validator paths."""

    def test_bookmark_base_color_none(self):
        """Line 28: return None when color is None in BookmarkBase"""
        from backend.schemas.bookmark import BookmarkBase

        bm = BookmarkBase(segment_start=0.0, segment_end=5.0, color=None)
        assert bm.color is None

    def test_bookmark_base_color_empty_string(self):
        """Line 28-31: return None when color is empty/whitespace string"""
        from backend.schemas.bookmark import BookmarkBase

        bm = BookmarkBase(segment_start=0.0, segment_end=5.0, color="  ")
        assert bm.color is None

    def test_bookmark_update_color_none(self):
        """Line 58: return None when color is None in BookmarkUpdate"""
        from backend.schemas.bookmark import BookmarkUpdate

        upd = BookmarkUpdate(color=None)
        assert upd.color is None

    def test_bookmark_update_color_empty(self):
        """Line 58-61: return None when color is empty in BookmarkUpdate"""
        from backend.schemas.bookmark import BookmarkUpdate

        upd = BookmarkUpdate(color="")
        assert upd.color is None

    def test_bookmark_update_color_invalid(self):
        """Line 63: raise ValueError for invalid color in BookmarkUpdate"""
        from backend.schemas.bookmark import BookmarkUpdate

        with pytest.raises(ValueError, match="color"):
            BookmarkUpdate(color="!!!invalid!!!")

    def test_bookmark_base_valid_color(self):
        """Valid hex color should be accepted"""
        from backend.schemas.bookmark import BookmarkBase

        bm = BookmarkBase(segment_start=0.0, segment_end=5.0, color="#FF5500")
        assert bm.color == "#FF5500"

    def test_bookmark_update_valid_color_name(self):
        """Valid color name should be accepted"""
        from backend.schemas.bookmark import BookmarkUpdate

        upd = BookmarkUpdate(color="red")
        assert upd.color == "red"
