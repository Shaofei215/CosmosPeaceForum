"""为热榜生成增加可选的 Tavily 管理员覆盖配置。

Revision ID: 0002_hot_topic_tavily
Revises: 0001_initial_schema
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_hot_topic_tavily"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加 Tavily 搜索参数的管理员覆盖列。"""

    op.add_column("hot_topic_settings", sa.Column("tavily_topic", sa.String(length=20), nullable=True))
    op.add_column("hot_topic_settings", sa.Column("tavily_max_results", sa.Integer(), nullable=True))
    op.add_column(
        "hot_topic_settings",
        sa.Column("tavily_search_depth", sa.String(length=20), nullable=True),
    )
    op.add_column("hot_topic_settings", sa.Column("tavily_include_domains", sa.Text(), nullable=True))
    op.add_column("hot_topic_settings", sa.Column("tavily_exclude_domains", sa.Text(), nullable=True))


def downgrade() -> None:
    """移除 Tavily 搜索参数的管理员覆盖列。"""

    op.drop_column("hot_topic_settings", "tavily_exclude_domains")
    op.drop_column("hot_topic_settings", "tavily_include_domains")
    op.drop_column("hot_topic_settings", "tavily_search_depth")
    op.drop_column("hot_topic_settings", "tavily_max_results")
    op.drop_column("hot_topic_settings", "tavily_topic")
