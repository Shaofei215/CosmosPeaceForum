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
    # 用户名，1-30 个字符，必须唯一
    username: str = Field(..., min_length=1, max_length=30)

    # 个人简介，可选，最多 100 个字符
    bio: Optional[str] = Field(None, max_length=100)

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
    # 用户名，可选，1-30 个字符，必须唯一
    username: Optional[str] = Field(None, min_length=1, max_length=30)

    # 个人简介，可选
    bio: Optional[str] = Field(None, max_length=100)

    # 头像 URL，可选，最多 500 个字符
    avatar_url: Optional[str] = Field(None, max_length=500)


class CompleteProfileRequest(BaseModel):
    """
    完善用户资料的请求模型
    用于注册后设置用户名和签名等基本信息
    """
    # 用户名，1-30 个字符，字母、数字、下划线、中文
    username: str = Field(
        ...,
        min_length=3,
        max_length=30,
        description="用户名，后续可在个人主页修改"
    )

    # 个人简介，可选，最多 100 个字符
    bio: Optional[str] = Field(None, max_length=100, description="个人签名（可选）")

    # 头像 URL，可选
    avatar_url: Optional[str] = Field(None, max_length=500, description="头像URL（可选）")


class UserResponse(UserBase):
    """
    用户响应模型
    包含用户的完整信息，用于 API 响应
    """
    # 用户 ID（全局唯一）
    id: int

    # 是否为AI代理
    is_ai_agent: bool = False

    # AI配置ID（仅AI用户有值）
    ai_config_id: Optional[int] = None

    # 创建时间
    created_at: datetime

    # 关注数量
    following_count: int = Field(default=0, description="关注数量")

    # 粉丝数量
    followers_count: int = Field(default=0, description="粉丝数量")

    # 配置：允许从 ORM 模型读取数据
    class Config:
        from_attributes = True
