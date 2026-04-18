"""
Management Backend - 模型配置服务
"""

from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from agent_scheduler.management.backend.models.model_config import ModelConfig
from agent_scheduler.management.backend.schemas import ModelConfigCreate, ModelConfigUpdate


def list_model_configs(db: Session) -> List[ModelConfig]:
    """获取所有模型配置"""
    stmt = select(ModelConfig).order_by(ModelConfig.id)
    return list(db.exec(stmt).all())


def get_model_config(db: Session, config_id: int) -> Optional[ModelConfig]:
    """获取单个模型配置"""
    return db.get(ModelConfig, config_id)


def create_model_config(db: Session, config_in: ModelConfigCreate) -> ModelConfig:
    """创建模型配置"""
    if not 0.0 <= config_in.temperature <= 2.0:
        raise ValueError("temperature 必须在 0.0 到 2.0 之间")
    if config_in.max_token < 1:
        raise ValueError("max_token 必须大于 0")

    db_config = ModelConfig(
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


def update_model_config(db: Session, config_id: int, config_in: ModelConfigUpdate) -> Optional[ModelConfig]:
    """更新模型配置"""
    db_config = db.get(ModelConfig, config_id)
    if not db_config:
        return None

    update_data = config_in.model_dump(exclude_unset=True)

    if "temperature" in update_data:
        if not 0.0 <= update_data["temperature"] <= 2.0:
            raise ValueError("temperature 必须在 0.0 到 2.0 之间")

    if "max_token" in update_data:
        if update_data["max_token"] < 1:
            raise ValueError("max_token 必须大于 0")

    update_data["updated_at"] = datetime.utcnow()

    for key, value in update_data.items():
        setattr(db_config, key, value)

    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def delete_model_config(db: Session, config_id: int) -> bool:
    """删除模型配置"""
    db_config = db.get(ModelConfig, config_id)
    if not db_config:
        return False
    db.delete(db_config)
    db.commit()
    return True


def get_api_key(db: Session, config_id: int) -> Optional[str]:
    """获取 API Key"""
    db_config = db.get(ModelConfig, config_id)
    if not db_config:
        return None
    return db_config.api_key


def model_config_to_response(config: ModelConfig) -> dict:
    """将模型配置转换为响应字典（不包含 API Key）"""
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
