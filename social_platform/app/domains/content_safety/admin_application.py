"""内容安全领域的管理端用例。

本模块承载管理端内容列表、内容删除、举报放行和举报删除处理。HTTP 层负责权限
和异常映射，本模块只表达内容安全相关业务流程。
"""

from datetime import datetime
from social_platform.app.core.timezone import local_now
from typing import Literal, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session, joinedload

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import (
    ContentItemResponse,
    ContentReportReasonResponse,
    ReportedContentItemResponse,
    ReportedUserItemResponse,
    UserViolationRequest,
)
from social_platform.app.admin.services.log_service import create_operation_log
from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.content_safety.events import (
    ContentModerationActionApplied,
    ReportedContentViolationConfirmed,
)
from social_platform.app.domains.content_safety.models import ContentReport, ContentReportEscalation
from social_platform.app.domains.heat import application as heat_service
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.post import application as post_application
from social_platform.app.domains.search import application as search_service
from social_platform.app.shared.events import publish_domain_event
from social_platform.app.domains.user.models import User


ContentType = Literal["post", "comment"]
CONTENT_STATUS_ACTIVE = "active"
CONTENT_STATUS_ARCHIVED = "archived"


def _notify_moderation_action(
    db: Session,
    recipient_id: int,
    resource_type: str,
    resource_id: int,
    reason: Optional[str],
) -> None:
    """发布内容作者处罚通知事件。

    Args:
        db: SQLAlchemy 数据库会话。
        recipient_id: 内容作者 ID。
        resource_type: 被处理资源类型。
        resource_id: 被处理资源 ID。
        reason: 可选处理原因。

    Raises:
        事件处理器抛出的异常会透传并阻止当前事务提交。
    """

    publish_domain_event(
        db,
        ContentModerationActionApplied(
            recipient_id=recipient_id,
            resource_type=resource_type,
            resource_id=resource_id,
            reason=reason,
        ),
    )


def delete_post_as_admin(
    db: Session,
    post_id: int,
    admin: PlatformAdminUser,
    reason: Optional[str] = None,
    notify_author: bool = True,
) -> None:
    """以管理员身份归档帖子并保留可恢复数据。

    Args:
        db: SQLAlchemy 数据库会话。
        post_id: 待删除帖子 ID。
        admin: 执行操作的管理员。
        reason: 可选处理原因。
        notify_author: 是否通知作者。

    Raises:
        ValueError: 帖子不存在时抛出。
    """

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise ValueError("帖子不存在")
    if post.moderation_status == CONTENT_STATUS_ARCHIVED:
        raise ValueError("帖子已归档")

    author_id = post.author_id
    if post.repost_source_type:
        post_application.adjust_repost_counts(db, post, -1)
    post.moderation_status = CONTENT_STATUS_ARCHIVED
    post.archived_at = local_now()
    post.archived_by_admin_id = admin.id
    post.archive_reason = reason
    from social_platform.app.admin.services.moderation_service import apply_user_violation

    apply_user_violation(
        db,
        author_id,
        "publish",
        admin,
        reason,
        source_type="post",
        source_id=post_id,
        notify_user=notify_author,
        commit=False,
    )
    create_operation_log(
        db,
        admin,
        action="archive_post",
        target_type="post",
        target_id=post_id,
        details={"reason": reason, "notify_author": notify_author},
    )
    db.commit()
    search_service.delete_post(post_id)


