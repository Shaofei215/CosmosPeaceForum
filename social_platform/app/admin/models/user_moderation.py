from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

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
    account_ban_reason = Column(Text, nullable=True)
    publish_banned_until = Column(DateTime, nullable=True)
    publish_ban_reason = Column(Text, nullable=True)
    comment_banned_until = Column(DateTime, nullable=True)
    comment_ban_reason = Column(Text, nullable=True)
    interaction_banned_until = Column(DateTime, nullable=True)
    interaction_ban_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    updated_by_admin_id = Column(Integer, nullable=True)
