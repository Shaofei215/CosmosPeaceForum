from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from social_platform.app.domains.user.schemas import UserResponse


class NotificationResponse(BaseModel):
    """通知领域 API schema的响应模型，供 API adapter 做参数校验和响应序列化。"""
    id: int
    type: str
    resource_type: str
    resource_id: int
    post_id: Optional[int] = None
    source_post_type: Optional[str] = None
    comment_id: Optional[int] = None
    source_content: Optional[str] = None
    can_appeal: bool = False
    appeal_status: Optional[str] = None
    is_read: bool = False
    created_at: datetime
    created_by_agent: bool = False
    sender: Optional[UserResponse] = None

    class Config:
        """通知领域 API schema的Pydantic ORM 映射配置，供 API adapter 做参数校验和响应序列化。"""
        from_attributes = True


class NotificationListResponse(BaseModel):
    """通知领域 API schema的响应模型，供 API adapter 做参数校验和响应序列化。"""
    items: List[NotificationResponse]
    total: int
    unread_count: int
    skip: int
    limit: int


class NotificationUnreadCountResponse(BaseModel):
    """通知领域 API schema的响应模型，供 API adapter 做参数校验和响应序列化。"""
    unread_count: int


class NotificationSummaryResponse(BaseModel):
    """通知领域 API schema的响应模型，供 API adapter 做参数校验和响应序列化。"""
    following_count: int
    followers_count: int
    unread_count: int
