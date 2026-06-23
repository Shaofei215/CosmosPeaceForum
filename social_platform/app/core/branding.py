"""平台品牌展示配置。

本模块集中提供公开平台对外展示名，供邮件模板、LLM 默认提示词和接口文案复用。
展示名来自 ``Settings.PLATFORM_DISPLAY_NAME``，空值会回退到项目默认名。
"""

from __future__ import annotations

from social_platform.app.core.config import get_settings


DEFAULT_PLATFORM_DISPLAY_NAME = "宇宙和平论坛"
"""平台展示名的内置默认值。"""


def normalize_platform_display_name(value: str | None) -> str:
    """规范化平台展示名。

    Args:
        value: 配置来源中的平台展示名，可为空。

    Returns:
        str: 去除首尾空白后的展示名；空值返回默认展示名。
    """

    normalized = (value or "").strip()
    return normalized or DEFAULT_PLATFORM_DISPLAY_NAME


def get_platform_display_name() -> str:
    """读取当前公开平台展示名。

    Returns:
        str: 当前环境配置的平台展示名。
    """

    return normalize_platform_display_name(get_settings().PLATFORM_DISPLAY_NAME)
