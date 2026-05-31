"""Add hot topics.

Revision ID: 0005_hot_topics
Revises: 0004_flat_comment_threads
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_hot_topics"
down_revision = "0004_flat_comment_threads"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


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
    tables = _table_names()

    if "hot_topic_generations" not in tables:
        op.create_table(
            "hot_topic_generations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
            sa.Column("publish_policy", sa.String(length=20), server_default="draft", nullable=False),
            sa.Column("input_snapshot", sa.Text(), nullable=True),
            sa.Column("output_json", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_hot_topic_generations_id"),
            "hot_topic_generations",
            ["id"],
            unique=False,
        )

    if "hot_topic_settings" not in tables:
        op.create_table(
            "hot_topic_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("agent_enabled", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("agent_interval_minutes", sa.Integer(), server_default="180", nullable=False),
            sa.Column("publish_policy", sa.String(length=20), server_default="draft", nullable=False),
            sa.Column("llm_base_url", sa.String(length=500), nullable=True),
            sa.Column("llm_model_name", sa.String(length=120), nullable=True),
            sa.Column("llm_api_key", sa.String(length=500), nullable=True),
            sa.Column("web_search_enabled", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("tavily_api_key", sa.String(length=500), nullable=True),
            sa.Column("history_limit", sa.Integer(), server_default="3", nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "hot_topics" not in tables:
        op.create_table(
            "hot_topics",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("search_query", sa.String(length=200), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=20), server_default="manual", nullable=False),
            sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
            sa.Column("rank", sa.Integer(), server_default="1", nullable=False),
            sa.Column("weight", sa.Float(), server_default="0", nullable=False),
            sa.Column("is_pinned", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("generation_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["generation_id"], ["hot_topic_generations.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_hot_topics_id"), "hot_topics", ["id"], unique=False)
        op.create_index(
            op.f("ix_hot_topics_generation_id"),
            "hot_topics",
            ["generation_id"],
            unique=False,
        )

    _create_index_if_missing(
        "idx_hot_topics_public_order",
        "hot_topics",
        ["status", "rank", "created_at"],
    )
    _create_index_if_missing(
        "idx_hot_topics_generation_status",
        "hot_topics",
        ["generation_id", "status"],
    )


def downgrade() -> None:
    pass
