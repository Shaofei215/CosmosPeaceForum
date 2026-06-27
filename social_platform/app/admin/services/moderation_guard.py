"""公开平台写操作的用户处罚状态校验服务。"""

from datetime import datetime
from social_platform.app.core.timezone import local_now
from typing import Literal, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from social_platform.app.admin.models.user_moderation import UserModeration
from social_platform.app.domains.user.models import User


RestrictionAction = Literal["publish", "comment", "interaction"]
ProfileField = Literal["avatar", "username", "bio"]


def get_user_moderation(db: Session, user_id: int) -> Optional[UserModeration]:
    """读取用户处罚状态。"""

    return db.query(UserModeration).filter(UserModeration.user_id == user_id).first()


def is_account_banned(moderation: Optional[UserModeration]) -> bool:
    """判断用户账号是否处于封禁状态。"""

    return bool(moderation and moderation.account_banned_at)


def _account_ban_detail(moderation: UserModeration) -> str:
    """构造账号封禁后的操作限制错误详情。"""

    return moderation.account_ban_reason or "账号已被封禁，当前操作不可执行"


def ensure_account_available(db: Session, user: User) -> None:
    """确保用户账号未被封禁，否则抛出 HTTP 403。"""

    moderation = get_user_moderation(db, user.id)
    if is_account_banned(moderation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_account_ban_detail(moderation),
        )


def ensure_action_allowed(db: Session, user: User, action: RestrictionAction) -> None:
    """确保用户指定动作未被封禁或临时限制，否则抛出 HTTP 403。"""

    moderation = get_user_moderation(db, user.id)
    if is_account_banned(moderation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_account_ban_detail(moderation),
        )
    if moderation is None:
        return

    now = local_now()
    field = f"{action}_banned_until"
    reason_field = f"{action}_ban_reason"
    banned_until = getattr(moderation, field, None)
    permanently_banned = bool(getattr(moderation, f"{action}_permanently_banned", False))
    if permanently_banned or (banned_until and banned_until > now):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=getattr(moderation, reason_field, None) or "当前操作已被临时限制",
        )


def ensure_profile_field_allowed(db: Session, user: User, field: ProfileField) -> None:
    """按实际修改的资料字段检查头像、用户名或签名限制。

    Args:
        db: 当前 SQLAlchemy 会话。
        user: 发起资料写入的当前用户。
        field: 实际要修改的资料字段。

    Returns:
        None: 字段可修改时正常返回。

    Raises:
        HTTPException: 账号封禁或字段仍在临时、永久限制中时抛出 403。
    """

    moderation = get_user_moderation(db, user.id)
    if is_account_banned(moderation):
        assert moderation is not None
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_account_ban_detail(moderation))
    if moderation is None:
        return
    banned_until = getattr(moderation, f"{field}_banned_until", None)
    permanent = bool(getattr(moderation, f"{field}_permanently_banned", False))
    if permanent or (banned_until and banned_until > local_now()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=getattr(moderation, f"{field}_ban_reason", None) or "当前资料字段已被限制",
        )
