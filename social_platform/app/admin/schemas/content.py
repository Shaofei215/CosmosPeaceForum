from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ContentItemResponse(BaseModel):
    id: int
    type: str
    post_id: Optional[int] = None
    author_id: int
    author_username: Optional[str]
    title: Optional[str] = None
    content: str
    created_at: datetime
    like_count: int
    comment_count: Optional[int] = None
    reply_count: Optional[int] = None

class ContentReportReasonResponse(BaseModel):
    reason: str
    count: int


class ReportedContentItemResponse(ContentItemResponse):
    report_count: int
    report_reasons: list[ContentReportReasonResponse]
    last_reported_at: datetime


class ReportedUserItemResponse(BaseModel):
    id: int
    username: Optional[str]
    bio: Optional[str]
    avatar_url: Optional[str]
    is_ai_agent: bool
    created_at: datetime
    report_count: int
    report_reasons: list[ContentReportReasonResponse]
    last_reported_at: datetime


class ContentModerationLLMSettingsResponse(BaseModel):
    id: int
    enabled: bool
    llm_base_url: Optional[str]
    llm_model_name: Optional[str]
    llm_api_key: Optional[str]
    updated_at: datetime


class ContentModerationLLMSettingsUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    llm_base_url: Optional[str] = Field(default=None, max_length=500)
    llm_model_name: Optional[str] = Field(default=None, max_length=120)
    llm_api_key: Optional[str] = Field(default=None, max_length=500)


class ContentModerationLLMPromptConfigResponse(BaseModel):
    key: str
    name: str
    description: str
    value: str
    default_value: str
    updated_at: datetime


class ContentModerationLLMPromptConfigUpdateRequest(BaseModel):
    value: str = Field(min_length=1)
