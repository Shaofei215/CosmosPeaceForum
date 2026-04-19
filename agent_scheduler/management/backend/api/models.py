"""
Management Backend - 模型配置路由
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from agent_scheduler.management.backend.core.database import get_db
from agent_scheduler.management.backend.api.deps import get_current_admin
from agent_scheduler.management.backend.models.admin_user import AdminUser
from agent_scheduler.management.backend.schemas import (
    ModelConfigCreate, ModelConfigUpdate, ModelConfigResponse, MessageResponse
)
from agent_scheduler.management.backend.services import model_service
from agent_scheduler.management.backend.services.log_service import create_log
from agent_scheduler.management.backend.services.registrar import notify_scheduler_reload

router = APIRouter()


@router.get("/", response_model=list[ModelConfigResponse])
def list_model_configs(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取模型配置列表"""
    items = model_service.list_model_configs(db)
    return [model_service.model_config_to_response(c) for c in items]


@router.post("/", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED)
def create_model_config(
    config_in: ModelConfigCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """创建模型配置"""
    config = model_service.create_model_config(db, config_in)

    if config.is_active:
        notify_scheduler_reload("model", config.id)

    create_log(db, current_admin.id, "create_model_config", "model", config.id)

    return model_service.model_config_to_response(config)


@router.get("/{config_id}", response_model=ModelConfigResponse)
def get_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取单个模型配置详情"""
    config = model_service.get_model_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    return model_service.model_config_to_response(config)


@router.put("/{config_id}", response_model=ModelConfigResponse)
def update_model_config(
    config_id: int,
    config_in: ModelConfigUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """更新模型配置"""
    config = model_service.get_model_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    updated = model_service.update_model_config(db, config_id, config_in)

    # 通知 scheduler 热更新模型
    notify_scheduler_reload("model", config_id)

    # 记录操作日志
    create_log(db, current_admin.id, "update_model_config", "model", config_id)

    return model_service.model_config_to_response(updated)


@router.delete("/{config_id}", response_model=MessageResponse)
def delete_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """删除模型配置"""
    config = model_service.get_model_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    was_active = config.is_active
    model_service.delete_model_config(db, config_id)

    if was_active:
        notify_scheduler_reload("model")

    create_log(db, current_admin.id, "delete_model_config", "model", config_id)

    return MessageResponse(message="模型配置已删除")