def _get_descendant_comment_ids(db: Session, comment_id: int) -> list[int]:
    """读取根评论下所有子评论 ID。

    Args:
        db: SQLAlchemy 数据库会话。
        comment_id: 根评论 ID。

    Returns:
        list[int]: 所有以该评论为根的子评论 ID。
    """

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
    """以管理员身份归档评论并修正帖子、根评论计数与热度。

    Args:
        db: SQLAlchemy 数据库会话。
        comment_id: 待删除评论 ID。
        admin: 执行操作的管理员。
        reason: 可选处理原因。
        notify_author: 是否通知评论作者。

    Raises:
        ValueError: 评论不存在时抛出。
    """

    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise ValueError("评论不存在")
    if comment.moderation_status == CONTENT_STATUS_ARCHIVED:
        raise ValueError("评论已归档")

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

    post = db.query(Post).filter(Post.id == post_id).first()
    if post:
        post.comment_count = max(0, post.comment_count - count_to_subtract)
        heat_service.refresh_post_heat_score(db, post)

    if parent_id is not None:
        root = db.query(Comment).filter(Comment.id == root_comment_id).first()
        if root:
            root.reply_count = max(0, root.reply_count - count_to_subtract)
            heat_service.refresh_comment_heat_score(db, root)

    comment.moderation_status = CONTENT_STATUS_ARCHIVED
    comment.archived_at = local_now()
    comment.archived_by_admin_id = admin.id
    comment.archive_reason = reason
    from social_platform.app.admin.services.moderation_service import apply_user_violation

    apply_user_violation(
        db,
        owner_id,
        "comment",
        admin,
        reason,
        source_type="comment",
        source_id=comment_id,
        notify_user=notify_author,
        commit=False,
    )
    create_operation_log(
        db,
        admin,
        action="archive_comment",
        target_type="comment",
        target_id=comment_id,
        details={"reason": reason, "notify_author": notify_author},
    )
    db.commit()


def restore_post_as_admin(db: Session, post_id: int, admin: PlatformAdminUser) -> None:
    """恢复管理员归档的帖子。

    Args:
        db: SQLAlchemy 数据库会话。
        post_id: 待恢复帖子 ID。
        admin: 执行操作的管理员。

    Raises:
        ValueError: 帖子不存在或未归档时抛出。
    """

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise ValueError("帖子不存在")
    if post.moderation_status != CONTENT_STATUS_ARCHIVED:
        raise ValueError("帖子未归档")

    post.moderation_status = CONTENT_STATUS_ACTIVE
    post.archived_at = None
    post.archived_by_admin_id = None
    post.archive_reason = None
    if post.repost_source_type:
        post_application.adjust_repost_counts(db, post, 1)
    from social_platform.app.admin.services.moderation_service import release_violation_event
    from social_platform.app.domains.content_safety.models import UserViolationEvent

    event = db.query(UserViolationEvent).filter(
        UserViolationEvent.dedup_key == f"post:{post_id}:publish"
    ).first()
    if event is not None:
        release_violation_event(
            db,
            event.id,
            admin,
            reverse_violation_count=True,
            commit=False,
        )
    create_operation_log(
        db,
        admin,
        action="restore_post",
        target_type="post",
        target_id=post_id,
        details={},
    )
    db.commit()
    db.refresh(post)
    search_service.index_post(post)


def restore_comment_as_admin(db: Session, comment_id: int, admin: PlatformAdminUser) -> None:
    """恢复管理员归档的评论并修正帖子与根评论计数。

    Args:
        db: SQLAlchemy 数据库会话。
        comment_id: 待恢复评论 ID。
        admin: 执行操作的管理员。

    Raises:
        ValueError: 评论不存在、未归档或所属帖子已归档时抛出。
    """

    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise ValueError("评论不存在")
    if comment.moderation_status != CONTENT_STATUS_ARCHIVED:
        raise ValueError("评论未归档")

    post = db.query(Post).filter(Post.id == comment.post_id).first()
    if not post or post.moderation_status == CONTENT_STATUS_ARCHIVED:
        raise ValueError("所属帖子不存在或已归档")

    parent_id = comment.parent_id
    count_to_add = 1 + len(_get_descendant_comment_ids(db, comment_id)) if parent_id is None else 1
    post.comment_count = max(0, post.comment_count + count_to_add)
    heat_service.refresh_post_heat_score(db, post)
    if parent_id is not None and comment.root_comment_id is not None:
        root = db.query(Comment).filter(Comment.id == comment.root_comment_id).first()
        if root and root.moderation_status == CONTENT_STATUS_ACTIVE:
            root.reply_count = max(0, root.reply_count + count_to_add)
            heat_service.refresh_comment_heat_score(db, root)

    comment.moderation_status = CONTENT_STATUS_ACTIVE
    comment.archived_at = None
    comment.archived_by_admin_id = None
    comment.archive_reason = None
    from social_platform.app.admin.services.moderation_service import release_violation_event
    from social_platform.app.domains.content_safety.models import UserViolationEvent

    event = db.query(UserViolationEvent).filter(
        UserViolationEvent.dedup_key == f"comment:{comment_id}:comment"
    ).first()
    if event is not None:
        release_violation_event(
            db,
            event.id,
            admin,
            reverse_violation_count=True,
            commit=False,
        )
    create_operation_log(
        db,
        admin,
        action="restore_comment",
        target_type="comment",
        target_id=comment_id,
        details={},
    )
    db.commit()


