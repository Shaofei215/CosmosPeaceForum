"""管理端用户处罚与仪表盘统计服务。"""

from datetime import datetime, timedelta
from social_platform.app.core.timezone import local_now
from typing import Literal, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.models.user_moderation import UserModeration
from social_platform.app.admin.schemas import (
    DashboardStatsResponse,
    UserModerationBatchUpdateRequest,
    UserModerationBatchUpdateResponse,
    UserModerationResponse,
    UserModerationStatusResponse,
    UserModerationUpdateRequest,
    UserViolationBatchRequest,
    UserWithModerationResponse,
)
from social_platform.app.admin.services.log_service import create_operation_log
from social_platform.app.domains.comment.models import Comment, CommentLike
from social_platform.app.domains.follow.models import Follow
from social_platform.app.domains.notification.system import create_user_moderation_notice
from social_platform.app.domains.notification import application as notification_service
from social_platform.app.domains.content_safety.models import UserViolationEvent
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.reaction.models import Like
from social_platform.app.domains.user.models import User


_RESTRICTION_LABELS = {
    "publish": "发帖功能",
    "comment": "评论功能",
    "interaction": "互动功能",
}

ViolationCategory = Literal[
    "publish", "comment", "interaction", "avatar", "username", "bio", "account"
]
COUNTED_VIOLATION_CATEGORIES = ("publish", "comment", "interaction", "avatar", "username", "bio")
VIOLATION_LABELS = {
    "publish": "发帖",
    "comment": "评论",
    "interaction": "互动",
    "avatar": "头像",
    "username": "用户名",
    "bio": "签名",
    "account": "账号",
}
DEFAULT_VIOLATION_REASONS = {
    category: f"{label}违反社区规则" for category, label in VIOLATION_LABELS.items()
}

_last_cpu_snapshot: tuple[int, int] | None = None


def moderation_to_status(
    moderation: Optional[UserModeration],
) -> UserModerationStatusResponse:
    """把用户处罚模型转换为管理端响应状态。"""

    if moderation is None:
        return UserModerationStatusResponse()
    return UserModerationStatusResponse(
        account_banned=bool(moderation.account_banned_at),
        account_banned_at=moderation.account_banned_at,
        account_ban_reason=moderation.account_ban_reason,
        publish_banned_until=moderation.publish_banned_until,
        publish_violation_count=moderation.publish_violation_count,
        publish_permanently_banned=moderation.publish_permanently_banned,
        publish_ban_reason=moderation.publish_ban_reason,
        comment_banned_until=moderation.comment_banned_until,
        comment_violation_count=moderation.comment_violation_count,
        comment_permanently_banned=moderation.comment_permanently_banned,
        comment_ban_reason=moderation.comment_ban_reason,
        interaction_banned_until=moderation.interaction_banned_until,
        interaction_violation_count=moderation.interaction_violation_count,
        interaction_permanently_banned=moderation.interaction_permanently_banned,
        interaction_ban_reason=moderation.interaction_ban_reason,
        avatar_banned_until=moderation.avatar_banned_until,
        avatar_violation_count=moderation.avatar_violation_count,
        avatar_permanently_banned=moderation.avatar_permanently_banned,
        avatar_ban_reason=moderation.avatar_ban_reason,
        username_banned_until=moderation.username_banned_until,
        username_violation_count=moderation.username_violation_count,
        username_permanently_banned=moderation.username_permanently_banned,
        username_ban_reason=moderation.username_ban_reason,
        bio_banned_until=moderation.bio_banned_until,
        bio_violation_count=moderation.bio_violation_count,
        bio_permanently_banned=moderation.bio_permanently_banned,
        bio_ban_reason=moderation.bio_ban_reason,
        updated_at=moderation.updated_at,
    )


