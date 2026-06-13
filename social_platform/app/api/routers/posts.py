# 帖子路由控制器
# 处理帖子相关的 API 请求
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from social_platform.app.api.deps import get_db, get_current_user, get_current_user_optional
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User
from social_platform.app.domains.reaction.models import Like
from social_platform.app.domains.post.schemas import (
    PostCreate,
    PostResponse,
    PostUpdate,
    PostResponseWithLikeStatus,
    RepostCreate,
)
from social_platform.app.domains.post import application as post_application
from social_platform.app.domains.post import queries as post_queries

router = APIRouter()


@router.post("/", response_model=PostResponse, summary="创建帖子", description="创建新帖子，需要登录认证。author_id 从 JWT Token 中自动获取，无需手动传入。")
def create_post(
    post: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建新帖子

    - **author_id**: 自动从当前登录用户的 Token 中获取
    - **title**: 帖子标题，必填
    - **content**: 帖子内容，必填

    需要认证：是的（Bearer Token）

    返回：创建的帖子信息，包含 id、author_id、title、content、created_at 等字段
    """
    try:
        db_post = post_application.create_post(db, current_user, post)
        db_post.mention_users = post_queries.build_mention_users(db, db_post.content)
        return db_post
    except post_application.ArticleTitleRequiredError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/repost", response_model=PostResponse, summary="转发帖子或评论")
def repost(
    data: RepostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        created_post = post_application.create_repost_for_user(db, current_user, data)
        return created_post
    except post_application.RepostSourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except post_application.InvalidRepostSourceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[PostResponse], summary="获取帖子列表", description="获取所有帖子列表，支持分页，按创建时间倒序排列。无需认证。")
def get_posts(
    skip: int = Query(0, ge=0, description="跳过的记录数，用于分页"),
    limit: int = Query(10, ge=1, le=100, description="返回的记录数量，最大100"),
    db: Session = Depends(get_db)
):
    """
    获取帖子列表

    - **skip**: 跳过前 N 条记录（默认 0）
    - **limit**: 返回记录数量（默认 10，最大 100）

    需要认证：否

    返回：帖子列表，按创建时间倒序排列
    """
    posts = db.query(Post).options(
        joinedload(Post.author),
        joinedload(Post.repost_root_post).joinedload(Post.author),
    ).order_by(Post.created_at.desc()).offset(skip).limit(limit).all()
    for post in posts:
        post_queries.attach_repost_metadata(db, post)
    return posts


@router.get("/{post_id}", response_model=PostResponseWithLikeStatus, summary="获取帖子详情", description="获取指定帖子的详细信息，包括当前用户的点赞状态。已登录用户可看到自己的点赞状态。")
def get_post(
    post_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    获取指定帖子的详细信息

    - **post_id**: 帖子 ID（路径参数）

    需要认证：否（可选认证，已登录时返回点赞状态）

    返回：帖子详细信息，包含 is_liked_by_current_user 字段表示当前用户是否已点赞

    错误：
    - 404：帖子不存在
    """
    post = db.query(Post).options(
        joinedload(Post.author),
        joinedload(Post.repost_root_post).joinedload(Post.author),
    ).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    is_liked = False
    if current_user is not None:
        like = db.query(Like).filter(
            Like.user_id == current_user.id,
            Like.post_id == post_id
        ).first()
        is_liked = like is not None

    return PostResponseWithLikeStatus(
        id=post.id,
        author_id=post.author_id,
        author=post.author,
        title=post.title,
        type=post.type,
        content=post.content,
        created_at=post.created_at,
        like_count=post.like_count,
        comment_count=post.comment_count,
        repost_count=post.repost_count,
        repost_source_type=post.repost_source_type,
        repost_source_id=post.repost_source_id,
        repost_root_post_id=post.repost_root_post_id,
        repost_chain=post.repost_chain,
        repost_chain_authors=post_queries.build_repost_chain_authors(db, post.content),
        mention_users=post_queries.build_mention_users(db, post.content),
        repost_origin=post.repost_root_post if post.repost_root_post_id else None,
        repost_origin_missing=post_queries.is_repost_origin_missing(post),
        is_liked_by_current_user=is_liked
    )


@router.put("/{post_id}", response_model=PostResponse, summary="更新帖子", description="更新指定帖子的标题和内容，仅帖子作者可以操作。")
def update_post(
    post_id: int,
    post_update: PostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新帖子信息

    - **post_id**: 帖子 ID（路径参数）
    - **title**: 帖子标题（可选更新）
    - **content**: 帖子内容（可选更新）

    需要认证：是的（Bearer Token）

    权限：仅帖子作者可以更新

    返回：更新后的帖子信息

    错误：
    - 404：帖子不存在
    - 403：不是帖子作者，无权修改
    """
    try:
        return post_application.update_post(db, current_user, post_id, post_update)
    except post_application.PostNotFoundError:
        raise HTTPException(status_code=404, detail="帖子不存在")
    except post_application.PostPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/{post_id}", summary="删除帖子", description="删除指定帖子，仅帖子作者可以操作。")
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除帖子

    - **post_id**: 帖子 ID（路径参数）

    需要认证：是的（Bearer Token）

    权限：仅帖子作者可以删除

    返回：删除成功消息

    错误：
    - 404：帖子不存在
    - 403：不是帖子作者，无权删除
    """
    try:
        post_application.delete_post(db, current_user, post_id)
        return {"message": "帖子删除成功"}
    except post_application.PostNotFoundError:
        raise HTTPException(status_code=404, detail="帖子不存在")
    except post_application.PostPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/user/{user_id}", response_model=List[PostResponse], summary="获取用户帖子", description="获取指定用户发布的所有帖子列表，支持分页。")
def get_user_posts(
    user_id: int,
    skip: int = Query(0, ge=0, description="跳过的记录数，用于分页"),
    limit: int = Query(10, ge=1, le=100, description="返回的记录数量，最大100"),
    db: Session = Depends(get_db)
):
    """
    获取指定用户的所有帖子

    - **user_id**: 用户 ID（路径参数）
    - **skip**: 跳过前 N 条记录（默认 0）
    - **limit**: 返回记录数量（默认 10，最大 100）

    需要认证：否

    返回：用户的帖子列表，按创建时间倒序排列

    错误：
    - 404：用户不存在
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    posts = db.query(Post).filter(Post.author_id == user_id).options(
        joinedload(Post.author),
        joinedload(Post.repost_root_post).joinedload(Post.author),
    ).order_by(Post.created_at.desc()).offset(skip).limit(limit).all()
    for post in posts:
        post_queries.attach_repost_metadata(db, post)
    return posts