def list_content(
    db: Session,
    content_type: Optional[ContentType],
    skip: int,
    limit: int,
    keyword: Optional[str] = None,
) -> tuple[list[ContentItemResponse], int]:
    """分页读取管理端内容列表。

    Args:
        db: SQLAlchemy 数据库会话。
        content_type: 可选内容类型过滤。
        skip: 分页偏移。
        limit: 分页大小。
        keyword: 可选关键词。

    Returns:
        tuple[list[ContentItemResponse], int]: 当前页内容和过滤后的总数。
    """

    items: list[ContentItemResponse] = []
    if content_type in (None, "post"):
        query = db.query(Post).options(joinedload(Post.author)).filter(
            Post.moderation_status == CONTENT_STATUS_ACTIVE
        )
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
                created_by_agent=post.created_by_agent,
                like_count=post.like_count,
                comment_count=post.comment_count,
                moderation_status=post.moderation_status,
                archived_at=post.archived_at,
                archive_reason=post.archive_reason,
            )
            for post in posts
        )
    if content_type in (None, "comment"):
        query = db.query(Comment).join(Post, Comment.post_id == Post.id).options(
            joinedload(Comment.owner)
        ).filter(
            Comment.moderation_status == CONTENT_STATUS_ACTIVE,
            Post.moderation_status == CONTENT_STATUS_ACTIVE,
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
                created_by_agent=comment.created_by_agent,
                like_count=comment.like_count,
                reply_count=comment.reply_count,
                moderation_status=comment.moderation_status,
                archived_at=comment.archived_at,
                archive_reason=comment.archive_reason,
            )
            for comment in comments
        )
    items.sort(key=lambda item: item.created_at, reverse=True)
    total = len(items)
    return items[skip:skip + limit], total


def list_archived_content(
    db: Session,
    content_type: Optional[ContentType],
    skip: int,
    limit: int,
    keyword: Optional[str] = None,
) -> tuple[list[ContentItemResponse], int]:
    """分页读取管理端已归档内容列表。

    Args:
        db: SQLAlchemy 数据库会话。
        content_type: 可选内容类型过滤。
        skip: 分页偏移。
        limit: 分页大小。
        keyword: 可选关键词。

    Returns:
        tuple[list[ContentItemResponse], int]: 当前页归档内容和过滤后的总数。
    """

    items: list[ContentItemResponse] = []
    keyword_value = keyword.strip() if keyword else None
    if content_type in (None, "post"):
        query = db.query(Post).options(joinedload(Post.author)).filter(
            Post.moderation_status == CONTENT_STATUS_ARCHIVED
        )
        if keyword_value:
            like = f"%{keyword_value}%"
            query = query.filter(or_(Post.title.like(like), Post.content.like(like)))
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
                created_by_agent=post.created_by_agent,
                like_count=post.like_count,
                comment_count=post.comment_count,
                moderation_status=post.moderation_status,
                archived_at=post.archived_at,
                archive_reason=post.archive_reason,
            )
            for post in query.order_by(Post.archived_at.desc(), Post.id.desc()).all()
        )
    if content_type in (None, "comment"):
        query = db.query(Comment).options(joinedload(Comment.owner)).filter(
            Comment.moderation_status == CONTENT_STATUS_ARCHIVED
        )
        if keyword_value:
            query = query.filter(Comment.content.like(f"%{keyword_value}%"))
        items.extend(
            ContentItemResponse(
                id=comment.id,
                type="comment",
                post_id=comment.post_id,
                author_id=comment.owner_id,
                author_username=comment.owner.username if comment.owner else None,
                content=comment.content,
                created_at=comment.created_at,
                created_by_agent=comment.created_by_agent,
                like_count=comment.like_count,
                reply_count=comment.reply_count,
                moderation_status=comment.moderation_status,
                archived_at=comment.archived_at,
                archive_reason=comment.archive_reason,
            )
            for comment in query.order_by(Comment.archived_at.desc(), Comment.id.desc()).all()
        )
    items.sort(key=lambda item: item.archived_at or item.created_at, reverse=True)
    total = len(items)
    return items[skip:skip + limit], total