def apply_user_violation(
    db: Session,
    user_id: int,
    category: ViolationCategory,
    admin: PlatformAdminUser,
    reason: Optional[str] = None,
    *,
    source_type: str = "manual",
    source_id: Optional[int] = None,
    notify_user: bool = True,
    commit: bool = True,
) -> tuple[UserModeration, UserViolationEvent]:
    """登记违规、执行处罚和资料撤下，并在同一事务创建事件与通知。

    内容来源使用唯一去重键，保证同一帖子或评论只累计一次。账号违规禁止普通写
    操作并撤下全部资料，但不修改六类累计次数，管理员或申诉流程可以解除封禁。

    Args:
        db: 当前 SQLAlchemy 会话。
        user_id: 被处罚用户 ID。
        category: 七类违规动作之一，其中账号违规不参与累计。
        admin: 执行处罚的管理员或 LLM 系统管理员。
        reason: 可选原因，空值使用类别默认原因。
        source_type: 处罚来源类型，帖子和评论来源参与去重。
        source_id: 来源内容 ID。
        notify_user: 是否生成可申诉的处罚通知。
        commit: 是否由本函数提交；组合用例传 False 以共享事务。

    Returns:
        tuple[UserModeration, UserViolationEvent]: 最新状态与本次或已存在的去重事件。

    Raises:
        ValueError: 用户不存在时抛出。
        sqlalchemy.exc.IntegrityError: 默认用户名被占用或数据库约束冲突时抛出。
    """

    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if user is None:
        raise ValueError("用户不存在")
    dedup_key = (
        f"{source_type}:{source_id}:{category}"
        if source_id is not None and source_type in {"post", "comment"}
        else None
    )
    if dedup_key:
        existing = db.query(UserViolationEvent).filter(
            UserViolationEvent.dedup_key == dedup_key
        ).first()
        if existing is not None:
            moderation = get_or_create_moderation(db, user_id, admin.id)
            return moderation, existing

    moderation = get_or_create_moderation(db, user_id, admin.id)
    moderation = (
        db.query(UserModeration)
        .filter(UserModeration.user_id == user_id)
        .with_for_update()
        .one()
    )
    now = local_now()
    normalized_reason = (reason or "").strip() or DEFAULT_VIOLATION_REASONS[category]
    violation_count: Optional[int] = None
    restriction_until: Optional[datetime] = None
    is_permanent = False

    if category == "account":
        moderation.account_banned_at = now
        moderation.account_ban_reason = normalized_reason
        user.avatar_url = None
        user.username = f"用户_{user.id}"
        user.bio = None
    else:
        count_field = f"{category}_violation_count"
        violation_count = int(getattr(moderation, count_field) or 0) + 1
        setattr(moderation, count_field, violation_count)
        is_permanent = violation_count >= 4
        if not is_permanent:
            restriction_until = now + timedelta(days=(1, 7, 30)[violation_count - 1])
        setattr(moderation, f"{category}_banned_until", restriction_until)
        setattr(moderation, f"{category}_permanently_banned", is_permanent)
        setattr(moderation, f"{category}_ban_reason", normalized_reason)
        if category == "avatar":
            user.avatar_url = None
        elif category == "username":
            user.username = f"用户_{user.id}"
        elif category == "bio":
            user.bio = None

    event = UserViolationEvent(
        user_id=user_id,
        category=category,
        violation_count=violation_count,
        reason=normalized_reason,
        source_type=source_type,
        source_id=source_id,
        dedup_key=dedup_key,
        created_by_admin_id=admin.id,
        restriction_until=restriction_until,
        is_permanent=is_permanent,
    )
    db.add(event)
    db.flush()
    setattr(moderation, f"{category}_current_event_id", event.id)
    moderation.updated_at = now
    moderation.updated_by_admin_id = admin.id

    if notify_user:
        if source_type in {"post", "comment"}:
            content = _append_reason("你的内容因违反社区规则已被管理端处理。", normalized_reason)
        elif category == "account":
            content = _append_reason("你的账号已被封禁，公开资料已撤下。", normalized_reason)
        elif is_permanent:
            content = _append_reason(f"你的{VIOLATION_LABELS[category]}功能已被永久限制。", normalized_reason)
        else:
            assert restriction_until is not None
            content = _append_reason(
                f"你的{VIOLATION_LABELS[category]}功能已被限制至 {_format_until(restriction_until)}。",
                normalized_reason,
            )
        notification = notification_service.create_notification(
            db=db,
            recipient_id=user_id,
            sender_id=None,
            notification_type="moderation",
            resource_type=source_type if source_type in {"post", "comment"} else "user",
            resource_id=source_id if source_id is not None else user_id,
            source_content=content,
            truncate_source_content=False,
        )
        db.flush()
        event.notification_id = notification.id if notification is not None else None

    create_operation_log(
        db,
        admin,
        action="apply_user_violation",
        target_type="user",
        target_id=user_id,
        details={
            "category": category,
            "reason": normalized_reason,
            "violation_count": violation_count,
            "source_type": source_type,
            "source_id": source_id,
        },
    )
    if commit:
        db.commit()
        db.refresh(moderation)
        db.refresh(event)
    return moderation, event


