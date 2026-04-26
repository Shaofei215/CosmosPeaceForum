"""
Management Backend - API 路由模块
"""

from fastapi import APIRouter

from agents.management.backend.api.auth import router as auth_router
from agents.management.backend.api.agents import router as agents_router
from agents.management.backend.api.models import router as models_router
from agents.management.backend.api.system import router as system_router
from agents.management.backend.api.logs import router as logs_router
from agents.management.backend.api.embeddings import router as embeddings_router
from agents.management.backend.api.chunk_models import router as chunk_models_router
from agents.management.backend.api.memories import router as memories_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(agents_router, prefix="/agents", tags=["Agent管理"])
api_router.include_router(models_router, prefix="/models", tags=["模型配置"])
api_router.include_router(chunk_models_router, prefix="/chunk-models", tags=["分块模型配置"])
api_router.include_router(system_router, prefix="/system", tags=["系统配置"])
api_router.include_router(logs_router, prefix="/logs", tags=["操作日志"])
api_router.include_router(embeddings_router, prefix="/embeddings", tags=["Embedding配置"])
api_router.include_router(memories_router, prefix="/memories", tags=["记忆管理"])

__all__ = ["api_router"]
