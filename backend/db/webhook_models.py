"""
SPEC-WEBHOOK-001: 웹훅 엔드포인트 ORM 모델

REQ-WEBHOOK-001: 사용자가 외부 URL을 등록하여 작업 완료 시 알림을 받는다.
REQ-WEBHOOK-002: 이벤트 타입 필터링 (transcription.completed 등)
REQ-WEBHOOK-003: HMAC-SHA256 서명으로 페이로드 검증 지원
REQ-WEBHOOK-004: 사용자 삭제 시 연결된 웹훅도 CASCADE로 삭제
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow

# 지원 이벤트 타입
WEBHOOK_EVENT_TYPES = frozenset({
    "transcription.completed",
    "transcription.failed",
    "diarization.completed",
    "diarization.failed",
    "minutes.completed",
    "minutes.failed",
    "summary.completed",
    "summary.failed",
})


class WebhookEndpoint(Base):
    """외부 웹훅 엔드포인트.

    - url: HTTP(S) 수신 URL (최대 500자)
    - events: 수신할 이벤트 타입 목록 (빈 배열 = 전체 이벤트)
    - secret: HMAC-SHA256 서명 키 (선택, 평문 저장)
    - is_active: False이면 이벤트 전송 건너뜀
    """

    __tablename__ = "webhook_endpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # 소유자
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 수신 URL
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    # 수신할 이벤트 타입 목록 (JSON list). 빈 배열 = 전체
    events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # HMAC-SHA256 서명 키 (선택)
    secret: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 활성화 여부
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 설명 (선택)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    __table_args__ = (
        Index("ix_webhook_endpoints_user_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<WebhookEndpoint(id={self.id}, user_id={self.user_id}, "
            f"url={self.url!r}, active={self.is_active})>"
        )
