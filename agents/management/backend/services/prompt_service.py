"""提示词配置服务。"""

from datetime import datetime
from agents.management.backend.core.timezone import local_now
from typing import List, Optional

from sqlmodel import Session, select

from agents.management.backend.models.prompt_config import PromptConfig
from agents.prompt_templates import (
    PROMPT_TEMPLATE_DEFINITIONS,
    get_default_prompt_template,
)


def list_prompt_configs(db: Session) -> List[PromptConfig]:
    """获取所有提示词配置，按默认定义顺序返回。"""
    items = list(db.exec(select(PromptConfig)).all())
    by_key = {item.key: item for item in items}
    default_keys = {definition.key for definition in PROMPT_TEMPLATE_DEFINITIONS}
    ordered = [
        by_key[definition.key]
        for definition in PROMPT_TEMPLATE_DEFINITIONS
        if definition.key in by_key
    ]
    ordered.extend(item for item in items if item.key not in default_keys)
    return ordered


def get_prompt_config(db: Session, key: str) -> Optional[PromptConfig]:
    """获取单个提示词配置。"""
    return db.exec(select(PromptConfig).where(PromptConfig.key == key)).first()


def update_prompt_config(db: Session, key: str, value: str) -> Optional[PromptConfig]:
    """更新提示词配置。"""
    db_config = get_prompt_config(db, key)
    if not db_config:
        return None

    db_config.value = value
    db_config.updated_at = local_now()
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def reset_prompt_config(db: Session, key: str) -> Optional[PromptConfig]:
    """恢复单个提示词配置为内置默认值。"""
    db_config = get_prompt_config(db, key)
    if not db_config:
        return None

    db_config.value = get_default_prompt_template(key)
    db_config.default_value = get_default_prompt_template(key)
    db_config.updated_at = local_now()
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def init_default_prompt_configs(db: Session) -> int:
    """初始化默认提示词配置，返回创建数量。"""
    count = 0
    changed = False
    for definition in PROMPT_TEMPLATE_DEFINITIONS:
        existing = get_prompt_config(db, definition.key)
        if not existing:
            db.add(
                PromptConfig(
                    key=definition.key,
                    name=definition.name,
                    value=definition.default_value,
                    default_value=definition.default_value,
                    description=definition.description,
                )
            )
            count += 1
            changed = True
        else:
            should_refresh_value = existing.value == existing.default_value
            next_value = definition.default_value if should_refresh_value else existing.value
            if (
                existing.name != definition.name
                or existing.description != definition.description
                or existing.default_value != definition.default_value
                or existing.value != next_value
            ):
                existing.name = definition.name
                existing.description = definition.description
                existing.value = next_value
                existing.default_value = definition.default_value
                existing.updated_at = local_now()
                db.add(existing)
                changed = True

    if changed:
        db.commit()
    return count
