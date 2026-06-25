"""帖子话题领域数据库模型。

本模块定义话题事实表和帖子-话题关联表。话题只应用在帖子正文中，关联表由
帖子创建、更新、删除以及转发事件维护。
"""

from __future__ import annotations

from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from social_platform.app.db.session import Base


class Topic(Base):
    """话题模型。

    Args:
        name: 去掉两侧 ``#`` 后的规范话题名。
        post_count: 当前 active 帖子中使用该话题的帖子数量。
        heat_score: 话题热度分数，由帖子数量、帖子热度和新鲜度综合计算。
        last_used_at: 该话题最近一次被 active 帖子使用的时间。
        created_at: 话题首次创建时间。
        updated_at: 话题统计最近更新时间。
    """

    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(40), nullable=False, unique=True, index=True)
    post_count = Column(Integer, nullable=False, default=0, server_default="0")
    heat_score = Column(Float, nullable=False, default=0.0, server_default="0")
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=local_now)
    updated_at = Column(DateTime, nullable=False, default=local_now, onupdate=local_now)

    post_topics = relationship("PostTopic", back_populates="topic", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_topics_heat", "heat_score", "last_used_at", "id"),
    )


class PostTopic(Base):
    """帖子与话题的关联模型。

    Args:
        post_id: 使用话题的帖子 ID。
        topic_id: 被使用的话题 ID。
        created_at: 关联创建时间，通常等于帖子被解析时的时间。
    """

    __tablename__ = "post_topics"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=local_now)

    topic = relationship("Topic", back_populates="post_topics")

    __table_args__ = (
        UniqueConstraint("post_id", "topic_id", name="uq_post_topics_post_topic"),
        Index("idx_post_topics_topic_post", "topic_id", "post_id"),
    )

