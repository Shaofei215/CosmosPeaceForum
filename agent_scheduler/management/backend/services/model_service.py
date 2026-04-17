"""
Management Backend - 模型配置服务
"""

from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from agent_scheduler.management.backend.models.model_config import ModelConfig
from agent_scheduler.management.backend.core.encryption import encrypt_value, decrypt_value
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
    db_config = ModelConfig(
        name=config_in.name,
        provider=config_in.provider,
        api_key_encrypted=encrypt_value(config_in.api_key),
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
    if "api_key" in update_data and update_data["api_key"]:
        update_data["api_key_encrypted"] = encrypt_value(update_data.pop("api_key"))
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
    """获取解密后的 API Key"""
    db_config = db.get(ModelConfig, config_id)
    if not db_config:
        return None
    try:
        return decrypt_value(db_config.api_key_encrypted)
    except ValueError:
        return None


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
