"""Add content archive state and report escalations.

Revision ID: 0013_content_archives
Revises: 0012_user_reports
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_content_archives"
down_revision = "0012_user_reports"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    """读取当前数据库表名，便于迁移在已补丁运行库上重复执行。"""

    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    """读取表列名，用于避免重复添加列。"""

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


def _add_archive_columns(table_name: str) -> None:
    """为内容表添加可恢复归档字段。"""

    columns = _column_names(table_name)
    with op.batch_alter_table(table_name) as batch_op:
        if "moderation_status" not in columns:
            batch_op.add_column(
                sa.Column(
                    "moderation_status",
                    sa.String(length=20),
                    server_default="active",
                    nullable=False,
                )
            )
        if "archived_at" not in columns:
            batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))
        if "archived_by_admin_id" not in columns:
            batch_op.add_column(sa.Column("archived_by_admin_id", sa.Integer(), nullable=True))
        if "archive_reason" not in columns:
            batch_op.add_column(sa.Column("archive_reason", sa.Text(), nullable=True))

    _create_index_once(
        f"idx_{table_name}_moderation_status",
        table_name,
        ["moderation_status", "created_at", "id"],
    )


def upgrade() -> None:
    """增加内容归档状态和用户级内容举报升级记录。"""

    _add_archive_columns("posts")
    _add_archive_columns("comments")

    if "content_report_escalations" not in _table_names():
        op.create_table(
            "content_report_escalations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("trigger_content_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_by_admin_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["reviewed_by_admin_id"], ["platform_admin_users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_once("ix_content_report_escalations_id", "content_report_escalations", ["id"])
    _create_index_once("ix_content_report_escalations_user_id", "content_report_escalations", ["user_id"])
    _create_index_once("ix_content_report_escalations_status", "content_report_escalations", ["status"])
    _create_index_once("ix_content_report_escalations_created_at", "content_report_escalations", ["created_at"])
    _create_index_once(
        "ix_content_report_escalations_reviewed_by_admin_id",
        "content_report_escalations",
        ["reviewed_by_admin_id"],
    )
    _create_index_once(
        "idx_content_report_escalations_user_status",
        "content_report_escalations",
        ["user_id", "status"],
    )

    if "escalation_id" not in _column_names("content_reports"):
        with op.batch_alter_table("content_reports") as batch_op:
            batch_op.add_column(sa.Column("escalation_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_content_reports_escalation_id_content_report_escalations",
                "content_report_escalations",
                ["escalation_id"],
                ["id"],
                ondelete="SET NULL",
            )
    _create_index_once("ix_content_reports_escalation_id", "content_reports", ["escalation_id"])


def downgrade() -> None:
    """本项目既有迁移不执行回滚破坏操作，保持空实现。"""

    pass
