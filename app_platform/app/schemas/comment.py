# 评论数据验证模型（Pydantic Schemas）
# 定义评论数据的请求和响应格式，支持无限层级嵌套
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

from app.schemas.user import UserResponse


class CommentBase(BaseModel):
    """
    评论基础模型
    包含评论的基本信息字段
    """
    # 评论内容，必填，至少 1 个字符
    content: str = Field(..., min_length=1)


class CommentCreate(BaseModel):
    """
    创建评论时的请求模型
    用于接收评论创建请求
    """
    # 评论内容，必填，至少 1 个字符
    content: str = Field(..., min_length=1)
    
    # 父评论ID，可选
    # 为空表示一级评论，有值表示回复
    parent_id: Optional[int] = None


class CommentUpdate(BaseModel):
    """
    更新评论时的请求模型
    所有字段都是可选的
    """
    # 评论内容，可选，至少 1 个字符
    content: Optional[str] = Field(None, min_length=1)


class CommentResponse(CommentBase):
    """
    评论响应模型
    包含评论的完整信息，用于 API 响应
    """
    # 评论 ID（全局唯一）
    id: int
    
    # 关联帖子 ID
    post_id: int
    
    # 评论发布者 ID
    owner_id: int
    
    # 父评论 ID，为空表示一级评论
    parent_id: Optional[int] = None
    
    # 点赞计数
    like_count: int = 0
    
    # 回复计数（所有子孙后代总数）
    reply_count: int = 0
    
    # 创建时间
    created_at: datetime
    
    # 当前用户是否已点赞该评论
    is_liked: bool = False
    
    # 评论发布者信息
    owner: Optional[UserResponse] = None
    
    # 配置：允许从 ORM 模型读取数据
    class Config:
        from_attributes = True


class CommentTreeResponse(CommentResponse):
    """
    评论树响应模型
    支持无限层级嵌套回复结构
    用于获取帖子的完整评论树
    """
    # 子评论列表（回复）
    # 递归结构，支持无限层级
    children: List['CommentTreeResponse'] = []
    
    # 配置：允许从 ORM 模型读取数据
    class Config:
        from_attributes = True


# 解决前向引用问题（Pydantic V2 需要显式处理递归模型）
CommentTreeResponse.model_rebuild()


class CommentLikeToggleResponse(BaseModel):
    """
    评论点赞操作响应模型
    用于返回点赞/取消点赞操作的结果
    """
    # 操作后的点赞状态
    # True 表示已点赞，False 表示未点赞
    is_liked: bool
    
    # 当前点赞总数
    like_count: int
    
    # 配置：允许从 ORM 模型读取数据
    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    """
    评论列表响应模型
    用于返回评论列表的分页数据
    """
    # 评论列表
    items: List[CommentTreeResponse]
    
    # 总数
    total: int
    
    # 跳过数量
    skip: int
    
    # 限制数量
    limit: int
    
    # 配置：允许从 ORM 模型读取数据
    class Config:
        from_attributes = True
