"""帖子投币 API。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from social_platform.app.admin.services.moderation_guard import ensure_action_allowed
from social_platform.app.api.deps import get_agent_operation_source, get_current_user, get_db
from social_platform.app.domains.coin import application as coin_service
from social_platform.app.domains.coin.schemas import PostCoinResponse, PostCoinStatusResponse
from social_platform.app.domains.user.models import User


router = APIRouter()


@router.post(
    "/{post_id}/coin",
    response_model=PostCoinResponse,
    summary="给帖子投币",
)
def give_post_coin(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    created_by_agent: bool = Depends(get_agent_operation_source),
) -> PostCoinResponse:
    """把当前用户的一枚硬币转给指定帖子的作者。"""

    ensure_action_allowed(db, current_user, "interaction")
    try:
        coin_count, coin_balance = coin_service.give_post_coin(
            db,
            current_user.id,
            post_id,
            created_by_agent=created_by_agent,
        )
    except coin_service.PostNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except coin_service.SelfCoinError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except coin_service.DuplicateCoinError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except coin_service.InsufficientCoinBalanceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except coin_service.RecipientCoinBalanceLimitError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except coin_service.CoinRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "60"},
        ) from exc

    return PostCoinResponse(
        post_id=post_id,
        coin_count=coin_count,
        is_coined=True,
        coin_balance=coin_balance,
        created_by_agent=created_by_agent,
    )


@router.get(
    "/{post_id}/coin-status",
    response_model=PostCoinStatusResponse,
    summary="获取帖子投币状态",
)
def get_post_coin_status(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostCoinStatusResponse:
    """读取当前用户是否已投币，以及帖子硬币数和用户余额。"""

    try:
        is_coined, coin_count, coin_balance = coin_service.get_post_coin_status(
            db,
            current_user.id,
            post_id,
        )
    except coin_service.PostNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PostCoinStatusResponse(
        post_id=post_id,
        coin_count=coin_count,
        is_coined=is_coined,
        coin_balance=coin_balance,
    )
