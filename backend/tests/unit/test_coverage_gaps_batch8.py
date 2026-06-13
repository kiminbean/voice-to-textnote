"""커버리지 gap 보충 배치8: WebSocket handler + enhanced_preprocess helpers"""

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_session_chain(scalar_returns=None):
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    if scalar_returns is not None:
        results = [MagicMock(scalar_one_or_none=MagicMock(return_value=r)) for r in scalar_returns]
        session.execute = AsyncMock(side_effect=results)
    else:
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    factory = MagicMock(return_value=session)
    return session, factory


class TestWebSocketCollab:
    @pytest.mark.asyncio
    async def test_no_token_closes(self):
        from backend.app.api.v1.collaboration.collab import websocket_collab
        ws = AsyncMock()
        ws.query_params = {}
        await websocket_collab(ws, "task1")
        ws.close.assert_awaited_once_with(code=4001, reason="JWT token required")

    @pytest.mark.asyncio
    async def test_invalid_token_closes(self):
        from backend.app.api.v1.collaboration.collab import websocket_collab
        ws = AsyncMock()
        ws.query_params = {"token": "bad.jwt.token"}
        with patch("backend.services.auth_service.AuthService") as MockAuth:
            MockAuth.return_value.decode_access_token.side_effect = Exception("bad token")
            await websocket_collab(ws, "task1")
        ws.close.assert_awaited_once_with(code=4001, reason="Invalid or expired token")

    @pytest.mark.asyncio
    async def test_empty_user_id_closes(self):
        from backend.app.api.v1.collaboration.collab import websocket_collab
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        with patch("backend.services.auth_service.AuthService") as MockAuth:
            MockAuth.return_value.decode_access_token.return_value = {"sub": "", "role": "member", "name": "User"}
            await websocket_collab(ws, "task1")
        ws.close.assert_awaited_once_with(code=4001, reason="Invalid token payload")

    @pytest.mark.asyncio
    async def test_team_membership_db_error_closes(self):
        from backend.app.api.v1.collaboration.collab import websocket_collab
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        with patch("backend.services.auth_service.AuthService") as MockAuth, \
             patch("backend.db.engine.create_engine", side_effect=Exception("DB error")):
            MockAuth.return_value.decode_access_token.return_value = {"sub": "user1", "role": "member", "name": "User1"}
            await websocket_collab(ws, "task1")
        ws.close.assert_awaited_once_with(code=4004, reason="Membership verification failed")

    @pytest.mark.asyncio
    async def test_room_full_closes(self):
        from backend.app.api.v1.collaboration.collab import websocket_collab, CollabConnectionManager
        from backend.schemas.collab import CollabUser
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        full_manager = CollabConnectionManager()
        for i in range(5):
            u = CollabUser(user_id=f"u{i}", display_name=f"User{i}", color="#000")
            await full_manager.connect("task1", u, AsyncMock())
        _, factory = _mock_session_chain(scalar_returns=[None])
        with patch("backend.services.auth_service.AuthService") as MockAuth, \
             patch("backend.db.engine.create_engine", return_value=MagicMock()), \
             patch("backend.db.engine.get_session_factory", return_value=factory), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_manager", return_value=full_manager), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_service", return_value=AsyncMock()):
            MockAuth.return_value.decode_access_token.return_value = {"sub": "user6", "role": "member", "name": "User6"}
            await websocket_collab(ws, "task1")
        ws.close.assert_awaited_once_with(code=4003, reason="Room is full (max 5 users)")

    @pytest.mark.asyncio
    async def test_successful_ping_pong(self):
        from backend.app.api.v1.collaboration.collab import websocket_collab, CollabConnectionManager
        from fastapi import WebSocketDisconnect
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        ws.receive_json = AsyncMock(side_effect=[{"type": "ping"}, WebSocketDisconnect()])
        fresh_manager = CollabConnectionManager()
        mock_service = MagicMock()
        mock_service.get_sync_state = AsyncMock(return_value={})
        mock_service.has_unpersisted_changes = MagicMock(return_value=False)
        _, factory = _mock_session_chain(scalar_returns=[None])
        with patch("backend.services.auth_service.AuthService") as MockAuth, \
             patch("backend.db.engine.create_engine", return_value=MagicMock()), \
             patch("backend.db.engine.get_session_factory", return_value=factory), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_manager", return_value=fresh_manager), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_service", return_value=mock_service):
            MockAuth.return_value.decode_access_token.return_value = {"sub": "user1", "role": "member", "name": "User1"}
            await websocket_collab(ws, "task1")
        ws.accept.assert_awaited_once()
        ws.send_json.assert_any_await({"type": "pong"})

    @pytest.mark.asyncio
    async def test_viewer_cannot_edit(self):
        from backend.app.api.v1.collaboration.collab import websocket_collab, CollabConnectionManager
        from fastapi import WebSocketDisconnect
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        ws.receive_json = AsyncMock(side_effect=[
            {"type": "edit", "field": "title", "value": "x", "client_ts": 1.0},
            WebSocketDisconnect(),
        ])
        fresh_manager = CollabConnectionManager()
        mock_service = MagicMock()
        mock_service.get_sync_state = AsyncMock(return_value={})
        mock_service.has_unpersisted_changes = MagicMock(return_value=False)
        _, factory = _mock_session_chain(scalar_returns=[None])
        with patch("backend.services.auth_service.AuthService") as MockAuth, \
             patch("backend.db.engine.create_engine", return_value=MagicMock()), \
             patch("backend.db.engine.get_session_factory", return_value=factory), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_manager", return_value=fresh_manager), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_service", return_value=mock_service):
            MockAuth.return_value.decode_access_token.return_value = {"sub": "viewer1", "role": "viewer", "name": "Viewer"}
            await websocket_collab(ws, "task1")
        ws.send_json.assert_any_await({"type": "error", "code": 4005, "message": "Viewer cannot edit"})

    @pytest.mark.asyncio
    async def test_edit_success_broadcasts(self):
        from backend.app.api.v1.collaboration.collab import websocket_collab, CollabConnectionManager
        from fastapi import WebSocketDisconnect
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        ws.receive_json = AsyncMock(side_effect=[
            {"type": "edit", "field": "title", "value": "New Title", "client_ts": 1.0},
            WebSocketDisconnect(),
        ])
        fresh_manager = CollabConnectionManager()
        mock_service = MagicMock()
        mock_service.get_sync_state = AsyncMock(return_value={})
        mock_service.has_unpersisted_changes = MagicMock(return_value=False)
        mock_service.apply_edit = AsyncMock(return_value={"type": "edit", "field": "title", "value": "New Title"})
        _, factory = _mock_session_chain(scalar_returns=[None])
        with patch("backend.services.auth_service.AuthService") as MockAuth, \
             patch("backend.db.engine.create_engine", return_value=MagicMock()), \
             patch("backend.db.engine.get_session_factory", return_value=factory), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_manager", return_value=fresh_manager), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_service", return_value=mock_service):
            MockAuth.return_value.decode_access_token.return_value = {"sub": "editor1", "role": "member", "name": "Editor"}
            await websocket_collab(ws, "task1")
        mock_service.apply_edit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_last_user_flush(self):
        from backend.app.api.v1.collaboration.collab import websocket_collab, CollabConnectionManager
        from fastapi import WebSocketDisconnect
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        ws.receive_json = AsyncMock(side_effect=[WebSocketDisconnect()])
        fresh_manager = CollabConnectionManager()
        mock_service = MagicMock()
        mock_service.get_sync_state = AsyncMock(return_value={})
        mock_service.has_unpersisted_changes = MagicMock(return_value=True)
        mock_service.flush_room = AsyncMock(return_value={"title": "dirty"})
        _, factory = _mock_session_chain(scalar_returns=[None])
        with patch("backend.services.auth_service.AuthService") as MockAuth, \
             patch("backend.db.engine.create_engine", return_value=MagicMock()), \
             patch("backend.db.engine.get_session_factory", return_value=factory), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_manager", return_value=fresh_manager), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_service", return_value=mock_service):
            MockAuth.return_value.decode_access_token.return_value = {"sub": "solo1", "role": "member", "name": "Solo"}
            await websocket_collab(ws, "task1")
        mock_service.flush_room.assert_awaited_once_with("task1")

    @pytest.mark.asyncio
    async def test_team_member_not_found_closes(self):
        from backend.app.api.v1.collaboration.collab import websocket_collab
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        _, factory = _mock_session_chain(scalar_returns=["team-123", None])
        with patch("backend.services.auth_service.AuthService") as MockAuth, \
             patch("backend.db.engine.create_engine", return_value=MagicMock()), \
             patch("backend.db.engine.get_session_factory", return_value=factory):
            MockAuth.return_value.decode_access_token.return_value = {"sub": "550e8400-e29b-41d4-a716-446655440001", "role": "member", "name": "User1"}
            await websocket_collab(ws, "task1")
        ws.close.assert_awaited_once_with(code=4004, reason="Not a team member")

    @pytest.mark.asyncio
    async def test_team_member_valid_passes(self):
        from backend.app.api.v1.collaboration.collab import websocket_collab, CollabConnectionManager
        from fastapi import WebSocketDisconnect
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        ws.receive_json = AsyncMock(side_effect=[WebSocketDisconnect()])
        fresh_manager = CollabConnectionManager()
        mock_service = MagicMock()
        mock_service.get_sync_state = AsyncMock(return_value={})
        mock_service.has_unpersisted_changes = MagicMock(return_value=False)
        _, factory = _mock_session_chain(scalar_returns=["team-123", "member-id"])
        with patch("backend.services.auth_service.AuthService") as MockAuth, \
             patch("backend.db.engine.create_engine", return_value=MagicMock()), \
             patch("backend.db.engine.get_session_factory", return_value=factory), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_manager", return_value=fresh_manager), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_service", return_value=mock_service):
            MockAuth.return_value.decode_access_token.return_value = {"sub": "550e8400-e29b-41d4-a716-446655440001", "role": "member", "name": "User1"}
            await websocket_collab(ws, "task1")
        ws.accept.assert_awaited_once()


