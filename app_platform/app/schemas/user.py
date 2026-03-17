# 用户数据验证模型（Pydantic Schemas）
# 定义用户数据的请求和响应格式
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """
    用户基础模型
    包含用户的基本信息字段
    """
    # 用户名，3-50 个字符，必须唯一
    username: str = Field(..., min_length=3, max_length=50)
    
    # 个人简介，可选
    bio: Optional[str] = None
    
    # 头像 URL，可选，最多 500 个字符
    avatar_url: Optional[str] = Field(None, max_length=500)


class UserCreate(UserBase):
    """
    创建用户时的请求模型
    继承 UserBase，用于接收用户创建请求
    """
    pass


class UserUpdate(BaseModel):
    """
    更新用户时的请求模型
    所有字段都是可选的
    """
    # 个人简介，可选
    bio: Optional[str] = None
    
    # 头像 URL，可选，最多 500 个字符
    avatar_url: Optional[str] = Field(None, max_length=500)


class UserResponse(UserBase):
    """
    用户响应模型
    包含用户的完整信息，用于 API 响应
    """
    # 用户 ID（全局唯一）
    id: int
    
    # 创建时间
    created_at: datetime
    
    # 配置：允许从 ORM 模型读取数据
    class Config:
        from_attributes = True
