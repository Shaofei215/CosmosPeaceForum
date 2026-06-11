"""用户领域应用服务。"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from social_platform.app.domains.events import UserDeleted, UserUpdated
from social_platform.app.models.post import Post
from social_platform.app.models.user import User
from social_platform.app.schemas.user import CompleteProfileRequest, UserUpdate
from social_platform.app.shared.events import publish_domain_event
from social_platform.app.shared.unit_of_work import commit_session



class UserNotFoundError(Exception):
    """用户不存在异常。"""

    def __init__(self) -> None:
        super().__init__("用户不存在")


class UserPermissionError(Exception):
    """用户权限异常。"""

    def __init__(self) -> None:
        super().__init__("无权修改此用户")


class UsernameValidationError(Exception):
    """用户名校验异常。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ProfileAlreadyCompletedError(Exception):
    """资料已经完善异常。"""

    def __init__(self) -> None:
        super().__init__("用户名已设置，无法再次修改")


def _validate_username(username: str | None) -> str:
    """校验并规范化用户名。

    Args:
        username: 待校验用户名。

    Returns:
        str: 去除首尾空白后的用户名。

    Raises:
        UsernameValidationError: 当用户名为空或格式不合法时抛出。
    """

    if username is None:
        raise UsernameValidationError("用户名不能为空")

    normalized = username.strip()
    if not re.fullmatch(r"[a-zA-Z0-9_一-龥]+", normalized):
        raise UsernameValidationError("用户名只能包含字母、数字、下划线和中文")
    return normalized


def _ensure_username_unique(db: Session, username: str, user_id: int) -> None:
    """确认用户名未被其他用户占用。

    Args:
        db: 当前数据库会话。
        username: 待检查用户名。
        user_id: 当前用户 ID。

    Raises:
        UsernameValidationError: 当用户名已存在时抛出。
    """

    existing_user = db.query(User).filter(User.username == username, User.id != user_id).first()
    if existing_user:
        raise UsernameValidationError("用户名已存在")


def update_user(db: Session, current_user: User, user_id: int, user_update: UserUpdate) -> User:
    """更新用户资料并发布用户更新事件。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        user_id: 待更新用户 ID。
        user_update: 用户更新请求数据。

    Returns:
        User: 更新后的用户对象。
    """

    if current_user.id != user_id:
        raise UserPermissionError()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError()

    update_data = user_update.model_dump(exclude_unset=True)
    if "username" in update_data:
        username = _validate_username(update_data["username"])
        _ensure_username_unique(db, username, user_id)
        update_data["username"] = username

    for field, value in update_data.items():
        setattr(user, field, value)

    publish_domain_event(db, UserUpdated(user_id=user.id))
    commit_session(db)
    db.refresh(user)
    return user


def complete_profile(
    db: Session,
    current_user: User,
    user_id: int,
    profile_data: CompleteProfileRequest,
) -> User:
    """完善注册后的用户资料。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        user_id: 待完善资料的用户 ID。
        profile_data: 完善资料请求数据。

    Returns:
        User: 更新后的用户对象。
    """

    if current_user.id != user_id:
        raise UserPermissionError()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError()

    if user.username and not user.username.startswith("用户_"):
        raise ProfileAlreadyCompletedError()

    username = _validate_username(profile_data.username)
    _ensure_username_unique(db, username, user_id)
    user.username = username
    if profile_data.bio is not None:
        user.bio = profile_data.bio
    if profile_data.avatar_url is not None:
        user.avatar_url = profile_data.avatar_url

    publish_domain_event(db, UserUpdated(user_id=user.id))
    commit_session(db)
    db.refresh(user)
    return user


def delete_user(db: Session, current_user: User, user_id: int) -> None:
    """删除用户并发布用户删除事件。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        user_id: 待删除用户 ID。
    """

    if current_user.id != user_id:
        raise UserPermissionError()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError()

    post_ids = tuple(row[0] for row in db.query(Post.id).filter(Post.author_id == user_id).all())
    db.delete(user)
    publish_domain_event(db, UserDeleted(user_id=user_id, post_ids=post_ids))
    commit_session(db)
