"""
SPEC-COLLAB-001: 실시간 공동 편집 WebSocket API

WS /api/v1/collab/{task_id}/ws?token=JWT

인증은 query parameter(?token=...)로 전달된 JWT를 디코딩하여 처리한다.
(HTTP header를 WS handshake에서 사용할 수 없기 때문)

메시지 플로우:
  1. 클라이언트 연결 → 서버 snapshot 전송 + presence broadcast
  2. 클라이언트 edit → 서버 LWW 판정 → ack(송신자) + broadcast(나머지)
  3. 클라이언트 cursor → 서버 broadcast (P2)
  4. 클라이언트 연결 해제 → presence broadcast + 마지막 사용자면 DB flush
"""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_redis_client
from backend.db.auth_models import User
from backend.schemas.collab import (
    WS_CLOSE_AUTH_FAILED,
    WS_CLOSE_NOT_FOUND,
    WS_CLOSE_ROOM_FULL,
)
from backend.services.auth_service import AuthService
from backend.services.collab_service import CollabService
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/collab", tags=["collaboration"])


# ---------------------------------------------------------------------------
# ConnectionManager: task_id별 WebSocket Room 관리
# ---------------------------------------------------------------------------


class ConnectionManager:
    """
    task_id별 WebSocket 연결을 관리한다.

    구조:
      rooms: {task_id: {user_id: WebSocket}}
    """

    def __init__(self) -> None:
        self.rooms: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, task_id: str, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        if task_id not in self.rooms:
            self.rooms[task_id] = {}
        self.rooms[task_id][user_id] = ws

    def disconnect(self, task_id: str, user_id: str) -> None:
        room = self.rooms.get(task_id)
        if room and user_id in room:
            del room[user_id]
            if not room:
                del self.rooms[task_id]

    def get_room(self, task_id: str) -> dict[str, WebSocket]:
        return self.rooms.get(task_id, {})

    async def broadcast(
        self,
        task_id: str,
        message: dict,
        exclude_user_id: str | None = None,
    ) -> None:
        """같은 방의 모든(또는 exclude_user_id 제외) 클라이언트에게 메시지 전송."""
        room = self.get_room(task_id)
        raw = json.dumps(message, ensure_ascii=False, default=str)
        disconnected: list[str] = []
        for uid, ws in room.items():
            if exclude_user_id and uid == exclude_user_id:
                continue
            try:
                await ws.send_text(raw)
            except Exception:
                logger.warning("Failed to send to user_id=%s in task_id=%s", uid, task_id)
                disconnected.append(uid)
        for uid in disconnected:
            self.disconnect(task_id, uid)

    async def send_to_user(self, task_id: str, user_id: str, message: dict) -> None:
        """특정 사용자에게만 메시지 전송."""
        room = self.get_room(task_id)
        ws = room.get(user_id)
        if ws is not None:
            raw = json.dumps(message, ensure_ascii=False, default=str)
            await ws.send_text(raw)


# 싱글톤
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# JWT 인증 헬퍼 (WebSocket 전용)
# ---------------------------------------------------------------------------


async def authenticate_ws_token(
    token: str | None,
    db: AsyncSession,
) -> User | None:
    """
    WebSocket query parameter에서 JWT를 검증하여 User를 반환.

    Returns:
        User 객체 (인증 성공) 또는 None (인증 실패)
    """
    if not token:
        return None

    auth_service = AuthService()
    try:
        payload = auth_service.decode_access_token(token)
    except Exception:
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        return None

    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    return user


# ---------------------------------------------------------------------------
# WebSocket 엔드포인트
# ---------------------------------------------------------------------------


def get_collab_service() -> CollabService:
    """CollabService 인스턴스 제공."""
    return CollabService()


