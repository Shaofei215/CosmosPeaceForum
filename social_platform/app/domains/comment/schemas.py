from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from social_platform.app.core.content_limits import COMMENT_CONTENT_MAX_LENGTH
from social_platform.app.domains.post.schemas import MentionUser
from social_platform.app.domains.user.schemas import UserResponse


class CommentBase(BaseModel):
    """评论领域 API schema的基础字段，供 API adapter 做参数校验和响应序列化。"""
    content: str = Field(..., min_length=1, max_length=COMMENT_CONTENT_MAX_LENGTH)


class CommentCreate(BaseModel):
    """评论领域 API schema的创建请求，供 API adapter 做参数校验和响应序列化。"""
    content: str = Field(..., min_length=1, max_length=COMMENT_CONTENT_MAX_LENGTH)
    parent_id: Optional[int] = None
    repost: bool = False


class CommentUpdate(BaseModel):
    """评论领域 API schema的更新请求，供 API adapter 做参数校验和响应序列化。"""
    content: Optional[str] = Field(
        None,
        min_length=1,
        max_length=COMMENT_CONTENT_MAX_LENGTH,
    )


class CommentParentResponse(BaseModel):
    """评论领域 API schema的响应模型，供 API adapter 做参数校验和响应序列化。"""
    id: int
    owner_id: int
    owner: Optional[UserResponse] = None

    class Config:
        """评论领域 API schema的Pydantic ORM 映射配置，供 API adapter 做参数校验和响应序列化。"""
        from_attributes = True


class CommentResponse(CommentBase):
    """评论领域 API schema的响应模型，供 API adapter 做参数校验和响应序列化。"""
    id: int
    post_id: int
    owner_id: int
    parent_id: Optional[int] = None
    root_comment_id: Optional[int] = None
    like_count: int = 0
    reply_count: int = 0
    heat_score: float = 0
    created_at: datetime
    is_liked: bool = False
    owner: Optional[UserResponse] = None
    parent: Optional[CommentParentResponse] = None
    mention_users: List[MentionUser] = Field(default_factory=list)

    class Config:
        """评论领域 API schema的Pydantic ORM 映射配置，供 API adapter 做参数校验和响应序列化。"""
        from_attributes = True


class CommentTreeResponse(CommentResponse):
    """评论领域 API schema的响应模型，供 API adapter 做参数校验和响应序列化。"""
    children: List["CommentTreeResponse"] = []

    class Config:
        """评论领域 API schema的Pydantic ORM 映射配置，供 API adapter 做参数校验和响应序列化。"""
        from_attributes = True


CommentTreeResponse.model_rebuild()


class CommentLikeToggleResponse(BaseModel):
    """评论领域 API schema的响应模型，供 API adapter 做参数校验和响应序列化。"""
    is_liked: bool
    like_count: int

    class Config:
        """评论领域 API schema的Pydantic ORM 映射配置，供 API adapter 做参数校验和响应序列化。"""
        from_attributes = True


class CommentListResponse(BaseModel):
    """评论领域 API schema的响应模型，供 API adapter 做参数校验和响应序列化。"""
    items: List[CommentTreeResponse]
    total: int
    skip: int
    limit: int

    class Config:
        """评论领域 API schema的Pydantic ORM 映射配置，供 API adapter 做参数校验和响应序列化。"""
        from_attributes = True
