"""内容安全领域的管理端用例。

本模块承载管理端内容列表、内容删除、举报放行和举报删除处理。HTTP 层负责权限
和异常映射，本模块只表达内容安全相关业务流程。
"""

from datetime import datetime
from typing import Literal, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session, joinedload

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import (
    ContentItemResponse,
    ContentReportReasonResponse,
    ReportedContentItemResponse,
)
from social_platform.app.admin.services.log_service import create_operation_log
from social_platform.app.domains.comment.models import Comment, CommentLike
from social_platform.app.domains.content_safety.events import (
    ContentModerationActionApplied,
    ReportedContentViolationConfirmed,
)
from social_platform.app.domains.content_safety.models import ContentReport
from social_platform.app.domains.heat import application as heat_service
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.reaction.models import Like
from social_platform.app.domains.search import application as search_service
from social_platform.app.shared.events import publish_domain_event


ContentType = Literal["post", "comment"]


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
    """以管理员身份删除帖子并清理相关互动数据。

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
    """以管理员身份删除评论并修正帖子、根评论计数与热度。

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
            heat_service.refresh_comment_heat_score(db, root)

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

    now = datetime.utcnow()
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
    _notify_reporters_content_deleted(db, reporter_ids, "comment", comment_id)
    delete_comment_as_admin(db, comment_id, admin, reason=reason, notify_author=notify_author)


def _pending_reports_query(db: Session, content_type: Optional[ContentType]) -> Query[ContentReport]:
    """构建待审举报查询，预加载被举报内容作者。"""

    query = db.query(ContentReport).options(
        joinedload(ContentReport.post).joinedload(Post.author),
        joinedload(ContentReport.comment).joinedload(Comment.owner),
    ).filter(ContentReport.status == "pending")
    if content_type:
        query = query.filter(ContentReport.target_type == content_type)
    return query


def _pending_reports_for_target(
    db: Session,
    content_type: ContentType,
    content_id: int,
) -> Query[ContentReport]:
    """构建指定内容的待审举报查询。"""

    query = db.query(ContentReport).filter(
        ContentReport.status == "pending",
        ContentReport.target_type == content_type,
    )
    if content_type == "post":
        return query.filter(ContentReport.post_id == content_id)
    return query.filter(ContentReport.comment_id == content_id)


def _pending_reporter_ids(db: Session, content_type: ContentType, content_id: int) -> list[int]:
    """读取指定内容的待审举报人 ID。"""

    return sorted({
        row[0]
        for row in _pending_reports_for_target(db, content_type, content_id)
        .with_entities(ContentReport.reporter_id)
        .all()
    })


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
            like_count=target.like_count,
            comment_count=target.comment_count,
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
        like_count=target.like_count,
        reply_count=target.reply_count,
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
