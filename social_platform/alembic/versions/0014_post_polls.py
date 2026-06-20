"""Add post poll tables.

Revision ID: 0014_post_polls
Revises: 0013_content_archives
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_post_polls"
down_revision = "0013_content_archives"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    """读取当前数据库表名，用于迁移幂等创建投票表。"""

    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    """读取指定表的索引名，用于避免重复创建索引。"""

    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_once(name: str, table_name: str, columns: list[str]) -> None:
    """在索引不存在时创建索引。

    Args:
        name: 索引名称。
        table_name: 目标表名。
        columns: 参与索引的列名列表。
    """

    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns)


def upgrade() -> None:
    """创建帖子投票选项表和用户投票记录表。"""

    tables = _table_names()
    if "poll_options" not in tables:
        op.create_table(
            "poll_options",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=False),
            sa.Column("text", sa.String(length=20), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("vote_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("post_id", "position", name="uq_poll_options_post_position"),
        )
    _create_index_once("ix_poll_options_id", "poll_options", ["id"])
    _create_index_once("ix_poll_options_post_id", "poll_options", ["post_id"])
    _create_index_once("idx_poll_options_post_position", "poll_options", ["post_id", "position"])

    if "poll_votes" not in tables:
        op.create_table(
            "poll_votes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=False),
            sa.Column("option_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["option_id"], ["poll_options.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("post_id", "user_id", name="uq_poll_votes_post_user"),
        )
    _create_index_once("ix_poll_votes_id", "poll_votes", ["id"])
    _create_index_once("ix_poll_votes_option_id", "poll_votes", ["option_id"])
    _create_index_once("ix_poll_votes_post_id", "poll_votes", ["post_id"])
    _create_index_once("ix_poll_votes_user_id", "poll_votes", ["user_id"])
    _create_index_once("idx_poll_votes_post_option", "poll_votes", ["post_id", "option_id"])


def downgrade() -> None:
    """删除帖子投票表。"""

    tables = _table_names()
    if "poll_votes" in tables:
        op.drop_table("poll_votes")
    if "poll_options" in tables:
        op.drop_table("poll_options")
