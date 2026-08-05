"""增加帖子点踩关系、计数与非负约束。

Revision ID: 0006_post_dislikes
Revises: 0005_coin_balance_limit
Create Date: 2026-08-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_post_dislikes"
down_revision: str | Sequence[str] | None = "0005_coin_balance_limit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建点踩表并给帖子增加冗余点踩计数。"""

    op.add_column(
        "posts",
        sa.Column("dislike_count", sa.Integer(), server_default="0", nullable=False),
    )
    with op.batch_alter_table("posts") as batch_op:
        batch_op.create_check_constraint(
            "ck_posts_dislike_count_nonnegative",
            "dislike_count >= 0",
        )
    op.create_table(
        "dislikes",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_agent", sa.Boolean(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "post_id", name="dislikes_pkey"),
    )
    op.create_index("idx_dislikes_post_id", "dislikes", ["post_id"], unique=False)
    op.create_index("idx_dislikes_user_id", "dislikes", ["user_id"], unique=False)


def downgrade() -> None:
    """移除帖子点踩关系与计数。"""

    op.drop_index("idx_dislikes_user_id", table_name="dislikes")
    op.drop_index("idx_dislikes_post_id", table_name="dislikes")
    op.drop_table("dislikes")
    with op.batch_alter_table("posts") as batch_op:
        batch_op.drop_constraint("ck_posts_dislike_count_nonnegative", type_="check")
        batch_op.drop_column("dislike_count")
