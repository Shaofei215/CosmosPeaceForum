from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int
    limit: int


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1)


class AdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    permissions: List[str]
    is_active: bool
    is_super_admin: bool
    must_change_credentials: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminResponse


class AdminProfileUpdateRequest(BaseModel):
    current_password: str = Field(min_length=1)
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class AdminCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    permissions: List[str] = Field(default_factory=list)
    is_active: bool = True
    is_super_admin: bool = False


class AdminUpdateRequest(BaseModel):
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_super_admin: Optional[bool] = None
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class DashboardStatsResponse(BaseModel):
    total_users: int
    daily_active_users: int
    total_posts: int
    total_comments: int
    banned_users: int
    active_restrictions: int
    active_threads: int
    process_memory_mb: float
    load_average_1m: float


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

