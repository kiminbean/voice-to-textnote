"""
협업 편집 WebSocket 메시지 Pydantic v2 스키마
SPEC-COLLAB-001: 실시간 공동 편집 메시지 타입 정의
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── 클라이언트 → 서버 메시지 ──────────────────────────────────────────


class EditMessage(BaseModel):
    """클라이언트가 필드 편집을 보낼 때 사용"""

    type: str = "edit"
    # 편집할 필드명 (예: summary_text, action_items 등)
    field: str = Field(..., description="편집할 필드명")
    # 새 값
    value: str = Field(..., description="필드的新 값")
    # 클라이언트 타임스탬프 (참고용, LWW는 서버 타임스탬프 사용)
    client_ts: float = Field(default=0.0, description="클라이언트 타임스탬프")


class CursorMessage(BaseModel):
    """클라이언트가 편집 시작/종료를 알릴 때 사용"""

    type: str = "cursor"
    # 편집 중인 필드명 (null이면 편집 종료)
    field: str | None = Field(default=None, description="편집 중인 필드명")


class PingMessage(BaseModel):
    """하트비트 ping"""

    type: str = "ping"


# ── 서버 → 클라이언트 메시지 ──────────────────────────────────────────


class EditBroadcastMessage(BaseModel):
    """다른 사용자의 편집을 브로드캐스트"""

    type: str = "edit_broadcast"
    field: str
    value: str
    user_id: str
    user_name: str = Field(default="")
    server_ts: float


class SyncStateMessage(BaseModel):
    """신규 참여자에게 전체 상태 전송"""

    type: str = "sync_state"
    # 필드명 → {value, user_id, server_ts}
    fields: dict[str, FieldState]
    # 활성 사용자 목록
    active_users: list[CollabUser] = Field(default_factory=list)


class FieldState(BaseModel):
    """개별 필드 상태"""

    value: str = ""
    user_id: str = ""
    server_ts: float = 0.0


class CollabUser(BaseModel):
    """협업 참여자 정보"""

    user_id: str
    display_name: str = ""
    color: str = ""


class UserJoinedMessage(BaseModel):
    """사용자 입장 알림"""

    type: str = "user_joined"
    user_id: str
    display_name: str = ""
    color: str = ""


class UserLeftMessage(BaseModel):
    """사용자 퇴장 알림"""

    type: str = "user_joined"
    user_id: str
    display_name: str = ""


class PongMessage(BaseModel):
    """하트비트 pong"""

    type: str = "pong"


class ErrorMessage(BaseModel):
    """에러 메시지"""

    type: str = "error"
    code: int
    message: str


class RateLimitedMessage(BaseModel):
    """Rate limit 초과 알림"""

    type: str = "rate_limited"
    retry_after_ms: int = 1000
