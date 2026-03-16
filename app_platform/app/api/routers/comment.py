# 评论路由控制器
# 处理评论相关的 API 请求，包括创建、查询、点赞等功能
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_db
from app.schemas.comment import (
    CommentCreate,
    CommentResponse,
    CommentTreeResponse,
    CommentLikeToggleResponse,
    CommentListResponse
)
from app.services import comment_service

# 创建 API 路由器
router = APIRouter()


@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    post_id: int,
    comment_data: CommentCreate,
    user_id: int = Query(..., description="当前用户 ID"),
    db: Session = Depends(get_db)
):
    """
    创建评论或回复
    
    在指定帖子下创建新评论或回复。如果是回复，需要指定 parent_id。
    创建评论时会自动更新帖子的 comment_count 和父评论的 reply_count。
    
    Args:
        post_id: 帖子 ID（路径参数）
        comment_data: 评论创建数据（请求体）
        user_id: 当前用户 ID（查询参数）
        db: 数据库会话（依赖注入）
    
    Returns:
        CommentResponse: 创建成功的评论信息
    
    Raises:
        HTTPException:
            - 404: 帖子不存在或父评论不存在
            - 400: 父评论与帖子不匹配
    
    Example:
        POST /posts/1/comments?user_id=123
        Body: {
            "content": "这是一条评论",
            "parent_id": null
        }
        Response: {
            "id": 1,
            "post_id": 1,
            "owner_id": 123,
            "parent_id": null,
            "content": "这是一条评论",
            "like_count": 0,
            "reply_count": 0,
            "created_at": "2024-01-01T00:00:00",
            "is_liked": false,
            "owner": {...}
        }
    """
    try:
        # 调用评论服务创建评论
        comment = comment_service.create_comment(
            post_id=post_id,
            user_id=user_id,
            content=comment_data.content,
            parent_id=comment_data.parent_id,
            db=db
        )
        
        # 注入 owner 信息和点赞状态
        comment.is_liked = False
        
        # 返回响应
        return comment
    
    except comment_service.PostNotFoundError as e:
        # 帖子不存在，返回 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
    except comment_service.ParentCommentNotFoundError as e:
        # 父评论不存在，返回 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
    except comment_service.ParentCommentMismatchError as e:
        # 父评论与帖子不匹配，返回 400
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{post_id}/comments", response_model=CommentListResponse)
def get_comment_tree(
    post_id: int,
    user_id: Optional[int] = Query(None, description="当前用户 ID（可选，用于判断点赞状态）"),
    skip: int = Query(0, ge=0, description="跳过的数量（分页）"),
    limit: int = Query(20, ge=1, le=100, description="返回的最大数量（分页）"),
    db: Session = Depends(get_db)
):
    """
    获取帖子的评论树
    
    查询指定帖子的所有评论，以树形结构返回。支持无限层级嵌套回复。
    一级评论按时间倒序排列，回复按时间正序排列。
    
    Args:
        post_id: 帖子 ID（路径参数）
        user_id: 当前用户 ID（可选查询参数，用于判断点赞状态）
        skip: 跳过的数量（分页，用于一级评论）
        limit: 返回的最大数量（分页，用于一级评论）
        db: 数据库会话（依赖注入）
    
    Returns:
        CommentListResponse: 评论树列表和总数
    
    Raises:
        HTTPException:
            - 404: 帖子不存在
    
    Example:
        GET /posts/1/comments?user_id=123&skip=0&limit=20
        Response: {
            "items": [
                {
                    "id": 1,
                    "post_id": 1,
                    "owner_id": 123,
                    "parent_id": null,
                    "content": "一级评论",
                    "like_count": 5,
                    "reply_count": 2,
                    "created_at": "2024-01-01T00:00:00",
                    "is_liked": true,
                    "owner": {...},
                    "children": [
                        {
                            "id": 2,
                            "post_id": 1,
                            "owner_id": 456,
                            "parent_id": 1,
                            "content": "回复",
                            "like_count": 1,
                            "reply_count": 0,
                            "created_at": "2024-01-01T01:00:00",
                            "is_liked": false,
                            "owner": {...},
                            "children": []
                        }
                    ]
                }
            ],
            "total": 10,
            "skip": 0,
            "limit": 20
        }
    """
    try:
        # 调用评论服务获取评论树
        comments, total = comment_service.get_comment_tree(
            post_id=post_id,
            user_id=user_id,
            skip=skip,
            limit=limit,
            db=db
        )
        
        # 返回响应
        return CommentListResponse(
            items=comments,
            total=total,
            skip=skip,
            limit=limit
        )
    
    except comment_service.PostNotFoundError as e:
        # 帖子不存在，返回 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/comments/{comment_id}/like", response_model=CommentLikeToggleResponse)
