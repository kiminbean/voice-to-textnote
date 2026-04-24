"""
SPEC-BOOKMARK-001: 회의록 북마크/하이라이트 ORM 모델

REQ-BOOKMARK-001: 사용자가 특정 회의록의 구간(timestamp)에 북마크/하이라이트를 저장한다.
REQ-BOOKMARK-002: (user_id, task_id) 조합으로 조회 가능해야 한다.
REQ-BOOKMARK-003: 회의록 삭제 시 연결된 북마크도 CASCADE로 함께 삭제된다.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class Bookmark(Base):
    """회의록 구간 북마크/하이라이트.

    - task_id는 task_results.task_id (String) 외래 키. 회의록 삭제 시 CASCADE.
    - user_id는 users.id (UUID) 외래 키. 사용자 삭제 시 CASCADE.
    - segment_start/end는 원본 오디오 기준 초 단위.
    """

    __tablename__ = "bookmarks"

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

    # 대상 회의록 task_id (task_results.task_id)
    task_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("task_results.task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 구간 시작/종료 (초)
    segment_start: Mapped[float] = mapped_column(Float, nullable=False)
    segment_end: Mapped[float] = mapped_column(Float, nullable=False)

    # 북마크 구간 본문 스냅샷 (회의록 내용 변경에도 원본 보존)
    text_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 사용자 메모
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 색상 (hex #RRGGBB 또는 이름). 선택.
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)

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

    # (user_id, task_id) 조회 최적화
    __table_args__ = (
        Index("ix_bookmarks_user_task", "user_id", "task_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Bookmark(id={self.id}, user_id={self.user_id}, "
            f"task_id={self.task_id!r}, start={self.segment_start})>"
        )
