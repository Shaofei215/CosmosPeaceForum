from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from social_platform.app.db.session import Base


class HotTopicGeneration(Base):
    """一次热榜 Agent 生成记录。"""

    __tablename__ = "hot_topic_generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    publish_policy: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    input_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    topics = relationship("HotTopic", back_populates="generation")


class HotTopicSettings(Base):
    """热榜生成运行期配置。"""

    __tablename__ = "hot_topic_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    agent_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    agent_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=180, server_default="180")
    publish_policy: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    llm_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    llm_model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    llm_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    web_search_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    tavily_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tavily_topic: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tavily_max_results: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tavily_search_depth: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tavily_include_domains: Mapped[str | None] = mapped_column(Text, nullable=True)
    tavily_exclude_domains: Mapped[str | None] = mapped_column(Text, nullable=True)
    history_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    max_llm_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=6, server_default="6")
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)


class HotTopic(Base):
    """对外展示的一条热榜内容。"""

    __tablename__ = "hot_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    search_query: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual", server_default="manual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    generation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("hot_topic_generations.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)

    generation = relationship("HotTopicGeneration", back_populates="topics")

    __table_args__ = (
        Index("idx_hot_topics_public_order", "status", "rank", "created_at"),
        Index("idx_hot_topics_generation_status", "generation_id", "status"),
    )