def list_reported_content(
    db: Session,
    content_type: Optional[ContentType],
    skip: int,
    limit: int,
    keyword: Optional[str] = None,
) -> tuple[list[ReportedContentItemResponse], int]:
    """分页读取管理端待审举报聚合列表。

    Args:
        db: SQLAlchemy 数据库会话。
        content_type: 可选内容类型过滤。
        skip: 分页偏移。
        limit: 分页大小。
        keyword: 可选内容关键词。

    Returns:
        tuple[list[ReportedContentItemResponse], int]: 当前页聚合举报内容和总数。
    """

    reports = _pending_reports_query(db, content_type).all()
    keyword_value = keyword.strip() if keyword else None
    grouped: dict[tuple[str, int], dict[str, object]] = {}

    for report in reports:
        if report.target_type == "post":
            target = report.post
            target_id = report.post_id
        else:
            target = report.comment
            target_id = report.comment_id
        if target is None or target_id is None:
            continue
        if getattr(target, "moderation_status", CONTENT_STATUS_ACTIVE) != CONTENT_STATUS_ACTIVE:
            continue

        key = (report.target_type, target_id)
        group = grouped.setdefault(
            key,
            {"target": target, "reports": []},
        )
        group_reports = group["reports"]
        assert isinstance(group_reports, list)
        group_reports.append(report)

    items: list[ReportedContentItemResponse] = []
    for (target_type, _), group in grouped.items():
        target = group["target"]
        group_reports = group["reports"]
        assert isinstance(group_reports, list)
        if not group_reports:
            continue

        item = _reported_content_item_from_group(target_type, target, group_reports)
        if keyword_value and keyword_value not in (item.title or "") and keyword_value not in item.content:
            continue
        items.append(item)

    items.sort(key=lambda item: (item.report_count, item.last_reported_at), reverse=True)
    total = len(items)
    return items[skip:skip + limit], total


def release_reported_content(
    db: Session,
    content_type: ContentType,
    content_id: int,
    admin: PlatformAdminUser,
) -> int:
    """放行某个被举报内容下的全部待审举报。

    Args:
        db: SQLAlchemy 数据库会话。
        content_type: 内容类型。
        content_id: 内容 ID。
        admin: 执行操作的管理员。

    Returns:
        int: 被放行的举报数量。

    Raises:
        ValueError: 没有待审举报时抛出。
    """

    reports = _pending_reports_for_target(db, content_type, content_id).all()
    if not reports:
        raise ValueError("待审举报不存在")

    now = local_now()
    for report in reports:
        report.status = "released"
        report.reviewed_at = now
        report.reviewed_by_admin_id = admin.id
    create_operation_log(
        db,
        admin,
        action="release_reported_content",
        target_type=content_type,
        target_id=content_id,
        details={"report_count": len(reports)},
    )
    db.commit()
    return len(reports)


def delete_reported_post_as_admin(
    db: Session,
    post_id: int,
    admin: PlatformAdminUser,
    reason: Optional[str] = None,
    notify_author: bool = True,
) -> None:
    """删除已被举报的帖子，并通知对应举报人。

    Args:
        db: SQLAlchemy 数据库会话。
        post_id: 被举报帖子 ID。
        admin: 执行操作的管理员。
        reason: 可选处理原因。
        notify_author: 是否通知作者。

    Raises:
        ValueError: 帖子不存在时抛出。
    """

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise ValueError("帖子不存在")
    reporter_ids = _pending_reporter_ids(db, "post", post_id)
    _confirm_pending_reports(db, "post", post_id, admin)
    _notify_reporters_content_deleted(db, reporter_ids, "post", post_id)
    delete_post_as_admin(db, post_id, admin, reason=reason, notify_author=notify_author)


