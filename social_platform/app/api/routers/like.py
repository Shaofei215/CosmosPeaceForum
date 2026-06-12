# 点赞路由控制器
# 处理点赞相关的 API 请求
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from social_platform.app.admin.services.moderation_guard import ensure_action_allowed
from social_platform.app.api.deps import get_db, get_current_user
from social_platform.app.domains.user.models import User
from social_platform.app.domains.reaction.schemas import LikeToggleResponse
from social_platform.app.domains.reaction import application as like_service

router = APIRouter()


@router.post("/{post_id}/like", response_model=LikeToggleResponse, summary="点赞/取消点赞", description="切换对帖子的点赞状态。如果未点赞则点赞，如果已点赞则取消点赞。")
def toggle_like(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    点赞/取消点赞切换

    根据当前用户的点赞状态进行切换操作：
    - 如果该用户尚未点赞此帖子，则添加点赞
    - 如果该用户已经点赞此帖子，则取消点赞

    - **post_id**: 帖子 ID（路径参数）

    需要认证：是的（Bearer Token）
    - user_id 从 JWT Token 中自动获取，无需手动传入

    返回：包含帖子 ID、当前点赞总数、当前用户是否已点赞

    错误：
    - 404：帖子不存在
    - 400：重复操作异常（理论上不会发生）
    """
    ensure_action_allowed(db, current_user, "interaction")
    try:
        is_liked, like_count = like_service.toggle_like(
            post_id=post_id,
            user_id=current_user.id,
            db=db
        )

        return LikeToggleResponse(
            post_id=post_id,
            like_count=like_count,
            is_liked=is_liked
        )

    except like_service.PostNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except like_service.DuplicateLikeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{post_id}/like-status", summary="获取点赞状态", description="获取当前用户对指定帖子的点赞状态和帖子的总点赞数。")
def get_like_status(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取点赞状态

    查询当前登录用户对指定帖子的点赞状态和帖子总点赞数

    - **post_id**: 帖子 ID（路径参数）

    需要认证：是的（Bearer Token）
    - user_id 从 JWT Token 中自动获取

    返回：
    - is_liked: 当前用户是否已点赞
    - like_count: 帖子的总点赞数

    错误：
    - 404：帖子不存在
    """
    try:
        is_liked, like_count = like_service.get_like_status(
            post_id=post_id,
            user_id=current_user.id,
            db=db
        )

        return {
            "is_liked": is_liked,
            "like_count": like_count
        }

    except like_service.PostNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
