"""增加每日登录硬币奖励与帖子投币系统。

Revision ID: 0003_coin_system
Revises: 0002_hot_topic_tavily
Create Date: 2026-08-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_coin_system"
down_revision: str | Sequence[str] | None = "0002_hot_topic_tavily"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加用户余额、登录奖励状态、帖子硬币计数和行为记录表。"""

    op.add_column(
        "users",
        sa.Column("coin_balance", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("login_streak", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("users", sa.Column("last_coin_reward_date", sa.Date(), nullable=True))
    op.add_column(
        "posts",
        sa.Column("coin_count", sa.Integer(), server_default="0", nullable=False),
    )

    op.create_table(
        "daily_coin_rewards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reward_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("streak", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "reward_date",
            name="uq_daily_coin_rewards_user_date",
        ),
    )
    op.create_index(
        "idx_daily_coin_rewards_date",
        "daily_coin_rewards",
        ["reward_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_coin_rewards_id"),
        "daily_coin_rewards",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_coin_rewards_user_id"),
        "daily_coin_rewards",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "post_coins",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_agent", sa.Boolean(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "post_id", name="post_coins_pkey"),
    )
    op.create_index("idx_post_coins_post_id", "post_coins", ["post_id"], unique=False)
    op.create_index("idx_post_coins_user_id", "post_coins", ["user_id"], unique=False)


def downgrade() -> None:
    """移除投币记录、登录奖励记录及对应冗余字段。"""

    op.drop_index("idx_post_coins_user_id", table_name="post_coins")
    op.drop_index("idx_post_coins_post_id", table_name="post_coins")
    op.drop_table("post_coins")

    op.drop_index(op.f("ix_daily_coin_rewards_user_id"), table_name="daily_coin_rewards")
    op.drop_index(op.f("ix_daily_coin_rewards_id"), table_name="daily_coin_rewards")
    op.drop_index("idx_daily_coin_rewards_date", table_name="daily_coin_rewards")
    op.drop_table("daily_coin_rewards")

    op.drop_column("posts", "coin_count")
    op.drop_column("users", "last_coin_reward_date")
    op.drop_column("users", "login_streak")
    op.drop_column("users", "coin_balance")