def toggle_comment_like(
    comment_id: int,
    user_id: int = Query(..., description="当前用户 ID"),
    db: Session = Depends(get_db)
):
    """
    评论点赞/取消点赞切换
    
    根据当前用户的点赞状态进行切换：
    - 如果未点赞，则点赞
    - 如果已点赞，则取消点赞
    
    Args:
        comment_id: 评论 ID（路径参数）
        user_id: 当前用户 ID（查询参数）
        db: 数据库会话（依赖注入）
    
    Returns:
        CommentLikeToggleResponse: 包含点赞状态和点赞总数
    
    Raises:
        HTTPException:
            - 404: 评论不存在
    
    Example:
        POST /comments/1/like?user_id=123
        Response: {
            "is_liked": true,
            "like_count": 10
        }
    """
    try:
        # 调用评论点赞服务
        is_liked, like_count = comment_service.toggle_like(
            comment_id=comment_id,
            user_id=user_id,
            db=db
        )
        
        # 返回响应
        return CommentLikeToggleResponse(
            is_liked=is_liked,
            like_count=like_count
        )
    
    except comment_service.CommentNotFoundError as e:
        # 评论不存在，返回 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/comments/{comment_id}/like-status")
def get_comment_like_status(
    comment_id: int,
    user_id: int = Query(..., description="当前用户 ID"),
    db: Session = Depends(get_db)
):
    """
    获取评论点赞状态
    
    查询指定用户对指定评论的点赞状态和评论的总点赞数。
    
    Args:
        comment_id: 评论 ID（路径参数）
        user_id: 当前用户 ID（查询参数）
        db: 数据库会话（依赖注入）
    
    Returns:
        dict: 包含是否已点赞和点赞总数
    
    Raises:
        HTTPException:
            - 404: 评论不存在
    
    Example:
        GET /comments/1/like-status?user_id=123
        Response: {
            "is_liked": true,
            "like_count": 10
        }
    """
    try:
        # 调用评论点赞状态查询服务
        is_liked, like_count = comment_service.get_like_status(
            comment_id=comment_id,
            user_id=user_id,
            db=db
        )
        
        # 返回响应
        return {
            "is_liked": is_liked,
            "like_count": like_count
        }
    
    except comment_service.CommentNotFoundError as e:
        # 评论不存在，返回 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/comments/{comment_id}", response_model=CommentResponse)
def get_comment_by_id(
    comment_id: int,
    user_id: Optional[int] = Query(None, description="当前用户 ID（可选，用于判断点赞状态）"),
    db: Session = Depends(get_db)
):
    """
    获取评论详情
    
    根据评论 ID 获取评论的详细信息，包括点赞状态。
    
    Args:
        comment_id: 评论 ID（路径参数）
        user_id: 当前用户 ID（可选查询参数，用于判断点赞状态）
        db: 数据库会话（依赖注入）
    
    Returns:
        CommentResponse: 评论详情
    
    Raises:
        HTTPException:
            - 404: 评论不存在
    
    Example:
        GET /comments/1?user_id=123
        Response: {
            "id": 1,
            "post_id": 1,
            "owner_id": 123,
            "parent_id": null,
            "content": "评论内容",
            "like_count": 5,
            "reply_count": 2,
            "created_at": "2024-01-01T00:00:00",
            "is_liked": true,
            "owner": {...}
        }
    """
    # 调用评论服务获取评论详情
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


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    user_id: int = Query(..., description="当前用户 ID"),
    db: Session = Depends(get_db)
):
    """
    删除评论
    
    删除指定评论及其所有回复。只有评论作者可以删除自己的评论。
    删除时会自动更新帖子的 comment_count 和父评论的 reply_count。
    
    Args:
        comment_id: 评论 ID（路径参数）
        user_id: 当前用户 ID（查询参数，用于权限验证）
        db: 数据库会话（依赖注入）
    
    Returns:
        None: 删除成功返回 204 No Content
    
    Raises:
        HTTPException:
            - 404: 评论不存在
            - 403: 无权删除评论
    
    Example:
        DELETE /comments/1?user_id=123
        Response: 204 No Content
    """
    try:
        # 调用评论服务删除评论
        comment_service.delete_comment(
            comment_id=comment_id,
            user_id=user_id,
            db=db
        )
        
        # 返回 204 No Content
        return None
    
    except comment_service.CommentNotFoundError as e:
        # 评论不存在，返回 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
    except PermissionError as e:
        # 无权删除，返回 403
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
