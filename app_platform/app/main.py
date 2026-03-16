# 应用主入口
# 初始化 FastAPI 应用，注册路由和中间件
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.session import engine, Base
from app.api.routers import users, posts, feeds, like

# 获取应用配置
settings = get_settings()

# 创建数据库表
# Base.metadata.create_all 会根据模型定义自动创建所有表
Base.metadata.create_all(bind=engine)

# 创建 FastAPI 应用实例
app = FastAPI(
    # 应用标题
    title=settings.PROJECT_NAME,
    # 应用版本
    version=settings.VERSION,
    # OpenAPI 文档路径
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
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

# 注册路由
# 将各个模块的路由器注册到应用中
app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["users"])
app.include_router(posts.router, prefix=f"{settings.API_V1_PREFIX}/posts", tags=["posts"])
app.include_router(feeds.router, prefix=f"{settings.API_V1_PREFIX}/feeds", tags=["feeds"])
app.include_router(like.router, prefix=f"{settings.API_V1_PREFIX}/posts", tags=["likes"])


@app.get("/")
def root():
    """
    根路径接口
    
    Returns:
        应用基本信息和文档链接
    """
    return {
        "message": "Welcome to Herta-Tree Social Platform",
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