def delete_reported_comment_as_admin(
    db: Session,
    comment_id: int,
    admin: PlatformAdminUser,
    reason: Optional[str] = None,
    notify_author: bool = True,
) -> None:
    """删除已被举报的评论，并通知对应举报人。

    Args:
        db: SQLAlchemy 数据库会话。
        comment_id: 被举报评论 ID。
        admin: 执行操作的管理员。
        reason: 可选处理原因。
        notify_author: 是否通知作者。

    Raises:
        ValueError: 评论不存在时抛出。
    """

    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise ValueError("评论不存在")
    reporter_ids = _pending_reporter_ids(db, "comment", comment_id)
    _confirm_pending_reports(db, "comment", comment_id, admin)
    _notify_reporters_content_deleted(db, reporter_ids, "comment", comment_id)
    delete_comment_as_admin(db, comment_id, admin, reason=reason, notify_author=notify_author)


def list_reported_users(
    db: Session,
    skip: int,
    limit: int,
    keyword: Optional[str] = None,
) -> tuple[list[ReportedUserItemResponse], int]:
    """分页读取管理端待审举报用户聚合列表。

    Args:
        db: SQLAlchemy 数据库会话。
        skip: 分页偏移。
        limit: 分页大小。
        keyword: 可选用户名或签名关键词。

    Returns:
        tuple[list[ReportedUserItemResponse], int]: 当前页聚合举报用户和总数。
    """

    reports = _pending_reports_query(db, "user").all()
    escalations = db.query(ContentReportEscalation).options(
        joinedload(ContentReportEscalation.user),
    ).filter(ContentReportEscalation.status == "pending").all()
    keyword_value = keyword.strip() if keyword else None
    grouped: dict[int, list[ContentReport]] = {}

    for report in reports:
        if report.user is None or report.user_id is None:
            continue
        grouped.setdefault(report.user_id, []).append(report)

    escalations_by_user: dict[int, list[ContentReportEscalation]] = {}
    for escalation in escalations:
        if escalation.user is None:
            continue
        escalations_by_user.setdefault(escalation.user_id, []).append(escalation)

    items: list[ReportedUserItemResponse] = []
    for user_id in sorted(set(grouped) | set(escalations_by_user)):
        group_reports = grouped.get(user_id, [])
        group_escalations = escalations_by_user.get(user_id, [])
        user = group_reports[0].user if group_reports else group_escalations[0].user
        if user is None:
            continue
        item = _reported_user_item_from_group(user, group_reports, group_escalations)
        if keyword_value and keyword_value not in (item.username or "") and keyword_value not in (item.bio or ""):
            continue
        items.append(item)

    items.sort(key=lambda item: (item.report_count, item.last_reported_at), reverse=True)
    total = len(items)
    return items[skip:skip + limit], total


def release_reported_user(
    db: Session,
    user_id: int,
    admin: PlatformAdminUser,
) -> int:
    """放行某个被举报用户下的全部待审举报。

    Args:
        db: SQLAlchemy 数据库会话。
        user_id: 被举报用户 ID。
        admin: 执行操作的管理员。

    Returns:
        int: 被放行的举报数量。

    Raises:
        ValueError: 没有待审举报时抛出。
    """

    reports = _pending_reports_for_target(db, "user", user_id).all()
    escalations = _pending_escalations_for_user(db, user_id).all()
    if not reports and not escalations:
        raise ValueError("待审举报不存在")

    now = local_now()
    for report in reports:
        report.status = "released"
        report.reviewed_at = now
        report.reviewed_by_admin_id = admin.id
    for escalation in escalations:
        escalation.status = "released"
        escalation.reviewed_at = now
        escalation.reviewed_by_admin_id = admin.id
    create_operation_log(
        db,
        admin,
        action="release_reported_user",
        target_type="user",
        target_id=user_id,
        details={"report_count": len(reports), "escalation_count": len(escalations)},
    )
    db.commit()
    return len(reports) + len(escalations)


