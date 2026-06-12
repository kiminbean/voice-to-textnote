"""
협업 편집 WebSocket 엔드포인트 + ConnectionManager
SPEC-COLLAB-001: REQ-COLLAB-001~004, 050~053
"""

from __future__ import annotations

import asyncio
import collections
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.schemas.collab import CollabUser, EditMessage
from backend.services.collab_service import CollabService
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["collaboration"])

# REQ-COLLAB-052: 사용자별 Rate limit — 1초당 최대 10개 edit
_EDIT_RATE_LIMIT = 10
_EDIT_RATE_WINDOW = 1.0

# REQ-COLLAB-051: viewer는 edit 불가
_VIEWER_ROLE = "viewer"


class _RateLimiter:
    """사용자별 슬라이딩 윈도우 Rate limiter"""

    def __init__(self, max_count: int, window_sec: float) -> None:
        self._max = max_count
        self._window = window_sec
        self._timestamps: dict[str, collections.deque[float]] = collections.defaultdict(
            lambda: collections.deque()
        )

    def is_limited(self, user_id: str) -> bool:
        now = time.time()
        ts = self._timestamps[user_id]
        cutoff = now - self._window
        while ts and ts[0] < cutoff:
            ts.popleft()
        if len(ts) >= self._max:
            return True
        ts.append(now)
        return False

    def clear(self, user_id: str) -> None:
        self._timestamps.pop(user_id, None)


_rate_limiter = _RateLimiter(_EDIT_RATE_LIMIT, _EDIT_RATE_WINDOW)


class CollabConnectionManager:
    """
    WebSocket 연결 관리자.
    # @MX:NOTE: room 기반 연결 관리. 최대 5명/room. 서버 타임스탬프 기준 LWW 충돌 해결.
    """

    MAX_USERS_PER_ROOM = 5

    def __init__(self) -> None:
        # room_id → {"users": {user_id: CollabUser}, "websockets": {user_id: WebSocket}}
        self._rooms: dict[str, dict[str, Any]] = {}

    async def connect(
        self,
        room_id: str,
        user: CollabUser,
        websocket: WebSocket | None = None,
    ) -> bool:
        """
        사용자를 room에 참가시킨다.
        최대 인원 초과 시 False 반환.
        """
        if room_id not in self._rooms:
            self._rooms[room_id] = {"users": {}, "websockets": {}}

        room = self._rooms[room_id]

        # 최대 인원 체크 (이미 참가 중인 사용자는 제외)
        if user.user_id not in room["users"] and len(room["users"]) >= self.MAX_USERS_PER_ROOM:
            logger.warning(
                "Room 최대 인원 초과",
                room_id=room_id,
                user_id=user.user_id,
                current=len(room["users"]),
                max=self.MAX_USERS_PER_ROOM,
            )
            return False

        room["users"][user.user_id] = user
        if websocket is not None:
            room["websockets"][user.user_id] = websocket

        logger.info(
            "사용자 room 참가",
            room_id=room_id,
            user_id=user.user_id,
            display_name=user.display_name,
            room_size=len(room["users"]),
        )
        return True

    async def disconnect(self, room_id: str, user_id: str) -> None:
        """사용자를 room에서 제거한다."""
        if room_id not in self._rooms:
            return

        room = self._rooms[room_id]
        room["users"].pop(user_id, None)
        room["websockets"].pop(user_id, None)

        logger.info(
            "사용자 room 퇴장",
            room_id=room_id,
            user_id=user_id,
            remaining=len(room["users"]),
        )

        # 마지막 참여자 퇴장 시 room 정리
        if len(room["users"]) == 0:
            del self._rooms[room_id]
            logger.info("Room 정리 (참여자 0명)", room_id=room_id)

    async def get_room_users(self, room_id: str) -> list[CollabUser]:
        """room의 활성 사용자 목록을 반환한다."""
        room = self._rooms.get(room_id)
        if room is None:
            return []
        return list(room["users"].values())

    async def broadcast(
        self,
        room_id: str,
        message: dict,
        exclude_user: str | None = None,
    ) -> None:
        """room 내 모든 사용자에게 메시지를 브로드캐스트한다."""
        room = self._rooms.get(room_id)
        if room is None:
            return

        for uid, ws in room["websockets"].items():
            if uid == exclude_user:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                logger.warning("브로드캐스트 전송 실패", room_id=room_id, user_id=uid)

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """특정 사용자에게 메시지를 전송한다."""
        for room in self._rooms.values():
            ws = room["websockets"].get(user_id)
            if ws is not None:
                try:
                    await ws.send_json(message)
                except Exception:
                    logger.warning("개별 전송 실패", user_id=user_id)
                return

    def get_room_count(self, room_id: str) -> int:
        """room의 현재 참여자 수를 반환한다."""
        room = self._rooms.get(room_id)
        return len(room["users"]) if room else 0


# ── 전역 ConnectionManager 인스턴스 ───────────────────────────────────

_manager: CollabConnectionManager | None = None
_service: CollabService | None = None


def get_collab_manager() -> CollabConnectionManager:
    """싱글톤 ConnectionManager 반환"""
    global _manager
    if _manager is None:
        _manager = CollabConnectionManager()
    return _manager


def get_collab_service() -> CollabService:
    """싱글톤 CollabService 반환"""
    global _service
    if _service is None:
        _service = CollabService(redis_client=None)
    return _service


# ── WebSocket 엔드포인트 ──────────────────────────────────────────────


