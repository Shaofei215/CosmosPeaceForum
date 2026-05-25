from datetime import datetime, timedelta
from typing import Literal, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.models.user_moderation import UserModeration
from social_platform.app.admin.schemas import (
    ContentItemResponse,
    DashboardStatsResponse,
    UserModerationBatchUpdateRequest,
    UserModerationBatchUpdateResponse,
    UserModerationResponse,
    UserModerationStatusResponse,
    UserModerationUpdateRequest,
    UserWithModerationResponse,
)
from social_platform.app.admin.services.announcement_service import create_user_moderation_notice
from social_platform.app.admin.services.log_service import create_operation_log
from social_platform.app.models.comment import Comment, CommentLike
from social_platform.app.models.follow import Follow
from social_platform.app.models.like import Like
from social_platform.app.models.post import Post
from social_platform.app.models.user import User
from social_platform.app.services import heat_service, notification_service, search_service


ContentType = Literal["post", "comment"]

_RESTRICTION_LABELS = {
    "publish": "发帖功能",
    "comment": "评论功能",
    "interaction": "互动功能",
}

_last_cpu_snapshot: tuple[int, int] | None = None


def moderation_to_status(
    moderation: Optional[UserModeration],
) -> UserModerationStatusResponse:
    if moderation is None:
        return UserModerationStatusResponse()
    return UserModerationStatusResponse(
        account_banned=bool(moderation.account_banned_at),
        account_banned_at=moderation.account_banned_at,
        account_ban_reason=moderation.account_ban_reason,
        publish_banned_until=moderation.publish_banned_until,
        publish_ban_reason=moderation.publish_ban_reason,
        comment_banned_until=moderation.comment_banned_until,
        comment_ban_reason=moderation.comment_ban_reason,
        interaction_banned_until=moderation.interaction_banned_until,
        interaction_ban_reason=moderation.interaction_ban_reason,
        updated_at=moderation.updated_at,
    )


def get_or_create_moderation(db: Session, user_id: int, admin_id: int) -> UserModeration:
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
        moderation.account_banned_at = datetime.utcnow() if request.account_banned else None
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

    moderation.updated_at = datetime.utcnow()
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
    return value.strftime("%Y-%m-%d %H:%M")


def _append_reason(content: str, reason: Optional[str]) -> str:
    if reason:
        return f"{content}\n原因：{reason}"
    return content


def _append_appeal_email(content: str, admin: PlatformAdminUser) -> str:
    if admin.email:
        return f"{content}\n如有异议，请向{admin.email}申诉。"
    return content


def _create_user_moderation_notification(
    db: Session,
    user_id: int,
    content: str,
) -> None:
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
    if request.account_banned is not None:
        current_reason = request.account_ban_reason if request.account_banned else None
        if request.account_banned and (
            not previous_account_banned or current_reason != previous_account_reason
        ):
            _create_user_moderation_notification(
                db,
                user_id,
                _append_appeal_email(
                    _append_reason("你的账号已被永久封禁。", current_reason),
                    admin,
                ),
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

        if current_until <= datetime.utcnow():
            continue

        content = f"你的{label}已被限制至 {_format_until(current_until)}。"
        _create_user_moderation_notification(
            db,
            user_id,
            _append_appeal_email(_append_reason(content, current_reason), admin),
        )


def list_users(
    db: Session,
    skip: int,
    limit: int,
    keyword: Optional[str] = None,
) -> tuple[list[UserWithModerationResponse], int]:
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
            is_ai_agent=user.is_ai_agent,
            ai_config_id=user.ai_config_id,
            created_at=user.created_at,
            following_count=user.following_count,
            followers_count=user.followers_count,
            post_count=post_counts.get(user.id, 0),
            comment_count=comment_counts.get(user.id, 0),
            moderation=moderation_to_status(moderations.get(user.id)),
        )
        for user in users
    ], total


def _notify_moderation_action(
    db: Session,
    recipient_id: int,
    resource_type: str,
    resource_id: int,
    reason: Optional[str],
) -> None:
    content = "你的内容因违反社区规则已被管理端处理。"
    if reason:
        content = f"{content}\n原因：{reason}"
    notification_service.create_notification(
        db=db,
        recipient_id=recipient_id,
        sender_id=None,
        notification_type="moderation",
        resource_type=resource_type,
        resource_id=resource_id,
        source_content=content,
        truncate_source_content=False,
    )


