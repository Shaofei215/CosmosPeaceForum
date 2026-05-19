"""
Management Backend - Embedding 配置路由
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.api.deps import require_permission
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.schemas import (
    EmbeddingConfigCreate, EmbeddingConfigUpdate, EmbeddingConfigResponse, MessageResponse
)
from agents.management.backend.services import embedding_service
from agents.management.backend.services.log_service import create_log
from agents.management.backend.services.permissions import PERMISSION_MANAGE_MODELS
from agents.management.backend.services.registrar import notify_scheduler_reload

router = APIRouter()


@router.get("/", response_model=EmbeddingConfigResponse)
def get_embedding_config(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_MODELS)),
):
    """获取 Embedding 配置"""
    config = embedding_service.get_embedding_config(db)
    if not config:
        config = embedding_service.init_default_embedding_config(db)
    return embedding_service.embedding_config_to_response(config)


@router.post("/", response_model=EmbeddingConfigResponse)
def create_embedding_config(
    config_in: EmbeddingConfigCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_MODELS)),
):
    """创建 Embedding 配置"""
    config = embedding_service.create_embedding_config(db, config_in)
    notify_scheduler_reload("system")
    create_log(db, current_admin, "create_embedding_config", "embedding", config.id)
    return embedding_service.embedding_config_to_response(config)


@router.put("/", response_model=EmbeddingConfigResponse)
def update_embedding_config(
    config_in: EmbeddingConfigUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_MODELS)),
):
    """更新 Embedding 配置"""
    updated = embedding_service.update_embedding_config(db, config_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Embedding 配置不存在，请先创建")

    notify_scheduler_reload("system")
    create_log(db, current_admin, "update_embedding_config", "embedding", updated.id)
    return embedding_service.embedding_config_to_response(updated)
