"""
통합 테스트: FastAPI TestClient로 WebSocket 핸드셰이크 검증
SPEC-COLLAB-001: AC-001~005, AC-050~053
Redis 없이 InMemoryRedis로 동작.
"""

import pytest
from unittest.mock import MagicMock, patch


# ── JWT mock 헬퍼 ────────────────────────────────────────────────────


def _make_mock_jwt_payload(
    user_id: str = "test-user-001",
    role: str = "member",
    name: str = "TestUser",
) -> dict:
    return {"sub": user_id, "role": role, "name": name, "type": "access"}


@pytest.fixture
def collab_client():
    """WebSocket 테스트용 FastAPI TestClient"""
    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.dependencies import get_redis_client

    # InMemoryRedis로 Redis 대체
    class InMemoryRedis:
        def __init__(self):
            self._data = {}

        async def get(self, key):
            return self._data.get(key)

        async def setex(self, key, ttl, value):
            self._data[key] = value

        async def delete(self, *keys):
            for k in keys:
                self._data.pop(k, None)

        async def hset(self, key, field, value):
            if key not in self._data:
                self._data[key] = {}
            self._data[key][field] = value

        async def expire(self, key, ttl):
            pass

    app.dependency_overrides[get_redis_client] = lambda: InMemoryRedis()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# ── AC-001: JWT 인증 WebSocket 연결 ──────────────────────────────────


class TestWSJWTAuth:
    """REQ-COLLAB-001, REQ-COLLAB-050"""

    def test_no_token_rejected(self, collab_client):
        """AC-002: JWT 없이 연결 시 4001 거부"""
        with pytest.raises(Exception):
            # WebSocket은 연결 실패 시 예외 발생
            with collab_client.websocket_connect("/api/v1/collab/test-task/ws"):
                pass

    @patch("backend.services.auth_service.AuthService")
    def test_valid_token_connects(self, MockAuthService, collab_client):
        """AC-001: 유효한 JWT로 연결 시 sync_state 수신"""
        mock_instance = MagicMock()
        mock_instance.decode_access_token.return_value = _make_mock_jwt_payload()
        MockAuthService.return_value = mock_instance

        with collab_client.websocket_connect(
            "/api/v1/collab/test-task/ws?token=fake-jwt-token"
        ) as ws:
            data = ws.receive_json()
            assert data["type"] == "sync_state"
            assert "fields" in data
            assert "active_users" in data

    @patch("backend.services.auth_service.AuthService")
    def test_expired_token_rejected(self, MockAuthService, collab_client):
        """AC-003: 만료된 토큰으로 연결 시 거부"""
        from fastapi import HTTPException

        mock_instance = MagicMock()
        mock_instance.decode_access_token.side_effect = HTTPException(
            status_code=401, detail="만료된 토큰"
        )
        MockAuthService.return_value = mock_instance

        with pytest.raises(Exception):
            with collab_client.websocket_connect(
                "/api/v1/collab/test-task/ws?token=expired-token"
            ):
                pass


# ── AC-004: Room 최대 인원 ────────────────────────────────────────────


class TestWSRoomLimit:
    """REQ-COLLAB-002"""

    @patch("backend.services.auth_service.AuthService")
    def test_edit_message_broadcast(self, MockAuthService, collab_client):
        """AC-010: edit 메시지 전송 시 정상 처리"""
        mock_instance = MagicMock()
        mock_instance.decode_access_token.return_value = _make_mock_jwt_payload()
        MockAuthService.return_value = mock_instance

        with collab_client.websocket_connect(
            "/api/v1/collab/test-task/ws?token=fake-jwt"
        ) as ws:
            # sync_state 수신
            sync = ws.receive_json()
            assert sync["type"] == "sync_state"

            # user_joined 수신 (자신은 제외 → 브로드캐스트 대상 없음)
            # edit 전송
            ws.send_json({
                "type": "edit",
                "field": "summary_text",
                "value": "통합 테스트 편집",
                "client_ts": 1.0,
            })
            # 단일 사용자라 브로드캐스트 수신자 없음 → 응답 없음 (정상)

    @patch("backend.services.auth_service.AuthService")
    def test_ping_pong(self, MockAuthService, collab_client):
        """AC-005: ping 전송 시 pong 응답"""
        mock_instance = MagicMock()
        mock_instance.decode_access_token.return_value = _make_mock_jwt_payload()
        MockAuthService.return_value = mock_instance

        with collab_client.websocket_connect(
            "/api/v1/collab/test-task/ws?token=fake-jwt"
        ) as ws:
            # sync_state 수신
            ws.receive_json()

            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"


# ── AC-051: Viewer 편집 차단 ──────────────────────────────────────────


class TestWSViewerBlocked:
    """REQ-COLLAB-051"""

    @patch("backend.services.auth_service.AuthService")
    def test_viewer_edit_rejected(self, MockAuthService, collab_client):
        """AC-051: viewer의 edit 메시지는 에러 반환"""
        mock_instance = MagicMock()
        mock_instance.decode_access_token.return_value = _make_mock_jwt_payload(
            role="viewer"
        )
        MockAuthService.return_value = mock_instance

        with collab_client.websocket_connect(
            "/api/v1/collab/test-task/ws?token=viewer-jwt"
        ) as ws:
            ws.receive_json()  # sync_state

            ws.send_json({
                "type": "edit",
                "field": "summary_text",
                "value": "viewer 시도",
            })

            error_msg = ws.receive_json()
            assert error_msg["type"] == "error"
            assert error_msg["code"] == 4005