def release_violation_event(
    db: Session,
    event_id: int,
    admin: PlatformAdminUser,
    *,
    reverse_violation_count: bool = False,
    commit: bool = True,
) -> bool:
    """解除事件仍对应的当前限制，并可在纠错场景撤销一次违规计数。

    Args:
        db: 当前 SQLAlchemy 会话。
        event_id: 申诉或内容恢复所对应的违规事件 ID。
        admin: 执行解除的管理员。
        reverse_violation_count: 申诉通过或内容恢复时是否撤销该事件对应的一次计数。
        commit: 是否立即提交事务。

    Returns:
        bool: 事件仍是当前处罚并成功解除时为 True，否则为 False。
    """

    event = db.query(UserViolationEvent).filter(UserViolationEvent.id == event_id).first()
    if event is None:
        return False
    moderation = get_or_create_moderation(db, event.user_id, admin.id)
    current_event_field = f"{event.category}_current_event_id"
    released = getattr(moderation, current_event_field, None) == event.id
    if released:
        if event.category == "account":
            moderation.account_banned_at = None
            moderation.account_ban_reason = None
        else:
            setattr(moderation, f"{event.category}_banned_until", None)
            setattr(moderation, f"{event.category}_permanently_banned", False)
            setattr(moderation, f"{event.category}_ban_reason", None)
        setattr(moderation, current_event_field, None)
        moderation.updated_at = local_now()
        moderation.updated_by_admin_id = admin.id
    if (
        reverse_violation_count
        and event.violation_count is not None
        and event.violation_count_reversed_at is None
        and event.category in COUNTED_VIOLATION_CATEGORIES
    ):
        count_field = f"{event.category}_violation_count"
        current_count = int(getattr(moderation, count_field) or 0)
        setattr(moderation, count_field, max(0, current_count - 1))
        event.violation_count_reversed_at = local_now()
        moderation.updated_at = local_now()
        moderation.updated_by_admin_id = admin.id
    event.released_at = local_now()
    event.released_by_admin_id = admin.id
    if commit:
        db.commit()
    return released


def release_current_user_restriction(
    db: Session,
    user_id: int,
    category: ViolationCategory,
    admin: PlatformAdminUser,
) -> UserModeration:
    """主动解除用户当前单项管控，不修改对应违规累计次数。

    Args:
        db: 当前 SQLAlchemy 会话。
        user_id: 被解除管控的用户 ID。
        category: 需要解除的账号或功能类别。
        admin: 执行解除操作的管理员。

    Returns:
        UserModeration: 解除后的完整用户管控状态。

    Raises:
        ValueError: 用户、管控状态不存在，或指定类别当前未受管控时抛出。
    """

    if db.query(User.id).filter(User.id == user_id).first() is None:
        raise ValueError("用户不存在")
    moderation = db.query(UserModeration).filter(UserModeration.user_id == user_id).first()
    if moderation is None:
        raise ValueError("该用户当前没有管控状态")

    current_event_id = getattr(moderation, f"{category}_current_event_id", None)
    if category == "account":
        active = moderation.account_banned_at is not None
    else:
        banned_until = getattr(moderation, f"{category}_banned_until", None)
        active = bool(
            getattr(moderation, f"{category}_permanently_banned", False)
            or (banned_until and banned_until > local_now())
        )
    if not active:
        raise ValueError("该类别当前未受管控")

    if current_event_id is not None:
        release_violation_event(db, current_event_id, admin, commit=False)
    elif category == "account":
        moderation.account_banned_at = None
        moderation.account_ban_reason = None
    else:
        setattr(moderation, f"{category}_banned_until", None)
        setattr(moderation, f"{category}_permanently_banned", False)
        setattr(moderation, f"{category}_ban_reason", None)

    setattr(moderation, f"{category}_current_event_id", None)
    moderation.updated_at = local_now()
    moderation.updated_by_admin_id = admin.id
    label = "账号封禁" if category == "account" else f"{VIOLATION_LABELS[category]}限制"
    create_user_moderation_notice(db, user_id, f"你的{label}已解除。")
    create_operation_log(
        db,
        admin,
        action="release_user_restriction",
        target_type="user",
        target_id=user_id,
        details={"category": category, "event_id": current_event_id},
    )
    db.commit()
    db.refresh(moderation)
    return moderation


