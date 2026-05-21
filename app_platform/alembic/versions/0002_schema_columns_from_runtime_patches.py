"""Move former startup schema patches into versioned migrations.

Revision ID: 0002_app_platform_runtime_columns
Revises: 0001_app_platform_initial
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_app_platform_runtime_columns"
down_revision = "0001_app_platform_initial"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if table_name not in _table_names():
        return
    if column.name in _column_names(table_name):
        return
    op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing(
        "posts",
        sa.Column("repost_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing("posts", sa.Column("repost_source_type", sa.String(20), nullable=True))
    _add_column_if_missing("posts", sa.Column("repost_source_id", sa.Integer(), nullable=True))
    _add_column_if_missing("posts", sa.Column("repost_root_post_id", sa.Integer(), nullable=True))
    _add_column_if_missing("posts", sa.Column("repost_chain", sa.Text(), nullable=True))
    _add_column_if_missing(
        "posts",
        sa.Column("type", sa.String(20), nullable=False, server_default="post"),
    )
    _add_column_if_missing(
        "posts",
        sa.Column("heat_score", sa.Float(), nullable=False, server_default="0"),
    )
    _add_column_if_missing("posts", sa.Column("heat_score_updated_at", sa.DateTime(), nullable=True))

    _add_column_if_missing(
        "comments",
        sa.Column("heat_score", sa.Float(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "comments",
        sa.Column("heat_score_updated_at", sa.DateTime(), nullable=True),
    )

    _add_column_if_missing(
        "platform_admin_users",
        sa.Column("email", sa.String(255), nullable=True),
    )

    _add_column_if_missing(
        "platform_theme_settings",
        sa.Column("topbar_action_active_color", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "platform_theme_settings",
        sa.Column("topbar_action_active_foreground_color", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "platform_theme_settings",
        sa.Column("topbar_action_inactive_color", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "platform_theme_settings",
        sa.Column("topbar_action_inactive_foreground_color", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "platform_theme_settings",
        sa.Column("topbar_background_image", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    pass
