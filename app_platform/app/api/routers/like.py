# 点赞路由控制器
# 处理点赞相关的 API 请求
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_db
from app.schemas.like import LikeToggleResponse
from app.services import like_service

# 创建 API 路由器
router = APIRouter()


@router.post("/{post_id}/like", response_model=LikeToggleResponse)
def toggle_like(
    post_id: int,
    user_id: int = Query(..., description="当前用户 ID"),
    db: Session = Depends(get_db)
):
    """
    点赞/取消点赞切换
    
    根据当前用户的点赞状态进行切换：
    - 如果未点赞，则点赞
    - 如果已点赞，则取消点赞
    
    Args:
        post_id: 帖子 ID（路径参数）
        user_id: 当前用户 ID（查询参数）
        db: 数据库会话（依赖注入）
    
    Returns:
        LikeToggleResponse: 包含帖子 ID、点赞总数、当前用户点赞状态
    
    Raises:
        HTTPException: 
            - 404: 帖子不存在
    
    Example:
        POST /posts/1/like?user_id=123
        Response: {
            "post_id": 1,
            "like_count": 10,
            "is_liked": true
        }
    """
    try:
        # 调用点赞服务
        is_liked, like_count = like_service.toggle_like(
            post_id=post_id,
            user_id=user_id,
            db=db
        )
        
        # 返回响应
        return LikeToggleResponse(
            post_id=post_id,
            like_count=like_count,
            is_liked=is_liked
        )
    
    except like_service.PostNotFoundError as e:
        # 帖子不存在，返回 404
        raise HTTPException(status_code=404, detail=str(e))
    
    except like_service.DuplicateLikeError as e:
        # 重复点赞（理论上不会发生），返回 400
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{post_id}/like-status")
def get_like_status(
    post_id: int,
    user_id: int = Query(..., description="当前用户 ID"),
    db: Session = Depends(get_db)
):
    """
    获取点赞状态
    
    查询指定用户对指定帖子的点赞状态和帖子的总点赞数。
    
    Args:
        post_id: 帖子 ID（路径参数）
        user_id: 当前用户 ID（查询参数）
        db: 数据库会话（依赖注入）
    
    Returns:
        dict: 包含是否已点赞和点赞总数
    
    Raises:
        HTTPException:
            - 404: 帖子不存在
    
    Example:
        GET /posts/1/like-status?user_id=123
        Response: {
            "is_liked": true,
            "like_count": 10
        }
    """
    try:
        # 调用点赞状态查询服务
        is_liked, like_count = like_service.get_like_status(
            post_id=post_id,
            user_id=user_id,
            db=db
        )
        
        # 返回响应
        return {
            "is_liked": is_liked,
            "like_count": like_count
        }
    
    except like_service.PostNotFoundError as e:
        # 帖子不存在，返回 404
        raise HTTPException(status_code=404, detail=str(e))
