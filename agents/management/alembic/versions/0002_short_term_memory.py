"""增加内部角色短期记忆当前快照表。

Revision ID: 0002_short_term_memory
Revises: 0001_initial_schema
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_short_term_memory"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建每个内部角色至多一条的短期记忆快照记录。"""

    op.create_table(
        "short_term_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
        sa.Column("updated_login_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["agent_configs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """移除短期记忆快照表。"""

    op.drop_table("short_term_memories")
