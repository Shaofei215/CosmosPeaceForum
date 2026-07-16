"""增加 Scheduler 缩放时间持久化锚点。

Revision ID: 0002_scheduler_time_state
Revises: 0001_initial_schema
Create Date: 2026-07-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_scheduler_time_state"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建保存唯一缩放时间锚点的运行期状态表。"""
    op.create_table(
        "scheduler_time_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scaled_timestamp", sa.Float(), nullable=False),
        sa.Column("real_timestamp", sa.Float(), nullable=False),
        sa.Column("scale", sa.Float(), nullable=False),
        sa.Column("offset_seconds", sa.Integer(), nullable=False),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """删除 Scheduler 缩放时间锚点表。"""
    op.drop_table("scheduler_time_state")
