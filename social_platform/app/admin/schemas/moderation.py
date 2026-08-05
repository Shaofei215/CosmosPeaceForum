from datetime import date, datetime
from social_platform.app.core.timezone import local_now
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserModerationRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=1000)
    until: Optional[datetime] = None


ViolationCategory = Literal[
    "publish", "comment", "interaction", "avatar", "username", "bio", "account"
]


class UserViolationRequest(BaseModel):
    """管理员登记一次违规，处罚期限由服务端根据累计次数计算。"""

    category: ViolationCategory
    reason: Optional[str] = Field(default=None, max_length=1000)


class UserViolationBatchRequest(UserViolationRequest):
    """批量登记同一种违规。"""

    user_ids: list[int] = Field(min_length=1, max_length=500)

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(cls, value: list[int]) -> list[int]:
        """去重并拒绝非正数用户 ID。"""

        unique_ids = list(dict.fromkeys(value))
        if any(user_id <= 0 for user_id in unique_ids):
            raise ValueError("用户 ID 必须为正整数")
        return unique_ids


class UserModerationUpdateRequest(BaseModel):
    account_banned: Optional[bool] = None
    account_ban_reason: Optional[str] = Field(default=None, max_length=1000)
    publish_banned_until: Optional[datetime] = None
    publish_ban_reason: Optional[str] = Field(default=None, max_length=1000)
    comment_banned_until: Optional[datetime] = None
    comment_ban_reason: Optional[str] = Field(default=None, max_length=1000)
    interaction_banned_until: Optional[datetime] = None
    interaction_ban_reason: Optional[str] = Field(default=None, max_length=1000)

    @field_validator(
        "publish_banned_until",
        "comment_banned_until",
        "interaction_banned_until",
    )
    @classmethod
    def validate_future_until(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone().replace(tzinfo=None)
        if value <= local_now():
            raise ValueError("封禁结束时间必须晚于当前时间")
        return value


class UserModerationBatchUpdateRequest(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=500)
    moderation: UserModerationUpdateRequest

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(cls, value: list[int]) -> list[int]:
        unique_ids = list(dict.fromkeys(value))
        if any(user_id <= 0 for user_id in unique_ids):
            raise ValueError("用户 ID 必须为正整数")
        return unique_ids


class UserModerationStatusResponse(BaseModel):
    account_banned: bool = False
    account_banned_at: Optional[datetime] = None
    account_ban_reason: Optional[str] = None
    publish_banned_until: Optional[datetime] = None
    publish_violation_count: int = 0
    publish_permanently_banned: bool = False
    publish_ban_reason: Optional[str] = None
    comment_banned_until: Optional[datetime] = None
    comment_violation_count: int = 0
    comment_permanently_banned: bool = False
    comment_ban_reason: Optional[str] = None
    interaction_banned_until: Optional[datetime] = None
    interaction_violation_count: int = 0
    interaction_permanently_banned: bool = False
    interaction_ban_reason: Optional[str] = None
    avatar_banned_until: Optional[datetime] = None
    avatar_violation_count: int = 0
    avatar_permanently_banned: bool = False
    avatar_ban_reason: Optional[str] = None
    username_banned_until: Optional[datetime] = None
    username_violation_count: int = 0
    username_permanently_banned: bool = False
    username_ban_reason: Optional[str] = None
    bio_banned_until: Optional[datetime] = None
    bio_violation_count: int = 0
    bio_permanently_banned: bool = False
    bio_ban_reason: Optional[str] = None
    updated_at: Optional[datetime] = None


class UserModerationResponse(UserModerationStatusResponse):
    user_id: int


class UserModerationBatchUpdateResponse(BaseModel):
    updated_count: int
    items: list[UserModerationResponse]


class UserWithModerationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: Optional[str]
    email: Optional[str]
    bio: Optional[str]
    avatar_url: Optional[str]
    created_at: datetime
    following_count: int
    followers_count: int
    post_count: int
    comment_count: int
    coin_balance: int
    login_streak: int
    last_coin_reward_date: Optional[date] = None
    moderation: UserModerationStatusResponse


class UserCoinBalanceUpdateRequest(BaseModel):
    """管理员设置用户硬币余额。"""

    coin_balance: int = Field(ge=0, le=65_535)


class UserCoinBalanceResponse(BaseModel):
    """管理员更新后的用户硬币余额。"""

    user_id: int
    coin_balance: int


class ContentDeleteRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=1000)
    notify_author: bool = True


class AdminAnnouncementRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class AdminAnnouncementResponse(BaseModel):
    recipient_count: int
