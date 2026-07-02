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
    created_by_agent: bool = False
    like_count: int
    comment_count: Optional[int] = None
    reply_count: Optional[int] = None
    moderation_status: str = "active"
    archived_at: Optional[datetime] = None
    archive_reason: Optional[str] = None

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
    created_at: datetime
    report_count: int
    report_reasons: list[ContentReportReasonResponse]
    last_reported_at: datetime
    source: str = "report"


class ModerationAppealItemResponse(BaseModel):
    """管理端申诉列表项，供内容管理和用户管理的申诉处理页复用。"""

    id: int
    notification_id: int
    appellant_id: int
    appellant_username: Optional[str]
    target_type: str
    target_id: int
    target_label: str
    target_content: Optional[str] = None
    action_label: str
    moderation_reason: Optional[str]
    appeal_reason: str
    status: str
    created_at: datetime
    updated_at: datetime


class ModerationAppealRejectRequest(BaseModel):
    """拒绝申诉请求。"""

    reason: str = Field(min_length=1, max_length=1000)


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
