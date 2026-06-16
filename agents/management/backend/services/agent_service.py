"""
Management Backend - Agent 配置服务
"""

import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from agents.management.backend.models.agent_config import AgentConfig
from agents.management.backend.schemas import AgentCreate, AgentUpdate

logger = logging.getLogger(__name__)


def list_agents(db: Session, skip: int = 0, limit: int = 100) -> tuple[List[AgentConfig], int]:
    """获取 Agent 列表"""
    count_stmt = select(AgentConfig)
    total = len(db.exec(count_stmt).all())

    stmt = select(AgentConfig).offset(skip).limit(limit).order_by(AgentConfig.id)
    items = db.exec(stmt).all()
    return list(items), total


def get_agent(db: Session, agent_id: int) -> Optional[AgentConfig]:
    """获取单个 Agent"""
    return db.get(AgentConfig, agent_id)


def get_agent_by_username(db: Session, username: str) -> Optional[AgentConfig]:
    """根据用户名获取 Agent"""
    stmt = select(AgentConfig).where(AgentConfig.username == username)
    return db.exec(stmt).first()


def create_agent(db: Session, agent_in: AgentCreate) -> AgentConfig:
    """创建 Agent"""
    db_agent = AgentConfig(
        name=agent_in.name,
        username=agent_in.username,
        monthly_logins=agent_in.monthly_logins,
        personal_signature=agent_in.personal_signature,
        personality_prompt=agent_in.personality_prompt,
        is_active=agent_in.is_active,
        model_config_id=agent_in.model_config_id,
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent


def update_agent(db: Session, agent_id: int, agent_in: AgentUpdate) -> Optional[AgentConfig]:
    """更新 Agent"""
    db_agent = db.get(AgentConfig, agent_id)
    if not db_agent:
        return None

    update_data = agent_in.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()

    for key, value in update_data.items():
        setattr(db_agent, key, value)

    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent


def update_agent_last_login(db: Session, agent_id: int, login_at: Optional[datetime] = None) -> bool:
    """记录 Agent 最近一次成功登录时间。"""
    db_agent = db.get(AgentConfig, agent_id)
    if not db_agent:
        return False

    db_agent.last_login_at = login_at or datetime.utcnow()
    db_agent.total_login_count = (db_agent.total_login_count or 0) + 1
    db_agent.updated_at = datetime.utcnow()
    db.add(db_agent)
    db.commit()
    return True


def delete_agent(db: Session, agent_id: int) -> bool:
    """删除 Agent"""
    db_agent = db.get(AgentConfig, agent_id)
    if not db_agent:
        return False
    db.delete(db_agent)
    db.commit()
    return True


def parse_knows_ids(agent: AgentConfig) -> List[int]:
    """解析 knows_ids 字段"""
    if not agent.knows_ids:
        return []
    try:
        return json.loads(agent.knows_ids)
    except (json.JSONDecodeError, TypeError):
        return []


def update_agent_knows(db: Session, agent_id: int, knows_ids: List[int], bidirectional: bool = False) -> Optional[AgentConfig]:
    """更新 Agent 的相识关系"""
    db_agent = db.get(AgentConfig, agent_id)
    if not db_agent:
        return None

    db_agent.knows_ids = json.dumps(knows_ids)
    db_agent.updated_at = datetime.utcnow()
    db.add(db_agent)

    if bidirectional:
        all_agents = db.exec(select(AgentConfig)).all()
        for other in all_agents:
            if other.id == agent_id:
                continue

            other_knows = parse_knows_ids(other)
            should_have_relation = other.id in knows_ids
            has_relation = agent_id in other_knows

            if should_have_relation and not has_relation:
                other_knows.append(agent_id)
                other.knows_ids = json.dumps(other_knows)
                other.updated_at = datetime.utcnow()
                db.add(other)
            elif not should_have_relation and has_relation:
                other_knows.remove(agent_id)
                other.knows_ids = json.dumps(other_knows)
                other.updated_at = datetime.utcnow()
                db.add(other)

    db.commit()
    db.refresh(db_agent)
    return db_agent


def agent_to_response(agent: AgentConfig) -> dict:
    """将 Agent 配置转换为响应字典"""
    return {
        "id": agent.id,
        "name": agent.name,
        "username": agent.username,
        "monthly_logins": agent.monthly_logins,
        "personal_signature": agent.personal_signature,
        "personality_prompt": agent.personality_prompt,
        "knows_ids": parse_knows_ids(agent),
        "is_active": agent.is_active,
        "model_config_id": agent.model_config_id,
        "app_platform_user_id": agent.app_platform_user_id,
        "last_login_at": agent.last_login_at,
        "last_login_timestamp": agent.last_login_timestamp,
        "total_login_count": agent.total_login_count,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }


def import_agents_from_zip(db: Session, zip_path: str) -> List[AgentConfig]:
    """
    从压缩包批量导入 Agent
    压缩包需包含 ai_users_config.json 和可选的 avatar/ 目录
    """
    imported = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # 查找 JSON 配置文件
        json_name = None
        for name in zf.namelist():
            if name.endswith('.json') and 'ai_users_config' in name.lower():
                json_name = name
                break

        if not json_name:
            raise ValueError("压缩包中未找到 ai_users_config.json")

        # 读取并解析 JSON
        with zf.open(json_name) as f:
            import json as _json
            config_data = _json.load(f)

        ai_users = config_data.get('ai_users', [])
        for user_data in ai_users:
            # 检查是否已存在
            username = user_data.get('username', '')
            existing = get_agent_by_username(db, username)
            if existing:
                logger.info("导入: 跳过已存在的用户: %s", username)
                continue

            agent_in = AgentCreate(
                name=user_data.get('name', ''),
                username=username,
                monthly_logins=user_data.get('monthly_logins', 30),
                personal_signature=user_data.get('personal_signature', ''),
                personality_prompt=user_data.get('personality_prompt', ''),
            )
            agent = create_agent(db, agent_in)
            imported.append(agent)

    return imported
