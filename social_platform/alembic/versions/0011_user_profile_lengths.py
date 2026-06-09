"""Normalize user profile field lengths.

Revision ID: 0011_user_profile_lengths
Revises: 0010_user_sessions
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_user_profile_lengths"
down_revision = "0010_user_sessions"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    """返回当前数据库中的表名，用于兼容首次部署和已有库迁移。"""
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    """统一用户昵称和签名的数据库长度，与 API 和前端校验保持一致。"""
    if "users" not in _table_names():
        return

    op.execute(
        sa.text(
            "UPDATE users SET bio = substr(bio, 1, 100) "
            "WHERE bio IS NOT NULL AND length(bio) > 100"
        )
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "username",
            existing_type=sa.String(length=50),
            type_=sa.String(length=30),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "bio",
            existing_type=sa.Text(),
            type_=sa.String(length=100),
            existing_nullable=True,
        )


def downgrade() -> None:
    """回退用户资料字段长度到旧模型声明，保留已有数据。"""
    if "users" not in _table_names():
        return

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "username",
            existing_type=sa.String(length=30),
            type_=sa.String(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "bio",
            existing_type=sa.String(length=100),
            type_=sa.Text(),
            existing_nullable=True,
        )
