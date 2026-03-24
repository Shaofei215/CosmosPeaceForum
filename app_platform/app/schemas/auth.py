# 认证数据验证模型（Pydantic Schemas）
# 定义认证相关的请求和响应格式
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from typing import Optional


class UserRegister(BaseModel):
    """
    用户注册请求模型

    真人用户注册和 AI 用户注册共用此模型，通过 is_ai_agent 参数区分：
    - 真人注册：需要提供 email
    - AI 注册：不需要 email
    """
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    is_ai_agent: bool = Field(default=False)
    ai_config_id: Optional[int] = Field(default=None)
    email: Optional[EmailStr] = Field(default=None, description="真人用户必填")


class UserLogin(BaseModel):
    """
    用户登录请求模型
    """
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """
    Token 响应模型
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """
    用户响应模型（认证模块专用）
    """
    id: int
    username: str
    is_ai_agent: bool
    ai_config_id: Optional[int] = None
    email: Optional[str] = None
    email_verified: bool = False
    email_verified_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
