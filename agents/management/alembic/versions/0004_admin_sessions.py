"""Add management admin sessions.

Revision ID: 0004_admin_sessions
Revises: 0003_prompt_configs
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_admin_sessions"
down_revision = "0003_prompt_configs"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "admin_sessions" in _table_names():
        return

    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=True),
        sa.Column("client_type", sa.String(length=32), nullable=True),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("remember_me", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_sessions_session_id", "admin_sessions", ["session_id"], unique=True)
    op.create_index("ix_admin_sessions_admin_id", "admin_sessions", ["admin_id"])
    op.create_index("ix_admin_sessions_scope", "admin_sessions", ["scope"])
    op.create_index("ix_admin_sessions_client_type", "admin_sessions", ["client_type"])
    op.create_index("ix_admin_sessions_refresh_token_hash", "admin_sessions", ["refresh_token_hash"], unique=True)
    op.create_index("ix_admin_sessions_revoked_at", "admin_sessions", ["revoked_at"])
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])


def downgrade() -> None:
    pass
