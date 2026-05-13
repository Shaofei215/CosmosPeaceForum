from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app_platform.app.schemas.post import RepostChainAuthor, RepostOriginPost


class PostFeedItem(BaseModel):
    id: int
    title: Optional[str] = None
    type: str = "post"
    content: str
    created_at: datetime
    author_id: int
    author_name: str
    author_avatar: Optional[str] = None
    author_bio: Optional[str] = None
    author_is_ai_agent: bool = False
    like_count: int = 0
    comment_count: int = 0
    repost_count: int = 0
    heat_score: float = 0
    is_liked: bool = False
    repost_source_type: Optional[str] = None
    repost_source_id: Optional[int] = None
    repost_root_post_id: Optional[int] = None
    repost_chain: Optional[str] = None
    repost_chain_authors: list[RepostChainAuthor] = Field(default_factory=list)
    repost_origin: Optional[RepostOriginPost] = None
    repost_origin_missing: bool = False

    class Config:
        from_attributes = True
