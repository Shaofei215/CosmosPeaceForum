"""
Management Backend - 系统配置服务

system_configs 只保存运行期可调的非敏感配置。基础设施和敏感配置
（JWT、数据库、平台地址、ADMIN_KEY、AI 默认密码、初始管理员账号密码等）
统一从 agents/.env 或环境变量读取。
"""

import math
from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from agents.management.backend.core.config import get_config
from agents.management.backend.core.timezone import local_now
from agents.management.backend.models.system_config import SystemConfig


ENV_MANAGED_CONFIG_KEYS = {
    "ADMIN_KEY",
    "AI_USER_PASSWORD",
    "SOCIAL_PLATFORM_API_BASE_URL",
    "LOG_LEVEL",
}

REMOVED_SYSTEM_CONFIG_KEYS: set[str] = {
    "LANGGRAPH_CHECKPOINTER_ENABLED",
}

DEFAULT_SYSTEM_CONFIGS = [
    ("SCHEDULER_TIME_SCALE", "1.0", "Scheduler 时间倍率（1.0 为现实时间）"),
    ("LANGGRAPH_MAX_STEPS", "20", "LangGraph 最大决策步数"),
    ("LANGGRAPH_MAX_CONSECUTIVE_ERRORS", "3", "最大连续错误次数"),
    ("LANGGRAPH_TOOL_TIMEOUT", "30", "工具调用超时时间（秒）"),
    ("WEB_SEARCH_ENABLED", "false", "启用联网搜索工具"),
    ("TAVILY_API_KEY", "", "Tavily API Key"),
    ("MEMORY_ENABLED", "true", "是否启用记忆系统"),
    ("MEMORY_RECALL_LIMIT", "5", "召回记忆数量"),
    ("MEMORY_RECALL_VECTOR_RESULTS", "20", "向量检索候选数量"),
    ("MEMORY_RECALL_BM25_RESULTS", "20", "BM25 检索候选数量"),
    ("MEMORY_RRF_RANK_CONSTANT", "60", "RRF 排名常数"),
    ("MEMORY_THRESHOLD", "0.1", "记忆系数最低阈值"),
    ("MEMORY_BOOST_FACTOR", "0.1", "唤醒时系数增量"),
    ("MEMORY_DECAY_RATE", "0.01", "衰减率（每日）"),
    ("MEMORY_DECAY_INTERVAL_SECONDS", "300", "记忆衰减任务实时执行间隔（秒）"),
]


def validate_system_config_value(key: str, value: str) -> None:
    """
    校验系统配置值是否符合该配置项的业务约束。

    Args:
        key: 系统配置键。
        value: 待写入系统配置表的字符串值。

    Returns:
        None: 校验通过时不返回业务数据。

    Raises:
        ValueError: 配置值格式非法或超出允许范围。
    """
    if key == "SCHEDULER_TIME_SCALE":
        try:
            scale = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Scheduler 时间倍率必须是数字") from exc
        if scale <= 0:
            raise ValueError("Scheduler 时间倍率必须大于 0")

    positive_integer_keys = {
        "MEMORY_RECALL_LIMIT",
        "MEMORY_RECALL_VECTOR_RESULTS",
        "MEMORY_RECALL_BM25_RESULTS",
        "MEMORY_RRF_RANK_CONSTANT",
        "MEMORY_DECAY_INTERVAL_SECONDS",
    }
    if key in positive_integer_keys:
        try:
            parsed_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} 必须是正整数") from exc
        if parsed_value <= 0 or str(parsed_value) != value.strip():
            raise ValueError(f"{key} 必须是正整数")

    unit_interval_keys = {"MEMORY_THRESHOLD", "MEMORY_BOOST_FACTOR"}
    if key in unit_interval_keys:
        try:
            parsed_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} 必须在 0.0 到 1.0 之间") from exc
        if not 0.0 <= parsed_value <= 1.0:
            raise ValueError(f"{key} 必须在 0.0 到 1.0 之间")

    if key == "MEMORY_DECAY_RATE":
        try:
            decay_rate = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("MEMORY_DECAY_RATE 必须大于 0") from exc
        if not math.isfinite(decay_rate) or decay_rate <= 0:
            raise ValueError("MEMORY_DECAY_RATE 必须大于 0")

    if key == "MEMORY_ENABLED" and value.lower() not in {"true", "false"}:
        raise ValueError("MEMORY_ENABLED 必须是 true 或 false")


def list_system_configs(db: Session) -> List[SystemConfig]:
    """获取所有系统配置"""
    stmt = select(SystemConfig)
    items = list(db.exec(stmt).all())
    default_order = {key: index for index, (key, _, _) in enumerate(DEFAULT_SYSTEM_CONFIGS)}
    default_descriptions = {key: description for key, _, description in DEFAULT_SYSTEM_CONFIGS}

    for item in items:
        if item.key in default_descriptions:
            item.description = default_descriptions[item.key]

    return sorted(items, key=lambda item: (default_order.get(item.key, len(default_order)), item.key))


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
    validate_system_config_value(key, value)

    db_config.value = value
    db_config.updated_at = local_now()
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def init_default_configs(db: Session) -> int:
    """初始化默认系统配置，返回创建的记录数"""
    count = 0
    purged_count = purge_env_managed_configs(db)
    purged_count += purge_removed_configs(db)
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


def purge_removed_configs(db: Session) -> int:
    """
    删除已经从系统中移除的历史配置。

    Args:
        db: Management 数据库会话。

    Returns:
        int: 本次删除的配置记录数量。
    """
    count = 0
    for key in REMOVED_SYSTEM_CONFIG_KEYS:
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
        "SOCIAL_PLATFORM_API_BASE_URL": env_config.social_platform_api_base_url,
        "LOG_LEVEL": env_config.log_level,
    }
    if key in env_value_map:
        return env_value_map.get(key) or default

    config = get_system_config(db, key)
    if config:
        return config.value

    fallback_map = {
        "SCHEDULER_TIME_SCALE": "1.0",
        "LANGGRAPH_MAX_STEPS": "20",
        "LANGGRAPH_MAX_CONSECUTIVE_ERRORS": "3",
        "LANGGRAPH_TOOL_TIMEOUT": "30",
        "WEB_SEARCH_ENABLED": "false",
        "TAVILY_API_KEY": "",
        "MEMORY_ENABLED": "true",
        "MEMORY_RECALL_LIMIT": "5",
        "MEMORY_RECALL_VECTOR_RESULTS": "20",
        "MEMORY_RECALL_BM25_RESULTS": "20",
        "MEMORY_RRF_RANK_CONSTANT": "60",
        "MEMORY_THRESHOLD": "0.1",
        "MEMORY_BOOST_FACTOR": "0.1",
        "MEMORY_DECAY_RATE": "0.01",
        "MEMORY_DECAY_INTERVAL_SECONDS": "300",
    }
    return fallback_map.get(key, default)
