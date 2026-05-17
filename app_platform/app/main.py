# 应用主入口
# 初始化 FastAPI 应用，注册路由和中间件
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import inspect, text

from app_platform.app.core.config import get_settings
from app_platform.app.core.paths import get_avatar_upload_dir
from app_platform.app.core.static_files import RaceSafeStaticFiles
from app_platform.app.db.session import engine, Base, SessionLocal

# 导入所有模型以确保 SQLAlchemy 正确注册关系
# 必须在创建表之前导入所有模型
from app_platform.app.models import User, Post, Like, Comment, CommentLike, Follow, Notification

from app_platform.app.api.routers import users, posts, feeds, like, comment, auth, avatar, follow, notifications, search


settings = get_settings()

# 创建数据库表
# Base.metadata.create_all 会根据模型定义自动创建所有表
Base.metadata.create_all(bind=engine)


def ensure_runtime_schema():
    # 项目当前没有正式迁移系统，新增运行期字段沿用启动时补列策略。
    inspector = inspect(engine)
    if "posts" not in inspector.get_table_names():
        return

    post_columns = {column["name"] for column in inspector.get_columns("posts")}
    statements = []
    if "repost_count" not in post_columns:
        statements.append("ALTER TABLE posts ADD COLUMN repost_count INTEGER NOT NULL DEFAULT 0")
    if "repost_source_type" not in post_columns:
        statements.append("ALTER TABLE posts ADD COLUMN repost_source_type VARCHAR(20)")
    if "repost_source_id" not in post_columns:
        statements.append("ALTER TABLE posts ADD COLUMN repost_source_id INTEGER")
    if "repost_root_post_id" not in post_columns:
        statements.append("ALTER TABLE posts ADD COLUMN repost_root_post_id INTEGER")
    if "repost_chain" not in post_columns:
        statements.append("ALTER TABLE posts ADD COLUMN repost_chain TEXT")
    if "type" not in post_columns:
        statements.append("ALTER TABLE posts ADD COLUMN type VARCHAR(20) NOT NULL DEFAULT 'post'")
    if "heat_score" not in post_columns:
        statements.append("ALTER TABLE posts ADD COLUMN heat_score FLOAT NOT NULL DEFAULT 0")
    if "heat_score_updated_at" not in post_columns:
        statements.append("ALTER TABLE posts ADD COLUMN heat_score_updated_at DATETIME")

    if "comments" in inspector.get_table_names():
        comment_columns = {column["name"] for column in inspector.get_columns("comments")}
        if "heat_score" not in comment_columns:
            statements.append("ALTER TABLE comments ADD COLUMN heat_score FLOAT NOT NULL DEFAULT 0")
        if "heat_score_updated_at" not in comment_columns:
            statements.append("ALTER TABLE comments ADD COLUMN heat_score_updated_at DATETIME")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


ensure_runtime_schema()

# 创建定时任务调度器
scheduler = BackgroundScheduler()


def start_scheduler():
    """
    启动定时任务调度器

    定期清理过期的验证码记录，防止数据库膨胀
    - 每6小时执行一次
    """
    from app_platform.app.services.heat_service import refresh_all_heat_scores
    from app_platform.app.tasks import cleanup_expired_verification_codes

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
    # 启动时先刷新一次，避免旧数据在首次定时任务前全部以 0 分参与推荐排序。
    scheduler.start()
    refresh_all_heat_scores()
    print("[启动] 验证码清理任务调度器已启动（每6小时执行），热度分数任务已启动（每5分钟执行）")


def ensure_search_indexes():
    """
    启动时确保平台搜索索引存在；索引是运行期投影，可由数据库重建。
    """
    from app_platform.app.services.search_service import ensure_search_indexes as ensure_indexes

    db = SessionLocal()
    try:
        ensure_indexes(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    在应用启动时启动调度器，关闭时停止调度器
    """
    start_scheduler()
    ensure_search_indexes()
    yield
    scheduler.shutdown()
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
# 允许所有来源访问，开发阶段使用，生产环境需要限制
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,  # 允许携带凭证
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有 HTTP 头
)

# 创建头像上传目录（如果不存在）
avatar_dir = get_avatar_upload_dir()
os.makedirs(avatar_dir, exist_ok=True)

# 挂载静态文件服务器，提供头像访问
# 访问URL: /uploads/avatars/avatar_1_xxx.jpg
# 实际目录: app_platform/uploads/avatars/
app.mount("/uploads", RaceSafeStaticFiles(directory=os.path.dirname(avatar_dir)), name="uploads")

# 注册路由
# 将各个模块的路由器注册到应用中
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


@app.get("/")
def root():
    """
    根路径接口

    Returns:
        应用基本信息和文档链接
    """
    return {
        "message": "Welcome to Imaginary Tree Social Platform",
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
