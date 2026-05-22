from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from social_platform.app.schemas.user import UserResponse


class NotificationResponse(BaseModel):
    id: int
    type: str
    resource_type: str
    resource_id: int
    post_id: Optional[int] = None
    source_post_type: Optional[str] = None
    comment_id: Optional[int] = None
    source_content: Optional[str] = None
    is_read: bool = False
    created_at: datetime
    sender: Optional[UserResponse] = None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread_count: int
    skip: int
    limit: int


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


class NotificationSummaryResponse(BaseModel):
    following_count: int
    followers_count: int
    unread_count: int
