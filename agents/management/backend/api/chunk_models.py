"""
Management Backend - 分块模型配置路由
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.api.deps import require_permission
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.schemas import (
    ChunkModelConfigCreate, ChunkModelConfigUpdate, ChunkModelConfigResponse, MessageResponse
)
from agents.management.backend.services import chunk_model_service
from agents.management.backend.services.log_service import create_log
from agents.management.backend.services.permissions import PERMISSION_MANAGE_MODELS

router = APIRouter()


@router.get("/", response_model=list[ChunkModelConfigResponse])
def list_chunk_model_configs(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_MODELS)),
):
    """获取分块模型配置列表"""
    items = chunk_model_service.list_chunk_model_configs(db)
    return [chunk_model_service.chunk_model_config_to_response(c) for c in items]


@router.post("/", response_model=ChunkModelConfigResponse, status_code=status.HTTP_201_CREATED)
def create_chunk_model_config(
    config_in: ChunkModelConfigCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_MODELS)),
):
    """创建分块模型配置"""
    config = chunk_model_service.create_chunk_model_config(db, config_in)
    create_log(db, current_admin, "create_chunk_model_config", "chunk_model", config.id)
    return chunk_model_service.chunk_model_config_to_response(config)


@router.get("/{config_id}", response_model=ChunkModelConfigResponse)
def get_chunk_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_MODELS)),
):
    """获取单个分块模型配置详情"""
    config = chunk_model_service.get_chunk_model_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="分块模型配置不存在")
    return chunk_model_service.chunk_model_config_to_response(config)


@router.put("/{config_id}", response_model=ChunkModelConfigResponse)
def update_chunk_model_config(
    config_id: int,
    config_in: ChunkModelConfigUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_MODELS)),
):
    """更新分块模型配置"""
    config = chunk_model_service.get_chunk_model_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="分块模型配置不存在")

    updated = chunk_model_service.update_chunk_model_config(db, config_id, config_in)
    create_log(db, current_admin, "update_chunk_model_config", "chunk_model", config_id)
    return chunk_model_service.chunk_model_config_to_response(updated)


@router.delete("/{config_id}", response_model=MessageResponse)
def delete_chunk_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_MODELS)),
):
    """删除分块模型配置"""
    config = chunk_model_service.get_chunk_model_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="分块模型配置不存在")

    chunk_model_service.delete_chunk_model_config(db, config_id)
    create_log(db, current_admin, "delete_chunk_model_config", "chunk_model", config_id)
    return MessageResponse(message="分块模型配置已删除")


@router.put("/{config_id}/toggle", response_model=ChunkModelConfigResponse)
def toggle_chunk_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_MODELS)),
):
    """切换分块模型启用/停用状态"""
    config = chunk_model_service.get_chunk_model_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="分块模型配置不存在")

    updated = chunk_model_service.toggle_chunk_model_config(db, config_id)
    create_log(db, current_admin, "toggle_chunk_model_config", "chunk_model", config_id)
    return chunk_model_service.chunk_model_config_to_response(updated)
