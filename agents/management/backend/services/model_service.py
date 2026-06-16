"""
Management Backend - 模型配置服务。

模型配置允许多个同时启用，角色通过 agent_configs.model_config_id 绑定到具体模型。
"""

from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from agents.management.backend.models.agent_config import AgentConfig
from agents.management.backend.models.model_config import ModelConfig
from agents.management.backend.schemas import ModelConfigCreate, ModelConfigUpdate


def _sync_assigned_agents(db: Session, config_id: int, assigned_agent_ids: Optional[List[int]]) -> None:
    """
    同步模型与角色的完整归属集合。

    Args:
        db: 数据库会话。
        config_id: 当前模型配置 ID。
        assigned_agent_ids: 归属于当前模型的角色 ID 列表；None 表示不修改归属。
    """
    if assigned_agent_ids is None:
        return

    assigned_ids = set(assigned_agent_ids)
    now = datetime.utcnow()
    agents = db.exec(select(AgentConfig)).all()
    for agent in agents:
        should_assign = agent.id in assigned_ids
        belongs_to_model = agent.model_config_id == config_id
        if should_assign and not belongs_to_model:
            agent.model_config_id = config_id
            agent.updated_at = now
            db.add(agent)
        elif belongs_to_model and not should_assign:
            agent.model_config_id = None
            agent.updated_at = now
            db.add(agent)


def list_model_configs(db: Session) -> List[ModelConfig]:
    """获取所有模型配置"""
    stmt = select(ModelConfig).order_by(ModelConfig.id)
    return list(db.exec(stmt).all())


def get_model_config(db: Session, config_id: int) -> Optional[ModelConfig]:
    """获取单个模型配置"""
    return db.get(ModelConfig, config_id)


def create_model_config(db: Session, config_in: ModelConfigCreate) -> ModelConfig:
    """创建模型配置，并按需同步角色归属。"""
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
        color=config_in.color,
    )
    db.add(db_config)
    db.flush()

    _sync_assigned_agents(db, db_config.id, config_in.assigned_agent_ids)

    db.commit()
    db.refresh(db_config)
    return db_config


def update_model_config(db: Session, config_id: int, config_in: ModelConfigUpdate) -> Optional[ModelConfig]:
    """更新模型配置，并按需同步角色归属。"""
    db_config = db.get(ModelConfig, config_id)
    if not db_config:
        return None

    update_data = config_in.model_dump(exclude_unset=True)
    assigned_agent_ids = update_data.pop("assigned_agent_ids", None)

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

    _sync_assigned_agents(db, config_id, assigned_agent_ids)

    db.commit()
    db.refresh(db_config)
    return db_config


def delete_model_config(db: Session, config_id: int) -> bool:
    """删除模型配置，并将使用该模型的角色置为未分配。"""
    db_config = db.get(ModelConfig, config_id)
    if not db_config:
        return False
    _sync_assigned_agents(db, config_id, [])
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
        "color": config.color,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }
