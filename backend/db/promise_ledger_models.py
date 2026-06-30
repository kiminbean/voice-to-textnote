"""
Promise Radar persistent ledger models.

The ledger turns one-off meeting action items into a durable obligation history.
It deliberately stores source evidence alongside editable user state so the app
can explain why a promise was detected while still letting the user correct it.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class PromiseLedgerEntry(Base):
    """Persistent cross-meeting promise ledger entry."""

    __tablename__ = "promise_ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    owner_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    guest_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    source_task_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("task_results.task_id", ondelete="CASCADE"),
        nullable=False,
    )
    last_source_task_id: Mapped[str] = mapped_column(String(255), nullable=False)

    canonical_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    canonical_text: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner_name: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    speaker_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    speaker_profile_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)

    due_date_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    calendar_event: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    action_item_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    evidence: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dismissed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_promise_ledger_owner_status", "owner_id", "status"),
        Index("ix_promise_ledger_guest_status", "guest_session_id", "status"),
        Index("ix_promise_ledger_source_key", "source_task_id", "canonical_key"),
    )

    def __repr__(self) -> str:
        return (
            f"<PromiseLedgerEntry(id={self.id}, status={self.status!r}, "
            f"canonical_key={self.canonical_key!r})>"
        )
