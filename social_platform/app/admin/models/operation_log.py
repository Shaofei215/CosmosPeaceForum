from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import Column, DateTime, Integer, String, Text

from social_platform.app.db.session import Base


class PlatformAdminOperationLog(Base):
    """公开平台管理器审计日志。"""

    __tablename__ = "platform_admin_operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    operator_id = Column(Integer, nullable=True, index=True)
    operator_username = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=False, index=True)
    target_id = Column(Integer, nullable=True, index=True)
    details = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=local_now, nullable=False, index=True)

