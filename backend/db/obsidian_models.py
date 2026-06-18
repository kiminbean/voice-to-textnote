"""
SPEC-OBSIDIAN-001: Obsidian vault 연계 설정 DB 모델
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class ObsidianConfig(Base):
    """Obsidian vault 설정 (팀/사용자 단위)."""

    __tablename__ = "obsidian_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    team_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    vault_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    vault_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    folder_pattern: Mapped[str] = mapped_column(
        String(512), nullable=False, default="Voice-to-TextNote/{{date}}"
    )
    filename_pattern: Mapped[str] = mapped_column(
        String(255), nullable=False, default="{{date}}_{{title}}"
    )

    auto_export: Mapped[bool] = mapped_column(
        default=False, server_default="0"
    )
    conflict_policy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="overwrite"
    )

    frontmatter_custom: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<ObsidianConfig(id={self.id}, vault={self.vault_name!r})>"
