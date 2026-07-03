# 应用主入口
# 初始化 FastAPI 应用，注册路由和中间件
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler

from social_platform.app.core.branding import get_platform_display_name
from social_platform.app.core.config import get_settings
from social_platform.app.core.paths import get_avatar_upload_dir, get_frontend_dist_dir
from social_platform.app.core.static_files import RaceSafeStaticFiles, SPAStaticFiles
from social_platform.app.db.session import SessionLocal
from social_platform.app.domains.bootstrap import ensure_domain_event_handlers_registered
from social_platform.app.admin.api import admin_router
from social_platform.app.admin.services.auth_service import ensure_initial_admin
from social_platform.app.admin.services.terminal_log_service import terminal_log_capture

from social_platform.app.api.routers import (
    users,
    posts,
    feeds,
    like,
    comment,
    auth,
    avatar,
    follow,
    notifications,
    search,
    hot_topics,
    topics,
    reports,
    external_agent_skill,
)


settings = get_settings()

# 创建定时任务调度器
scheduler = BackgroundScheduler()


def start_scheduler():
    """
    启动定时任务调度器

    定期清理过期的验证码记录，防止数据库膨胀
    - 每6小时执行一次
    """
    from social_platform.app.domains.heat.application import refresh_all_heat_scores
    from social_platform.app.domains.hot_topic.application import register_hot_topic_scheduler
    from social_platform.app.tasks import cleanup_expired_verification_codes

    scheduler.add_job(
        cleanup_expired_verification_codes,
        'interval',
        hours=6,
        id='cleanup_expired_codes',
        replace_existing=True
    )
    scheduler.add_job(
        refresh_all_heat_scores,
        'interval',
        minutes=5,
        id='refresh_heat_scores',
        replace_existing=True
    )
    register_hot_topic_scheduler(scheduler)
    # 启动时先刷新一次，避免旧数据在首次定时任务前全部以 0 分参与推荐排序。
    scheduler.start()
    refresh_all_heat_scores()
    print("[启动] 验证码清理任务调度器已启动（每6小时执行），热度分数任务已启动（每5分钟执行）")


def ensure_search_indexes():
    """
    启动时确保平台搜索索引存在；索引是运行期投影，可由数据库重建。
    """
    from social_platform.app.domains.search.application import ensure_search_indexes as ensure_indexes

    db = SessionLocal()
    try:
        ensure_indexes(db)
    finally:
        db.close()


def ensure_topic_projection():
    """启动时为历史帖子补齐话题投影。"""
    from social_platform.app.domains.topic.application import ensure_topic_projection as ensure_topics

    db = SessionLocal()
    try:
        ensure_topics(db)
    finally:
        db.close()


def initialize_admin_manager():
    """初始化公开平台管理器运行时数据。"""
    db = SessionLocal()
    try:
        ensure_initial_admin(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    在应用启动时启动调度器，关闭时停止调度器
    """
    # 启动时完成部署级 Skill 渲染和配置校验；后续下载直接复用进程内缓存。
    external_agent_skill.get_runtime_skill_package()
    ensure_domain_event_handlers_registered()
    terminal_log_capture.start()
    initialize_admin_manager()
    start_scheduler()
    ensure_search_indexes()
    ensure_topic_projection()
    yield
    scheduler.shutdown()
    terminal_log_capture.stop()
    print("[关闭] 调度器已关闭")


# 创建 FastAPI 应用实例
app = FastAPI(
    # 应用标题
    title=settings.PROJECT_NAME,
    # 应用版本
    version=settings.VERSION,
    # OpenAPI 文档路径
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    # 生命周期管理
    lifespan=lifespan
)

# 配置跨域中间件（CORS）
# 允许所有来源访问，开发阶段使用，生产环境需要限制。
# 当前认证使用 Authorization Bearer Token，不需要跨域 Cookie 凭证。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=False,  # 通配来源不能与凭证模式同时启用
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有 HTTP 头
)

if settings.AVATAR_STORAGE_STRATEGY == "local":
    # 创建头像上传目录（如果不存在）
    avatar_dir = get_avatar_upload_dir()
    os.makedirs(avatar_dir, exist_ok=True)

    # 挂载静态文件服务器，提供头像访问
    # 访问URL: /uploads/avatars/avatar_1_xxx.jpg
    # 实际目录: social_platform/uploads/avatars/
    app.mount("/uploads", RaceSafeStaticFiles(directory=os.path.dirname(avatar_dir)), name="uploads")

# 注册路由
# 将各个模块的路由器注册到应用中
app.include_router(external_agent_skill.router)
app.include_router(avatar.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["avatar"])
app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["users"])
app.include_router(posts.router, prefix=f"{settings.API_V1_PREFIX}/posts", tags=["posts"])
app.include_router(feeds.router, prefix=f"{settings.API_V1_PREFIX}/feeds", tags=["feeds"])
app.include_router(like.router, prefix=f"{settings.API_V1_PREFIX}/posts", tags=["likes"])
app.include_router(comment.router, prefix=f"{settings.API_V1_PREFIX}/posts", tags=["comments"])
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])
app.include_router(follow.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["follows"])
app.include_router(notifications.router, prefix=f"{settings.API_V1_PREFIX}/notifications", tags=["notifications"])
app.include_router(search.router, prefix=f"{settings.API_V1_PREFIX}/search", tags=["search"])
app.include_router(hot_topics.router, prefix=f"{settings.API_V1_PREFIX}/hot-topics", tags=["hot-topics"])
app.include_router(topics.router, prefix=f"{settings.API_V1_PREFIX}/topics", tags=["topics"])
app.include_router(reports.router, prefix=f"{settings.API_V1_PREFIX}/reports", tags=["reports"])
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root():
    """
    根路径接口

    Returns:
        应用基本信息和文档链接
    """
    frontend_index = os.path.join(get_frontend_dist_dir(), "index.html")
    if os.path.exists(frontend_index):
        return FileResponse(frontend_index)

    return {
        "message": f"Welcome to {get_platform_display_name()} Social Platform",
        "version": settings.VERSION,
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """
    健康检查接口

    Returns:
        应用健康状态
    """
    return {"status": "healthy"}


frontend_dist_dir = get_frontend_dist_dir()
if os.path.isdir(frontend_dist_dir):
    app.mount("/", SPAStaticFiles(directory=frontend_dist_dir, html=True), name="frontend")
