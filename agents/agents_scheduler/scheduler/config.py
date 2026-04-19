"""
Scheduler 配置模块

所有业务配置均通过 management 数据库抽象层加载（system_configs 表）
"""

from dataclasses import dataclass

from agents.management.backend.db_client import get_db_client


@dataclass
class SchedulerConfig:
    """
    调度器配置类

    所有业务配置均从 management 数据库加载，无环境变量 fallback。
    """
    admin_key: str = ""
    ai_user_password: str = "ai123456"
    log_level: str = "INFO"
    api_base_url: str = "http://localhost:8000/api/v1"

    @classmethod
    def from_db(cls) -> "SchedulerConfig":
        """从数据库加载配置"""
        db = get_db_client()

        def _get(key: str, default: str) -> str:
            val = db.get_system_config(key)
            return val if val else default

        return cls(
            admin_key=_get("ADMIN_KEY", ""),
            ai_user_password=_get("AI_USER_PASSWORD", "ai123456"),
            log_level=_get("LOG_LEVEL", "INFO"),
            api_base_url=_get("API_BASE_URL", "http://localhost:8000/api/v1").rstrip('/'),
        )


_scheduler_config: SchedulerConfig | None = None


def get_scheduler_config() -> SchedulerConfig:
    """获取调度器配置单例"""
    global _scheduler_config
    if _scheduler_config is None:
        _scheduler_config = SchedulerConfig.from_db()
    return _scheduler_config


def reload_scheduler_config():
    """重载调度器配置（热更新）"""
    global _scheduler_config
    _scheduler_config = SchedulerConfig.from_db()
    return _scheduler_config
