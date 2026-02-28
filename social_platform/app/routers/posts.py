"""
帖子路由模块
处理帖子相关的API请求
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/posts", tags=["帖子"])


@router.post("", response_model=schemas.PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    post: schemas.PostCreate,
    author_id: int = Query(..., description="作者ID"),
    db: Session = Depends(get_db)
):
    """
    创建新帖子
    """
    author = crud.get_user(db, user_id=author_id)
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="作者不存在"
        )
    return crud.create_post(db=db, post=post, author_id=author_id)


@router.get("/{post_id}", response_model=schemas.PostResponse)
def get_post(post_id: int, db: Session = Depends(get_db)):
    """
    获取帖子详情
    """
    post = crud.get_post(db, post_id=post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="帖子不存在"
        )
    return post


@router.get("", response_model=List[schemas.PostResponse])
def list_posts(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """
    获取帖子列表（全局时间线）
    """
    posts = crud.get_posts(db, skip=skip, limit=limit)
    return posts
