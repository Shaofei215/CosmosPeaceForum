"""
将记忆系数最低阈值的旧默认值从 0.3 降低到 0.1。

Revision ID: 0008_reduce_memory_threshold
Revises: 0007_reduce_memory_boost
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_reduce_memory_threshold"
down_revision = "0007_reduce_memory_boost"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    将仍使用旧默认值 0.3 的记忆阈值更新为 0.1。

    其他管理员自定义值保持不变。

    Returns:
        None: 数据迁移执行完成后直接返回。
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "system_configs" not in inspector.get_table_names():
        return

    bind.execute(
        sa.text(
            """
            UPDATE system_configs
            SET value = '0.1'
            WHERE key = 'MEMORY_THRESHOLD'
            AND value = '0.3'
            """
        )
    )


def downgrade() -> None:
    """
    保留当前记忆阈值，避免回滚时覆盖后续管理员配置。

    Returns:
        None: 该数据迁移不执行逆向覆盖。
    """
    return None
