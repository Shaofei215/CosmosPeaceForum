"""
Management Backend - FastAPI 应用主入口
管理端后端服务，端口 8001
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agents.management.backend.core.config import get_config
from agents.management.backend.core.database import init_db
from agents.management.backend.api import api_router
from agents.management.backend.services.init_data import initialize_database
from agents.management.backend.services.terminal_log_service import terminal_log_capture
from agents.external_access import router as external_access_router

logger = logging.getLogger(__name__)


def get_frontend_dist_dir() -> Path:
    """Return the management frontend production build directory."""
    return Path(__file__).resolve().parents[1] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    config = get_config()
    numeric_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    terminal_log_capture.start()
    logger.info("=" * 50)
    logger.info("Management Backend 启动中...")
    logger.info("=" * 50)
    logger.info("数据库路径: %s", config.get_db_path())
    logger.info("服务器: %s:%d", config.server_host, config.server_port)
    logger.info("Scheduler 内部接口: %s", config.scheduler_internal_base_url)

    init_db()
    initialize_database()

    logger.info("Management Backend 启动完成!")
    logger.info("=" * 50)

    yield

    logger.info("Management Backend 关闭中...")
    terminal_log_capture.stop()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    config = get_config()

    app = FastAPI(
        title="Agent Management Backend",
        description="AI Agent 管理系统后端 API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(api_router, prefix="/api")
    app.include_router(external_access_router, prefix="/external/v1", tags=["external-access"])

    frontend_dist = get_frontend_dist_dir()
    assets_dir = frontend_dist / "assets"
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="management-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_management_frontend(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")

            requested_file = frontend_dist / full_path
            if requested_file.is_file():
                return FileResponse(requested_file)

            return FileResponse(index_file)

    return app


app = create_app()
