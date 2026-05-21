"""Move former management startup schema patches into versioned migrations.

Revision ID: 0002_management_runtime_columns
Revises: 0001_management_initial
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_management_runtime_columns"
down_revision = "0001_management_initial"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> bool:
    if table_name not in _table_names():
        return False
    if column.name in _column_names(table_name):
        return False
    op.add_column(table_name, column)
    return True


def upgrade() -> None:
    _add_column_if_missing("agent_configs", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    _add_column_if_missing(
        "agent_configs",
        sa.Column("last_login_timestamp", sa.Float(), nullable=True),
    )
    _add_column_if_missing(
        "agent_configs",
        sa.Column("total_login_count", sa.Integer(), nullable=False, server_default="0"),
    )

    _add_column_if_missing("admin_users", sa.Column("email", sa.String(255), nullable=True))
    _add_column_if_missing(
        "admin_users",
        sa.Column("permissions", sa.Text(), nullable=False, server_default="[]"),
    )
    _add_column_if_missing(
        "admin_users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    _add_column_if_missing(
        "admin_users",
        sa.Column("is_super_admin", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    _add_column_if_missing(
        "admin_users",
        sa.Column("must_change_credentials", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    added_updated_at = _add_column_if_missing(
        "admin_users",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    if added_updated_at:
        op.execute("UPDATE admin_users SET updated_at = created_at WHERE updated_at IS NULL")

    _add_column_if_missing(
        "operation_logs",
        sa.Column("operator_username", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    pass
