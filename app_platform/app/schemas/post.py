# 帖子数据验证模型（Pydantic Schemas）
# 定义帖子数据的请求和响应格式
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

from app.schemas.user import UserResponse
from app.schemas.comment import CommentTreeResponse


class PostBase(BaseModel):
    """
    帖子基础模型
    包含帖子的基本信息字段
    """
    # 帖子标题，可选，最多 200 个字符
    title: Optional[str] = Field(None, max_length=200)
    
    # 帖子内容，必填，至少 1 个字符
    content: str = Field(..., min_length=1)


class PostCreate(PostBase):
    """
    创建帖子时的请求模型
    继承 PostBase，用于接收帖子创建请求
    注意：author_id 从 JWT Token 自动获取，不再从请求体传入
    """


class PostUpdate(BaseModel):
    """
    更新帖子时的请求模型
    所有字段都是可选的
    """
    # 帖子标题，可选，最多 200 个字符
    title: Optional[str] = Field(None, max_length=200)
    
    # 帖子内容，可选，至少 1 个字符
    content: Optional[str] = Field(None, min_length=1)


class PostResponse(PostBase):
    """
    帖子响应模型
    包含帖子的完整信息，用于 API 响应
    """
    # 帖子 ID（全局唯一）
    id: int
    
    # 作者 ID
    author_id: int
    
    # 创建时间
    created_at: datetime
    
    # 点赞计数
    like_count: int = 0
    
    # 配置：允许从 ORM 模型读取数据
    class Config:
        from_attributes = True


class PostResponseWithLikeStatus(PostResponse):
    """
    带点赞状态的帖子响应模型
    继承 PostResponse，增加当前用户点赞状态字段
    用于需要显示当前用户是否已点赞的场景
    """
    # 当前用户是否已点赞该帖子
    is_liked_by_current_user: bool = False
