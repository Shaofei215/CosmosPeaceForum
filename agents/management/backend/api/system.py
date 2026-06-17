"""
Management Backend - 系统配置路由
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.api.deps import require_permission
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.schemas import (
    SystemConfigResponse, SystemConfigUpdate, MessageResponse
)
from agents.management.backend.services import system_service
from agents.management.backend.services.log_service import create_log
from agents.management.backend.services.permissions import PERMISSION_MANAGE_SYSTEM
from agents.management.backend.services.registrar import notify_scheduler_reload

router = APIRouter()


@router.get("/", response_model=list[SystemConfigResponse])
def list_system_configs(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_SYSTEM)),
):
    """获取系统配置列表"""
    items = system_service.list_system_configs(db)
    return items


@router.put("/{key}", response_model=SystemConfigResponse)
def update_system_config(
    key: str,
    config_in: SystemConfigUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_SYSTEM)),
):
    """更新系统配置"""
    try:
        updated = system_service.update_system_config(db, key, config_in.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail=f"配置项 '{key}' 不存在")

    # 通知 scheduler 重载系统配置
    notify_scheduler_reload("system")

    # 记录操作日志
    create_log(db, current_admin, "update_system_config", "system", details={"key": key})

    return updated


@router.post("/restart", response_model=MessageResponse)
def restart_scheduler(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_SYSTEM)),
):
    """触发 scheduler 全部重载"""
    success = notify_scheduler_reload("all")
    if not success:
        raise HTTPException(status_code=502, detail="无法连接 scheduler 服务")

    # 记录操作日志
    create_log(db, current_admin, "restart_scheduler", "system")

    return MessageResponse(message="Scheduler 重启请求已发送")
