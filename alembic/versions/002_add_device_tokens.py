"""add device_tokens table

Revision ID: 002_add_device_tokens
Revises: 001
Create Date: 2026-06-06

TASK-002: DeviceToken 테이블 migration
- device_tokens 테이블 생성 (FCM 토큰 영속 저장)
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002_add_device_tokens'
down_revision: str | None = '001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ### DeviceToken 테이블 생성 ###
    op.create_table(
        'device_tokens',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('fcm_token', sa.String(length=512), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fcm_token'),
        sqlite_autoincrement=True,
    )
    # 인덱스 생성
    op.create_index(op.f('ix_device_tokens_user_id'), 'device_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_device_tokens_fcm_token'), 'device_tokens', ['fcm_token'], unique=True)
    # ### end DeviceToken ###


def downgrade() -> None:
    # ### DeviceToken 테이블 삭제 ###
    op.drop_index(op.f('ix_device_tokens_fcm_token'), table_name='device_tokens')
    op.drop_index(op.f('ix_device_tokens_user_id'), table_name='device_tokens')
    op.drop_table('device_tokens')
    # ### end DeviceToken ###
