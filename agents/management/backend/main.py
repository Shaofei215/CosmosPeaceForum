"""
Management Backend - FastAPI 应用主入口
管理端后端服务，端口 8001
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from contextlib import suppress
from html import escape
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from agents.management.backend.core.config import get_config
from agents.logging_config import AccessLogMiddleware, SERVICE_NAME, configure_logging
from agents.management.backend.core.database import init_db
from agents.management.backend.api import api_router
from agents.management.backend.services.init_data import initialize_database
from agents.management.backend.services.log_service import cleanup_expired_logs
from agents.management.backend.services.terminal_log_service import terminal_log_capture
from agents.external_access import router as external_access_router

logger = logging.getLogger(__name__)

PLATFORM_DISPLAY_NAME_PLACEHOLDER = "__PLATFORM_DISPLAY_NAME__"


def cleanup_management_audit_logs() -> None:
    """使用独立数据库会话清理超过保留期限的 Management 审计日志。"""

    from agents.management.backend.core.database import get_session_local

    config = get_config()
    with get_session_local()() as db:
        deleted = cleanup_expired_logs(db, config.log_retention_days)
    logger.info(
        "Management 审计日志清理完成: deleted=%d retention_days=%d",
        deleted,
        config.log_retention_days,
        extra={"event": "audit.retention_cleanup", "component": "management"},
    )


async def audit_cleanup_loop() -> None:
    """每 24 小时执行一次 Management 审计日志清理。"""

    while True:
        await asyncio.sleep(24 * 60 * 60)
        try:
            await asyncio.to_thread(cleanup_management_audit_logs)
        except Exception:
            logger.exception("Management 审计日志清理失败")


def get_frontend_dist_dir() -> Path:
    """Return the management frontend production build directory."""
    return Path(__file__).resolve().parents[1] / "frontend" / "dist"


def resolve_frontend_path(frontend_dist: Path, full_path: str) -> Path:
    """解析并校验管理前端请求对应的本地文件路径。

    路由参数可能已经由 ASGI 服务器完成百分号解码，因此必须在拼接后解析
    ``..`` 与符号链接，并确认最终路径仍位于前端构建目录中。

    Args:
        frontend_dist: 管理前端构建产物的根目录。
        full_path: 浏览器请求的前端相对路径。

    Returns:
        Path: 已解析且确认位于构建目录内的路径。

    Raises:
        HTTPException: 请求路径逃逸出前端构建目录时抛出 404。
    """

    frontend_root = frontend_dist.resolve()
    requested_path = (frontend_root / full_path).resolve()
    try:
        requested_path.relative_to(frontend_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not Found") from exc
    return requested_path


def render_management_index(index_file: Path, platform_display_name: str) -> str:
    """将平台展示名称注入管理前端入口页面。

    管理前端在构建产物中保留占位符，管理后端启动后从 ``agents/.env``
    加载展示名称，并在返回页面时完成 HTML 转义与替换。

    Args:
        index_file: 管理前端构建产物中的 ``index.html`` 路径。
        platform_display_name: 从管理后端配置读取的平台展示名称。

    Returns:
        str: 已注入并完成 HTML 转义的入口页面内容。

    Raises:
        OSError: 读取入口页面失败时抛出。
        UnicodeError: 入口页面不是有效 UTF-8 文本时抛出。
    """
    html = index_file.read_text(encoding="utf-8")
    escaped_display_name = escape(platform_display_name, quote=True)
    return html.replace(PLATFORM_DISPLAY_NAME_PLACEHOLDER, escaped_display_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    config = get_config()
    numeric_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    terminal_log_capture.start()
    logger.info("管理器启动中...")
    logger.info("数据库路径: %s", config.get_db_path())
    logger.info("服务器: %s:%d", config.server_host, config.server_port)
    logger.info("Scheduler 内部接口: %s", config.scheduler_internal_base_url)

    init_db()
    initialize_database()
    try:
        await asyncio.to_thread(cleanup_management_audit_logs)
    except Exception:
        logger.exception("Management 启动时审计日志清理失败")
    audit_cleanup_task = asyncio.create_task(audit_cleanup_loop())

    logger.info("管理器启动完成!")
    logger.info("=" * 50)

    yield

    logger.info("管理器关闭中...")
    audit_cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await audit_cleanup_task
    terminal_log_capture.stop()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    config = get_config()
    if getattr(logging.getLogger(), "_cpf_logging_service", None) != SERVICE_NAME:
        configure_logging(
            level=config.log_level,
            log_dir=config.log_dir,
            retention_days=config.log_retention_days,
            segment_max_mb=config.log_segment_max_mb,
            max_total_mb=config.log_max_total_mb,
        )

    app = FastAPI(
        title="Agent Management Backend",
        description="管理器后端 API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        # 管理端通过 Authorization Bearer Token 认证，不依赖跨域 Cookie。
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        AccessLogMiddleware,
        api_prefixes=("/api", "/external/v1"),
        health_paths=("/external/v1/health",),
    )

    # 注册路由
    app.include_router(api_router, prefix="/api")
    app.include_router(external_access_router, prefix="/external/v1", tags=["external-access"])

    frontend_dist = get_frontend_dist_dir().resolve()
    assets_dir = frontend_dist / "assets"
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="management-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_management_frontend(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")

            requested_file = resolve_frontend_path(frontend_dist, full_path)
            if requested_file.is_file() and requested_file != index_file:
                return FileResponse(requested_file)

            html = render_management_index(index_file, config.platform_display_name)
            return HTMLResponse(html)

    return app


app = create_app()
