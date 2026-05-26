"""
Management Backend - 请求/响应模型
"""

from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int = 0
    limit: int = 100


# ==================== Auth ====================

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: "AdminUserResponse"


class AgentAppLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    app_platform_user_id: int
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


class AdminCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: str = Field(min_length=8, max_length=128)
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


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    monthly_logins: Optional[int] = None
    personal_signature: Optional[str] = None
    personality_prompt: Optional[str] = None
    is_active: Optional[bool] = None


class AgentResponse(BaseModel):
    id: int
    name: str
    username: str
    monthly_logins: int
    personal_signature: str
    personality_prompt: str
    knows_ids: List[int]
    is_active: bool
    app_platform_user_id: Optional[int] = None
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


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    is_active: Optional[bool] = None
    max_token: Optional[int] = None


class ModelConfigResponse(BaseModel):
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


class EmbeddingConfigCreate(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model_name: str = "text-embedding-3-small"
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
