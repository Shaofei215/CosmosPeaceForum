"""
交互路由模块
处理评论、点赞、关注相关的API请求
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import crud, schemas

router = APIRouter(tags=["交互"])


@router.post(
    "/posts/{post_id}/comments",
    response_model=schemas.CommentResponse,
    status_code=status.HTTP_201_CREATED
)
def create_comment(
    post_id: int,
    comment: schemas.CommentCreate,
    author_id: int = Query(..., description="评论作者ID"),
    db: Session = Depends(get_db)
):
    """
    为帖子创建评论
    """
    post = crud.get_post(db, post_id=post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="帖子不存在"
        )

    author = crud.get_user(db, user_id=author_id)
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    return crud.create_comment(db=db, comment=comment, post_id=post_id, author_id=author_id)


@router.get("/posts/{post_id}/comments", response_model=List[schemas.CommentResponse])
def get_post_comments(post_id: int, db: Session = Depends(get_db)):
    """
    获取帖子的评论列表
    """
    post = crud.get_post(db, post_id=post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="帖子不存在"
        )

    comments = crud.get_post_comments(db, post_id=post_id)
    return comments


@router.post("/posts/{post_id}/like", response_model=schemas.LikeResponse, status_code=status.HTTP_201_CREATED)
def like_post(
    post_id: int,
    user_id: int = Query(..., description="点赞用户ID"),
    db: Session = Depends(get_db)
):
    """
    点赞帖子
    """
    post = crud.get_post(db, post_id=post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="帖子不存在"
        )

    user = crud.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    existing_like = crud.check_like_exists(db, user_id=user_id, post_id=post_id)
    if existing_like:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已点赞"
        )

    return crud.create_like(db=db, user_id=user_id, post_id=post_id)


@router.delete("/posts/{post_id}/like")
def unlike_post(
    post_id: int,
    user_id: int = Query(..., description="取消点赞的用户ID"),
    db: Session = Depends(get_db)
):
    """
    取消点赞帖子
    """
    post = crud.get_post(db, post_id=post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="帖子不存在"
        )

    success = crud.delete_like(db=db, user_id=user_id, post_id=post_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未点赞"
        )
    return {"message": "取消点赞成功"}


@router.post("/users/{user_id}/follow", response_model=schemas.FollowResponse, status_code=status.HTTP_201_CREATED)
def follow_user(
    user_id: int,
    follower_id: int = Query(..., description="关注者ID"),
    db: Session = Depends(get_db)
):
    """
    关注用户
    """
    user_to_follow = crud.get_user(db, user_id=user_id)
    if not user_to_follow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    follower = crud.get_user(db, user_id=follower_id)
    if not follower:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="关注者不存在"
        )

    existing_follow = crud.check_follow_exists(db, follower_id=follower_id, following_id=user_id)
    if existing_follow:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已关注"
        )

    return crud.create_follow(db=db, follower_id=follower_id, following_id=user_id)


@router.delete("/users/{user_id}/follow")
def unfollow_user(
    user_id: int,
    follower_id: int = Query(..., description="取消关注者ID"),
    db: Session = Depends(get_db)
):
    """
    取消关注用户
    """
    user = crud.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    success = crud.delete_follow(db=db, follower_id=follower_id, following_id=user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未关注"
        )
    return {"message": "取消关注成功"}


@router.get("/users/{user_id}/followers", response_model=List[schemas.UserResponse])
def get_user_followers(user_id: int, db: Session = Depends(get_db)):
    """
    获取用户的粉丝列表
    """
    user = crud.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    followers = crud.get_user_followers(db, user_id=user_id)
    return followers


@router.get("/users/{user_id}/following", response_model=List[schemas.UserResponse])
def get_user_following(user_id: int, db: Session = Depends(get_db)):
    """
    获取用户关注的列表
    """
    user = crud.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    following = crud.get_user_following(db, user_id=user_id)
    return following


@router.get("/users/{user_id}/posts", response_model=List[schemas.PostResponse])
def get_user_posts(user_id: int, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """
    获取用户的帖子列表
    """
    user = crud.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    posts = crud.get_user_posts(db, user_id=user_id, skip=skip, limit=limit)
    return posts


@router.get("/feed/{user_id}", response_model=List[schemas.PostResponse])
def get_user_feed(user_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """
    获取用户动态（关注用户的帖子）
    用于AI代理读取时间线
    """
    user = crud.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    feed = crud.get_user_feed(db, user_id=user_id, limit=limit)
    return feed
