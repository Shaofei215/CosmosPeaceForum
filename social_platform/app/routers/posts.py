"""
帖子路由模块
处理帖子相关的API请求
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import crud, schemas
from app.hot_score import get_hot_posts, get_mixed_posts, update_post_hot_score, update_all_hot_scores

router = APIRouter(prefix="/posts", tags=["帖子"])


@router.get("/hot", response_model=List[schemas.PostResponse])
def list_hot_posts(limit: int = 50, db: Session = Depends(get_db)):
    """
    获取热门帖子列表（按热度排序）
    """
    posts = get_hot_posts(db, limit=limit)
    return posts


@router.get("/mixed", response_model=List[schemas.PostResponse])
def list_mixed_posts(
    limit: int = 50,
    hot_ratio: float = Query(0.4, ge=0.0, le=1.0, description="热门帖子比例（默认40%）"),
    fresh_ratio: float = Query(0.3, ge=0.0, le=1.0, description="最新帖子比例（默认30%）"),
    random_ratio: float = Query(0.3, ge=0.0, le=1.0, description="随机帖子比例（默认30%）"),
    user_id: int = Query(None, description="用户ID，用于过滤已读帖子"),
    db: Session = Depends(get_db)
):
    """
    获取三层混合帖子（热门+最新+随机，顺序随机）
    默认40%热门 + 30%最新 + 30%随机
    如果提供user_id，将过滤该用户已读的帖子
    """
    posts = get_mixed_posts(
        db, 
        user_id=user_id, 
        hot_ratio=hot_ratio,
        fresh_ratio=fresh_ratio,
        random_ratio=random_ratio,
        total_limit=limit
    )
    return posts


@router.post("/update-all-hot-scores")
def refresh_all_hot_scores(db: Session = Depends(get_db)):
    """
    刷新所有帖子热度分数
    """
    updated_count = update_all_hot_scores(db)
    return {"updated_count": updated_count}


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


@router.get("", response_model=List[schemas.PostResponse])
def list_posts(
    skip: int = 0, 
    limit: int = 50, 
    sort: str = Query("recommended", description="排序方式：recommended=推荐算法，latest=最新，hot=最热"),
    user_id: int = Query(None, description="用户 ID，用于推荐算法过滤已读帖子"),
    db: Session = Depends(get_db)
):
    """
    获取帖子列表（支持多种排序方式）
    - sort=recommended: 推荐算法（40% 热门 + 30% 最新 + 30% 随机）
    - sort=latest: 按时间倒序
    - sort=hot: 按热度排序
    """
    if sort == "recommended":
        # 使用推荐算法（混合排序）
        posts = get_mixed_posts(db, user_id=user_id, total_limit=limit)
    elif sort == "latest":
        # 按时间倒序
        posts = crud.get_posts(db, skip=skip, limit=limit)
    elif sort == "hot":
        # 按热度排序
        posts = get_hot_posts(db, limit=limit)
    else:
        # 默认使用推荐算法
        posts = get_mixed_posts(db, user_id=user_id, total_limit=limit)
    
    return posts


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


@router.post("/{post_id}/update-hot-score")
def refresh_post_hot_score(post_id: int, db: Session = Depends(get_db)):
    """
    手动刷新帖子热度分数
    """
    post = crud.get_post(db, post_id=post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="帖子不存在"
        )
    
    new_score = update_post_hot_score(db, post_id)
    return {"post_id": post_id, "hot_score": new_score}
