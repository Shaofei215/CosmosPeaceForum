from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserModerationRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=1000)
    until: Optional[datetime] = None


class UserModerationUpdateRequest(BaseModel):
    account_banned: Optional[bool] = None
    account_ban_reason: Optional[str] = Field(default=None, max_length=1000)
    publish_banned_until: Optional[datetime] = None
    publish_ban_reason: Optional[str] = Field(default=None, max_length=1000)
    comment_banned_until: Optional[datetime] = None
    comment_ban_reason: Optional[str] = Field(default=None, max_length=1000)
    interaction_banned_until: Optional[datetime] = None
    interaction_ban_reason: Optional[str] = Field(default=None, max_length=1000)


class UserModerationStatusResponse(BaseModel):
    account_banned: bool = False
    account_banned_at: Optional[datetime] = None
    account_ban_reason: Optional[str] = None
    publish_banned_until: Optional[datetime] = None
    publish_ban_reason: Optional[str] = None
    comment_banned_until: Optional[datetime] = None
    comment_ban_reason: Optional[str] = None
    interaction_banned_until: Optional[datetime] = None
    interaction_ban_reason: Optional[str] = None
    updated_at: Optional[datetime] = None


class UserModerationResponse(UserModerationStatusResponse):
    user_id: int


class UserWithModerationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: Optional[str]
    email: Optional[str]
    bio: Optional[str]
    avatar_url: Optional[str]
    is_ai_agent: bool
    ai_config_id: Optional[int]
    created_at: datetime
    following_count: int
    followers_count: int
    post_count: int
    comment_count: int
    moderation: UserModerationStatusResponse


class ContentDeleteRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=1000)
    notify_author: bool = True