def apply_users_violation(
    db: Session,
    request: UserViolationBatchRequest,
    admin: PlatformAdminUser,
) -> UserModerationBatchUpdateResponse:
    """在单一事务内为一组用户登记同类违规。

    Args:
        db: 当前 SQLAlchemy 会话。
        request: 用户 ID、违规类别和可选原因。
        admin: 执行批量处罚的管理员。

    Returns:
        UserModerationBatchUpdateResponse: 更新数量和每个用户的最新处罚状态。

    Raises:
        ValueError: 任一用户不存在时在写入前抛出。
    """

    existing_ids = {
        row[0] for row in db.query(User.id).filter(User.id.in_(request.user_ids)).all()
    }
    missing_ids = sorted(set(request.user_ids) - existing_ids)
    if missing_ids:
        raise ValueError(f"用户不存在：{', '.join(str(item) for item in missing_ids)}")
    moderations = [
        apply_user_violation(
            db,
            user_id,
            request.category,
            admin,
            request.reason,
            source_type="batch",
            commit=False,
        )[0]
        for user_id in request.user_ids
    ]
    db.commit()
    return UserModerationBatchUpdateResponse(
        updated_count=len(moderations),
        items=[
            UserModerationResponse(
                user_id=item.user_id,
                **moderation_to_status(item).model_dump(),
            )
            for item in moderations
        ],
    )


def get_or_create_moderation(db: Session, user_id: int, admin_id: int) -> UserModeration:
    """读取或创建用户处罚状态记录。"""

    moderation = db.query(UserModeration).filter(UserModeration.user_id == user_id).first()
    if moderation is not None:
        return moderation
    moderation = UserModeration(user_id=user_id, updated_by_admin_id=admin_id)
    db.add(moderation)
    db.flush()
    return moderation


