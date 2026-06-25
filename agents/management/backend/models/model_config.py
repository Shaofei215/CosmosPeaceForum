"""
Management Backend - 模型配置模型
对应 model_configs 表
"""

from datetime import datetime
from agents.management.backend.core.timezone import local_now
from typing import Optional

from sqlmodel import Field, SQLModel


class ModelConfig(SQLModel, table=True):
    """LLM 模型配置"""

    __tablename__ = "model_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=100)
    provider: str = Field(max_length=50, description="提供商（openai/anthropic）")
    api_key: str = Field(max_length=500, description="API Key（明文存储）")
    base_url: str = Field(default="", max_length=500)
    model_name: str = Field(max_length=100)
    temperature: float = Field(default=0.7)
    is_active: bool = Field(default=True)
    max_token: int = Field(default=4096)
    color: str = Field(default="#10A37F", max_length=20)
    created_at: datetime = Field(default_factory=local_now)
    updated_at: datetime = Field(default_factory=local_now)
