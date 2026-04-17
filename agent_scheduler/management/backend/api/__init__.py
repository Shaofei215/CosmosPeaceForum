"""
Management Backend - API 路由模块
"""

from fastapi import APIRouter

from agent_scheduler.management.backend.api.auth import router as auth_router
from agent_scheduler.management.backend.api.agents import router as agents_router
from agent_scheduler.management.backend.api.models import router as models_router
from agent_scheduler.management.backend.api.system import router as system_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(agents_router, prefix="/agents", tags=["Agent管理"])
api_router.include_router(models_router, prefix="/models", tags=["模型配置"])
api_router.include_router(system_router, prefix="/system", tags=["系统配置"])

__all__ = ["api_router"]
