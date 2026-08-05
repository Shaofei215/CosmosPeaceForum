"""帖子点踩 API。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from social_platform.app.admin.services.moderation_guard import ensure_action_allowed
from social_platform.app.api.deps import get_agent_operation_source, get_current_user, get_db
from social_platform.app.domains.reaction import application as reaction_service
from social_platform.app.domains.reaction.schemas import (
    DislikeStatusResponse,
    DislikeToggleResponse,
)
from social_platform.app.domains.user.models import User


router = APIRouter()


@router.post(
    "/{post_id}/dislike",
    response_model=DislikeToggleResponse,
    summary="点踩/取消点踩",
)
def toggle_dislike(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    created_by_agent: bool = Depends(get_agent_operation_source),
) -> DislikeToggleResponse:
    """切换当前用户的点踩状态；达到配置阈值时自动归档帖子。"""

    ensure_action_allowed(db, current_user, "interaction")
    try:
        result = reaction_service.toggle_dislike(
            post_id,
            current_user.id,
            db,
            created_by_agent=created_by_agent,
        )
    except reaction_service.PostNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except reaction_service.SelfDislikeError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except reaction_service.DuplicateDislikeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except reaction_service.DislikeRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "60"},
        ) from exc

    return DislikeToggleResponse(
        post_id=post_id,
        dislike_count=result.dislike_count,
        is_disliked=result.is_disliked,
        like_count=result.like_count,
        is_liked=result.is_liked,
        archived=result.archived,
        created_by_agent=result.created_by_agent,
    )


@router.get(
    "/{post_id}/dislike-status",
    response_model=DislikeStatusResponse,
    summary="获取点踩状态",
)
def get_dislike_status(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DislikeStatusResponse:
    """读取当前用户是否已点踩以及帖子当前点踩总数。"""

    try:
        is_disliked, dislike_count, created_by_agent = reaction_service.get_dislike_status(
            post_id,
            current_user.id,
            db,
        )
    except reaction_service.PostNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DislikeStatusResponse(
        post_id=post_id,
        dislike_count=dislike_count,
        is_disliked=is_disliked,
        created_by_agent=created_by_agent,
    )
