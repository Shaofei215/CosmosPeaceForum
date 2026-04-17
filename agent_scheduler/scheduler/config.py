# 调度器配置模块
# 从 .env 加载调度器相关配置，保证扩展性、内聚性、解耦性

import os
from dataclasses import dataclass
from pathlib import Path


def _get_scheduler_env_file() -> str:
    """
    获取 .env 文件路径

    查找顺序：
    1. agent_scheduler 目录下的 .env
    2. 当前工作目录下的 .env

    Returns:
        str: .env 文件路径
    """
    config_dir = Path(__file__).parent.parent
    env_file = config_dir / ".env"
    if env_file.exists():
        return str(env_file)
    return ".env"


def _load_env_file() -> None:
    """
    从 .env 文件加载环境配置到 os.environ
    """
    env_file = _get_scheduler_env_file()
    if not os.path.exists(env_file):
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
                    value = value.strip()
                    if key not in os.environ:
                        os.environ[key] = value
    except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
        print(f"[调度器配置][warning]无法加载环境文件 {env_file}: {e}")
        return


def _get_config_file_path() -> str:
    """
    获取 AI 用户配置文件路径

    Returns:
        str: 配置文件绝对路径
    """
    scheduler_dir = Path(__file__).parent.parent
    config_path = os.environ.get('AI_USERS_CONFIG_PATH', './ai_users_config.json')
    if config_path.startswith('./'):
        return str(scheduler_dir / config_path[2:])
    elif os.path.isabs(config_path):
        return config_path
    else:
        return str(scheduler_dir / config_path)


def _get_api_base_url() -> str:
    """
    获取 API 基础 URL

    Returns:
        str: API 基础 URL
    """
    _api_base = os.environ.get('AGENT_SCHEDULER_API_BASE_URL')
    if not _api_base:
        _api_base = os.environ.get('API_BASE_URL')
    if not _api_base:
        _api_base = os.environ.get('VITE_API_BASE_URL', 'http://localhost:8000/api/v1')

    if _api_base.endswith('/api/v1/'):
        return _api_base[:-1]
    elif not _api_base.endswith('/api/v1'):
        return _api_base if _api_base.endswith('/') else f"{_api_base}/api/v1"
    return _api_base


@dataclass
class SchedulerConfig:
    """
    调度器配置类

    包含控制调度器行为的所有配置参数。

    配置加载顺序（优先级从高到低）：
    1. 环境变量
    2. .env 文件
    3. 程序默认值

    Attributes:
        admin_key: 管理员密钥（用于 AI 用户注册）
        ai_user_password: AI 用户默认密码
        ai_users_config_path: AI 用户配置文件路径
        log_level: 日志级别
        api_base_url: API 基础 URL
    """
    admin_key: str = ""
    ai_user_password: str = "ai123456"
    ai_users_config_path: str = ""
    log_level: str = "INFO"
    api_base_url: str = "http://localhost:8000/api/v1"

    @classmethod
    def from_env(cls) -> "SchedulerConfig":
        """
        从环境变量创建配置实例

        优先从环境变量获取配置值，环境变量不存在时使用默认值。

        Returns:
            SchedulerConfig: 配置实例
        """
        _load_env_file()
        return cls(
            admin_key=os.environ.get("ADMIN_KEY", ""),
            ai_user_password=os.environ.get("AI_USER_PASSWORD", "ai123456"),
            ai_users_config_path=_get_config_file_path(),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            api_base_url=_get_api_base_url(),
        )


_scheduler_config: SchedulerConfig | None = None


def get_scheduler_config() -> SchedulerConfig:
    """
    获取调度器配置单例

    首次调用时从环境变量加载配置，后续调用返回缓存实例。

    Returns:
        SchedulerConfig: 调度器配置实例
    """
    global _scheduler_config
    if _scheduler_config is None:
        _scheduler_config = SchedulerConfig.from_env()
    return _scheduler_config
