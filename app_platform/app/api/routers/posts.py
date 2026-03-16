# 帖子路由控制器
# 处理帖子相关的 API 请求
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostCreate, PostResponse, PostUpdate

# 创建 API 路由器
router = APIRouter()


@router.post("/", response_model=PostResponse)
def create_post(post: PostCreate, db: Session = Depends(get_db)):
    """
    创建新帖子
    
    Args:
        post: 帖子创建请求数据
        db: 数据库会话
    
    Returns:
        创建的帖子信息
    """
    # 创建新帖子
    db_post = Post(**post.model_dump())
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post


@router.get("/", response_model=List[PostResponse])
def get_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取帖子列表（分页，按创建时间倒序）
    
    Args:
        skip: 跳过前 N 条记录
        limit: 返回记录数量，最大 100
        db: 数据库会话
    
    Returns:
        帖子列表
    """
    posts = db.query(Post).order_by(Post.created_at.desc()).offset(skip).limit(limit).all()
    return posts


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: int, db: Session = Depends(get_db)):
    """
    获取指定帖子的详细信息
    
    Args:
        post_id: 帖子 ID
        db: 数据库会话
    
    Returns:
        帖子详细信息
    
    Raises:
        HTTPException: 帖子不存在时抛出 404 错误
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return post


@router.put("/{post_id}", response_model=PostResponse)
def update_post(
    post_id: int,
    post_update: PostUpdate,
    db: Session = Depends(get_db)
):
    """
    更新帖子信息
    
    Args:
        post_id: 帖子 ID
        post_update: 帖子更新数据
        db: 数据库会话
    
    Returns:
        更新后的帖子信息
    
    Raises:
        HTTPException: 帖子不存在时抛出 404 错误
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    
    # 只更新提供的字段
    update_data = post_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)
    
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    """
    删除帖子
    
    Args:
        post_id: 帖子 ID
        db: 数据库会话
    
    Returns:
        删除成功消息
    
    Raises:
        HTTPException: 帖子不存在时抛出 404 错误
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    
    db.delete(post)
    db.commit()
    return {"message": "帖子删除成功"}


@router.get("/user/{user_id}", response_model=List[PostResponse])
def get_user_posts(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取指定用户的所有帖子（分页，按创建时间倒序）
    
    Args:
        user_id: 用户 ID
        skip: 跳过前 N 条记录
        limit: 返回记录数量，最大 100
        db: 数据库会话
    
    Returns:
        用户的帖子列表
    
    Raises:
        HTTPException: 用户不存在时抛出 404 错误
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    posts = db.query(Post).filter(Post.author_id == user_id).order_by(Post.created_at.desc()).offset(skip).limit(limit).all()
    return posts
