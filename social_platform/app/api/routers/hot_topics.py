from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from social_platform.app.api.deps import get_db
from social_platform.app.schemas.hot_topic import HotTopicResponse
from social_platform.app.services import hot_topic_service

router = APIRouter()


@router.get("", response_model=List[HotTopicResponse], summary="获取公开热榜")
def list_hot_topics(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return hot_topic_service.list_public_hot_topics(db, limit=limit)
