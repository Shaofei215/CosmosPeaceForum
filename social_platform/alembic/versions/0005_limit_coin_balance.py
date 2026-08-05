"""将用户硬币余额限制为 0 到 65535。

Revision ID: 0005_coin_balance_limit
Revises: 0004_unbounded_coins
Create Date: 2026-08-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_coin_balance_limit"
down_revision: str | Sequence[str] | None = "0004_unbounded_coins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """归一化已有余额并添加数据库范围约束。"""

    op.execute("UPDATE users SET coin_balance = 0 WHERE coin_balance < 0")
    op.execute("UPDATE users SET coin_balance = 65535 WHERE coin_balance > 65535")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "coin_balance",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
            existing_server_default="0",
        )
        batch_op.create_check_constraint(
            "ck_users_coin_balance_range",
            "coin_balance >= 0 AND coin_balance <= 65535",
        )


def downgrade() -> None:
    """移除余额范围约束并恢复大整数字段。"""

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_coin_balance_range", type_="check")
        batch_op.alter_column(
            "coin_balance",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
            existing_server_default="0",
        )
