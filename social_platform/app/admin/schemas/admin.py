"""平台内管理员 API 请求/响应模型。

管理员登录响应包含短期 access token、opaque refresh token 和 session_id，
用于支持 refresh token 轮换与服务端会话撤销。
"""

from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int
    limit: int


class AdminLoginRequest(BaseModel):
    """平台管理员登录请求，remember_me 控制 refresh/session 生命周期。"""

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1)
    remember_me: bool = False


class AdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[EmailStr] = None
    permissions: List[str]
    is_active: bool
    is_super_admin: bool
    must_change_credentials: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None


class AdminLoginResponse(BaseModel):
    """平台管理员登录/刷新响应，返回新的 token 对和当前管理员资料。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    session_id: str
    admin: AdminResponse


class AdminRefreshTokenRequest(BaseModel):
    """平台管理员 refresh 请求体，携带 opaque refresh token。"""

    refresh_token: str = Field(min_length=32)


class AdminSessionResponse(BaseModel):
    """平台管理员会话列表项，用于展示和撤销 active sessions。"""

    session_id: str
    scope: str
    client_type: str
    remember_me: bool
    expires_at: datetime
    last_seen_at: datetime
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    is_current: bool = False


class AdminProfileUpdateRequest(BaseModel):
    current_password: str = Field(min_length=1)
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=32)


class AdminCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: str = Field(min_length=8, max_length=32)
    permissions: List[str] = Field(default_factory=list)
    is_active: bool = True
    is_super_admin: bool = False


class AdminUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_super_admin: Optional[bool] = None
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class DashboardStatsResponse(BaseModel):
    total_users: int
    daily_active_users: int
    cpu_usage_percent: float
    memory_usage_percent: float


class OperationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    operator_id: Optional[int]
    operator_username: Optional[str]
    action: str
    target_type: str
    target_id: Optional[int]
    details: str
    created_at: datetime


class OperationLogListResponse(PaginatedResponse[OperationLogResponse]):
    pass


class TerminalLogResponse(BaseModel):
    timestamp: str
    level: str
    message: str


class TerminalLogListResponse(BaseModel):
    items: List[TerminalLogResponse]
    total: int
