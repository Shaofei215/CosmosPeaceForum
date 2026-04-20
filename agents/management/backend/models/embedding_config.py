"""
Management Backend - Embedding 配置模型
对应 embedding_configs 表
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class EmbeddingConfig(SQLModel, table=True):
    """Embedding 模型配置"""

    __tablename__ = "embedding_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    base_url: str = Field(default="", max_length=500, description="向量化模型 Base URL")
    api_key: str = Field(default="", max_length=500, description="API Key")
    model_name: str = Field(default="text-embedding-3-small", max_length=100, description="向量化模型名称")
    dimension: int = Field(default=1536, description="向量维度")
    is_active: bool = Field(default=False, description="是否启用")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
