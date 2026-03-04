"""
FastAPI主应用模块
初始化应用、注册路由、启动配置
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from app.database import engine, Base
from app.routers import users, posts, interactions

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="社交平台API",
    description="一个面向AI代理的简约社交平台后端",
    version="1.0.0"
)

# 配置CORS，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

# 配置静态文件服务（头像图片）
# 头像目录在项目根目录下的avatar文件夹
avatar_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "avatar")
if os.path.exists(avatar_path):
    app.mount("/avatar", StaticFiles(directory=avatar_path), name="avatar")
    print(f"[INFO] 头像服务已挂载: {avatar_path}")
else:
    print(f"[WARNING] 头像目录不存在: {avatar_path}")

app.include_router(users.router)
app.include_router(posts.router)
app.include_router(interactions.router)


@app.get("/")
def root():
    """根路径健康检查"""
    return {"message": "社交平台API运行中", "status": "ok"}


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "healthy"}
