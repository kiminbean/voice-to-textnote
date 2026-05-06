"""
SPEC-TAG-001: 회의록 자동 태그 ORM 모델

REQ-TAG-001: 회의록 내용에서 주제, 카테고리, 중요도 태그를 자동/수동 생성.
REQ-TAG-002: task_id 기반으로 회의록에 태그 연결.
REQ-TAG-003: 사용자 삭제 시 연결된 태그도 CASCADE 삭제.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class MeetingTag(Base):
    """회의록 태그 모델.

    - tag_type: 태그 종류 (topic, category, priority, custom)
    - tag_value: 태그 값 (예: "프로젝트A", "중요", "회의")
    - source: 태그 생성 방식 (auto=AI자동, manual=수동)
    - confidence: AI 자동 태그의 신뢰도 (0.0~1.0, 수동 태그는 NULL)
    """

    __tablename__ = "meeting_tags"

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

    # 대상 회의록 task_id
    task_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("task_results.task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 태그 종류 (topic, category, priority, custom)
    tag_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # 태그 값
    tag_value: Mapped[str] = mapped_column(String(200), nullable=False)

    # 생성 방식 (auto, manual)
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
    )

    # AI 신뢰도 (0.0~1.0)
    confidence: Mapped[float | None] = mapped_column(nullable=True)

    # 메모 — 선택
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

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
        Index(
            "ix_meeting_tags_user_task_type",
            "user_id",
            "task_id",
            "tag_type",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<MeetingTag(id={self.id}, task_id={self.task_id!r}, "
            f"type={self.tag_type!r}, value={self.tag_value!r})>"
        )
