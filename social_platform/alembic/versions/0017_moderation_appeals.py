"""Add moderation appeals table.

Revision ID: 0017_moderation_appeals
Revises: 0016_registration_invitations
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_moderation_appeals"
down_revision = "0016_registration_invitations"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    """读取当前数据库表名，用于幂等创建申诉表。"""

    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    """读取指定表索引名，用于避免重复创建索引。"""

    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_once(name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    """在索引不存在时创建索引。"""

    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    """创建站内管理申诉表。"""

    if "moderation_appeals" not in _table_names():
        op.create_table(
            "moderation_appeals",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("notification_id", sa.Integer(), nullable=False),
            sa.Column("appellant_id", sa.Integer(), nullable=False),
            sa.Column("target_type", sa.String(length=20), nullable=False),
            sa.Column("target_id", sa.Integer(), nullable=False),
            sa.Column("action_label", sa.String(length=100), nullable=False),
            sa.Column("moderation_reason", sa.Text(), nullable=True),
            sa.Column("appeal_reason", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
            sa.Column("reject_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_by_admin_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["appellant_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["resolved_by_admin_id"],
                ["platform_admin_users.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("notification_id", name="uq_moderation_appeals_notification_id"),
        )
    _create_index_once("ix_moderation_appeals_id", "moderation_appeals", ["id"])
    _create_index_once(
        "ix_moderation_appeals_notification_id",
        "moderation_appeals",
        ["notification_id"],
        unique=True,
    )
    _create_index_once("ix_moderation_appeals_appellant_id", "moderation_appeals", ["appellant_id"])
    _create_index_once("ix_moderation_appeals_target_type", "moderation_appeals", ["target_type"])
    _create_index_once("ix_moderation_appeals_target_id", "moderation_appeals", ["target_id"])
    _create_index_once("ix_moderation_appeals_status", "moderation_appeals", ["status"])
    _create_index_once("ix_moderation_appeals_created_at", "moderation_appeals", ["created_at"])
    _create_index_once(
        "ix_moderation_appeals_resolved_by_admin_id",
        "moderation_appeals",
        ["resolved_by_admin_id"],
    )
    _create_index_once(
        "idx_moderation_appeals_target_status",
        "moderation_appeals",
        ["target_type", "target_id", "status"],
    )
    _create_index_once(
        "idx_moderation_appeals_appellant_status",
        "moderation_appeals",
        ["appellant_id", "status"],
    )


def downgrade() -> None:
    """删除站内管理申诉表。"""

    if "moderation_appeals" in _table_names():
        op.drop_table("moderation_appeals")
