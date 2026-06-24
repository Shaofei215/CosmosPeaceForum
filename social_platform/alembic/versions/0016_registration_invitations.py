"""Add registration invitation table.

Revision ID: 0016_registration_invitations
Revises: 0015_post_topics
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_registration_invitations"
down_revision = "0015_post_topics"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    """读取当前数据库表名，用于幂等创建邀请码表。"""

    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    """读取指定表的索引名，用于避免重复创建索引。"""

    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_once(name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    """在索引不存在时创建索引。

    Args:
        name: 索引名称。
        table_name: 目标表名。
        columns: 参与索引的列名列表。
        unique: 是否创建唯一索引。
    """

    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    """创建注册邀请码表。"""

    if "registration_invitations" not in _table_names():
        op.create_table(
            "registration_invitations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("prefix", sa.String(length=16), nullable=False),
            sa.Column("code_suffix", sa.String(length=6), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
            sa.Column("used_by_user_id", sa.Integer(), nullable=True),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["created_by_admin_id"],
                ["platform_admin_users.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(["used_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email", name="uq_registration_invitations_email"),
            sa.UniqueConstraint("code", name="uq_registration_invitations_code"),
            sa.UniqueConstraint(
                "used_by_user_id",
                name="uq_registration_invitations_used_by_user_id",
            ),
        )
    _create_index_once("ix_registration_invitations_id", "registration_invitations", ["id"])
    _create_index_once("ix_registration_invitations_email", "registration_invitations", ["email"])
    _create_index_once("ix_registration_invitations_code", "registration_invitations", ["code"])
    _create_index_once(
        "ix_registration_invitations_created_by_admin_id",
        "registration_invitations",
        ["created_by_admin_id"],
    )
    _create_index_once(
        "ix_registration_invitations_used_by_user_id",
        "registration_invitations",
        ["used_by_user_id"],
        unique=True,
    )


def downgrade() -> None:
    """删除注册邀请码表。"""

    if "registration_invitations" in _table_names():
        op.drop_table("registration_invitations")

