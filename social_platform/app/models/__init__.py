# 模型包初始化
# 仅保留尚未迁移到领域目录的旧模型。领域模型请导入 social_platform.app.domains.registry。

from social_platform.app.models.theme import PlatformThemeSettings

__all__ = [
    "PlatformThemeSettings",
]
