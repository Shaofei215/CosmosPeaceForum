"""
Management Backend - 系统配置服务

system_configs 只保存运行期可调的非敏感配置。基础设施和敏感配置
（JWT、数据库、平台地址、ADMIN_KEY、AI 默认密码、初始管理员账号密码等）
统一从 agents/.env 或环境变量读取。
"""

from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from agents.management.backend.core.config import get_config
from agents.management.backend.models.system_config import SystemConfig


ENV_MANAGED_CONFIG_KEYS = {
    "ADMIN_KEY",
    "AI_USER_PASSWORD",
    "API_BASE_URL",
    "APP_PLATFORM_API_BASE_URL",
    "LOG_LEVEL",
}

DEFAULT_SYSTEM_CONFIGS = [
    ("LANGGRAPH_MAX_STEPS", "20", "LangGraph 最大决策步数"),
    ("LANGGRAPH_MAX_CONSECUTIVE_ERRORS", "3", "最大连续错误次数"),
    ("LANGGRAPH_TOOL_TIMEOUT", "30", "工具调用超时时间（秒）"),
    ("WEB_SEARCH_ENABLED", "false", "是否启用 Agent 联网搜索工具"),
    ("TAVILY_API_KEY", "", "Tavily 联网搜索 API Key"),
    ("MEMORY_ENABLED", "true", "是否启用记忆系统"),
    ("MEMORY_RECALL_LIMIT", "5", "召回记忆数量"),
    ("MEMORY_RECALL_VECTOR_RESULTS", "5", "向量检索返回数量"),
    ("MEMORY_RECALL_BM25_RESULTS", "5", "BM25 检索返回数量"),
    ("MEMORY_THRESHOLD", "0.3", "记忆系数最低阈值"),
    ("MEMORY_BOOST_FACTOR", "0.3", "唤醒时系数增量"),
    ("MEMORY_DECAY_RATE", "0.01", "衰减率（每日）"),
]


def list_system_configs(db: Session) -> List[SystemConfig]:
    """获取所有系统配置"""
    stmt = select(SystemConfig).order_by(SystemConfig.key)
    return list(db.exec(stmt).all())


def get_system_config(db: Session, key: str) -> Optional[SystemConfig]:
    """获取单个系统配置"""
    stmt = select(SystemConfig).where(SystemConfig.key == key)
    return db.exec(stmt).first()


def update_system_config(db: Session, key: str, value: str) -> Optional[SystemConfig]:
    """更新系统配置"""
    if key in ENV_MANAGED_CONFIG_KEYS:
        return None

    db_config = get_system_config(db, key)
    if not db_config:
        return None

    db_config.value = value
    db_config.updated_at = datetime.utcnow()
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def init_default_configs(db: Session) -> int:
    """初始化默认系统配置，返回创建的记录数"""
    count = 0
    purged_count = purge_env_managed_configs(db)
    for key, value, description in DEFAULT_SYSTEM_CONFIGS:
        existing = get_system_config(db, key)
        if not existing:
            config = SystemConfig(
                key=key,
                value=value,
                description=description,
            )
            db.add(config)
            count += 1
    if count > 0 or purged_count > 0:
        db.commit()
    return count


def purge_env_managed_configs(db: Session) -> int:
    """删除旧库里仍保存的环境变量托管配置，避免敏感值继续留在 SQLite。"""
    count = 0
    for key in ENV_MANAGED_CONFIG_KEYS:
        existing = get_system_config(db, key)
        if existing:
            db.delete(existing)
            count += 1
    return count


def get_config_value(db: Session, key: str, default: str = "") -> str:
    """获取配置值。环境托管配置直接读 agents/.env，其余配置从数据库读取。"""
    env_config = get_config()
    env_value_map = {
        "ADMIN_KEY": env_config.admin_key,
        "AI_USER_PASSWORD": env_config.ai_user_password,
        "API_BASE_URL": env_config.app_platform_api_base_url,
        "APP_PLATFORM_API_BASE_URL": env_config.app_platform_api_base_url,
        "LOG_LEVEL": env_config.log_level,
    }
    if key in env_value_map:
        return env_value_map.get(key) or default

    config = get_system_config(db, key)
    if config:
        return config.value

    fallback_map = {
        "LANGGRAPH_MAX_STEPS": "20",
        "LANGGRAPH_MAX_CONSECUTIVE_ERRORS": "3",
        "LANGGRAPH_TOOL_TIMEOUT": "30",
        "WEB_SEARCH_ENABLED": "false",
        "TAVILY_API_KEY": "",
        "MEMORY_ENABLED": "true",
        "MEMORY_RECALL_LIMIT": "5",
        "MEMORY_RECALL_VECTOR_RESULTS": "5",
        "MEMORY_RECALL_BM25_RESULTS": "5",
        "MEMORY_THRESHOLD": "0.3",
        "MEMORY_BOOST_FACTOR": "0.3",
        "MEMORY_DECAY_RATE": "0.01",
    }
    return fallback_map.get(key, default)
