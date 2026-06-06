"""
SPEC-MOBILE-001: FCM 디바이스 토큰 모델

REQ-MOBILE-001~006: FCM 토큰 영속 저장 및 관리
- user_id: 사용자 ID (String, auth system 호환)
- fcm_token: FCM 등록 토큰 (Unique)
- platform: 디바이스 플랫폼 (ios/android/web)
- is_active: 토큰 활성화 여부
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class DeviceToken(Base):
    """
    SPEC-MOBILE-001: FCM 디바이스 토큰 모델

    FCM 토큰을 영속 저장하고 관리합니다.
    동일한 fcm_token은 중복 저장될 수 없습니다.
    """

    __tablename__ = "device_tokens"

    # REQ-DB-006: UUID 기본 키
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # 사용자 ID (String, auth system user_id pattern)
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # FCM 등록 토큰 (유니크 제약조건)
    fcm_token: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
        index=True,
    )

    # 디바이스 플랫폼 (ios/android/web)
    platform: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # 토큰 활성화 여부 (기본값 True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        server_default="1",
    )

    # REQ-DB-006: 자동 타임스탬프
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

    def __repr__(self) -> str:
        return (
            f"<DeviceToken(id={self.id}, user_id={self.user_id!r}, "
            f"platform={self.platform!r}, is_active={self.is_active})>"
        )