def ban_reported_user_as_admin(
    db: Session,
    user_id: int,
    admin: PlatformAdminUser,
    reason: Optional[str] = None,
    notify_user: bool = True,
) -> None:
    """封禁被举报用户并通知举报人。

    Args:
        db: SQLAlchemy 数据库会话。
        user_id: 被举报用户 ID。
        admin: 执行操作的管理员。
        reason: 可选封禁原因。
        notify_user: 是否通知被封禁用户；当前用户处罚流程会始终发送处罚通知。

    Raises:
        ValueError: 用户或待审举报不存在时抛出。
    """

    if db.query(User).filter(User.id == user_id).first() is None:
        raise ValueError("用户不存在")
    reports = _pending_reports_for_target(db, "user", user_id).all()
    escalations = _pending_escalations_for_user(db, user_id).all()
    if not reports and not escalations:
        raise ValueError("待审举报不存在")

    reporter_ids = sorted({report.reporter_id for report in reports})
    from social_platform.app.admin.services.moderation_service import apply_user_violation

    apply_user_violation(
        db,
        user_id,
        "account",
        admin,
        reason or "账号因违反社区规则被封禁",
        source_type="user_report",
        notify_user=notify_user,
        commit=False,
    )

    now = local_now()
    for report in reports:
        report.status = "confirmed"
        report.reviewed_at = now
        report.reviewed_by_admin_id = admin.id
    for escalation in escalations:
        escalation.status = "confirmed"
        escalation.reviewed_at = now
        escalation.reviewed_by_admin_id = admin.id
    _notify_reporters_content_deleted(db, reporter_ids, "user", user_id)
    db.commit()


def moderate_reported_user_as_admin(
    db: Session,
    user_id: int,
    request: UserViolationRequest,
    admin: PlatformAdminUser,
) -> object:
    """对被举报用户应用任意管控并关闭待审用户举报。

    Args:
        db: SQLAlchemy 数据库会话。
        user_id: 被举报用户 ID。
        request: 用户管控更新请求。
        admin: 执行操作的管理员。

    Returns:
        object: 更新后的用户管控模型。

    Raises:
        ValueError: 用户或待审举报不存在时抛出。
    """

    if db.query(User).filter(User.id == user_id).first() is None:
        raise ValueError("用户不存在")
    reports = _pending_reports_for_target(db, "user", user_id).all()
    escalations = _pending_escalations_for_user(db, user_id).all()
    if not reports and not escalations:
        raise ValueError("待审举报不存在")

    from social_platform.app.admin.services.moderation_service import apply_user_violation

    moderation, _ = apply_user_violation(
        db,
        user_id,
        request.category,
        admin,
        request.reason,
        source_type="user_report",
        commit=False,
    )
    now = local_now()
    for report in reports:
        report.status = "confirmed"
        report.reviewed_at = now
        report.reviewed_by_admin_id = admin.id
    for escalation in escalations:
        escalation.status = "confirmed"
        escalation.reviewed_at = now
        escalation.reviewed_by_admin_id = admin.id
    reporter_ids = sorted({report.reporter_id for report in reports})
    _notify_reporters_content_deleted(db, reporter_ids, "user", user_id)
    db.commit()
    db.refresh(moderation)
    return moderation


def _pending_reports_query(db: Session, content_type: Optional[str]) -> Query[ContentReport]:
    """构建待审举报查询，预加载被举报内容作者。"""

    query = db.query(ContentReport).options(
        joinedload(ContentReport.post).joinedload(Post.author),
        joinedload(ContentReport.comment).joinedload(Comment.owner),
        joinedload(ContentReport.user),
    ).filter(ContentReport.status == "pending")
    if content_type:
        query = query.filter(ContentReport.target_type == content_type)
    return query


def _pending_reports_for_target(
    db: Session,
    content_type: str,
    content_id: int,
) -> Query[ContentReport]:
    """构建指定内容的待审举报查询。"""

    query = db.query(ContentReport).filter(
        ContentReport.status == "pending",
        ContentReport.target_type == content_type,
    )
    if content_type == "post":
        return query.filter(ContentReport.post_id == content_id)
    if content_type == "user":
        return query.filter(ContentReport.user_id == content_id)
    return query.filter(ContentReport.comment_id == content_id)


def _pending_escalations_for_user(db: Session, user_id: int) -> Query[ContentReportEscalation]:
    """构建指定用户待审升级记录查询。"""

    return db.query(ContentReportEscalation).filter(
        ContentReportEscalation.status == "pending",
        ContentReportEscalation.user_id == user_id,
    )


