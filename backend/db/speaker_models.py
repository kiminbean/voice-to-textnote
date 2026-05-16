"""
SPEC-SPEAKER-001: 화자 프로필 ORM 모델

REQ-SPEAKER-001: 사용자가 화자 레이블(SPEAKER_00 등)에 이름과 역할을 매핑한다.
REQ-SPEAKER-002: task_id가 None이면 전역 프로필, 값이 있으면 해당 회의록 전용 오버라이드.
REQ-SPEAKER-003: 사용자 삭제 시 연결된 화자 프로필도 CASCADE로 삭제된다.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class SpeakerProfile(Base):
    """화자 ID → 이름/역할 매핑 프로필.

    - speaker_label: 화자 분리 결과의 레이블 (예: SPEAKER_00, SPEAKER_01)
    - task_id=None: 전역 프로필 (모든 회의록에 적용)
    - task_id 지정: 해당 회의록 전용 오버라이드
    """

    __tablename__ = "speaker_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # 소유자 ID
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 화자 분리 레이블 (예: SPEAKER_00)
    speaker_label: Mapped[str] = mapped_column(String(50), nullable=False)

    # 표시 이름 (예: 김철수)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 역할 (예: 팀장, 개발자) — 선택
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 메모 — 선택
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 대상 회의록 task_id — None이면 전역, 값이면 회의록 오버라이드
    task_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("task_results.task_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

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

    # (user_id, speaker_label, task_id) 조합 인덱스 (조회 최적화)
    __table_args__ = (
        Index("ix_speaker_profiles_user_label_task", "user_id", "speaker_label", "task_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<SpeakerProfile(id={self.id}, user_id={self.user_id}, "
            f"label={self.speaker_label!r}, name={self.display_name!r})>"
        )
