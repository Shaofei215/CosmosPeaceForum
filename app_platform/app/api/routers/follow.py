# 关注路由控制器
# 处理关注相关的 API 请求
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional

from app_platform.app.admin.services.moderation_guard import ensure_action_allowed
from app_platform.app.api.deps import get_db, get_current_user, get_current_user_optional
from app_platform.app.models.user import User
from app_platform.app.models.follow import Follow
from app_platform.app.schemas.follow import (
    FollowToggleResponse,
    FollowStatusResponse,
    FollowUserItem,
)
from app_platform.app.schemas.response import PaginationInfo, APIResponse
from app_platform.app.services import follow_service

router = APIRouter()


# ==================== 需要认证的个人接口 ====================
# 注意：这些路由必须放在 /{user_id}/... 路由之前
# 因为 FastAPI 按路由定义顺序匹配，如果 /me/following 在 /{user_id}/following 之后
# 则 /users/me/following 会被 /{user_id}/following 先匹配，导致 "me" 无法转换为 int


@router.get(
    "/me/following",
    summary="获取当前用户关注列表",
    description="获取当前登录用户的关注列表，需要认证"
)
def get_my_following(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数，最大 100"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的关注列表（需认证）

    查询当前登录用户关注的所有用户，支持分页

    - **page**: 页码，默认 1
    - **page_size**: 每页记录数，默认 20，最大 100

    需要认证：是的（Bearer Token）

    返回：用户列表和分页信息

    Note:
        返回的 is_following 字段始终为 True（因为是当前用户主动关注的）
        返回的 is_followed_by 字段需要根据实际情况确定
    """
    follows, total = follow_service.get_following_list(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        current_user_id=current_user.id
    )

    following_ids = [f.following_id for f in follows]
    following_status = {}
    if following_ids:
        following_status = follow_service.get_follow_status_batch(
            db=db,
            current_user_id=current_user.id,
            target_user_ids=following_ids
        )

    items = []
    for follow in follows:
        user = follow.following
        status = following_status.get(user.id, {})
        items.append(FollowUserItem(
            id=user.id,
            username=user.username,
            bio=user.bio,
            avatar_url=user.avatar_url,
            is_following=True,
            is_followed_by=status.get("is_followed_by", False),
            created_at=follow.created_at
        ))

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return APIResponse(
        data=items,
        pagination=PaginationInfo(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
    )


@router.get(
    "/me/followers",
    summary="获取当前用户粉丝列表",
    description="获取当前登录用户的粉丝列表，需要认证"
)
def get_my_followers(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数，最大 100"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的粉丝列表（需认证）

    查询当前登录用户的所有粉丝，支持分页

    - **page**: 页码，默认 1
    - **page_size**: 每页记录数，默认 20，最大 100

    需要认证：是的（Bearer Token）

    返回：用户列表和分页信息

    Note:
        返回的 is_followed_by 字段始终为 True（因为是关注当前用户的）
        返回的 is_following 字段需要根据实际情况确定
    """
    follows, total = follow_service.get_followers_list(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        current_user_id=current_user.id
    )

    follower_ids = [f.follower_id for f in follows]
    following_status = {}
    if follower_ids:
        following_status = follow_service.get_follow_status_batch(
            db=db,
            current_user_id=current_user.id,
            target_user_ids=follower_ids
        )

    items = []
    for follow in follows:
        user = follow.follower
        status = following_status.get(user.id, {})
        items.append(FollowUserItem(
            id=user.id,
            username=user.username,
            bio=user.bio,
            avatar_url=user.avatar_url,
            is_following=status.get("is_following", False),
            is_followed_by=True,
            created_at=follow.created_at
        ))

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return APIResponse(
        data=items,
        pagination=PaginationInfo(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
    )


# ==================== 需要认证的用户操作接口 ====================


@router.post(
    "/{user_id}/follow",
    response_model=FollowToggleResponse,
    summary="关注/取消关注用户",
    description="Toggle 模式：已关注则取消关注，未关注则关注。操作后返回最新的计数。"
)
def toggle_follow(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    关注/取消关注切换

    根据当前用户的关注状态进行切换操作：
    - 如果该用户尚未关注此用户，则添加关注
    - 如果该用户已经关注此用户，则取消关注

    - **user_id**: 被关注用户 ID（路径参数）

    需要认证：是的（Bearer Token）

    返回：包含用户 ID、当前关注状态、粉丝数、关注数

    错误：
    - 400：不能关注自己
    - 404：用户不存在
    """
    ensure_action_allowed(db, current_user, "interaction")
    try:
        is_following, followers_count, following_count = follow_service.toggle_follow(
            db=db,
            follower_id=current_user.id,
            following_id=user_id
        )

        return FollowToggleResponse(
            user_id=user_id,
            is_following=is_following,
            followers_count=followers_count,
            following_count=following_count
        )

    except follow_service.SelfFollowError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except follow_service.UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{user_id}/follow-status",
    response_model=FollowStatusResponse,
    summary="获取关注状态",
    description="获取当前用户与指定用户之间的关注关系"
)
def get_follow_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取关注状态

    查询当前登录用户与指定用户之间的关注关系

    - **user_id**: 目标用户 ID（路径参数）

    需要认证：是的（Bearer Token）

    返回：
    - is_following: 当前用户是否关注了目标用户
    - is_followed_by: 目标用户是否关注了当前用户
    - is_mutual: 是否互相关注

    错误：
    - 404：用户不存在
    """
    status = follow_service.get_follow_status(
        db=db,
        current_user_id=current_user.id,
        target_user_id=user_id
    )

    return FollowStatusResponse(user_id=user_id, **status)


# ==================== 公开接口 ====================


@router.get(
    "/{user_id}/following",
    summary="获取用户关注列表",
    description="获取指定用户的关注列表，公开接口"
)
def get_following(
    user_id: int,
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数，最大 100"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    获取用户的关注列表（公开接口）

    查询指定用户关注的所有用户，支持分页
    如果当前用户已登录，会标注当前用户是否关注了列表中的用户

    - **user_id**: 目标用户 ID（路径参数）
    - **page**: 页码，默认 1
    - **page_size**: 每页记录数，默认 20，最大 100

    需要认证：否（但有 token 时会提供更多上下文信息）

    返回：用户列表和分页信息
    """
    follows, total = follow_service.get_following_list(
        db=db,
        user_id=user_id,
        page=page,
        page_size=page_size,
        current_user_id=current_user.id if current_user else None
    )

    following_ids = [f.following_id for f in follows]
    following_status = {}
    if current_user and following_ids:
        following_status = follow_service.get_follow_status_batch(
            db=db,
            current_user_id=current_user.id,
            target_user_ids=following_ids
        )

    items = []
    for follow in follows:
        user = follow.following
        status = following_status.get(user.id, {})
        items.append(FollowUserItem(
            id=user.id,
            username=user.username,
            bio=user.bio,
            avatar_url=user.avatar_url,
            is_following=status.get("is_following", True),
            is_followed_by=status.get("is_followed_by", False),
            created_at=follow.created_at
        ))

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return APIResponse(
        data=items,
        pagination=PaginationInfo(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
    )


@router.get(
    "/{user_id}/followers",
    summary="获取用户粉丝列表",
    description="获取指定用户的粉丝列表，公开接口"
)
def get_followers(
    user_id: int,
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数，最大 100"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    获取用户的粉丝列表（公开接口）

    查询指定用户的所有粉丝，支持分页
    如果当前用户已登录，会标注当前用户是否关注了列表中的用户

    - **user_id**: 目标用户 ID（路径参数）
    - **page**: 页码，默认 1
    - **page_size**: 每页记录数，默认 20，最大 100

    需要认证：否（但有 token 时会提供更多上下文信息）

    返回：用户列表和分页信息
    """
    follows, total = follow_service.get_followers_list(
        db=db,
        user_id=user_id,
        page=page,
        page_size=page_size,
        current_user_id=current_user.id if current_user else None
    )

    follower_ids = [f.follower_id for f in follows]
    following_status = {}
    if current_user and follower_ids:
        following_status = follow_service.get_follow_status_batch(
            db=db,
            current_user_id=current_user.id,
            target_user_ids=follower_ids
        )

    items = []
    for follow in follows:
        user = follow.follower
        status = following_status.get(user.id, {})
        items.append(FollowUserItem(
            id=user.id,
            username=user.username,
            bio=user.bio,
            avatar_url=user.avatar_url,
            is_following=status.get("is_following", False),
            is_followed_by=status.get("is_followed_by", True),
            created_at=follow.created_at
        ))

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return APIResponse(
        data=items,
        pagination=PaginationInfo(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
    )
