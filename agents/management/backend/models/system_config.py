"""
Management Backend - 系统配置模型
对应 system_configs 表
"""

from datetime import datetime
from agents.management.backend.core.timezone import local_now
from typing import Optional

from sqlmodel import Field, SQLModel


class SystemConfig(SQLModel, table=True):
    """系统配置"""

    __tablename__ = "system_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=100)
    value: str = Field(max_length=1000)
    description: str = Field(default="", max_length=500)
    created_at: datetime = Field(default_factory=local_now)
    updated_at: datetime = Field(default_factory=local_now)