class TestEnhancedPreprocessHelpers:
    def test_get_quality_grade(self):
        from backend.app.api.v1.audio.enhanced_preprocess import _get_quality_grade
        assert _get_quality_grade(35) == "excellent"
        assert _get_quality_grade(25) == "good"
        assert _get_quality_grade(17) == "fair"
        assert _get_quality_grade(12) == "poor"
        assert _get_quality_grade(5) == "very_poor"

    def test_recommendations_low_snr(self):
        from backend.app.api.v1.audio.enhanced_preprocess import _generate_improvement_recommendations
        recs = _generate_improvement_recommendations({"snr": 10, "clarity": 0.5, "noise_level": 0.05})
        assert any("노이즈 제거" in r for r in recs)

    def test_recommendations_low_clarity(self):
        from backend.app.api.v1.audio.enhanced_preprocess import _generate_improvement_recommendations
        recs = _generate_improvement_recommendations({"snr": 20, "clarity": 0.2, "noise_level": 0.05})
        assert any("고주파" in r for r in recs)

    def test_recommendations_high_noise(self):
        from backend.app.api.v1.audio.enhanced_preprocess import _generate_improvement_recommendations
        recs = _generate_improvement_recommendations({"snr": 20, "clarity": 0.5, "noise_level": 0.2})
        assert any("배경 소음" in r for r in recs)

    def test_recommendations_good_quality(self):
        from backend.app.api.v1.audio.enhanced_preprocess import _generate_improvement_recommendations
        recs = _generate_improvement_recommendations({"snr": 25, "clarity": 0.6, "noise_level": 0.05})
        assert any("양호" in r for r in recs)

    def test_safe_unlink_no_error(self):
        from backend.app.api.v1.audio.enhanced_preprocess import _safe_unlink
        _safe_unlink(Path("/tmp/nonexistent_file_12345.bin"))

    @pytest.mark.asyncio
    async def test_download_enhanced_not_found(self):
        from backend.app.api.v1.audio.enhanced_preprocess import download_enhanced_audio
        from backend.app.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            await download_enhanced_audio("nonexistent_id")

    @pytest.mark.asyncio
    async def test_get_supported_formats(self):
        from backend.app.api.v1.audio.enhanced_preprocess import get_supported_formats
        result = await get_supported_formats()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_model_status(self):
        from backend.app.api.v1.audio.enhanced_preprocess import get_model_status
        mock_processor = MagicMock()
        mock_processor.ai_model.model_loaded = False
        mock_processor.max_batch_files = 20
        with patch("backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    new_callable=AsyncMock, return_value=mock_processor):
            result = await get_model_status()
            assert result["model_loaded"] is False


class TestRateLimiter:
    def test_limited_at_threshold(self):
        from backend.app.api.v1.collaboration.collab import _RateLimiter
        limiter = _RateLimiter(max_count=3, window_sec=1.0)
        assert not limiter.is_limited("u1")
        assert not limiter.is_limited("u1")
        assert not limiter.is_limited("u1")
        assert limiter.is_limited("u1")

    def test_clear_resets(self):
        from backend.app.api.v1.collaboration.collab import _RateLimiter
        limiter = _RateLimiter(max_count=1, window_sec=60.0)
        limiter.is_limited("u1")
        assert limiter.is_limited("u1")
        limiter.clear("u1")
        assert not limiter.is_limited("u1")

    def test_different_users_independent(self):
        from backend.app.api.v1.collaboration.collab import _RateLimiter
        limiter = _RateLimiter(max_count=1, window_sec=60.0)
        assert not limiter.is_limited("u1")
        assert not limiter.is_limited("u2")
        assert limiter.is_limited("u1")
        assert limiter.is_limited("u2")
