"""add device_id to device_tokens

Revision ID: 003_add_device_id_to_device_tokens
Revises: 002_add_device_tokens
Create Date: 2026-06-15

SPEC-MOBILE-001/004: Persist client device_id so unregister can deactivate the
requested physical device instead of the first active FCM token.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_add_device_id_to_device_tokens"
down_revision: str | None = "002_add_device_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("device_tokens", sa.Column("device_id", sa.String(length=255), nullable=True))
    op.create_index(
        op.f("ix_device_tokens_device_id"),
        "device_tokens",
        ["device_id"],
        unique=False,
    )
    op.create_index(
        "ix_device_tokens_user_device_id",
        "device_tokens",
        ["user_id", "device_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_device_tokens_user_device_id", table_name="device_tokens")
    op.drop_index(op.f("ix_device_tokens_device_id"), table_name="device_tokens")
    op.drop_column("device_tokens", "device_id")
