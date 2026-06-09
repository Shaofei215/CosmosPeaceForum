"""Management 管理员服务端 session 模型。

admin_sessions 让 management 管理员 access token 可以被立即撤销，并承载
refresh token 轮换所需的哈希、过期时间和审计信息。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, String, Text
from sqlmodel import Field, SQLModel


class AdminSession(SQLModel, table=True):
    """Management 管理员可撤销会话，保存 refresh token 哈希和审计字段。"""

    __tablename__ = "admin_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(sa_column=Column(String(64), unique=True, nullable=False, index=True))
    admin_id: int = Field(index=True)
    scope: str = Field(default="management_admin", max_length=32, index=True)
    client_type: str = Field(default="desktop", max_length=32, index=True)
    refresh_token_hash: str = Field(sa_column=Column(String(64), unique=True, nullable=False, index=True))
    revoked_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, index=True))
    expires_at: datetime = Field(sa_column=Column(DateTime, nullable=False, index=True))
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    user_agent: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    ip_address: Optional[str] = Field(default=None, max_length=64)
    remember_me: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
