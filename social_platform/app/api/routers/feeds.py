# 信息流路由控制器
# 处理信息流相关的 API 请求
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from social_platform.app.api.deps import get_db, get_current_user_optional
from social_platform.app.models.user import User
from social_platform.app.schemas.feed import PostFeedItem
from social_platform.app.schemas.response import APIResponse
from social_platform.app.services import feed_service

router = APIRouter()


@router.get("/feed/all", response_model=APIResponse[List[PostFeedItem]],
           summary="获取全局信息流", description="获取所有用户的公开帖子信息流，包含完整帖子数据、作者信息、点赞状态和预览评论。已登录用户可看到个性化的点赞状态。")
def get_global_feed(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数，最大100"),
    feed_type: str = Query(
        "recommended",
        description="信息流类型：recommended（推荐）、latest（最新）或 following（关注）"
    ),
    seed: str = Query(
        "default",
        description="推荐流重排种子；同一 seed 下分页稳定，不同 seed 会在 Top-N 候选池内换序"
    ),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    获取全局信息流

    返回所有用户的公开帖子信息，包含完整的帖子数据：
    - 基础信息：id、title、content、created_at
    - 作者信息：author_id、author_name、author_avatar
    - 统计信息：like_count、comment_count
    - 状态信息：is_liked（已登录用户）、has_more_comments
    - 预览评论：preview_comments（最多2条）

    - **page**: 页码，从1开始（默认 1）
    - **page_size**: 每页记录数（默认 20，最大 100）

    需要认证：否（可选认证，已登录时返回个性化的点赞状态）

    返回结构：
    - code: 状态码，200 表示成功
    - message: 消息，"success" 表示成功
    - data: 帖子列表
    - pagination: 分页信息（page、page_size、total、total_pages、has_next、has_prev）

    错误：
    - 500：服务器内部错误
    """
    try:
        current_user_id = current_user.id if current_user else None
        response = feed_service.get_feed(
            db=db,
            page=page,
            page_size=page_size,
            current_user_id=current_user_id,
            feed_type=feed_type,
            seed=seed,
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取信息流失败: {str(e)}")


@router.get("/feed/user/{user_id}", response_model=APIResponse[List[PostFeedItem]],
           summary="获取用户帖子流", description="获取指定用户发布的所有帖子信息流，包含完整的帖子数据。已登录用户可看到个性化的点赞状态。")
def get_user_feed(
    user_id: int,
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数，最大100"),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    获取指定用户的帖子信息流

    返回指定用户发布的所有帖子，包含完整的信息流数据

    - **user_id**: 用户 ID（路径参数）
    - **page**: 页码，从1开始（默认 1）
    - **page_size**: 每页记录数（默认 20，最大 100）

    需要认证：否（可选认证，已登录时返回个性化的点赞状态）

    返回结构：
    - code: 状态码，200 表示成功
    - message: 消息，"success" 表示成功
    - data: 帖子列表
    - pagination: 分页信息

    错误：
    - 404：用户不存在
    - 500：服务器内部错误
    """
    try:
        current_user_id = current_user.id if current_user else None
        response = feed_service.get_user_feed(
            db=db,
            user_id=user_id,
            page=page,
            page_size=page_size,
            current_user_id=current_user_id
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户帖子流失败: {str(e)}")