def _pending_reporter_ids(db: Session, content_type: ContentType, content_id: int) -> list[int]:
    """读取指定内容的待审举报人 ID。"""

    return sorted({
        row[0]
        for row in _pending_reports_for_target(db, content_type, content_id)
        .with_entities(ContentReport.reporter_id)
        .all()
    })


def _confirm_pending_reports(
    db: Session,
    content_type: ContentType,
    content_id: int,
    admin: PlatformAdminUser,
) -> None:
    """把指定内容的待审举报标记为违规确认。"""

    now = local_now()
    for report in _pending_reports_for_target(db, content_type, content_id).all():
        report.status = "confirmed"
        report.reviewed_at = now
        report.reviewed_by_admin_id = admin.id


def _reported_user_item_from_group(
    user: User,
    reports: list[ContentReport],
    escalations: list[ContentReportEscalation],
) -> ReportedUserItemResponse:
    """把同一用户的多条举报聚合为管理端响应项。"""

    reason_counts: dict[str, int] = {}
    for report in reports:
        reason_counts[report.reason] = reason_counts.get(report.reason, 0) + 1
    for escalation in escalations:
        reason_counts[escalation.reason] = reason_counts.get(escalation.reason, 0) + 1
    report_reasons = [
        ContentReportReasonResponse(reason=reason, count=count)
        for reason, count in sorted(reason_counts.items(), key=lambda item: item[1], reverse=True)
    ]
    last_reported_values = [report.created_at for report in reports] + [
        escalation.created_at for escalation in escalations
    ]
    unique_reporter_count = len({report.reporter_id for report in reports})
    return ReportedUserItemResponse(
        id=user.id,
        username=user.username,
        bio=user.bio,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        report_count=unique_reporter_count + len(escalations),
        report_reasons=report_reasons,
        last_reported_at=max(last_reported_values),
        source="report+escalation" if reports and escalations else ("escalation" if escalations else "report"),
    )


def _reported_content_item_from_group(
    target_type: str,
    target: Post | Comment,
    reports: list[ContentReport],
) -> ReportedContentItemResponse:
    """把同一内容的多条举报聚合为管理端响应项。"""

    reason_counts: dict[str, int] = {}
    for report in reports:
        reason_counts[report.reason] = reason_counts.get(report.reason, 0) + 1
    report_reasons = [
        ContentReportReasonResponse(reason=reason, count=count)
        for reason, count in sorted(reason_counts.items(), key=lambda item: item[1], reverse=True)
    ]
    last_reported_at = max(report.created_at for report in reports)

    if target_type == "post":
        assert isinstance(target, Post)
        return ReportedContentItemResponse(
            id=target.id,
            type=target.type,
            post_id=target.id,
            author_id=target.author_id,
            author_username=target.author.username if target.author else None,
            title=target.title,
            content=target.content,
            created_at=target.created_at,
            created_by_agent=target.created_by_agent,
            like_count=target.like_count,
            comment_count=target.comment_count,
            moderation_status=target.moderation_status,
            archived_at=target.archived_at,
            archive_reason=target.archive_reason,
            report_count=len({report.reporter_id for report in reports}),
            report_reasons=report_reasons,
            last_reported_at=last_reported_at,
        )

    assert isinstance(target, Comment)
    return ReportedContentItemResponse(
        id=target.id,
        type="comment",
        post_id=target.post_id,
        author_id=target.owner_id,
        author_username=target.owner.username if target.owner else None,
        content=target.content,
        created_at=target.created_at,
        created_by_agent=target.created_by_agent,
        like_count=target.like_count,
        reply_count=target.reply_count,
        moderation_status=target.moderation_status,
        archived_at=target.archived_at,
        archive_reason=target.archive_reason,
        report_count=len({report.reporter_id for report in reports}),
        report_reasons=report_reasons,
        last_reported_at=last_reported_at,
    )


def _notify_reporters_content_deleted(
    db: Session,
    reporter_ids: list[int],
    resource_type: str,
    resource_id: int,
) -> None:
    """发布举报确认违规通知事件。"""

    publish_domain_event(
        db,
        ReportedContentViolationConfirmed(
            reporter_ids=tuple(reporter_ids),
            resource_type=resource_type,
            resource_id=resource_id,
        ),
    )
