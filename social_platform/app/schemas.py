"""
Pydantic模型定义
用于API请求和响应的数据校验
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class UserCreate(BaseModel):
    """创建用户请求"""
    username: str
    bio: Optional[str] = None


class UserResponse(BaseModel):
    """用户响应"""
    id: int
    username: str
    bio: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PostCreate(BaseModel):
    """创建帖子请求"""
    content: str


class PostResponse(BaseModel):
    """帖子响应"""
    id: int
    author_id: int
    content: str
    created_at: datetime
    author: Optional[UserResponse] = None

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    """创建评论请求"""
    content: str


class CommentResponse(BaseModel):
    """评论响应"""
    id: int
    post_id: int
    author_id: int
    content: str
    created_at: datetime
    author: Optional[UserResponse] = None

    class Config:
        from_attributes = True


class LikeResponse(BaseModel):
    """点赞响应"""
    id: int
    user_id: int
    post_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class FollowResponse(BaseModel):
    """关注响应"""
    id: int
    follower_id: int
    following_id: int
    created_at: datetime

    class Config:
        from_attributes = True
