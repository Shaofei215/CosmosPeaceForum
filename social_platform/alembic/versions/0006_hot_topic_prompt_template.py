"""Add hot topic prompt template.

Revision ID: 0006_hot_topic_prompt_template
Revises: 0005_hot_topics
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_hot_topic_prompt_template"
down_revision = "0005_hot_topics"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if "prompt_template" not in _column_names("hot_topic_settings"):
        op.add_column("hot_topic_settings", sa.Column("prompt_template", sa.Text(), nullable=True))


def downgrade() -> None:
    pass
