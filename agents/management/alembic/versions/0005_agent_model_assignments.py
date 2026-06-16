"""Add model colors and Agent model assignments.

Revision ID: 0005_agent_model_assignments
Revises: 0004_admin_sessions
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_agent_model_assignments"
down_revision = "0004_admin_sessions"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    """返回当前数据库中的表名集合。"""
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    """返回指定表的列名集合。"""
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> bool:
    """在表存在且列缺失时添加列，兼容已被运行期补丁更新过的数据库。"""
    if table_name not in _table_names():
        return False
    if column.name in _column_names(table_name):
        return False
    op.add_column(table_name, column)
    return True


def upgrade() -> None:
    _add_column_if_missing(
        "model_configs",
        sa.Column("color", sa.String(length=20), nullable=False, server_default="#10A37F"),
    )
    _add_column_if_missing(
        "agent_configs",
        sa.Column("model_config_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    pass
