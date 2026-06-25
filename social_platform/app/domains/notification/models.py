from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from social_platform.app.db.session import Base


class Notification(Base):
    """通知领域数据库模型，记录由其他领域事件驱动生成的用户通知。"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    type = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(Integer, nullable=False, index=True)

    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True)
    source_content = Column(Text, nullable=True)

    is_read = Column(Integer, default=0, nullable=False, index=True)
    created_at = Column(DateTime, default=local_now, nullable=False, index=True)

    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="notifications")
    sender = relationship("User", foreign_keys=[sender_id])
    post = relationship("Post", foreign_keys=[post_id])
    comment = relationship("Comment", foreign_keys=[comment_id])

    @property
    def source_post_type(self):
        """返回通知来源帖子类型，兼容列表展示中的 post/article 区分。"""
        if self.type == "repost" and self.post and self.post.repost_root_post:
            return self.post.repost_root_post.type
        return self.post.type if self.post else None

    __table_args__ = (
        Index("idx_notifications_recipient_read_created", "recipient_id", "is_read", "created_at"),
        Index("idx_notifications_recipient_created", "recipient_id", "created_at"),
        Index("idx_notifications_resource", "resource_type", "resource_id"),
    )

# 导入关系依赖模型，确保单独导入 Notification 时 SQLAlchemy 字符串关系可解析。
from social_platform.app.domains.comment import models as _comment_models  # noqa: E402,F401
from social_platform.app.domains.post import models as _post_models  # noqa: E402,F401
from social_platform.app.domains.user import models as _user_models  # noqa: E402,F401
