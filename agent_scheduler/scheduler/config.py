"""
Scheduler 配置模块

从 management 数据库读取系统配置（优先级最高）
如果数据库未配置，则 fallback 到 .env 文件
"""

import os
from dataclasses import dataclass
from pathlib import Path

from agent_scheduler.management.backend.db_client import get_db_client


def _load_env_file() -> None:
    """从 .env 文件加载环境变量"""
    scheduler_dir = Path(__file__).parent.parent
    env_file = scheduler_dir / ".env"
    if not env_file.exists():
        return

    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    if key not in os.environ:
                        os.environ[key] = value.strip()
    except Exception:
        pass


@dataclass
class SchedulerConfig:
    """
    调度器配置类

    配置加载顺序（优先级从高到低）：
    1. 数据库 system_configs 表（主存储）
    2. 环境变量
    3. .env 文件
    4. 程序默认值
    """
    admin_key: str = ""
    ai_user_password: str = "ai123456"
    ai_users_config_path: str = "./ai_users_config.json"
    log_level: str = "INFO"
    api_base_url: str = "http://localhost:8000/api/v1"

    @classmethod
    def from_db_or_env(cls) -> "SchedulerConfig":
        """
        从数据库或环境变量加载配置

        优先从 management 数据库读取，不存在则 fallback 到环境变量
        """
        _load_env_file()
        db = get_db_client()

        admin_key = db.get_system_config("ADMIN_KEY")
        if not admin_key:
            admin_key = os.environ.get("ADMIN_KEY", "")

        ai_user_password = db.get_system_config("AI_USER_PASSWORD")
        if not ai_user_password:
            ai_user_password = os.environ.get("AI_USER_PASSWORD", "ai123456")

        api_base_url = db.get_system_config("API_BASE_URL")
        if not api_base_url:
            api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")

        log_level = db.get_system_config("LOG_LEVEL")
        if not log_level:
            log_level = os.environ.get("LOG_LEVEL", "INFO")

        config_path = os.environ.get("AI_USERS_CONFIG_PATH", "./ai_users_config.json")
        if config_path.startswith('./'):
            scheduler_dir = Path(__file__).parent.parent
            config_path = str(scheduler_dir / config_path[2:])
        elif not os.path.isabs(config_path):
            scheduler_dir = Path(__file__).parent.parent
            config_path = str(scheduler_dir / config_path)

        return cls(
            admin_key=admin_key,
            ai_user_password=ai_user_password,
            ai_users_config_path=config_path,
            log_level=log_level,
            api_base_url=api_base_url.rstrip('/'),
        )


_scheduler_config: SchedulerConfig | None = None


def get_scheduler_config() -> SchedulerConfig:
    """获取调度器配置单例"""
    global _scheduler_config
    if _scheduler_config is None:
        _scheduler_config = SchedulerConfig.from_db_or_env()
    return _scheduler_config


def reload_scheduler_config():
    """重载调度器配置（热更新）"""
    global _scheduler_config
    _scheduler_config = SchedulerConfig.from_db_or_env()
    return _scheduler_config
