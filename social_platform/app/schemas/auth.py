"""公开平台认证请求/响应模型。

这里的 token 响应已经从单一长寿命 JWT 升级为 access + refresh + session_id。
前端和 Agent 调度器都依赖这些字段完成 refresh token 轮换和服务端 session 撤销。
"""
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from typing import Literal, Optional


class UserRegister(BaseModel):
    """邮箱注册和管理员创建用户名密码账号共享的请求模型。"""

    username: Optional[str] = Field(None, min_length=1, max_length=30, description="用户名")
    password: str = Field(..., min_length=8, max_length=32)
    email: Optional[EmailStr] = Field(default=None, description="邮箱注册用户必填")
    invitation_code: Optional[str] = Field(default=None, max_length=64, description="邀请码")
    remember_me: bool = Field(default=False, description="是否记住登录状态")
    client_type: Optional[Literal["desktop", "mobile", "agent"]] = Field(
        default=None,
        description="客户端类型；未提供时根据 User-Agent 自动识别",
    )


class UserLogin(BaseModel):
    """
    用户登录请求模型
    支持邮箱+密码或邮箱+验证码登录
    """
    email: Optional[EmailStr] = Field(default=None, description="邮箱地址（真人用户必填）")
    password: Optional[str] = Field(default=None, min_length=6, description="密码（与code二选一）")
    code: Optional[str] = Field(default=None, min_length=6, max_length=6, description="验证码（与password二选一）")
    remember_me: bool = Field(default=False, description="是否记住登录状态")
    client_type: Optional[Literal["desktop", "mobile", "agent"]] = Field(
        default=None,
        description="客户端类型；agent 只用于 Session 分组和生命周期，不增加权限",
    )

    def validate_login_method(self):
        """验证登录方式：必须提供password或code其中一个，但不能同时提供"""
        if self.password is None and self.code is None:
            raise ValueError("必须提供密码或验证码")
        if self.password is not None and self.code is not None:
            raise ValueError("不能同时提供密码和验证码")
        return self


class InternalAgentLoginRequest(BaseModel):
    """内建 Agent 使用用户名和密码登录无邮箱账号。"""

    username: str = Field(..., min_length=1, max_length=30, description="用户名")
    password: str = Field(..., min_length=6, description="密码")


class AgentLoginContext(BaseModel):
    """外部 Agent 登录后立即可见的平台账号上下文。

    该结构只包含公开社交平台能够直接提供的当前状态。登录次数和上次登录
    暂不纳入外部 Agent 契约，避免把浏览器 Session 与 Agent 会话混合统计。
    """

    platform_user_id: int
    following_count: int = 0
    followers_count: int = 0
    unread_count: Optional[int] = Field(default=None, gt=0)
    hot_topic_titles: list[str] = Field(default_factory=list)
    topic_titles: list[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    """登录、AI 登录和 refresh 共享的 token 响应。

    access_token 是短期 JWT；refresh_token 是 opaque 明文，只返回客户端；
    session_id 对应服务端 user_sessions.session_id。
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    session_id: str
    agent_context: Optional[AgentLoginContext] = None


class RefreshTokenRequest(BaseModel):
    """refresh 接口请求体，携带客户端保存的 opaque refresh token。"""

    refresh_token: str = Field(..., min_length=32)


class SessionResponse(BaseModel):
    """当前账号可管理的 active session 列表项。"""

    session_id: str
    scope: str
    client_type: str
    remember_me: bool
    expires_at: datetime
    last_seen_at: datetime
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    is_current: bool = False


class UserResponse(BaseModel):
    """
    用户响应模型（认证模块专用）
    """
    id: int
    username: str
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
    注册响应模型。

    真人邮箱注册成功后会自动登录，因此响应包含 access/refresh token 与 session_id，
    用于引导用户继续完善资料并支持后续 refresh。
    """
    id: int
    username: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    session_id: str
    message: str = "注册成功，请完善您的个人资料"

    class Config:
        from_attributes = True
