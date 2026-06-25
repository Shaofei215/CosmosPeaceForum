"""
Management Backend - 提示词配置模型
对应 prompt_configs 表
"""

from datetime import datetime
from agents.management.backend.core.timezone import local_now
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class PromptConfig(SQLModel, table=True):
    """可编辑提示词配置"""

    __tablename__ = "prompt_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=100)
    name: str = Field(max_length=100)
    value: str = Field(sa_column=sa.Column(sa.Text(), nullable=False))
    default_value: str = Field(sa_column=sa.Column(sa.Text(), nullable=False))
    description: str = Field(default="", max_length=500)
    created_at: datetime = Field(default_factory=local_now)
    updated_at: datetime = Field(default_factory=local_now)
