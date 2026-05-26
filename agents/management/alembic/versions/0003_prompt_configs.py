"""Add editable prompt configs.

Revision ID: 0003_prompt_configs
Revises: 0002_management_runtime_columns
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_prompt_configs"
down_revision = "0002_management_runtime_columns"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "prompt_configs" in _table_names():
        return

    op.create_table(
        "prompt_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompt_configs_key", "prompt_configs", ["key"], unique=True)


def downgrade() -> None:
    pass
