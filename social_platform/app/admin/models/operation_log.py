from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from social_platform.app.db.session import Base


class PlatformAdminOperationLog(Base):
    """公开平台管理器审计日志。"""

    __tablename__ = "platform_admin_operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    operator_username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False, index=True)

