"""add unique constraint on minutes_versions (task_id, version_number)

Revision ID: 004_unique_minutes_versions_task_version
Revises: 003_add_device_id_to_device_tokens
Create Date: 2026-06-15

SPEC-BUGFIX-002 REQ-BF2-005: Prevent duplicate version_number within the same
task_id. The ORM model declares UniqueConstraint("task_id", "version_number")
but existing databases do not have it applied. This migration backfills the
constraint. If duplicate rows exist (caused by the previous race condition),
they must be cleaned up before this migration can apply.
"""
from collections.abc import Sequence

from sqlalchemy import inspect as sa_inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_unique_minutes_versions_task_version"
down_revision: str | None = "003_add_device_id_to_device_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "minutes_versions" not in sa_inspect(bind).get_table_names():
        return
    with op.batch_alter_table("minutes_versions") as batch_op:
        batch_op.create_unique_constraint(
            "uq_minutes_versions_task_version",
            ["task_id", "version_number"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "minutes_versions" not in sa_inspect(bind).get_table_names():
        return
    with op.batch_alter_table("minutes_versions") as batch_op:
        batch_op.drop_constraint(
            "uq_minutes_versions_task_version",
            type_="unique",
        )