def update_user_moderation(
    db: Session,
    user_id: int,
    request: UserModerationUpdateRequest,
    admin: PlatformAdminUser,
) -> UserModeration:
    """更新单个用户的处罚状态并记录操作日志。"""

    moderation = _apply_user_moderation_update(db, user_id, request, admin)
    create_operation_log(
        db,
        admin,
        action="update_user_moderation",
        target_type="user",
        target_id=user_id,
        details=request.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    db.refresh(moderation)
    return moderation


def update_users_moderation(
    db: Session,
    request: UserModerationBatchUpdateRequest,
    admin: PlatformAdminUser,
) -> UserModerationBatchUpdateResponse:
    """批量更新用户处罚状态并返回更新摘要。"""

    existing_user_ids = {
        row[0]
        for row in db.query(User.id).filter(User.id.in_(request.user_ids)).all()
    }
    missing_user_ids = sorted(set(request.user_ids) - existing_user_ids)
    if missing_user_ids:
        raise ValueError(f"用户不存在：{', '.join(str(user_id) for user_id in missing_user_ids)}")

    moderations = [
        _apply_user_moderation_update(db, user_id, request.moderation, admin)
        for user_id in request.user_ids
    ]
    details = request.moderation.model_dump(mode="json", exclude_unset=True)
    create_operation_log(
        db,
        admin,
        action="batch_update_user_moderation",
        target_type="user",
        target_id=None,
        details={"user_ids": request.user_ids, "moderation": details},
    )
    db.commit()
    for moderation in moderations:
        db.refresh(moderation)
    return UserModerationBatchUpdateResponse(
        updated_count=len(moderations),
        items=[
            UserModerationResponse(
                user_id=moderation.user_id,
                **moderation_to_status(moderation).model_dump(),
            )
            for moderation in moderations
        ],
    )


def _apply_user_moderation_update(
    db: Session,
    user_id: int,
    request: UserModerationUpdateRequest,
    admin: PlatformAdminUser,
) -> UserModeration:
    """应用用户处罚字段变更并生成必要通知。"""

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("用户不存在")

    moderation = get_or_create_moderation(db, user_id, admin.id)
    previous_account_banned = bool(moderation.account_banned_at)
    previous_account_reason = moderation.account_ban_reason
    previous_restrictions = {
        "publish": (moderation.publish_banned_until, moderation.publish_ban_reason),
        "comment": (moderation.comment_banned_until, moderation.comment_ban_reason),
        "interaction": (moderation.interaction_banned_until, moderation.interaction_ban_reason),
    }
    if request.account_banned is not None:
        moderation.account_banned_at = local_now() if request.account_banned else None
        moderation.account_ban_reason = (
            request.account_ban_reason if request.account_banned else None
        )
    fields_set = request.model_fields_set
    if "publish_banned_until" in fields_set:
        moderation.publish_banned_until = request.publish_banned_until
        moderation.publish_ban_reason = request.publish_ban_reason
    if "comment_banned_until" in fields_set:
        moderation.comment_banned_until = request.comment_banned_until
        moderation.comment_ban_reason = request.comment_ban_reason
    if "interaction_banned_until" in fields_set:
        moderation.interaction_banned_until = request.interaction_banned_until
        moderation.interaction_ban_reason = request.interaction_ban_reason

    moderation.updated_at = local_now()
    moderation.updated_by_admin_id = admin.id
    _notify_user_moderation_changes(
        db=db,
        user_id=user_id,
        request=request,
        previous_account_banned=previous_account_banned,
        previous_account_reason=previous_account_reason,
        previous_restrictions=previous_restrictions,
        admin=admin,
    )
    return moderation


def _format_until(value: datetime) -> str:
    """格式化临时限制截止时间。"""

    return value.strftime("%Y-%m-%d %H:%M")


def _append_reason(content: str, reason: Optional[str]) -> str:
    """在通知正文中附加处罚原因。"""

    if reason:
        return f"{content}\n原因：{reason}"
    return content


def _create_user_moderation_notification(
    db: Session,
    user_id: int,
    content: str,
) -> None:
    """创建用户处罚系统通知。"""

    create_user_moderation_notice(db, user_id, content)


def _notify_user_moderation_changes(
    db: Session,
    user_id: int,
    request: UserModerationUpdateRequest,
    previous_account_banned: bool,
    previous_account_reason: Optional[str],
    previous_restrictions: dict[str, tuple[Optional[datetime], Optional[str]]],
    admin: PlatformAdminUser,
) -> None:
    """根据处罚前后状态差异向用户发送通知。"""

    if request.account_banned is not None:
        current_reason = request.account_ban_reason if request.account_banned else None
        if request.account_banned and (
            not previous_account_banned or current_reason != previous_account_reason
        ):
            _create_user_moderation_notification(
                db,
                user_id,
                _append_reason("你的账号已被封禁。", current_reason),
            )
        elif previous_account_banned and not request.account_banned:
            _create_user_moderation_notification(db, user_id, "你的账号封禁已解除。")

    fields_set = request.model_fields_set
    for action, label in _RESTRICTION_LABELS.items():
        until_field = f"{action}_banned_until"
        reason_field = f"{action}_ban_reason"
        if until_field not in fields_set:
            continue

        previous_until, previous_reason = previous_restrictions[action]
        current_until = getattr(request, until_field)
        current_reason = getattr(request, reason_field)
        if current_until == previous_until and current_reason == previous_reason:
            continue

        if current_until is None:
            if previous_until is not None:
                _create_user_moderation_notification(db, user_id, f"你的{label}限制已解除。")
            continue

        if current_until <= local_now():
            continue

        content = f"你的{label}已被限制至 {_format_until(current_until)}。"
        _create_user_moderation_notification(
            db,
            user_id,
            _append_reason(content, current_reason),
        )


def list_users(
    db: Session,
    skip: int,
    limit: int,
    keyword: Optional[str] = None,
) -> tuple[list[UserWithModerationResponse], int]:
    """分页读取用户列表，并附加内容数量和处罚状态。"""

    query = db.query(User)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(User.username.like(like), User.email.like(like)))
    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    user_ids = [user.id for user in users]

    post_counts = dict(
        db.query(Post.author_id, func.count(Post.id)).filter(Post.author_id.in_(user_ids))
        .group_by(Post.author_id)
        .all()
    ) if user_ids else {}
    comment_counts = dict(
        db.query(Comment.owner_id, func.count(Comment.id)).filter(Comment.owner_id.in_(user_ids))
        .group_by(Comment.owner_id)
        .all()
    ) if user_ids else {}
    moderations = {
        item.user_id: item
        for item in db.query(UserModeration).filter(UserModeration.user_id.in_(user_ids)).all()
    } if user_ids else {}

    return [
        UserWithModerationResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            bio=user.bio,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
            following_count=user.following_count,
            followers_count=user.followers_count,
            post_count=post_counts.get(user.id, 0),
            comment_count=comment_counts.get(user.id, 0),
            moderation=moderation_to_status(moderations.get(user.id)),
        )
        for user in users
    ], total


