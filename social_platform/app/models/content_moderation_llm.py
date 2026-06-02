from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from social_platform.app.db.session import Base


class ContentModerationLLMSettings(Base):
    """被举报内容 LLM 自动审查配置。"""

    __tablename__ = "content_moderation_llm_settings"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, nullable=False, default=False, server_default="0")
    llm_base_url = Column(String(500), nullable=True)
    llm_model_name = Column(String(120), nullable=True)
    llm_api_key = Column(String(500), nullable=True)
    prompt_template = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
