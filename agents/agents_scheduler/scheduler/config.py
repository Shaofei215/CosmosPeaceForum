"""
Scheduler 配置模块

基础/敏感配置从 agents/.env 读取，运行期可调配置继续通过
management 数据库抽象层加载。
"""

from dataclasses import dataclass

from agents.management.backend.core.config import get_config


@dataclass
class SchedulerConfig:
    """
    调度器配置类

    app_platform 地址、ADMIN_KEY、AI 默认密码和日志级别从 agents/.env 加载。
    """
    admin_key: str = ""
    agent_service_token: str = ""
    ai_user_password: str = "ChangeMe123!"
    log_level: str = "INFO"
    api_base_url: str = "http://localhost:8000/api/v1"
    internal_host: str = "127.0.0.1"
    internal_port: int = 8002
    internal_base_url: str = "http://127.0.0.1:8002"

    @classmethod
    def from_db(cls) -> "SchedulerConfig":
        """加载调度器配置"""
        config = get_config()
        return cls(
            admin_key=config.admin_key,
            agent_service_token=config.agent_service_token,
            ai_user_password=config.ai_user_password,
            log_level=config.log_level,
            api_base_url=config.app_platform_api_base_url.rstrip('/'),
            internal_host=config.scheduler_internal_host,
            internal_port=config.scheduler_internal_port,
            internal_base_url=config.scheduler_internal_base_url,
        )


_scheduler_config: SchedulerConfig | None = None


def get_scheduler_config() -> SchedulerConfig:
    """获取调度器配置单例"""
    global _scheduler_config
    if _scheduler_config is None:
        _scheduler_config = SchedulerConfig.from_db()
    return _scheduler_config


def reload_scheduler_config():
    """重载调度器配置"""
    global _scheduler_config
    _scheduler_config = SchedulerConfig.from_db()
    return _scheduler_config