@router.websocket("/collab/{task_id}/ws")
async def websocket_collab(websocket: WebSocket, task_id: str) -> None:
    """
    협업 편집 WebSocket 엔드포인트
    WS /api/v1/collab/{task_id}/ws?token=<jwt>

    SPEC-COLLAB-001:
    - REQ-COLLAB-001: JWT 인증 WebSocket 연결
    - REQ-COLLAB-002: task_id 기준 room 관리, 최대 5명
    - REQ-COLLAB-003: user_joined/user_left 이벤트
    - REQ-COLLAB-004: 30초 ping/pong 하트비트
    - REQ-COLLAB-010~013: LWW 편집 동기화
    - REQ-COLLAB-020~022: 디바운스 영속화
    """
    manager = get_collab_manager()
    service = get_collab_service()

    # REQ-COLLAB-050: JWT 검증
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="JWT token required")
        return

    try:
        from backend.services.auth_service import AuthService
        auth_service = AuthService()
        payload = auth_service.decode_access_token(token)
        decoded_user_id = payload.get("sub", "")
        user_role = payload.get("role", "member")
        display_name = payload.get("name", "User")
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    if not decoded_user_id:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    user_id = decoded_user_id

    # AC-053: 팀 멤버십 검증 — task_id가 속한 팀의 멤버인지 확인
    try:
        from backend.db.engine import create_engine, get_session_factory
        from backend.db.auth_models import MeetingOwnership, TeamMember
        import uuid

        _engine = create_engine()
        _session_factory = get_session_factory(_engine)
        async with _session_factory() as session:
            # 1) task_id가 공유된 팀 찾기
            from sqlalchemy import select
            ownership_stmt = (
                select(MeetingOwnership.team_id)
                .where(MeetingOwnership.task_id == task_id)
                .limit(1)
            )
            result = await session.execute(ownership_stmt)
            team_id_row = result.scalar_one_or_none()

            if team_id_row is not None:
                # 2) 해당 팀의 멤버인지 확인
                member_stmt = select(TeamMember.id).where(
                    TeamMember.team_id == team_id_row,
                    TeamMember.user_id == uuid.UUID(user_id),
                )
                member_result = await session.execute(member_stmt)
                if member_result.scalar_one_or_none() is None:
                    await websocket.close(code=4004, reason="Not a team member")
                    return
            # team_id가 NULL이면 개인 회의 — 소유자 확인 (선택적)
    except Exception as exc:
        logger.warning("팀 멤버십 검증 실패: %s", exc)
        # 검증 실패 시 연결 차단 (안전 우선)
        await websocket.close(code=4004, reason="Membership verification failed")
        return

    user = CollabUser(user_id=user_id, display_name=display_name, color="#3B82F6")

    # Room 참가 시도
    accepted = await manager.connect(task_id, user, websocket)
    if not accepted:
        await websocket.close(code=4003, reason="Room is full (max 5 users)")
        return

    # WebSocket 연결 수립
    await websocket.accept()

    try:
        # sync_state 전송 (REQ-COLLAB-012) — 서비스 상태 반영
        users = await manager.get_room_users(task_id)
        fields_raw = await service.get_sync_state(task_id)
        fields_dict = {
            k: v.model_dump() for k, v in fields_raw.items()
        }
        await websocket.send_json({
            "type": "sync_state",
            "fields": fields_dict,
            "active_users": [u.model_dump() for u in users],
        })

        # user_joined 브로드캐스트 (REQ-COLLAB-003)
        await manager.broadcast(task_id, {
            "type": "user_joined",
            "user_id": user.user_id,
            "display_name": user.display_name,
            "color": user.color,
        }, exclude_user=user.user_id)

        # 메시지 루프
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "edit":
                # REQ-COLLAB-051: viewer는 편집 불가
                if user_role == _VIEWER_ROLE:
                    await websocket.send_json({
                        "type": "error",
                        "code": 4005,
                        "message": "Viewer cannot edit",
                    })
                    continue

                # REQ-COLLAB-052: Rate limit 체크
                if _rate_limiter.is_limited(user_id):
                    await websocket.send_json({
                        "type": "rate_limited",
                        "retry_after_ms": 1000,
                    })
                    continue

                edit = EditMessage(
                    field=data.get("field", ""),
                    value=data.get("value", ""),
                    client_ts=data.get("client_ts", 0.0),
                )
                broadcast_msg = await service.apply_edit(task_id, user, edit)
                await manager.broadcast(task_id, broadcast_msg, exclude_user=user.user_id)

            elif msg_type == "cursor":
                # TODO: 커서 브로드캐스트 (M4에서 구현)
                pass

    except WebSocketDisconnect:
        logger.info("WebSocket 연결 종료", task_id=task_id, user_id=user_id)
    finally:
        # user_left 브로드캐스트 + room 정리
        await manager.disconnect(task_id, user_id)
        await manager.broadcast(task_id, {
            "type": "user_left",
            "user_id": user_id,
        })

        # REQ-COLLAB-022: 마지막 사용자 퇴장 시 즉시 flush
        remaining = manager.get_room_count(task_id)
        if remaining == 0 and service.has_unpersisted_changes(task_id):
            dirty = await service.flush_room(task_id)
            if dirty:
                logger.info(
                    "마지막 사용자 퇴장 — flush 수행",
                    task_id=task_id,
                    fields=list(dirty.keys()),
                )
                # TODO: 실제 DB 영속화 (PATCH /minutes/{task_id} 호출)
