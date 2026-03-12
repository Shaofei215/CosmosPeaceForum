"""
Pydantic模型定义
用于API请求和响应的数据校验
"""
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List


class UserCreate(BaseModel):
    """创建用户请求"""
    username: str
    bio: Optional[str] = None
    avatar: Optional[str] = None  # 头像图片路径


class UserResponse(BaseModel):
    """用户响应"""
    id: int
    username: str
    bio: Optional[str]
    avatar: Optional[str]  # 头像图片路径
    created_at: datetime

    @field_validator('avatar', mode='before')
    @classmethod
    def format_avatar_path(cls, v):
        """确保头像路径格式正确，添加/avatar前缀"""
        if v is None:
            return '/avatar/Avatar.png'
        if isinstance(v, str):
            # 如果已经是完整路径，直接返回
            if v.startswith('/avatar/'):
                return v
            # 如果包含路径分隔符，只取文件名
            if '/' in v:
                v = v.split('/')[-1]
            if '\\' in v:
                v = v.split('\\')[-1]
            return f'/avatar/{v}'
        return v

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
    hot_score: int = 0
    last_hot_update: Optional[datetime] = None
    author: Optional[UserResponse] = None
    likes_count: int = 0
    comments_count: int = 0
    reposts_count: int = 0
    views_count: int = 0
    likers: Optional[List[UserResponse]] = None
    
    # ========== 重构：转发相关字段 ==========
    post_type: str = "original"  # original=原创，quote=引用转发
    quote_from_id: Optional[int] = None  # 被直接转发的帖子 ID（用于计数）
    original_post_id: Optional[int] = None  # 原始帖子 ID（用于小卡片展示）
    repost_type: Optional[str] = None  # direct=直接转发，comment=评论转发，reply=回复转发
    comment_id: Optional[int] = None  # 关联的评论 ID
    reply_id: Optional[int] = None  # 关联的回复 ID
    quote_comment: Optional[str] = None  # 转发时的原始评论（仅用于内部存储）
    original_post: Optional["PostResponse"] = None  # 原始帖子（小卡片用）

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
    hot_score: int = 0
    last_hot_update: Optional[datetime] = None
    author: Optional[UserResponse] = None
    likes_count: int = 0
    replies_count: int = 0
    replies: Optional[List["ReplyResponse"]] = None

    class Config:
        from_attributes = True


class ReplyCreate(BaseModel):
    """创建回复请求"""
    content: str
    parent_reply_id: Optional[int] = None  # 如果是回复回复，则填写


class ReplyResponse(BaseModel):
    """回复响应"""
    id: int
    comment_id: int
    parent_reply_id: Optional[int] = None
    author_id: int
    content: str
    created_at: datetime
    hot_score: int = 0
    last_hot_update: Optional[datetime] = None
    author: Optional[UserResponse] = None
    likes_count: int = 0

    class Config:
        from_attributes = True


class LikeResponse(BaseModel):
    """点赞响应"""
    id: int
    user_id: int
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    reply_id: Optional[int] = None
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


# 重建模型以处理前向引用
CommentResponse.model_rebuild()
PostResponse.model_rebuild()  # 处理 quote_from 的自引用
