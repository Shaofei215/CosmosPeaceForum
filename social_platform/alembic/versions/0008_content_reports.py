"""Add content reports.

Revision ID: 0008_content_reports
Revises: 0007_hot_topic_max_llm_rounds
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_content_reports"
down_revision = "0007_hot_topic_max_llm_rounds"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_once(name: str, table_name: str, columns: list[str]) -> None:
    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns)


def upgrade() -> None:
    if "content_reports" not in _table_names():
        op.create_table(
            "content_reports",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("reporter_id", sa.Integer(), nullable=False),
            sa.Column("target_type", sa.String(length=20), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=True),
            sa.Column("comment_id", sa.Integer(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_by_admin_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["reviewed_by_admin_id"],
                ["platform_admin_users.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_once("ix_content_reports_id", "content_reports", ["id"])
    _create_index_once("ix_content_reports_reporter_id", "content_reports", ["reporter_id"])
    _create_index_once("ix_content_reports_target_type", "content_reports", ["target_type"])
    _create_index_once("ix_content_reports_post_id", "content_reports", ["post_id"])
    _create_index_once("ix_content_reports_comment_id", "content_reports", ["comment_id"])
    _create_index_once("ix_content_reports_status", "content_reports", ["status"])
    _create_index_once("ix_content_reports_created_at", "content_reports", ["created_at"])
    _create_index_once(
        "ix_content_reports_reviewed_by_admin_id",
        "content_reports",
        ["reviewed_by_admin_id"],
    )
    _create_index_once("idx_content_reports_post_status", "content_reports", ["post_id", "status"])
    _create_index_once(
        "idx_content_reports_comment_status",
        "content_reports",
        ["comment_id", "status"],
    )
    _create_index_once(
        "idx_content_reports_reporter_post_status",
        "content_reports",
        ["reporter_id", "post_id", "status"],
    )
    _create_index_once(
        "idx_content_reports_reporter_comment_status",
        "content_reports",
        ["reporter_id", "comment_id", "status"],
    )


def downgrade() -> None:
    pass
