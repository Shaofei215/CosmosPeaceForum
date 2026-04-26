"""
Management Backend - 分块模型配置模型
对应 chunk_model_configs 表
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ChunkModelConfig(SQLModel, table=True):
    """分块模型配置（用于记忆智能分块）"""

    __tablename__ = "chunk_model_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=100)
    provider: str = Field(max_length=50, description="提供商（openai/anthropic）")
    api_key: str = Field(max_length=500, description="API Key（明文存储）")
    base_url: str = Field(default="", max_length=500)
    model_name: str = Field(max_length=100)
    temperature: float = Field(default=0.7)
    is_active: bool = Field(default=True)
    max_token: int = Field(default=4096)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
