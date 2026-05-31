from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from social_platform.app.db.session import Base


class HotTopicGeneration(Base):
    """一次热榜 Agent 生成记录。"""

    __tablename__ = "hot_topic_generations"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    publish_policy = Column(String(20), nullable=False, default="draft", server_default="draft")
    input_snapshot = Column(Text, nullable=True)
    output_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    topics = relationship("HotTopic", back_populates="generation")


class HotTopicSettings(Base):
    """热榜生成运行期配置。"""

    __tablename__ = "hot_topic_settings"

    id = Column(Integer, primary_key=True, default=1)
    agent_enabled = Column(Boolean, nullable=False, default=False, server_default="0")
    agent_interval_minutes = Column(Integer, nullable=False, default=180, server_default="180")
    publish_policy = Column(String(20), nullable=False, default="draft", server_default="draft")
    llm_base_url = Column(String(500), nullable=True)
    llm_model_name = Column(String(120), nullable=True)
    llm_api_key = Column(String(500), nullable=True)
    web_search_enabled = Column(Boolean, nullable=False, default=False, server_default="0")
    tavily_api_key = Column(String(500), nullable=True)
    history_limit = Column(Integer, nullable=False, default=3, server_default="3")
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class HotTopic(Base):
    """对外展示的一条热榜内容。"""

    __tablename__ = "hot_topics"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(120), nullable=False)
    search_query = Column(String(200), nullable=False)
    summary = Column(Text, nullable=True)
    source = Column(String(20), nullable=False, default="manual", server_default="manual")
    status = Column(String(20), nullable=False, default="active", server_default="active")
    rank = Column(Integer, nullable=False, default=1, server_default="1")
    weight = Column(Float, nullable=False, default=0.0, server_default="0")
    is_pinned = Column(Boolean, nullable=False, default=False, server_default="0")
    generation_id = Column(Integer, ForeignKey("hot_topic_generations.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    generation = relationship("HotTopicGeneration", back_populates="topics")

    __table_args__ = (
        Index("idx_hot_topics_public_order", "status", "rank", "created_at"),
        Index("idx_hot_topics_generation_status", "generation_id", "status"),
    )
