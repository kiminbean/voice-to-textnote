"""
Root conftest for backend tests.

Injects missing modules BEFORE any test collection or app import happens.

The API at backend/app/api/v1/action_items.py imports:
  - backend.schemas.action_item (does not exist; real file is backend/app/schemas/action_item.py)
  - backend.db.models.ActionItem (does not exist in models.py)

This conftest must be at backend/tests/ level to run before any test files are collected.
"""

import sys

import uuid
from datetime import datetime

from sqlalchemy import Float, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column


# ---------------------------------------------------------------------------
# 1. Inject backend.schemas.action_item -> re-export from backend.app.schemas.action_item
# ---------------------------------------------------------------------------

import backend.app.schemas.action_item as _real_action_item_schema  # noqa: E402

sys.modules["backend.schemas.action_item"] = _real_action_item_schema

# ---------------------------------------------------------------------------
# 2. Inject ActionItem ORM model into backend.db.models
# ---------------------------------------------------------------------------

import backend.db.models as _models_mod  # noqa: E402
from backend.db.models import Base  # noqa: E402


class _FakeActionItemModel(Base):
    """ActionItem ORM model stub for testing.

    Inherits from real Base so SQLAlchemy select()/update()/delete() work.
    """

    __tablename__ = "action_items_test"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(nullable=True)
    meeting_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    estimated_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


_models_mod.ActionItem = _FakeActionItemModel  # type: ignore[attr-defined]
