"""Add feed, search, and comment performance indexes.

Revision ID: 0003_performance_indexes
Revises: 0002_runtime_columns
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_performance_indexes"
down_revision = "0002_runtime_columns"
branch_labels = None
depends_on = None


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    _create_index_if_missing("idx_posts_latest", "posts", ["created_at", "id"])
    _create_index_if_missing(
        "idx_posts_heat_latest",
        "posts",
        ["heat_score", "created_at", "id"],
    )
    _create_index_if_missing(
        "idx_posts_author_latest",
        "posts",
        ["author_id", "created_at", "id"],
    )
    _create_index_if_missing(
        "idx_comments_post_parent_latest",
        "comments",
        ["post_id", "parent_id", "created_at", "id"],
    )
    _create_index_if_missing(
        "idx_comments_post_parent_heat",
        "comments",
        ["post_id", "parent_id", "heat_score", "created_at", "id"],
    )


def downgrade() -> None:
    pass