@router.websocket("/{task_id}/ws")
async def collab_ws(
    ws: WebSocket,
    task_id: str,
) -> None:
    """
    실시간 공동 편집 WebSocket.

    Query Parameters:
        token: JWT access token (필수)

    Close Codes:
        4401: 인증 실패
        4403: Room 가득 참 (최대 5명)
        4404: 회의록 없음
    """
    # DB 세션 수동 획득 (WebSocket에서는 Depends가 제한적)
    from backend.app.dependencies import _session_factory

    # 인증
    token = ws.query_params.get("token")
    async with _session_factory() as db:
        user = await authenticate_ws_token(token, db)
        if user is None:
            await ws.close(code=WS_CLOSE_AUTH_FAILED, reason="인증에 실패했습니다")
            return

        # task_id 존재 확인
        svc = get_collab_service()
        task_exists = await svc._ensure_task_exists(db, task_id)
        if not task_exists:
            await ws.close(code=WS_CLOSE_NOT_FOUND, reason="회의록을 찾을 수 없습니다")
            return

        # Redis 클라이언트
        redis = get_redis_client()

        # Presence 추가 (Room 정원 확인)
        joined, presence_list = await svc.add_presence(
            redis,
            task_id,
            str(user.id),
            user.display_name or user.email,
            getattr(user, "avatar_url", None),
        )
        if not joined:
            await ws.close(code=WS_CLOSE_ROOM_FULL, reason="편집 세션이 가득 찼습니다 (최대 5명)")
            return

        # DB에서 문서 초기화 (최초 연결 시)
        document = await svc.init_document_from_db(db, redis, task_id)
        document, field_timestamps = await svc.get_document(redis, task_id)

        # WebSocket accept + Room 등록
        await manager.connect(task_id, str(user.id), ws)

        # 1. snapshot 전송 (본인)
        snapshot_msg = {
            "type": "snapshot",
            "payload": {
                "document": document,
                "field_timestamps": {k: v.isoformat() for k, v in field_timestamps.items()},
                "presence": presence_list,
            },
        }
        await manager.send_to_user(task_id, str(user.id), snapshot_msg)

        # 2. presence broadcast (다른 참여자들)
        await manager.broadcast(
            task_id,
            {"type": "presence", "payload": {"presence": presence_list}},
            exclude_user_id=str(user.id),
        )

    # 메시지 루프
    try:
        while True:
            raw_text = await ws.receive_text()
            try:
                msg = json.loads(raw_text)
            except json.JSONDecodeError:
                await manager.send_to_user(
                    task_id,
                    str(user.id),
                    {"type": "error", "payload": {"detail": "잘못된 JSON 형식입니다"}},
                )
                continue

            msg_type = msg.get("type")
            payload = msg.get("payload", {})

            if msg_type == "edit":
                await _handle_edit(task_id, str(user.id), user, payload)
            elif msg_type == "cursor":
                await _handle_cursor(task_id, str(user.id), payload)
            else:
                await manager.send_to_user(
                    task_id,
                    str(user.id),
                    {"type": "error", "payload": {"detail": f"알 수 없는 메시지 타입: {msg_type}"}},
                )

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Unexpected error in collab_ws for task_id=%s", task_id)
    finally:
        await _handle_disconnect(task_id, str(user.id), user)


async def _handle_edit(
    task_id: str,
    user_id: str,
    user: User,
    payload: dict,
) -> None:
    """edit 메시지 처리: LWW 판정 → ack + broadcast."""

    redis = get_redis_client()
    svc = get_collab_service()

    field = payload.get("field")
    value = payload.get("value")
    client_ts_raw = payload.get("client_timestamp")

    if not field or client_ts_raw is None:
        await manager.send_to_user(
            task_id,
            user_id,
            {"type": "error", "payload": {"detail": "field와 client_timestamp는 필수입니다"}},
        )
        return

    try:
        client_ts = datetime.fromisoformat(client_ts_raw)
    except (ValueError, TypeError):
        await manager.send_to_user(
            task_id,
            user_id,
            {"type": "error", "payload": {"detail": "잘못된 timestamp 형식"}},
        )
        return

    applied, server_ts = await svc.apply_edit(redis, task_id, field, value, client_ts)

    # ack to sender
    await manager.send_to_user(
        task_id,
        user_id,
        {
            "type": "ack",
            "payload": {
                "field": field,
                "server_timestamp": server_ts.isoformat(),
                "applied": applied,
            },
        },
    )

    # broadcast to others (only if applied)
    if applied:
        await manager.broadcast(
            task_id,
            {
                "type": "edit",
                "payload": {
                    "user_id": user_id,
                    "field": field,
                    "value": value,
                    "server_timestamp": server_ts.isoformat(),
                    "applied": True,
                },
            },
            exclude_user_id=user_id,
        )


async def _handle_cursor(
    task_id: str,
    user_id: str,
    payload: dict,
) -> None:
    """cursor 메시지 처리: broadcast only (P2)."""
    field = payload.get("field")
    if not field:
        return

    redis = get_redis_client()
    svc = get_collab_service()

    # presence 업데이트
    await svc.update_active_field(redis, task_id, user_id, field)

    await manager.broadcast(
        task_id,
        {
            "type": "cursor",
            "payload": {"user_id": user_id, "field": field},
        },
        exclude_user_id=user_id,
    )


async def _handle_disconnect(
    task_id: str,
    user_id: str,
    user: User,
) -> None:
    """연결 해제 처리: presence 제거 + 마지막 사용자면 DB flush."""
    from backend.app.dependencies import _session_factory

    redis = get_redis_client()
    svc = get_collab_service()

    manager.disconnect(task_id, user_id)

    remaining = await svc.remove_presence(redis, task_id, user_id)

    # 남은 사용자들에게 presence 업데이트 broadcast
    if remaining:
        await manager.broadcast(
            task_id,
            {"type": "presence", "payload": {"presence": remaining}},
        )
    else:
        # 마지막 사용자 → DB flush
        async with _session_factory() as db:
            await svc.flush_to_db(
                db,
                redis,
                task_id,
                last_editor_id=uuid.UUID(user_id) if user_id else None,
            )
