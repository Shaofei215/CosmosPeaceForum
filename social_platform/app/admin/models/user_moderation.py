from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text

from social_platform.app.db.session import Base


class UserModeration(Base):
    """用户管理处罚状态，与公开用户表解耦保存。"""

    __tablename__ = "platform_user_moderations"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    account_banned_at = Column(DateTime, nullable=True)
    account_current_event_id = Column(Integer, nullable=True)
    account_ban_reason = Column(Text, nullable=True)
    publish_banned_until = Column(DateTime, nullable=True)
    publish_violation_count = Column(Integer, nullable=False, default=0, server_default="0")
    publish_permanently_banned = Column(Boolean, nullable=False, default=False, server_default="0")
    publish_current_event_id = Column(Integer, nullable=True)
    publish_ban_reason = Column(Text, nullable=True)
    comment_banned_until = Column(DateTime, nullable=True)
    comment_violation_count = Column(Integer, nullable=False, default=0, server_default="0")
    comment_permanently_banned = Column(Boolean, nullable=False, default=False, server_default="0")
    comment_current_event_id = Column(Integer, nullable=True)
    comment_ban_reason = Column(Text, nullable=True)
    interaction_banned_until = Column(DateTime, nullable=True)
    interaction_violation_count = Column(Integer, nullable=False, default=0, server_default="0")
    interaction_permanently_banned = Column(Boolean, nullable=False, default=False, server_default="0")
    interaction_current_event_id = Column(Integer, nullable=True)
    interaction_ban_reason = Column(Text, nullable=True)
    avatar_banned_until = Column(DateTime, nullable=True)
    avatar_violation_count = Column(Integer, nullable=False, default=0, server_default="0")
    avatar_permanently_banned = Column(Boolean, nullable=False, default=False, server_default="0")
    avatar_current_event_id = Column(Integer, nullable=True)
    avatar_ban_reason = Column(Text, nullable=True)
    username_banned_until = Column(DateTime, nullable=True)
    username_violation_count = Column(Integer, nullable=False, default=0, server_default="0")
    username_permanently_banned = Column(Boolean, nullable=False, default=False, server_default="0")
    username_current_event_id = Column(Integer, nullable=True)
    username_ban_reason = Column(Text, nullable=True)
    bio_banned_until = Column(DateTime, nullable=True)
    bio_violation_count = Column(Integer, nullable=False, default=0, server_default="0")
    bio_permanently_banned = Column(Boolean, nullable=False, default=False, server_default="0")
    bio_current_event_id = Column(Integer, nullable=True)
    bio_ban_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=local_now, nullable=False)
    updated_at = Column(DateTime, default=local_now, onupdate=local_now, nullable=False)
    updated_by_admin_id = Column(Integer, nullable=True)
