from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from social_platform.app.domains.user.schemas import UserResponse


class PostBase(BaseModel):
    """帖子领域 API schema的基础字段，供 API adapter 做参数校验和响应序列化。"""
    title: Optional[str] = Field(None, max_length=200)
    type: str = Field("post", pattern="^(post|article)$")
    content: str = Field(..., min_length=1)


class PostCreate(PostBase):
    """帖子领域 API schema的创建请求，供 API adapter 做参数校验和响应序列化。"""
    pass


class RepostCreate(BaseModel):
    """帖子领域 API schema的创建请求，供 API adapter 做参数校验和响应序列化。"""
    content: Optional[str] = Field(None, max_length=5000)
    source_type: str = Field(..., pattern="^(post|comment)$")
    source_id: int


class RepostOriginPost(BaseModel):
    """帖子领域 API schema中的领域类型，封装该上下文内的结构化数据。"""
    id: int
    author_id: int
    author: Optional[UserResponse] = None
    title: Optional[str] = None
    type: str = "post"
    content: str
    created_at: datetime

    class Config:
        """帖子领域 API schema的Pydantic ORM 映射配置，供 API adapter 做参数校验和响应序列化。"""
        from_attributes = True


class MentionUser(BaseModel):
    """帖子领域 API schema中的领域类型，封装该上下文内的结构化数据。"""
    user_id: int
    username: str


class RepostChainAuthor(MentionUser):
    """帖子领域 API schema中的领域类型，封装该上下文内的结构化数据。"""
    pass


class PostUpdate(BaseModel):
    """帖子领域 API schema的更新请求，供 API adapter 做参数校验和响应序列化。"""
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, min_length=1)


class PostResponse(PostBase):
    """帖子领域 API schema的响应模型，供 API adapter 做参数校验和响应序列化。"""
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
    mention_users: List[MentionUser] = Field(default_factory=list)
    repost_origin: Optional[RepostOriginPost] = None
    repost_origin_missing: bool = False

    class Config:
        """帖子领域 API schema的Pydantic ORM 映射配置，供 API adapter 做参数校验和响应序列化。"""
        from_attributes = True


class PostResponseWithLikeStatus(PostResponse):
    """帖子领域 API schema的响应模型，供 API adapter 做参数校验和响应序列化。"""
    is_liked_by_current_user: bool = False
