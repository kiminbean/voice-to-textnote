"""
SPEC-COLLAB-001: 실시간 공동 편집 WebSocket 메시지 스키마 (Pydantic v2)

메시지 타입:
- snapshot: 최초 연결 시 전체 문서 전송
- edit: 필드 단위 편집 (LWW 적용 대상)
- presence: 활성 사용자 목록 변화
- cursor: 커서 위치 표시 (P2)
- ack: 서버가 edit 수신 확인 (클라이언트 LWW 확인용)
- error: 에러 메시지
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# 공통: 활성 사용자 (presence)
# ---------------------------------------------------------------------------


class PresenceUser(BaseModel):
    """활성 사용자 단건 표현 (presence broadcast용)."""

    user_id: str
    display_name: str
    avatar_url: str | None = None
    active_field: str | None = Field(
        default=None, description="현재 편집 중인 필드 경로 (cursor presence)"
    )


# ---------------------------------------------------------------------------
# 클라이언트 → 서버 메시지 (inbound)
# ---------------------------------------------------------------------------


class EditPayload(BaseModel):
    """단일 필드 편집 페이로드 (LWW 적용 대상)."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(
        ..., description="편집 대상 필드 경로 (예: 'summary_text', 'sections.0.content')"
    )
    value: Any = Field(..., description="새 값 (문자열·숫자·배열·객체 모두 허용)")
    client_timestamp: datetime = Field(..., description="클라이언트 편집 시각 (ISO 8601)")


class CursorPayload(BaseModel):
    """커서 위치 표시 페이로드 (P2, broadcast-only)."""

    model_config = ConfigDict(extra="forbid")

    field: str
    position: int = Field(default=0, ge=0)


class ClientMessage(BaseModel):
    """클라이언트 → 서버 WebSocket 메시지 래퍼."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., description="메시지 타입: 'edit' | 'cursor'")
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 서버 → 클라이언트 메시지 (outbound)
# ---------------------------------------------------------------------------


class SnapshotPayload(BaseModel):
    """최초 연결 시 전체 문서 스냅샷."""

    document: dict[str, Any] = Field(default_factory=dict, description="field-level 문서 JSON")
    field_timestamps: dict[str, datetime] = Field(
        default_factory=dict,
        description="필드별 서버 최종 수정 시각 (LWW 기준 시각)",
    )
    presence: list[PresenceUser] = Field(default_factory=list)


class EditBroadcastPayload(BaseModel):
    """다른 클라이언트에게 브로드캐스트되는 편집 메시지."""

    user_id: str
    field: str
    value: Any
    server_timestamp: datetime = Field(..., description="LWW 판정용 서버 타임스탬프")
    applied: bool = Field(..., description="LWW 결과 (True=반영됨, False=거부됨)")


class AckPayload(BaseModel):
    """편집 송신자에게 돌아가는 수신 확인."""

    field: str
    server_timestamp: datetime
    applied: bool


class ServerMessage(BaseModel):
    """서버 → 클라이언트 WebSocket 메시지 래퍼."""

    type: str = Field(
        ..., description="'snapshot' | 'edit' | 'presence' | 'cursor' | 'ack' | 'error'"
    )
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# WebSocket 닫기 코드 (SPEC-COLLAB-001 맞춤)
# ---------------------------------------------------------------------------

# 4401: 인증 실패 (잘못된 토큰)
# 4403: Room 가득 참 (최대 5명)
# 4404: 회의록 없음
WS_CLOSE_AUTH_FAILED = 4401
WS_CLOSE_ROOM_FULL = 4403
WS_CLOSE_NOT_FOUND = 4404
