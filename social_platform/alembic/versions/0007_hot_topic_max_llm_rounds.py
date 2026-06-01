"""Add hot topic max LLM rounds.

Revision ID: 0007_hot_topic_max_llm_rounds
Revises: 0006_hot_topic_prompt_template
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_hot_topic_max_llm_rounds"
down_revision = "0006_hot_topic_prompt_template"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if "max_llm_rounds" not in _column_names("hot_topic_settings"):
        op.add_column(
            "hot_topic_settings",
            sa.Column("max_llm_rounds", sa.Integer(), server_default="6", nullable=False),
        )


def downgrade() -> None:
    pass
