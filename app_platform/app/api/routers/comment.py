# 评论路由控制器
# 处理评论相关的 API 请求，包括创建、查询、删除、点赞等功能
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_db, get_current_user, get_current_user_optional
from app.models.user import User
from app.schemas.comment import (
    CommentCreate,
    CommentResponse,
    CommentTreeResponse,
    CommentLikeToggleResponse,
    CommentListResponse
)
from app.services import comment_service

router = APIRouter()


@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED,
              summary="创建评论", description="在指定帖子下创建新评论或回复。需要登录认证，评论作者从 JWT Token 中自动获取。")
def create_comment(
    post_id: int,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建评论或回复

    在指定帖子下创建新评论。如果指定了 parent_id，则创建的是回复评论

    - **post_id**: 帖子 ID（路径参数）
    - **content**: 评论内容，必填
    - **parent_id**: 父评论 ID（可选，填写则创建回复）

    需要认证：是的（Bearer Token）
    - owner_id 从 JWT Token 中自动获取，无需手动传入

    返回：创建的评论信息，包含评论 ID、所属帖子 ID、评论者信息、内容、点赞数、回复数等

    错误：
    - 404：帖子不存在或父评论不存在
    - 400：父评论与帖子不匹配
    """
    try:
        comment = comment_service.create_comment(
            post_id=post_id,
            user_id=current_user.id,
            content=comment_data.content,
            parent_id=comment_data.parent_id,
            db=db
        )

        comment.is_liked = False

        return comment

    except comment_service.PostNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except comment_service.ParentCommentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except comment_service.ParentCommentMismatchError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{post_id}/comments", response_model=CommentListResponse,
            summary="获取评论树", description="获取指定帖子的所有评论，以树形结构返回。一级评论按时间倒序排列。")
def get_comment_tree(
    post_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    skip: int = Query(0, ge=0, description="跳过的数量，用于一级评论分页"),
    limit: int = Query(20, ge=1, le=100, description="返回的最大数量，用于一级评论分页"),
    db: Session = Depends(get_db)
):
    """
    获取帖子的评论树

    以树形结构返回指定帖子的所有评论，支持无限层级嵌套回复

    - **post_id**: 帖子 ID（路径参数）
    - **skip**: 跳过的数量（分页，用于一级评论，默认 0）
    - **limit**: 返回的最大数量（分页，用于一级评论，默认 20，最大 100）

    需要认证：否（可选认证，已登录时返回点赞状态）

    返回结构：
    - items: 评论列表，每条评论包含 children 字段表示回复
    - total: 一级评论总数
    - skip: 跳过的数量
    - limit: 返回的数量

    错误：
    - 404：帖子不存在
    """
    try:
        user_id = current_user.id if current_user else None
        comments, total = comment_service.get_comment_tree(
            post_id=post_id,
            user_id=user_id,
            skip=skip,
            limit=limit,
            db=db
        )

        return CommentListResponse(
            items=comments,
            total=total,
            skip=skip,
            limit=limit
        )

    except comment_service.PostNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{post_id}/comments/{comment_id}/like", response_model=CommentLikeToggleResponse,
             summary="评论点赞/取消点赞", description="切换对评论的点赞状态。")
def toggle_comment_like(
    post_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    评论点赞/取消点赞切换

    - **post_id**: 帖子 ID（路径参数，用于路径匹配）
    - **comment_id**: 评论 ID（路径参数）

    需要认证：是的（Bearer Token）
    - user_id 从 JWT Token 中自动获取

    返回：包含点赞状态和评论总点赞数

    错误：
    - 404：评论不存在
    """
    try:
        is_liked, like_count = comment_service.toggle_like(
            comment_id=comment_id,
            user_id=current_user.id,
            db=db
        )

        return CommentLikeToggleResponse(
            is_liked=is_liked,
            like_count=like_count
        )

    except comment_service.CommentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{post_id}/comments/{comment_id}/like-status",
            summary="获取评论点赞状态", description="获取当前用户对指定评论的点赞状态和评论的总点赞数。")
def get_comment_like_status(
    post_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取评论点赞状态

    - **post_id**: 帖子 ID（路径参数）
    - **comment_id**: 评论 ID（路径参数）

    需要认证：是的（Bearer Token）

    返回：
    - is_liked: 当前用户是否已点赞
    - like_count: 评论的总点赞数

    错误：
    - 404：评论不存在
    """
    try:
        is_liked, like_count = comment_service.get_like_status(
            comment_id=comment_id,
            user_id=current_user.id,
            db=db
        )

        return {
            "is_liked": is_liked,
            "like_count": like_count
        }

    except comment_service.CommentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{post_id}/comments/{comment_id}", response_model=CommentResponse,
            summary="获取评论详情", description="根据评论 ID 获取评论的详细信息。")
def get_comment_by_id(
    post_id: int,
    comment_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    获取评论详情

    - **post_id**: 帖子 ID（路径参数）
    - **comment_id**: 评论 ID（路径参数）

    需要认证：否（可选认证，已登录时返回点赞状态）

    返回：评论详细信息，包含评论内容、作者信息、点赞状态等

    错误：
    - 404：评论不存在
    """
    user_id = current_user.id if current_user else None
    comment = comment_service.get_comment_by_id(
        comment_id=comment_id,
        user_id=user_id,
        db=db
    )

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"评论不存在 (ID: {comment_id})"
        )

    return comment


@router.delete("/{post_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="删除评论", description="删除指定评论及其所有回复，仅评论作者可以操作。")
def delete_comment(
    post_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除评论

    删除指定评论及其所有回复。只有评论作者可以删除自己的评论

    - **post_id**: 帖子 ID（路径参数）
    - **comment_id**: 评论 ID（路径参数）

    需要认证：是的（Bearer Token）

    权限：仅评论作者可以删除

    级联删除：删除评论时会同时删除所有子回复

    返回：204 No Content

    错误：
    - 404：评论不存在
    - 403：无权删除评论（不是评论作者）
    """
    try:
        comment_service.delete_comment(
            comment_id=comment_id,
            user_id=current_user.id,
            db=db
        )

        return None

    except comment_service.CommentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
