"""Add content moderation LLM settings.

Revision ID: 0009_content_moderation_llm_settings
Revises: 0008_content_reports
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_content_moderation_llm_settings"
down_revision = "0008_content_reports"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "content_moderation_llm_settings" not in _table_names():
        op.create_table(
            "content_moderation_llm_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("llm_base_url", sa.String(length=500), nullable=True),
            sa.Column("llm_model_name", sa.String(length=120), nullable=True),
            sa.Column("llm_api_key", sa.String(length=500), nullable=True),
            sa.Column("prompt_template", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    pass
