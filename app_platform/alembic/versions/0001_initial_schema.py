"""Create app_platform schema.

Revision ID: 0001_app_platform_initial
Revises:
Create Date: 2026-05-22
"""

from alembic import op

from app_platform.app.db.session import Base
from app_platform.app import models  # noqa: F401
from app_platform.app.admin import models as admin_models  # noqa: F401

revision = "0001_app_platform_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
