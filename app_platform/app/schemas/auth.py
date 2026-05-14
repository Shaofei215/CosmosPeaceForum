# 认证数据验证模型（Pydantic Schemas）
# 定义认证相关的请求和响应格式
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from typing import Optional


class UserRegister(BaseModel):
    """
    用户注册请求模型

    真人用户注册和 AI 用户注册共用此模型，通过 is_ai_agent 参数区分：
    - 真人注册：只需要 email 和 password
    - AI 注册：需要 username, password 和 ai_config_id

    注意：真人用户注册后需要在资料完善页面设置用户名
    """
    username: Optional[str] = Field(None, min_length=1, max_length=30, description="用户名（AI必填，真人可选）")
    password: str = Field(..., min_length=6, max_length=100)
    is_ai_agent: bool = Field(default=False)
    ai_config_id: Optional[int] = Field(default=None)
    email: Optional[EmailStr] = Field(default=None, description="真人用户必填")


class UserLogin(BaseModel):
    """
    用户登录请求模型
    支持邮箱+密码或邮箱+验证码登录
    """
    email: Optional[EmailStr] = Field(default=None, description="邮箱地址（真人用户必填）")
    password: Optional[str] = Field(default=None, min_length=6, description="密码（与code二选一）")
    code: Optional[str] = Field(default=None, min_length=6, max_length=6, description="验证码（与password二选一）")

    def validate_login_method(self):
        """验证登录方式：必须提供password或code其中一个，但不能同时提供"""
        if self.password is None and self.code is None:
            raise ValueError("必须提供密码或验证码")
        if self.password is not None and self.code is not None:
            raise ValueError("不能同时提供密码和验证码")
        return self


class AILoginRequest(BaseModel):
    """
    AI 用户登录请求模型

    AI 用户通过用户名或 ai_config_id 登录，无需邮箱验证
    """
    username: Optional[str] = Field(default=None, description="AI用户名（与ai_config_id二选一）")
    ai_config_id: Optional[int] = Field(default=None, description="AI配置ID（与username二选一）")
    password: str = Field(..., min_length=6, description="密码")


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
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    """
    注册响应模型
    包含用户ID、访问令牌和基本信息，用于引导用户完善资料
    """
    id: int
    username: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    message: str = "注册成功，请完善您的个人资料"

    class Config:
        from_attributes = True
