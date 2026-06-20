"""Add post topic tables.

Revision ID: 0015_post_topics
Revises: 0014_post_polls
Create Date: 2026-06-21
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_post_topics"
down_revision = "0014_post_polls"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    """读取当前数据库表名，用于幂等创建话题表。"""

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
    """创建帖子话题表和帖子-话题关联表。"""

    tables = _table_names()
    if "topics" not in tables:
        op.create_table(
            "topics",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=40), nullable=False),
            sa.Column("post_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("heat_score", sa.Float(), server_default="0", nullable=False),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
    _create_index_once("ix_topics_id", "topics", ["id"])
    _create_index_once("ix_topics_name", "topics", ["name"])
    _create_index_once("idx_topics_heat", "topics", ["heat_score", "last_used_at", "id"])

    if "post_topics" not in tables:
        op.create_table(
            "post_topics",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=False),
            sa.Column("topic_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("post_id", "topic_id", name="uq_post_topics_post_topic"),
        )
    _create_index_once("ix_post_topics_id", "post_topics", ["id"])
    _create_index_once("ix_post_topics_post_id", "post_topics", ["post_id"])
    _create_index_once("ix_post_topics_topic_id", "post_topics", ["topic_id"])
    _create_index_once("idx_post_topics_topic_post", "post_topics", ["topic_id", "post_id"])


def downgrade() -> None:
    """删除帖子话题相关表。"""

    tables = _table_names()
    if "post_topics" in tables:
        op.drop_table("post_topics")
    if "topics" in tables:
        op.drop_table("topics")

