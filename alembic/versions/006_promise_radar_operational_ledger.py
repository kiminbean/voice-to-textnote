"""promise radar operational ledger

Revision ID: 006_promise_radar_operational_ledger
Revises: 005_add_team_sharing_policy
Create Date: 2026-07-01

Adds the Promise Radar ledger/event schema used by the operational obligation
workflow. The migration is intentionally defensive because some deployed SQLite
databases may already have promise_ledger_entries from create_all().
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_promise_radar_operational_ledger"
down_revision: str | None = "005_add_team_sharing_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    tables = _table_names()
    if "promise_ledger_entries" not in tables:
        op.create_table(
            "promise_ledger_entries",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("owner_id", sa.Uuid(), nullable=True),
            sa.Column("guest_session_id", sa.String(length=64), nullable=True),
            sa.Column("team_id", sa.Uuid(), nullable=True),
            sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
            sa.Column("source_task_id", sa.String(length=255), nullable=False),
            sa.Column("last_source_task_id", sa.String(length=255), nullable=False),
            sa.Column("canonical_key", sa.String(length=512), nullable=False),
            sa.Column("canonical_text", sa.Text(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("semantic_summary", sa.Text(), nullable=True),
            sa.Column("owner_name", sa.String(length=200), nullable=True),
            sa.Column("speaker_label", sa.String(length=100), nullable=True),
            sa.Column("speaker_profile_id", sa.Uuid(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("priority", sa.String(length=32), nullable=False),
            sa.Column("risk_level", sa.String(length=32), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("due_date_text", sa.String(length=120), nullable=True),
            sa.Column("due_at", sa.DateTime(), nullable=True),
            sa.Column("reminder_at", sa.DateTime(), nullable=True),
            sa.Column("notification_sent_at", sa.DateTime(), nullable=True),
            sa.Column("calendar_event", sa.JSON(), nullable=True),
            sa.Column("action_item_id", sa.Uuid(), nullable=True),
            sa.Column("occurrences", sa.Integer(), nullable=False),
            sa.Column("first_seen_at", sa.DateTime(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=True),
            sa.Column("user_confirmed", sa.Boolean(), nullable=False),
            sa.Column("dismissed_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["source_task_id"], ["task_results.task_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        columns = _columns("promise_ledger_entries")
        with op.batch_alter_table("promise_ledger_entries") as batch_op:
            if "team_id" not in columns:
                batch_op.add_column(sa.Column("team_id", sa.Uuid(), nullable=True))
            if "assigned_user_id" not in columns:
                batch_op.add_column(sa.Column("assigned_user_id", sa.Uuid(), nullable=True))
            if "notification_sent_at" not in columns:
                batch_op.add_column(sa.Column("notification_sent_at", sa.DateTime(), nullable=True))

    op.create_index(
        "ix_promise_ledger_owner_status",
        "promise_ledger_entries",
        ["owner_id", "status"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_promise_ledger_guest_status",
        "promise_ledger_entries",
        ["guest_session_id", "status"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_promise_ledger_team_status",
        "promise_ledger_entries",
        ["team_id", "status"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_promise_ledger_source_key",
        "promise_ledger_entries",
        ["source_task_id", "canonical_key"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_promise_ledger_entries_assigned_user_id",
        "promise_ledger_entries",
        ["assigned_user_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_promise_ledger_entries_canonical_key",
        "promise_ledger_entries",
        ["canonical_key"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_promise_ledger_entries_owner_name",
        "promise_ledger_entries",
        ["owner_name"],
        unique=False,
        if_not_exists=True,
    )

    tables = _table_names()
    if "promise_ledger_events" not in tables:
        op.create_table(
            "promise_ledger_events",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("ledger_entry_id", sa.Uuid(), nullable=False),
            sa.Column("owner_id", sa.Uuid(), nullable=True),
            sa.Column("guest_session_id", sa.String(length=64), nullable=True),
            sa.Column("team_id", sa.Uuid(), nullable=True),
            sa.Column("actor_user_id", sa.Uuid(), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("old_value", sa.JSON(), nullable=True),
            sa.Column("new_value", sa.JSON(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["ledger_entry_id"],
                ["promise_ledger_entries.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    op.create_index(
        "ix_promise_ledger_events_ledger_entry_id",
        "promise_ledger_events",
        ["ledger_entry_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_promise_ledger_events_owner_id",
        "promise_ledger_events",
        ["owner_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_promise_ledger_events_guest_session_id",
        "promise_ledger_events",
        ["guest_session_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_promise_ledger_events_team_id",
        "promise_ledger_events",
        ["team_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_promise_ledger_events_event_type",
        "promise_ledger_events",
        ["event_type"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_promise_ledger_events_entry_created",
        "promise_ledger_events",
        ["ledger_entry_id", "created_at"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    tables = _table_names()
    if "promise_ledger_events" in tables:
        op.drop_index("ix_promise_ledger_events_entry_created", table_name="promise_ledger_events")
        op.drop_index("ix_promise_ledger_events_event_type", table_name="promise_ledger_events")
        op.drop_index("ix_promise_ledger_events_team_id", table_name="promise_ledger_events")
        op.drop_index("ix_promise_ledger_events_guest_session_id", table_name="promise_ledger_events")
        op.drop_index("ix_promise_ledger_events_owner_id", table_name="promise_ledger_events")
        op.drop_index("ix_promise_ledger_events_ledger_entry_id", table_name="promise_ledger_events")
        op.drop_table("promise_ledger_events")

    if "promise_ledger_entries" not in tables:
        return
    op.drop_index("ix_promise_ledger_entries_owner_name", table_name="promise_ledger_entries")
    op.drop_index("ix_promise_ledger_entries_canonical_key", table_name="promise_ledger_entries")
    op.drop_index(
        "ix_promise_ledger_entries_assigned_user_id",
        table_name="promise_ledger_entries",
    )
    op.drop_index("ix_promise_ledger_source_key", table_name="promise_ledger_entries")
    op.drop_index("ix_promise_ledger_team_status", table_name="promise_ledger_entries")
    op.drop_index("ix_promise_ledger_guest_status", table_name="promise_ledger_entries")
    op.drop_index("ix_promise_ledger_owner_status", table_name="promise_ledger_entries")
    with op.batch_alter_table("promise_ledger_entries") as batch_op:
        columns = _columns("promise_ledger_entries")
        if "notification_sent_at" in columns:
            batch_op.drop_column("notification_sent_at")
        if "assigned_user_id" in columns:
            batch_op.drop_column("assigned_user_id")
        if "team_id" in columns:
            batch_op.drop_column("team_id")
