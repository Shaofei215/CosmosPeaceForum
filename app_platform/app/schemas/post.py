# 帖子数据验证模型（Pydantic Schemas）
# 定义帖子数据的请求和响应格式
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


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
    """
    pass


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
    
    # 配置：允许从 ORM 模型读取数据
    class Config:
        from_attributes = True
