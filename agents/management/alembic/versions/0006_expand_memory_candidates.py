"""
将记忆混合检索的旧默认候选数从 5 扩大到 20。

Revision ID: 0006_expand_memory_candidates
Revises: 0005_agent_model_assignments
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_expand_memory_candidates"
down_revision = "0005_agent_model_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    升级仍使用旧默认值的向量与 BM25 候选数。

    只更新值恰好为 5 的历史配置，其他自定义值保持不变。

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
            SET value = '20'
            WHERE key IN (
                'MEMORY_RECALL_VECTOR_RESULTS',
                'MEMORY_RECALL_BM25_RESULTS'
            )
            AND value = '5'
            """
        )
    )


def downgrade() -> None:
    """
    保留当前候选数，避免回滚时覆盖迁移后的管理员配置。

    Returns:
        None: 该数据迁移不执行逆向覆盖。
    """
    return None