def list_moderated_users(
    db: Session,
    skip: int,
    limit: int,
    keyword: Optional[str] = None,
) -> tuple[list[UserWithModerationResponse], int]:
    """分页读取当前处于账号或功能管控状态的用户。"""

    now = local_now()
    query = db.query(User).join(UserModeration, UserModeration.user_id == User.id).filter(
        or_(
            UserModeration.account_banned_at.isnot(None),
            UserModeration.publish_banned_until > now,
            UserModeration.publish_permanently_banned.is_(True),
            UserModeration.comment_banned_until > now,
            UserModeration.comment_permanently_banned.is_(True),
            UserModeration.interaction_banned_until > now,
            UserModeration.interaction_permanently_banned.is_(True),
            UserModeration.avatar_banned_until > now,
            UserModeration.avatar_permanently_banned.is_(True),
            UserModeration.username_banned_until > now,
            UserModeration.username_permanently_banned.is_(True),
            UserModeration.bio_banned_until > now,
            UserModeration.bio_permanently_banned.is_(True),
        )
    )
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(User.username.like(like), User.email.like(like), User.bio.like(like)))

    total = query.count()
    users = query.order_by(UserModeration.updated_at.desc(), User.id.desc()).offset(skip).limit(limit).all()
    user_ids = [user.id for user in users]
    post_counts = dict(
        db.query(Post.author_id, func.count(Post.id)).filter(Post.author_id.in_(user_ids))
        .group_by(Post.author_id)
        .all()
    ) if user_ids else {}
    comment_counts = dict(
        db.query(Comment.owner_id, func.count(Comment.id)).filter(Comment.owner_id.in_(user_ids))
        .group_by(Comment.owner_id)
        .all()
    ) if user_ids else {}
    moderations = {
        item.user_id: item
        for item in db.query(UserModeration).filter(UserModeration.user_id.in_(user_ids)).all()
    } if user_ids else {}

    return [
        UserWithModerationResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            bio=user.bio,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
            following_count=user.following_count,
            followers_count=user.followers_count,
            post_count=post_counts.get(user.id, 0),
            comment_count=comment_counts.get(user.id, 0),
            moderation=moderation_to_status(moderations.get(user.id)),
        )
        for user in users
    ], total


