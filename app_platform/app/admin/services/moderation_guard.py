from datetime import datetime
from typing import Literal, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app_platform.app.admin.models.user_moderation import UserModeration
from app_platform.app.models.user import User


RestrictionAction = Literal["publish", "comment", "interaction"]


def get_user_moderation(db: Session, user_id: int) -> Optional[UserModeration]:
    return db.query(UserModeration).filter(UserModeration.user_id == user_id).first()


def is_account_banned(moderation: Optional[UserModeration]) -> bool:
    return bool(moderation and moderation.account_banned_at)


def ensure_account_available(db: Session, user: User) -> None:
    moderation = get_user_moderation(db, user.id)
    if is_account_banned(moderation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=moderation.account_ban_reason or "账号已被封禁",
        )


def ensure_action_allowed(db: Session, user: User, action: RestrictionAction) -> None:
    moderation = get_user_moderation(db, user.id)
    if is_account_banned(moderation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=moderation.account_ban_reason or "账号已被封禁",
        )
    if moderation is None:
        return

    now = datetime.utcnow()
    field = f"{action}_banned_until"
    reason_field = f"{action}_ban_reason"
    banned_until = getattr(moderation, field, None)
    if banned_until and banned_until > now:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=getattr(moderation, reason_field, None) or "当前操作已被临时限制",
        )
