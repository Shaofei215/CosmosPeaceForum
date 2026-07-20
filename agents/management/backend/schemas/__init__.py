"""
Management Backend - 请求/响应模型。

认证响应包含短期 access token、opaque refresh token 和 session_id，
用于支持 management admin session 撤销和 refresh token 轮换。
"""

from datetime import datetime
from typing import Annotated, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

T = TypeVar("T")
AdminUsername = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=30),
]


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int = 0
    limit: int = 100


# ==================== Auth ====================

class LoginRequest(BaseModel):
    """Management 管理员登录请求，remember_me 控制 refresh/session 生命周期。"""

    username: AdminUsername
    password: str = Field(min_length=1)
    remember_me: bool = False


class LoginResponse(BaseModel):
    """Management 管理员登录/刷新响应，返回新的 token 对和管理员资料。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    session_id: str
    admin: "AdminUserResponse"


class RefreshTokenRequest(BaseModel):
    """Management refresh 请求体，携带 opaque refresh token。"""

    refresh_token: str = Field(min_length=32)


class SessionResponse(BaseModel):
    """Management 管理员会话列表项。"""

    session_id: str
    scope: str
    client_type: str
    remember_me: bool
    expires_at: datetime
    last_seen_at: datetime
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    is_current: bool = False


class AgentAppLoginResponse(BaseModel):
    """Agent 角色登录公开平台后的 token 与浏览器跳转地址响应。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    session_id: str
    social_platform_user_id: int
    social_platform_frontend_url: str
    username: str


class AdminUserResponse(BaseModel):
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


class AdminProfileUpdateRequest(BaseModel):
    """当前管理员更新首次登录资料的请求。"""

    current_password: str = Field(min_length=1)
    username: Optional[AdminUsername] = None
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=32)


class AdminCreateRequest(BaseModel):
    """创建管理员请求，用户名沿用 Management 账号的统一长度约束。"""

    username: AdminUsername
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


class AdminListResponse(PaginatedResponse[AdminUserResponse]):
    pass


# ==================== Agent ====================

class AgentCreate(BaseModel):
    name: str
    username: str = Field(min_length=1, max_length=30)
    monthly_logins: int = 30
    personal_signature: str = ""
    personality_prompt: str = ""
    is_active: bool = True
    model_config_id: Optional[int] = None


class AgentUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=1, max_length=30)
    name: Optional[str] = None
    monthly_logins: Optional[int] = None
    personal_signature: Optional[str] = None
    personality_prompt: Optional[str] = None
    is_active: Optional[bool] = None
    model_config_id: Optional[int] = None


class AgentResponse(BaseModel):
    id: int
    name: str
    username: str
    monthly_logins: int
    personal_signature: str
    personality_prompt: str
    knows_ids: List[int]
    is_active: bool
    model_config_id: Optional[int] = None
    social_platform_user_id: Optional[int] = None
    last_login_at: Optional[datetime] = None
    last_login_timestamp: Optional[float] = None
    total_login_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    items: List[AgentResponse]
    total: int


class AgentRelationUpdate(BaseModel):
    knows_ids: List[int] = []
    bidirectional: bool = False


class PromptInjectionRequest(BaseModel):
    agent_ids: List[int] = Field(min_length=1)
    content: str = Field(min_length=1, max_length=8000)


class AgentRelationResponse(BaseModel):
    id: int
    name: str
    username: str
    knows_ids: List[int]

    class Config:
        from_attributes = True


class DashboardStatsResponse(BaseModel):
    total_roles: int
    enabled_roles: int
    daily_active_roles: int
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0


# ==================== Memory ====================

class MemoryUpdateRequest(BaseModel):
    """
    单条记忆编辑请求。

    owner_id 与系统创建时间不可由管理端修改；内容、语义时间、系数和类型变更后，
    后端会以 SQLite 为主数据并在响应后重建 Chroma 与 Tantivy 派生索引。
    """

    content: str = Field(min_length=1)
    semantic_timestamp: float = Field(ge=0)
    memory_coefficient: float = Field(ge=0, le=1)
    memory_type: Literal["normal", "static"]


# ==================== Model Config ====================

class ModelConfigCreate(BaseModel):
    name: str
    provider: str
    api_key: str
    base_url: str = ""
    model_name: str
    temperature: float = 1.2
    is_active: bool = True
    max_token: int = 4096
    color: str = "#10A37F"
    assigned_agent_ids: Optional[List[int]] = None


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    is_active: Optional[bool] = None
    max_token: Optional[int] = None
    color: Optional[str] = None
    assigned_agent_ids: Optional[List[int]] = None


class ModelConfigResponse(BaseModel):
    id: int
    name: str
    provider: str
    base_url: str
    model_name: str
    temperature: float
    is_active: bool
    max_token: int
    color: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmbeddingConfigCreate(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model_name: str = ""
    dimension: int = 1536
    is_active: bool = False


class EmbeddingConfigUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    dimension: Optional[int] = None
    is_active: Optional[bool] = None


class EmbeddingConfigResponse(BaseModel):
    id: int
    base_url: str
    api_key: str
    model_name: str
    dimension: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChunkModelConfigCreate(BaseModel):
    name: str
    provider: str
    api_key: str
    base_url: str = ""
    model_name: str
    temperature: float = 1.2
    is_active: bool = True
    max_token: int = 4096


class ChunkModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    is_active: Optional[bool] = None
    max_token: Optional[int] = None


class ChunkModelConfigResponse(BaseModel):
    id: int
    name: str
    provider: str
    base_url: str
    model_name: str
    temperature: float
    is_active: bool
    max_token: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== System Config ====================

class SystemConfigResponse(BaseModel):
    id: int
    key: str
    value: str
    description: str
    updated_at: datetime

    class Config:
        from_attributes = True


class SystemConfigUpdate(BaseModel):
    value: str


class PromptConfigResponse(BaseModel):
    id: int
    key: str
    name: str
    value: str
    default_value: str
    description: str
    updated_at: datetime

    class Config:
        from_attributes = True


class PromptConfigUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=50000)


# ==================== Operation Log ====================

class OperationLogResponse(BaseModel):
    id: int
    operator_id: Optional[int]
    operator_username: Optional[str] = None
    action: str
    target_type: str
    target_id: Optional[int] = None
    details: str
    created_at: datetime

    class Config:
        from_attributes = True


class OperationLogListResponse(BaseModel):
    items: List[OperationLogResponse]
    total: int


# ==================== Terminal Log ====================

class TerminalLogResponse(BaseModel):
    timestamp: str
    level: str
    message: str


class TerminalLogListResponse(BaseModel):
    items: List[TerminalLogResponse]
    total: int


# ==================== Generic Response ====================

class MessageResponse(BaseModel):
    message: str
