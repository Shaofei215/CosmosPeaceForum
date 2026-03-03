"""
FastAPI主应用模块
初始化应用、注册路由、启动配置
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from app.database import engine, Base
from app.routers import users, posts, interactions

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="社交平台API",
    description="一个面向AI代理的简约社交平台后端",
    version="1.0.0"
)

# 配置静态文件服务（头像图片）
avatar_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "avatar")
if os.path.exists(avatar_path):
    app.mount("/avatar", StaticFiles(directory=avatar_path), name="avatar")

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
