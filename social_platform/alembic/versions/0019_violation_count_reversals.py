"""记录申诉通过或内容恢复产生的违规计数撤销。

Revision ID: 0019_violation_count_reversals
Revises: 0018_user_violation_events
Create Date: 2026-06-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_violation_count_reversals"
down_revision = "0018_user_violation_events"
branch_labels = None
depends_on = None


def _column_names() -> set[str]:
    """读取违规事件表字段，用于保证迁移可重复检查。

    Returns:
        set[str]: 当前违规事件表的字段名集合。
    """

    inspector = sa.inspect(op.get_bind())
    if "user_violation_events" not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns("user_violation_events")}


def upgrade() -> None:
    """增加违规计数撤销时间，不回写既有事件。

    Returns:
        None: Alembic 通过当前迁移上下文直接执行 DDL。
    """

    if "violation_count_reversed_at" not in _column_names():
        op.add_column(
            "user_violation_events",
            sa.Column("violation_count_reversed_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    """删除违规计数撤销时间字段。

    Returns:
        None: Alembic 通过当前迁移上下文直接执行 DDL。
    """

    if "violation_count_reversed_at" in _column_names():
        op.drop_column("user_violation_events", "violation_count_reversed_at")
