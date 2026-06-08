"""add search service columns to task_results

Revision ID: 003_add_search_guest
Revises: 002_add_device_tokens
Create Date: 2026-06-08

TASK-003: task_results에 검색 서비스용 6컬럼 추가
- title, content, summary, speakers, tags, word_count (검색 서비스용)
모든 컬럼은 nullable하여 기존 행에 안전하게 추가됩니다.

게스트 컬럼(is_guest, guest_session_id)은 create_all()로 이미 존재하므로
이 마이그레이션에서는 검색 6개만 다룹니다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003_add_search_guest"
down_revision: str | None = "002_add_device_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("task_results", sa.Column("title", sa.String(length=500), nullable=True))
    op.add_column("task_results", sa.Column("content", sa.Text(), nullable=True))
    op.add_column("task_results", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("task_results", sa.Column("speakers", sa.JSON(), nullable=True))
    op.add_column("task_results", sa.Column("tags", sa.JSON(), nullable=True))
    op.add_column("task_results", sa.Column("word_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("task_results", "word_count")
    op.drop_column("task_results", "tags")
    op.drop_column("task_results", "speakers")
    op.drop_column("task_results", "summary")
    op.drop_column("task_results", "content")
    op.drop_column("task_results", "title")
