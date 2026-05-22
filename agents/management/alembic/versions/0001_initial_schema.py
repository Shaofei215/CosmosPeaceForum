"""Create management schema.

Revision ID: 0001_management_initial
Revises:
Create Date: 2026-05-22
"""

from alembic import op
from sqlmodel import SQLModel

from agents.management.backend import models  # noqa: F401
from agents.management.backend.models import chunk_model_config, embedding_config  # noqa: F401

revision = "0001_management_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind=bind)
