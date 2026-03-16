# 信息流路由控制器
# 处理信息流相关的 API 请求
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostResponse

# 创建 API 路由器
router = APIRouter()


@router.get("/feed/all", response_model=List[PostResponse])
def get_global_feed(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取全局信息流 - 所有用户的公开帖子
    
    Args:
        skip: 跳过前 N 条记录
        limit: 返回记录数量，最大 100
        db: 数据库会话
    
    Returns:
        全局帖子列表（按创建时间倒序）
    """
    posts = db.query(Post).order_by(Post.created_at.desc()).offset(skip).limit(limit).all()
    return posts


@router.get("/feed/user/{user_id}", response_model=List[PostResponse])
def get_user_feed(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取指定用户的帖子流
    
    Args:
        user_id: 用户 ID
        skip: 跳过前 N 条记录
        limit: 返回记录数量，最大 100
        db: 数据库会话
    
    Returns:
        用户的帖子列表（按创建时间倒序）
    
    Raises:
        HTTPException: 用户不存在时抛出 404 错误
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    posts = db.query(Post).filter(Post.author_id == user_id).order_by(Post.created_at.desc()).offset(skip).limit(limit).all()
    return posts
