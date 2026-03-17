# 信息流路由控制器
# 处理信息流相关的 API 请求
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.feed import PostFeedItem
from app.schemas.response import APIResponse
from app.services import feed_service

# 创建 API 路由器
router = APIRouter()


@router.get("/feed/all", response_model=APIResponse[List[PostFeedItem]])
def get_global_feed(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数，最大100"),
    current_user_id: int = Query(None, description="当前用户ID，用于返回点赞状态"),
    db: Session = Depends(get_db)
):
    """
    获取全局信息流 - 所有用户的公开帖子
    
    返回包含作者信息、点赞状态、预览评论的完整帖子数据，
    前端可直接用于展示，无需额外请求。
    
    Args:
        page: 页码，从1开始，默认1
        page_size: 每页记录数，默认20，最大100
        current_user_id: 当前用户ID（可选），用于判断点赞状态
        db: 数据库会话
    
    Returns:
        APIResponse[List[PostFeedItem]]: 标准化响应
        - code: 状态码，200表示成功
        - message: 消息，"success"表示成功
        - data: 帖子列表，每个帖子包含：
            - 基础信息：id, title, content, created_at
            - 作者信息：author_id, author_name, author_avatar
            - 统计信息：like_count, comment_count
            - 状态信息：is_liked, has_more_comments
            - 预览评论：preview_comments（最多2条）
        - pagination: 分页信息
    
    Example:
        GET /api/v1/feeds/feed/all?page=1&page_size=20&current_user_id=123
        Response:
        {
            "code": 200,
            "message": "success",
            "data": [
                {
                    "id": 1,
                    "title": "今天天气真好",
                    "content": "适合出去走走！",
                    "created_at": "2024-01-01T10:00:00",
                    "author_id": 1,
                    "author_name": "三月七",
                    "author_avatar": "https://example.com/avatar.jpg",
                    "like_count": 15,
                    "comment_count": 8,
                    "is_liked": true,
                    "has_more_comments": true,
                    "preview_comments": [
                        {
                            "id": 1,
                            "content": "确实不错！",
                            "created_at": "2024-01-01T11:00:00",
                            "owner_id": 2,
                            "owner_name": "丹恒",
                            "owner_avatar": "...",
                            "like_count": 3
                        }
                    ]
                }
            ],
            "pagination": {
                "page": 1,
                "page_size": 20,
                "total": 100,
                "total_pages": 5,
                "has_next": true,
                "has_prev": false
            }
        }
    """
    try:
        response = feed_service.get_feed(
            db=db,
            page=page,
            page_size=page_size,
            current_user_id=current_user_id
        )
        return response
    except Exception as e:
        # 处理异常，返回错误响应
        raise HTTPException(status_code=500, detail=f"获取信息流失败: {str(e)}")


@router.get("/feed/user/{user_id}", response_model=APIResponse[List[PostFeedItem]])
def get_user_feed(
    user_id: int,
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数，最大100"),
    current_user_id: int = Query(None, description="当前用户ID，用于返回点赞状态"),
    db: Session = Depends(get_db)
):
    """
    获取指定用户的帖子流
    
    返回指定用户发布的帖子列表，包含完整的信息流数据。
    
    Args:
        user_id: 用户ID（路径参数）
        page: 页码，从1开始，默认1
        page_size: 每页记录数，默认20，最大100
        current_user_id: 当前用户ID（可选），用于判断点赞状态
        db: 数据库会话
    
    Returns:
        APIResponse[List[PostFeedItem]]: 标准化响应
    
    Raises:
        HTTPException: 
            - 404: 用户不存在
            - 500: 服务器内部错误
    
    Example:
        GET /api/v1/feeds/feed/user/123?page=1&page_size=20&current_user_id=456
    """
    try:
        response = feed_service.get_user_feed(
            db=db,
            user_id=user_id,
            page=page,
            page_size=page_size,
            current_user_id=current_user_id
        )
        return response
    except ValueError as e:
        # 用户不存在
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # 其他异常
        raise HTTPException(status_code=500, detail=f"获取用户帖子流失败: {str(e)}")
