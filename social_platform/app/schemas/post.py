from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from social_platform.app.schemas.user import UserResponse


class PostBase(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    type: str = Field("post", pattern="^(post|article)$")
    content: str = Field(..., min_length=1)


class PostCreate(PostBase):
    pass


class RepostCreate(BaseModel):
    content: Optional[str] = Field(None, max_length=5000)
    source_type: str = Field(..., pattern="^(post|comment)$")
    source_id: int


class RepostOriginPost(BaseModel):
    id: int
    author_id: int
    author: Optional[UserResponse] = None
    title: Optional[str] = None
    type: str = "post"
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class RepostChainAuthor(BaseModel):
    user_id: int
    username: str


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, min_length=1)


class PostResponse(PostBase):
    id: int
    author_id: int
    author: Optional[UserResponse] = None
    created_at: datetime
    like_count: int = 0
    comment_count: int = 0
    repost_count: int = 0
    repost_source_type: Optional[str] = None
    repost_source_id: Optional[int] = None
    repost_root_post_id: Optional[int] = None
    repost_chain: Optional[str] = None
    repost_chain_authors: List[RepostChainAuthor] = Field(default_factory=list)
    repost_origin: Optional[RepostOriginPost] = None
    repost_origin_missing: bool = False

    class Config:
        from_attributes = True


class PostResponseWithLikeStatus(PostResponse):
    is_liked_by_current_user: bool = False
