"""Rename management social platform fields.

Revision ID: 0009_rename_social_platform_fields
Revises: 0008_reduce_memory_threshold
Create Date: 2026-06-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_rename_social_platform_fields"
down_revision = "0008_reduce_memory_threshold"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    """读取指定表的列名集合，用于让迁移可重复处理部分升级状态。"""

    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    """将 Agent 与公开平台账号绑定列改为 social_platform 命名。"""

    columns = _column_names("agent_configs")
    if "app_platform_user_id" in columns and "social_platform_user_id" not in columns:
        with op.batch_alter_table("agent_configs") as batch_op:
            batch_op.alter_column("app_platform_user_id", new_column_name="social_platform_user_id")


def downgrade() -> None:
    """回滚列名，供本地测试或迁移回退使用。"""

    columns = _column_names("agent_configs")
    if "social_platform_user_id" in columns and "app_platform_user_id" not in columns:
        with op.batch_alter_table("agent_configs") as batch_op:
            batch_op.alter_column("social_platform_user_id", new_column_name="app_platform_user_id")
