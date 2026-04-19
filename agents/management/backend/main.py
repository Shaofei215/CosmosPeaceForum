"""
Management Backend - FastAPI 应用主入口
管理端后端服务，端口 8001
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.management.backend.core.config import get_config
from agents.management.backend.core.database import init_db
from agents.management.backend.api import api_router
from agents.management.backend.services.init_data import initialize_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    config = get_config()
    logger.info("=" * 50)
    logger.info("Management Backend 启动中...")
    logger.info("=" * 50)
    logger.info("数据库路径: %s", config.get_db_path())
    logger.info("服务器: %s:%d", config.server_host, config.server_port)
    logger.info("Scheduler 内部端口: %d", config.scheduler_internal_port)

    # 初始化数据库
    init_db()

    # 初始化默认数据
    initialize_database()

    logger.info("Management Backend 启动完成!")
    logger.info("=" * 50)

    yield

    # 关闭时
    logger.info("Management Backend 关闭中...")


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

    return app


app = create_app()