def delete_post_as_admin(
    db: Session,
    post_id: int,
    admin: PlatformAdminUser,
    reason: Optional[str] = None,
    notify_author: bool = True,
) -> None:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise ValueError("帖子不存在")

    author_id = post.author_id
    db.query(Post).filter(Post.repost_root_post_id == post_id).update(
        {Post.repost_root_post_id: None},
        synchronize_session=False,
    )
    db.query(Like).filter(Like.post_id == post_id).delete(synchronize_session=False)
    db.query(Comment).filter(Comment.post_id == post_id).delete(synchronize_session=False)
    if notify_author:
        _notify_moderation_action(db, author_id, "post", post_id, reason)
    create_operation_log(
        db,
        admin,
        action="delete_post",
        target_type="post",
        target_id=post_id,
        details={"reason": reason, "notify_author": notify_author},
    )
    db.delete(post)
    db.commit()
    search_service.delete_post(post_id)


def _get_descendant_comment_ids(db: Session, comment_id: int) -> list[int]:
    return [
        row[0]
        for row in db.query(Comment.id).filter(Comment.root_comment_id == comment_id).all()
    ]


def delete_comment_as_admin(
    db: Session,
    comment_id: int,
    admin: PlatformAdminUser,
    reason: Optional[str] = None,
    notify_author: bool = True,
) -> None:
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise ValueError("评论不存在")

    post_id = comment.post_id
    parent_id = comment.parent_id
    root_comment_id = comment.root_comment_id
    owner_id = comment.owner_id
    if parent_id is None:
        count_to_subtract = 1 + len(_get_descendant_comment_ids(db, comment_id))
    else:
        count_to_subtract = 1
        db.query(Comment).filter(Comment.parent_id == comment_id).update(
            {Comment.parent_id: parent_id},
            synchronize_session=False,
        )
        db.flush()

    db.query(CommentLike).filter(CommentLike.comment_id == comment_id).delete(
        synchronize_session=False
    )
    post = db.query(Post).filter(Post.id == post_id).first()
    if post:
        post.comment_count = max(0, post.comment_count - count_to_subtract)
        heat_service.refresh_post_heat_score(db, post)

    if parent_id is not None:
        root = db.query(Comment).filter(Comment.id == root_comment_id).first()
        if root:
            root.reply_count = max(0, root.reply_count - count_to_subtract)

    if notify_author:
        _notify_moderation_action(db, owner_id, "comment", comment_id, reason)
    create_operation_log(
        db,
        admin,
        action="delete_comment",
        target_type="comment",
        target_id=comment_id,
        details={"reason": reason, "notify_author": notify_author},
    )
    db.delete(comment)
    db.commit()


def list_content(
    db: Session,
    content_type: Optional[ContentType],
    skip: int,
    limit: int,
    keyword: Optional[str] = None,
) -> tuple[list[ContentItemResponse], int]:
    items: list[ContentItemResponse] = []
    if content_type in (None, "post"):
        query = db.query(Post).options(joinedload(Post.author))
        if keyword:
            like = f"%{keyword.strip()}%"
            query = query.filter(or_(Post.title.like(like), Post.content.like(like)))
        posts = query.order_by(Post.created_at.desc()).all()
        items.extend(
            ContentItemResponse(
                id=post.id,
                type=post.type,
                post_id=post.id,
                author_id=post.author_id,
                author_username=post.author.username if post.author else None,
                title=post.title,
                content=post.content,
                created_at=post.created_at,
                like_count=post.like_count,
                comment_count=post.comment_count,
            )
            for post in posts
        )
    if content_type in (None, "comment"):
        query = db.query(Comment).join(Post, Comment.post_id == Post.id).options(
            joinedload(Comment.owner)
        )
        if keyword:
            query = query.filter(Comment.content.like(f"%{keyword.strip()}%"))
        comments = query.order_by(Comment.created_at.desc()).all()
        items.extend(
            ContentItemResponse(
                id=comment.id,
                type="comment",
                post_id=comment.post_id,
                author_id=comment.owner_id,
                author_username=comment.owner.username if comment.owner else None,
                content=comment.content,
                created_at=comment.created_at,
                like_count=comment.like_count,
                reply_count=comment.reply_count,
            )
            for comment in comments
        )
    items.sort(key=lambda item: item.created_at, reverse=True)
    total = len(items)
    return items[skip:skip + limit], total


def get_dashboard_stats(db: Session) -> DashboardStatsResponse:
    since = datetime.utcnow() - timedelta(days=1)
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
    with open("/proc/self/stat", "r", encoding="utf-8") as f:
        content = f.read()
    fields = content.rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])


def _read_system_cpu_ticks() -> int:
    with open("/proc/stat", "r", encoding="utf-8") as f:
        return sum(int(value) for value in f.readline().split()[1:])


def _read_process_average_cpu_usage_percent(process_ticks: int, cpu_count: int) -> float:
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
    import os

    return int(os.sysconf(os.sysconf_names["SC_CLK_TCK"]))


def _cpu_count() -> int:
    import os

    return os.cpu_count() or 1
