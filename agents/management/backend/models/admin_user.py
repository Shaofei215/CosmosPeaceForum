"""
Management Backend - 管理员用户模型
对应 admin_users 表
"""

from datetime import datetime
from agents.management.backend.core.timezone import local_now
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class AdminUser(SQLModel, table=True):
    """管理员用户"""

    __tablename__ = "admin_users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    password_hash: str = Field(max_length=255)
    permissions: str = Field(default="[]", sa_column=Column(Text, nullable=False, default="[]"))
    is_active: bool = Field(default=True)
    is_super_admin: bool = Field(default=False)
    must_change_credentials: bool = Field(default=False)
    created_at: datetime = Field(default_factory=local_now)
    updated_at: datetime = Field(default_factory=local_now)
    last_login: Optional[datetime] = Field(default=None)
