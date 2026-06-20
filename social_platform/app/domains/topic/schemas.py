"""帖子话题领域 API schema。

这些 DTO 用于公开热门话题接口、帖子响应中的话题标记，以及前端话题搜索跳转。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TopicMention(BaseModel):
    """帖子正文中一次可跳转话题对应的元数据。

    Args:
        id: 话题 ID。
        name: 去掉两侧 ``#`` 后的规范话题名。
    """

    id: int
    name: str


class TopicResponse(TopicMention):
    """公开热门话题响应模型。

    Args:
        post_count: 当前使用该话题的 active 帖子数量。
        heat_score: 话题热度分数。
        last_used_at: 最近一次使用时间。
        created_at: 话题创建时间。
        updated_at: 统计更新时间。
    """

    post_count: int = 0
    heat_score: float = 0
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        """启用 Pydantic ORM 属性读取。"""

        from_attributes = True


class TopicSearchMeta(BaseModel):
    """话题搜索响应的轻量元信息。"""

    topic: TopicMention | None = Field(default=None)

