"""
Management Backend - 提示词配置路由
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from agents.management.backend.api.deps import require_permission
from agents.management.backend.core.database import get_db
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.schemas import PromptConfigResponse, PromptConfigUpdate
from agents.management.backend.services import prompt_service
from agents.management.backend.services.log_service import create_log
from agents.management.backend.services.permissions import PERMISSION_MANAGE_PROMPTS

router = APIRouter()


@router.get("/", response_model=list[PromptConfigResponse])
def list_prompt_configs(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_PROMPTS)),
):
    """获取提示词配置列表"""
    return prompt_service.list_prompt_configs(db)


@router.put("/{key}", response_model=PromptConfigResponse)
def update_prompt_config(
    key: str,
    config_in: PromptConfigUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_PROMPTS)),
):
    """更新提示词配置"""
    updated = prompt_service.update_prompt_config(db, key, config_in.value)
    if not updated:
        raise HTTPException(status_code=404, detail=f"提示词配置项 '{key}' 不存在")

    create_log(db, current_admin, "update_prompt_config", "prompt", details={"key": key})
    return updated


@router.post("/{key}/reset", response_model=PromptConfigResponse)
def reset_prompt_config(
    key: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_PROMPTS)),
):
    """恢复提示词配置为默认值"""
    updated = prompt_service.reset_prompt_config(db, key)
    if not updated:
        raise HTTPException(status_code=404, detail=f"提示词配置项 '{key}' 不存在")

    create_log(db, current_admin, "reset_prompt_config", "prompt", details={"key": key})
    return updated
