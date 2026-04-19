"""
Management Backend - 系统配置服务
所有业务配置通过数据库存储，环境变量仅保留基础设施参数

配置加载优先级：
1. 数据库（主存储）
2. 代码默认值（数据库未配置时的 fallback）
"""

import os
from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from agent_scheduler.management.backend.models.system_config import SystemConfig


DEFAULT_SYSTEM_CONFIGS = [
    ("ADMIN_KEY", "", "AI 用户注册管理员密钥"),
    ("AI_USER_PASSWORD", "ai123456", "AI 用户默认密码"),
    ("API_BASE_URL", "http://localhost:8000/api/v1", "app_platform API 地址"),
    ("LOG_LEVEL", "INFO", "日志级别"),
    ("LANGGRAPH_MAX_STEPS", "20", "LangGraph 最大决策步数"),
    ("LANGGRAPH_MAX_CONSECUTIVE_ERRORS", "3", "最大连续错误次数"),
    ("LANGGRAPH_TOOL_TIMEOUT", "30", "工具调用超时时间（秒）"),
    ("LANGGRAPH_ENVIRONMENT_CACHE_TTL", "180", "环境感知缓存有效期（秒）"),
    ("MEMORY_ENABLED", "true", "是否启用记忆系统"),
    ("MEMORY_RECALL_LIMIT", "5", "召回记忆数量"),
    ("MEMORY_RECALL_VECTOR_RESULTS", "5", "向量检索返回数量"),
    ("MEMORY_RECALL_BM25_RESULTS", "5", "BM25 检索返回数量"),
    ("MEMORY_THRESHOLD", "0.3", "记忆系数最低阈值"),
    ("MEMORY_BOOST_FACTOR", "0.3", "唤醒时系数增量"),
    ("MEMORY_DECAY_RATE", "0.01", "衰减率（每日）"),
    ("EMBEDDING_BASE_URL", "", "向量化模型 Base URL"),
    ("EMBEDDING_API_KEY", "", "向量化模型 API Key"),
    ("EMBEDDING_MODEL_NAME", "text-embedding-3-small", "向量化模型名称"),
    ("EMBEDDING_DIMENSION", "1536", "向量维度"),
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
    if count > 0:
        db.commit()
    return count


def get_config_value(db: Session, key: str, default: str = "") -> str:
    """获取配置值，数据库优先，不存在则 fallback 到代码默认值"""
    config = get_system_config(db, key)
    if config:
        return config.value

    fallback_map = {
        "ADMIN_KEY": "",
        "AI_USER_PASSWORD": "ai123456",
        "API_BASE_URL": "http://localhost:8000/api/v1",
        "LOG_LEVEL": "INFO",
        "LANGGRAPH_MAX_STEPS": "20",
        "LANGGRAPH_MAX_CONSECUTIVE_ERRORS": "3",
        "LANGGRAPH_TOOL_TIMEOUT": "30",
        "LANGGRAPH_ENVIRONMENT_CACHE_TTL": "180",
        "MEMORY_ENABLED": "true",
        "MEMORY_RECALL_LIMIT": "5",
        "MEMORY_RECALL_VECTOR_RESULTS": "5",
        "MEMORY_RECALL_BM25_RESULTS": "5",
        "MEMORY_THRESHOLD": "0.3",
        "MEMORY_BOOST_FACTOR": "0.3",
        "MEMORY_DECAY_RATE": "0.01",
        "EMBEDDING_BASE_URL": "",
        "EMBEDDING_API_KEY": "",
        "EMBEDDING_MODEL_NAME": "text-embedding-3-small",
        "EMBEDDING_DIMENSION": "1536",
    }
    return fallback_map.get(key, default)
