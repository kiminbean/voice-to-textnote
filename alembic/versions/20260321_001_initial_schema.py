"""초기 스키마 - task_results, audit_logs 테이블 생성

Revision ID: 001
Revises:
Create Date: 2026-03-21

REQ-DB-007: Alembic 스키마 버전 관리
REQ-DB-008: alembic upgrade head로 모든 테이블 생성
"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """REQ-DB-008: 모든 테이블 생성"""

    # task_results 테이블 (REQ-DB-004)
    op.create_table(
        "task_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.String(length=255), nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_metadata", sa.JSON(), nullable=True),
        sa.Column("result_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index(
        op.f("ix_task_results_task_id"),
        "task_results",
        ["task_id"],
        unique=True,
    )

    # audit_logs 테이블 (REQ-DB-005)
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("client_ip", sa.String(length=45), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """모든 테이블 제거"""
    op.drop_index(op.f("ix_task_results_task_id"), table_name="task_results")
    op.drop_table("audit_logs")
    op.drop_table("task_results")
