"""将硬币余额和帖子投币数升级为大整数字段。

Revision ID: 0004_unbounded_coins
Revises: 0003_coin_system
Create Date: 2026-08-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_unbounded_coins"
down_revision: str | Sequence[str] | None = "0003_coin_system"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """扩大硬币余额和帖子投币数的数据库存储范围。"""

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "coin_balance",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
            existing_server_default="0",
        )
    with op.batch_alter_table("posts") as batch_op:
        batch_op.alter_column(
            "coin_count",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
            existing_server_default="0",
        )


def downgrade() -> None:
    """把硬币字段恢复为普通整数字段。"""

    with op.batch_alter_table("posts") as batch_op:
        batch_op.alter_column(
            "coin_count",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
            existing_server_default="0",
        )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "coin_balance",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
            existing_server_default="0",
        )
