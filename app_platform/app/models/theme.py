from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, Text

from app_platform.app.db.session import Base


class PlatformThemeSettings(Base):
    """公开平台用户侧主题配置。"""

    __tablename__ = "platform_theme_settings"

    id = Column(Integer, primary_key=True, default=1)

    accent_color = Column(Text, nullable=False, default="#111827")
    accent_foreground_color = Column(Text, nullable=False, default="#ffffff")
    subtle_color = Column(Text, nullable=False, default="rgba(243, 244, 246, 0.82)")
    subtle_foreground_color = Column(Text, nullable=False, default="#4b5563")

    topbar_background_mode = Column(Text, nullable=False, default="solid")
    topbar_solid_color = Column(Text, nullable=False, default="#ffffff")
    topbar_gradient_from = Column(Text, nullable=False, default="#ffffff")
    topbar_gradient_to = Column(Text, nullable=False, default="#f3f4f6")
    topbar_gradient_direction = Column(Text, nullable=False, default="90deg")
    topbar_scrolled_background = Column(Text, nullable=False, default="rgba(255, 255, 255, 0.45)")

    topbar_decoration_top = Column(Text, nullable=True)
    topbar_decoration_bottom = Column(Text, nullable=True)
    topbar_decoration_left = Column(Text, nullable=True)
    topbar_decoration_right = Column(Text, nullable=True)

    topbar_action_active_color = Column(Text, nullable=True)
    topbar_action_active_foreground_color = Column(Text, nullable=True)
    topbar_action_inactive_color = Column(Text, nullable=True)
    topbar_action_inactive_foreground_color = Column(Text, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
