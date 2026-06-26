"""
Management Backend - Embedding 配置服务
全局只允许一个 Embedding 配置。
"""

from datetime import datetime
from agents.management.backend.core.timezone import local_now
from typing import Optional

from sqlmodel import Session, select

from agents.management.backend.models.embedding_config import EmbeddingConfig
from agents.management.backend.schemas import EmbeddingConfigCreate, EmbeddingConfigUpdate


def get_embedding_config(db: Session) -> Optional[EmbeddingConfig]:
    """获取 Embedding 配置（全局唯一）"""
    stmt = select(EmbeddingConfig).limit(1)
    return db.exec(stmt).first()


def create_embedding_config(db: Session, config_in: EmbeddingConfigCreate) -> EmbeddingConfig:
    """创建 Embedding 配置"""
    if config_in.dimension < 1:
        raise ValueError("dimension 必须大于 0")

    db_config = EmbeddingConfig(
        base_url=config_in.base_url,
        api_key=config_in.api_key,
        model_name=config_in.model_name,
        dimension=config_in.dimension,
        is_active=config_in.is_active,
    )
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def update_embedding_config(db: Session, config_in: EmbeddingConfigUpdate) -> Optional[EmbeddingConfig]:
    """更新 Embedding 配置"""
    db_config = get_embedding_config(db)
    if not db_config:
        return None

    update_data = config_in.model_dump(exclude_unset=True)

    if "dimension" in update_data:
        if update_data["dimension"] < 1:
            raise ValueError("dimension 必须大于 0")

    update_data["updated_at"] = local_now()

    for key, value in update_data.items():
        setattr(db_config, key, value)

    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def init_default_embedding_config(db: Session) -> Optional[EmbeddingConfig]:
    """初始化默认 Embedding 配置（若不存在）"""
    existing = get_embedding_config(db)
    if existing:
        return existing

    default = EmbeddingConfig(
        base_url="",
        api_key="",
        model_name="",
        dimension=1536,
        is_active=False,
    )
    db.add(default)
    db.commit()
    db.refresh(default)
    return default


def embedding_config_to_response(config: EmbeddingConfig) -> dict:
    """将 Embedding 配置转换为响应字典"""
    model_name = config.model_name
    if (
        model_name == "text-embedding-3-small"
        and not config.is_active
        and not config.api_key
        and not config.base_url
    ):
        model_name = ""

    return {
        "id": config.id,
        "base_url": config.base_url,
        "api_key": config.api_key,
        "model_name": model_name,
        "dimension": config.dimension,
        "is_active": config.is_active,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }
