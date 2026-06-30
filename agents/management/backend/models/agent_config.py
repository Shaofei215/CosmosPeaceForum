"""
Management Backend - Agent 配置模型
对应 agent_configs 表
"""

from datetime import datetime
from agents.management.backend.core.timezone import local_now
from typing import Optional

from sqlmodel import Field, SQLModel


class AgentConfig(SQLModel, table=True):
    """Agent 配置"""

    __tablename__ = "agent_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    username: str = Field(unique=True, index=True, max_length=100)
    monthly_logins: int = Field(default=30)
    personal_signature: str = Field(default="", max_length=500)
    personality_prompt: str = Field(default="", max_length=4000)
    knows_ids: str = Field(default="")
    is_active: bool = Field(default=True)
    model_config_id: Optional[int] = Field(default=None, foreign_key="model_configs.id")
    social_platform_user_id: Optional[int] = Field(default=None)
    last_login_at: Optional[datetime] = Field(default=None)
    last_login_timestamp: Optional[float] = Field(default=None)
    total_login_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=local_now)
    updated_at: datetime = Field(default_factory=local_now)
