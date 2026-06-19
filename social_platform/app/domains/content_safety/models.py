"""内容安全领域持久化模型。

本模块拥有用户举报记录和被举报内容 LLM 自动审查配置。表结构保持与迁移前一致，
供公开举报 API、管理端内容审核和后台 LLM 审核流程共同使用。
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from social_platform.app.db.session import Base


class ContentReport(Base):
    """用户对帖子、评论或用户主页的举报记录。"""

    __tablename__ = "content_reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type = Column(String(20), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    reason = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="pending", server_default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by_admin_id = Column(
        Integer,
        ForeignKey("platform_admin_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    escalation_id = Column(
        Integer,
        ForeignKey("content_report_escalations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    reporter = relationship("User", foreign_keys=[reporter_id])
    post = relationship("Post")
    comment = relationship("Comment")
    user = relationship("User", foreign_keys=[user_id])
    reviewed_by_admin = relationship("PlatformAdminUser")
    escalation = relationship("ContentReportEscalation", back_populates="reports")

    __table_args__ = (
        Index("idx_content_reports_post_status", "post_id", "status"),
        Index("idx_content_reports_comment_status", "comment_id", "status"),
        Index("idx_content_reports_user_status", "user_id", "status"),
        Index("idx_content_reports_reporter_post_status", "reporter_id", "post_id", "status"),
        Index("idx_content_reports_reporter_comment_status", "reporter_id", "comment_id", "status"),
        Index("idx_content_reports_reporter_user_status", "reporter_id", "user_id", "status"),
    )


class ContentReportEscalation(Base):
    """内容举报累计触发的用户级审查记录。"""

    __tablename__ = "content_report_escalations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="pending", server_default="pending", index=True)
    reason = Column(Text, nullable=False)
    trigger_content_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by_admin_id = Column(
        Integer,
        ForeignKey("platform_admin_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user = relationship("User")
    reviewed_by_admin = relationship("PlatformAdminUser")
    reports = relationship("ContentReport", back_populates="escalation")

    __table_args__ = (
        Index("idx_content_report_escalations_user_status", "user_id", "status"),
    )


class ContentModerationLLMSettings(Base):
    """被举报内容 LLM 自动审查配置。"""

    __tablename__ = "content_moderation_llm_settings"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, nullable=False, default=False, server_default="0")
    llm_base_url = Column(String(500), nullable=True)
    llm_model_name = Column(String(120), nullable=True)
    llm_api_key = Column(String(500), nullable=True)
    prompt_template = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
