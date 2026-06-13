"""
SPEC-COLLAB-001: 실시간 공동 편집 세션 ORM 모델

회의록(task_id)별 실시간 편집 세션 메타데이터를 영속화한다.
실시간 상태는 Redis에 보관하고, 편집 세션 종료 시 최종 스냅샷을
이 테이블에 flush 한다 (debounced persistence).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class CollabSession(Base):
    """
    실시간 공동 편집 세션.

    회의록 하나(task_id)에 대해 활성 WebSocket Room이 존재한다.
    마지막 참여자 퇴장 시 최종 문서 스냅샷을 content에 저장한다.
    """

    __tablename__ = "collab_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # 대상 회의록 (task_results.task_id 참조, 삭제 시 연쇄 삭제)
    task_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("task_results.task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 최종 문서 스냅샷 (field-level JSON)
    content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # 마지막 편집자 (users.id 참조, 사용자 삭제 시 NULL)
    last_editor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 최대 동시 편집자 수 기록 (audit 용도)
    peak_participants: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # 비고 (선택)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<CollabSession(id={self.id}, task_id={self.task_id!r})>"
