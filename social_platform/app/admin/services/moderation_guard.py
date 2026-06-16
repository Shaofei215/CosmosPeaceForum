"""公开平台写操作的用户处罚状态校验服务。"""

from datetime import datetime
from typing import Literal, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.models.user_moderation import UserModeration
from social_platform.app.domains.user.models import User


RestrictionAction = Literal["publish", "comment", "interaction"]


def get_user_moderation(db: Session, user_id: int) -> Optional[UserModeration]:
    """读取用户处罚状态。"""

    return db.query(UserModeration).filter(UserModeration.user_id == user_id).first()


def is_account_banned(moderation: Optional[UserModeration]) -> bool:
    """判断用户账号是否处于永久封禁状态。"""

    return bool(moderation and moderation.account_banned_at)


def _account_ban_detail(db: Session, moderation: UserModeration) -> str:
    """构造账号封禁错误详情，并附带可用申诉邮箱。"""

    detail = moderation.account_ban_reason or "账号已被封禁"
    if not moderation.updated_by_admin_id:
        return detail

    admin = (
        db.query(PlatformAdminUser.email)
        .filter(PlatformAdminUser.id == moderation.updated_by_admin_id)
        .first()
    )
    if admin and admin[0]:
        return f"{detail}\n如有异议，请向{admin[0]}申诉。"
    return detail


def ensure_account_available(db: Session, user: User) -> None:
    """确保用户账号未被封禁，否则抛出 HTTP 403。"""

    moderation = get_user_moderation(db, user.id)
    if is_account_banned(moderation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_account_ban_detail(db, moderation),
        )


def ensure_action_allowed(db: Session, user: User, action: RestrictionAction) -> None:
    """确保用户指定动作未被封禁或临时限制，否则抛出 HTTP 403。"""

    moderation = get_user_moderation(db, user.id)
    if is_account_banned(moderation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_account_ban_detail(db, moderation),
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
