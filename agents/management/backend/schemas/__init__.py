"""
Management Backend - 请求/响应模型
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ==================== Auth ====================

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminUserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None
    current_password: str
    new_password: Optional[str] = None


# ==================== Agent ====================

class AgentCreate(BaseModel):
    name: str
    username: str
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


class AgentRelationResponse(BaseModel):
    id: int
    name: str
    username: str
    knows_ids: List[int]

    class Config:
        from_attributes = True


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


# ==================== Operation Log ====================

class OperationLogResponse(BaseModel):
    id: int
    operator_id: int
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


# ==================== Generic Response ====================

class MessageResponse(BaseModel):
    message: str
