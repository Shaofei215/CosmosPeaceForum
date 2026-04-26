"""
Management Backend - 分块模型配置服务
"""

from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from agents.management.backend.models.chunk_model_config import ChunkModelConfig
from agents.management.backend.schemas import ChunkModelConfigCreate, ChunkModelConfigUpdate


def list_chunk_model_configs(db: Session) -> List[ChunkModelConfig]:
    """获取分块模型配置列表"""
    stmt = select(ChunkModelConfig).order_by(ChunkModelConfig.id)
    return list(db.exec(stmt).all())


def get_chunk_model_config(db: Session, config_id: int) -> Optional[ChunkModelConfig]:
    """获取单个分块模型配置"""
    return db.get(ChunkModelConfig, config_id)


def create_chunk_model_config(db: Session, config_in: ChunkModelConfigCreate) -> ChunkModelConfig:
    """创建分块模型配置"""
    db_config = ChunkModelConfig(
        name=config_in.name,
        provider=config_in.provider,
        api_key=config_in.api_key,
        base_url=config_in.base_url,
        model_name=config_in.model_name,
        temperature=config_in.temperature,
        is_active=config_in.is_active,
        max_token=config_in.max_token,
    )
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def update_chunk_model_config(
    db: Session, config_id: int, config_in: ChunkModelConfigUpdate
) -> Optional[ChunkModelConfig]:
    """更新分块模型配置"""
    db_config = get_chunk_model_config(db, config_id)
    if not db_config:
        return None

    update_data = config_in.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()

    for key, value in update_data.items():
        setattr(db_config, key, value)

    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def delete_chunk_model_config(db: Session, config_id: int) -> bool:
    """删除分块模型配置"""
    db_config = get_chunk_model_config(db, config_id)
    if not db_config:
        return False

    db.delete(db_config)
    db.commit()
    return True


def toggle_chunk_model_config(db: Session, config_id: int) -> Optional[ChunkModelConfig]:
    """切换分块模型启用/停用状态"""
    db_config = get_chunk_model_config(db, config_id)
    if not db_config:
        return None

    db_config.is_active = not db_config.is_active
    db_config.updated_at = datetime.utcnow()
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def get_active_chunk_model_config(db: Session) -> Optional[ChunkModelConfig]:
    """获取当前启用的分块模型配置"""
    stmt = select(ChunkModelConfig).where(ChunkModelConfig.is_active == True).limit(1)
    return db.exec(stmt).first()


def chunk_model_config_to_response(config: ChunkModelConfig) -> dict:
    """将分块模型配置转换为响应字典"""
    return {
        "id": config.id,
        "name": config.name,
        "provider": config.provider,
        "base_url": config.base_url,
        "model_name": config.model_name,
        "temperature": config.temperature,
        "is_active": config.is_active,
        "max_token": config.max_token,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }
