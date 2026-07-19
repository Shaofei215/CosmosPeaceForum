from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from social_platform.app.db.session import Base


class UserModeration(Base):
    """用户管理处罚状态，与公开用户表解耦保存。"""

    __tablename__ = "platform_user_moderations"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    account_banned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    account_current_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    account_ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_banned_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    publish_violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    publish_permanently_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    publish_current_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publish_ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment_banned_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comment_violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    comment_permanently_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    comment_current_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    interaction_banned_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interaction_violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    interaction_permanently_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    interaction_current_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interaction_ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_banned_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    avatar_violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    avatar_permanently_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    avatar_current_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avatar_ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    username_banned_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    username_violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    username_permanently_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    username_current_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username_ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio_banned_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    bio_violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    bio_permanently_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    bio_current_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bio_ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, onupdate=local_now, nullable=False)
    updated_by_admin_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
