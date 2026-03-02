"""
交互路由模块
处理评论、点赞、关注相关的API请求
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import crud, schemas
from app.hot_score import (
    update_post_hot_score, 
    get_mixed_comments, 
    get_mixed_replies,
    get_comments_by_interest,
    update_comment_hot_score,
    update_reply_hot_score
)

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

    new_comment = crud.create_comment(db=db, comment=comment, post_id=post_id, author_id=author_id)
    
    # 更新帖子热度
    update_post_hot_score(db, post_id)
    
    return new_comment


@router.get("/posts/{post_id}/comments", response_model=List[schemas.CommentResponse])
def get_post_comments(
    post_id: int, 
    mixed: bool = Query(False, description="是否使用混合排序（70%热门+30%最新）"),
    limit: int = Query(50, description="返回数量"),
    db: Session = Depends(get_db)
):
    """
    获取帖子的评论列表
    支持混合排序：70%热门评论 + 30%最新评论，顺序随机
    """
    post = crud.get_post(db, post_id=post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="帖子不存在"
        )

    if mixed:
        # 使用混合排序
        comments = get_mixed_comments(db, post_id=post_id, hot_ratio=0.7, total_limit=limit)
    else:
        # 使用默认排序（时间倒序）
        comments = crud.get_post_comments(db, post_id=post_id)
    
    return comments


@router.get("/posts/{post_id}/comments/by-interest", response_model=List[schemas.CommentResponse])
def get_post_comments_by_interest(
    post_id: int,
    interest_score: float = Query(..., ge=0.0, le=1.0, description="兴趣系数（0-1）"),
    max_comments: int = Query(7, description="最大评论数"),
    db: Session = Depends(get_db)
):
    """
    根据兴趣系数获取评论
    
    阅读评论数 = floor(兴趣系数 × max_comments)
    例如：兴趣系数0.6，max_comments=7 → 阅读4条评论
    """
    post = crud.get_post(db, post_id=post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="帖子不存在"
        )
    
    comments = get_comments_by_interest(
        db, 
        post_id=post_id, 
        interest_score=interest_score, 
        max_comments=max_comments
    )
    
    return comments


@router.post("/comments/{comment_id}/update-hot-score")
def refresh_comment_hot_score(comment_id: int, db: Session = Depends(get_db)):
    """
    手动刷新评论热度分数
    """
    comment = crud.get_comment(db, comment_id=comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="评论不存在"
        )
    
    new_score = update_comment_hot_score(db, comment_id)
    return {"comment_id": comment_id, "hot_score": new_score}


# ==================== 回复相关 API ====================

@router.post(
    "/comments/{comment_id}/replies",
    response_model=schemas.ReplyResponse,
    status_code=status.HTTP_201_CREATED
)
def create_reply(
    comment_id: int,
    reply: schemas.ReplyCreate,
    author_id: int = Query(..., description="回复作者ID"),
    db: Session = Depends(get_db)
):
    """
    为评论创建回复（支持楼中楼）
    """
    comment = crud.get_comment(db, comment_id=comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="评论不存在"
        )

    author = crud.get_user(db, user_id=author_id)
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    new_reply = crud.create_reply(
        db=db, 
        reply=reply, 
        comment_id=comment_id, 
        author_id=author_id,
        parent_reply_id=reply.parent_reply_id
    )
    
    # 更新评论热度
    update_comment_hot_score(db, comment_id)
    
    return new_reply


@router.get("/comments/{comment_id}/replies", response_model=List[schemas.ReplyResponse])
def get_comment_replies(
    comment_id: int, 
    mixed: bool = Query(False, description="是否使用混合排序（70%热门+30%最新）"),
    limit: int = Query(50, description="返回数量"),
    db: Session = Depends(get_db)
):
    """
    获取评论的回复列表
    支持混合排序：70%热门回复 + 30%最新回复，顺序随机
    """
    comment = crud.get_comment(db, comment_id=comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="评论不存在"
        )

    if mixed:
        # 使用混合排序
        replies = get_mixed_replies(db, comment_id=comment_id, hot_ratio=0.7, total_limit=limit)
    else:
        # 使用默认排序（时间倒序）
        replies = crud.get_comment_replies(db, comment_id=comment_id)
    
    return replies


@router.get("/replies/{reply_id}", response_model=schemas.ReplyResponse)
def get_reply(reply_id: int, db: Session = Depends(get_db)):
    """
    获取单个回复信息
    """
    reply = crud.get_reply(db, reply_id=reply_id)
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回复不存在"
        )
    return reply


@router.post("/replies/{reply_id}/update-hot-score")
def refresh_reply_hot_score(reply_id: int, db: Session = Depends(get_db)):
    """
    手动刷新回复热度分数
    """
    reply = crud.get_reply(db, reply_id=reply_id)
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回复不存在"
        )
    
    new_score = update_reply_hot_score(db, reply_id)
    return {"reply_id": reply_id, "hot_score": new_score}


# ==================== 通用点赞 API ====================

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

    new_like = crud.create_like(db=db, user_id=user_id, post_id=post_id)
    
    # 更新帖子热度
    update_post_hot_score(db, post_id)
    
    return new_like


@router.post("/comments/{comment_id}/like", response_model=schemas.LikeResponse, status_code=status.HTTP_201_CREATED)
def like_comment(
    comment_id: int,
    user_id: int = Query(..., description="点赞用户ID"),
    db: Session = Depends(get_db)
):
    """
    点赞评论
    """
    comment = crud.get_comment(db, comment_id=comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="评论不存在"
        )

    user = crud.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    existing_like = crud.check_comment_like_exists(db, user_id=user_id, comment_id=comment_id)
    if existing_like:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已点赞"
        )

    new_like = crud.create_comment_like(db=db, user_id=user_id, comment_id=comment_id)
    
    # 更新评论热度
    update_comment_hot_score(db, comment_id)
    
    return new_like


@router.post("/replies/{reply_id}/like", response_model=schemas.LikeResponse, status_code=status.HTTP_201_CREATED)
def like_reply(
    reply_id: int,
    user_id: int = Query(..., description="点赞用户ID"),
    db: Session = Depends(get_db)
):
    """
    点赞回复
    """
    reply = crud.get_reply(db, reply_id=reply_id)
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回复不存在"
        )

    user = crud.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    existing_like = crud.check_reply_like_exists(db, user_id=user_id, reply_id=reply_id)
    if existing_like:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已点赞"
        )

    new_like = crud.create_reply_like(db=db, user_id=user_id, reply_id=reply_id)
    
    # 更新回复热度
    update_reply_hot_score(db, reply_id)
    
    return new_like


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

    new_like = crud.create_like(db=db, user_id=user_id, post_id=post_id)
    
    # 更新帖子热度
    update_post_hot_score(db, post_id)
    
    return new_like


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
