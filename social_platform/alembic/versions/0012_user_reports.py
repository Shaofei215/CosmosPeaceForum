"""Add user targets to content reports.

Revision ID: 0012_user_reports
Revises: 0011_user_profile_lengths
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_user_reports"
down_revision = "0011_user_profile_lengths"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    """读取表列名，用于让迁移可重复执行在已补丁过的运行库上。"""

    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    """读取表索引名，用于避免重复创建索引。"""

    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_once(name: str, table_name: str, columns: list[str]) -> None:
    """在索引不存在时创建索引。"""

    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns)


def upgrade() -> None:
    """为举报表增加被举报用户目标列和查询索引。"""

    if "user_id" not in _column_names("content_reports"):
        with op.batch_alter_table("content_reports") as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_content_reports_user_id_users",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

    _create_index_once("ix_content_reports_user_id", "content_reports", ["user_id"])
    _create_index_once("idx_content_reports_user_status", "content_reports", ["user_id", "status"])
    _create_index_once(
        "idx_content_reports_reporter_user_status",
        "content_reports",
        ["reporter_id", "user_id", "status"],
    )


def downgrade() -> None:
    """本项目既有迁移不执行回滚破坏操作，保持空实现。"""

    pass
