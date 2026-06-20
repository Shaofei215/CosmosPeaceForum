"""公开话题 API 路由。

该路由只暴露帖子话题的公开读接口，写入由帖子正文中的 ``#话题#`` 自动驱动。
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from social_platform.app.api.deps import get_db
from social_platform.app.domains.topic import application as topic_service
from social_platform.app.domains.topic.schemas import TopicResponse


router = APIRouter()


@router.get("/trending", response_model=List[TopicResponse], summary="获取热门话题")
def list_trending_topics(
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """获取热门话题候选。

    Args:
        limit: 最大返回数量。
        db: 当前数据库会话。

    Returns:
        list[TopicResponse]: 热门话题候选列表。
    """

    return topic_service.list_trending_topics(db, limit=limit)

