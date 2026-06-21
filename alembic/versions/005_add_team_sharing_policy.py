"""add team sharing policy

Revision ID: 005_add_team_sharing_policy
Revises: 004_unique_minutes_versions_task_version
Create Date: 2026-06-21

Persist team-level default sharing policy so private-by-default ownership can
be configured explicitly per team without changing existing meeting shares.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_add_team_sharing_policy"
down_revision: str | None = "004_unique_minutes_versions_task_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "teams" not in inspector.get_table_names():
        return
    op.add_column("teams", sa.Column("sharing_policy", sa.JSON(), nullable=True))


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "teams" not in inspector.get_table_names():
        return
    op.drop_column("teams", "sharing_policy")