def get_dashboard_stats(db: Session) -> DashboardStatsResponse:
    """读取管理端 dashboard 汇总统计。"""

    since = local_now() - timedelta(days=1)
    active_user_ids = set()
    for rows in (
        db.query(Post.author_id).filter(Post.created_at >= since).all(),
        db.query(Comment.owner_id).filter(Comment.created_at >= since).all(),
        db.query(Like.user_id).filter(Like.created_at >= since).all(),
        db.query(CommentLike.user_id).filter(CommentLike.created_at >= since).all(),
        db.query(Follow.follower_id).filter(Follow.created_at >= since).all(),
    ):
        active_user_ids.update(row[0] for row in rows)

    return DashboardStatsResponse(
        total_users=db.query(User).count(),
        daily_active_users=len(active_user_ids),
        cpu_usage_percent=_read_process_cpu_usage_percent(),
        memory_usage_percent=_read_process_memory_usage_percent(),
    )


def _read_process_cpu_usage_percent() -> float:
    """读取当前进程 CPU 占用百分比。"""
    global _last_cpu_snapshot
    try:
        process_ticks = _read_process_cpu_ticks()
        system_ticks = _read_system_cpu_ticks()
        cpu_count = _cpu_count()

        if _last_cpu_snapshot is not None:
            last_process_ticks, last_system_ticks = _last_cpu_snapshot
            _last_cpu_snapshot = (process_ticks, system_ticks)
            process_delta = process_ticks - last_process_ticks
            system_delta = system_ticks - last_system_ticks
            if system_delta <= 0:
                return 0.0
            return round(max(0.0, min(process_delta / system_delta * cpu_count * 100, 100.0)), 2)

        _last_cpu_snapshot = (process_ticks, system_ticks)
        return _read_process_average_cpu_usage_percent(process_ticks, cpu_count)
    except (OSError, ValueError, IndexError):
        return 0.0


def _read_process_cpu_ticks() -> int:
    """读取当前进程累计 CPU tick。"""

    with open("/proc/self/stat", "r", encoding="utf-8") as f:
        content = f.read()
    fields = content.rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])


def _read_system_cpu_ticks() -> int:
    """读取系统累计 CPU tick。"""

    with open("/proc/stat", "r", encoding="utf-8") as f:
        return sum(int(value) for value in f.readline().split()[1:])


def _read_process_average_cpu_usage_percent(process_ticks: int, cpu_count: int) -> float:
    """按进程启动以来的平均值估算 CPU 使用率。"""

    clock_ticks = _clock_ticks()
    with open("/proc/self/stat", "r", encoding="utf-8") as f:
        fields = f.read().rsplit(")", 1)[1].split()
    process_start_ticks = int(fields[19])
    with open("/proc/uptime", "r", encoding="utf-8") as f:
        uptime_seconds = float(f.readline().split()[0])

    elapsed_seconds = uptime_seconds - process_start_ticks / clock_ticks
    if elapsed_seconds <= 0:
        return 0.0
    cpu_seconds = process_ticks / clock_ticks
    return round(max(0.0, min(cpu_seconds / elapsed_seconds / cpu_count * 100, 100.0)), 2)


def _read_process_memory_usage_percent() -> float:
    """读取当前进程常驻内存占系统总内存的百分比。"""
    try:
        process_rss_kb = 0
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    process_rss_kb = int(line.split()[1])
                    break

        total_kb = 0
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total_kb = int(line.split()[1])
                    break

        if total_kb <= 0:
            return 0.0
        return round(max(0.0, min(process_rss_kb / total_kb * 100, 100.0)), 2)
    except (OSError, ValueError):
        return 0.0


def _clock_ticks() -> int:
    """读取系统每秒 clock tick 数。"""

    import os

    return int(os.sysconf(os.sysconf_names["SC_CLK_TCK"]))


def _cpu_count() -> int:
    """读取可用 CPU 核心数。"""

    import os

    return os.cpu_count() or 1
