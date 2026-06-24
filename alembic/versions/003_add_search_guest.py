"""add search and guest task metadata

Revision ID: 003_add_search_guest
Revises: 003_add_device_id_to_device_tokens
Create Date: 2026-06-14

This revision was referenced by existing local databases but the migration file
was missing from the repo. Restoring it keeps Alembic's revision graph
resolvable and adds the guest-session task metadata required by the current ORM
when upgrading older databases.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_add_search_guest"
down_revision: str | None = "003_add_device_id_to_device_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("task_results")
    if not columns:
        return
    with op.batch_alter_table("task_results") as batch_op:
        if "is_guest" not in columns:
            batch_op.add_column(
                sa.Column("is_guest", sa.Boolean(), nullable=False, server_default="0")
            )
        if "guest_session_id" not in columns:
            batch_op.add_column(sa.Column("guest_session_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    columns = _columns("task_results")
    if not columns:
        return
    with op.batch_alter_table("task_results") as batch_op:
        if "guest_session_id" in columns:
            batch_op.drop_column("guest_session_id")
        if "is_guest" in columns:
            batch_op.drop_column("is_guest")
