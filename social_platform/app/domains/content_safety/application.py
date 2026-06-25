"""内容安全领域公开举报用例。"""

import json
from datetime import datetime
from social_platform.app.core.timezone import local_now
from typing import Literal

from sqlalchemy.orm import Session, joinedload

from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.content_safety.models import ContentReport, ContentReportEscalation
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User


ReportTargetType = Literal["post", "comment", "user"]
REPORT_STATUS_PENDING = "pending"
USER_REVIEW_ESCALATION_CONTENT_LIMIT = 5


class ReportTargetNotFoundError(ValueError):
    """被举报的帖子、评论或用户不存在时抛出。"""


class SelfReportError(ValueError):
    """用户举报自己或自己发布的内容时抛出。"""


def create_content_report(
    db: Session,
    reporter: User,
    target_type: ReportTargetType,
    target_id: int,
    reason: str,
) -> ContentReport:
    """创建或更新当前用户对同一目标的待审举报。

    Args:
        db: SQLAlchemy 数据库会话。
        reporter: 发起举报的用户。
        target_type: 被举报目标类型。
        target_id: 被举报目标 ID。
        reason: 举报原因。

    Returns:
        ContentReport: 新建或更新后的举报记录。

    Raises:
        ReportTargetNotFoundError: 被举报目标不存在时抛出。
        SelfReportError: 用户举报自己或自己内容时抛出。
    """

    post_id, comment_id, user_id, owner_id = _resolve_target(db, target_type, target_id)
    if owner_id == reporter.id:
        raise SelfReportError("不能举报自己或自己的内容")

    query = db.query(ContentReport).filter(
        ContentReport.reporter_id == reporter.id,
        ContentReport.status == REPORT_STATUS_PENDING,
    )
    if target_type == "post":
        query = query.filter(ContentReport.post_id == post_id)
    elif target_type == "comment":
        query = query.filter(ContentReport.comment_id == comment_id)
    else:
        query = query.filter(ContentReport.user_id == user_id)

    existing = query.first()
    if existing:
        existing.reason = reason
        existing.updated_at = local_now()
        db.commit()
        db.refresh(existing)
        _maybe_create_user_review_escalation(db, owner_id)
        return existing

    report = ContentReport(
        reporter_id=reporter.id,
        target_type=target_type,
        post_id=post_id,
        comment_id=comment_id,
        user_id=user_id,
        reason=reason,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    _maybe_create_user_review_escalation(db, owner_id)
    return report


def _maybe_create_user_review_escalation(db: Session, owner_id: int) -> None:
    """在同一作者有 5 条不同待审内容被举报时创建用户级审查批次。

    Args:
        db: SQLAlchemy 数据库会话。
        owner_id: 被举报内容作者 ID。

    Raises:
        数据库异常会透传给调用方。
    """

    candidate_reports = (
        db.query(ContentReport)
        .options(
            joinedload(ContentReport.post).joinedload(Post.author),
            joinedload(ContentReport.comment).joinedload(Comment.owner),
        )
        .filter(
            ContentReport.status == REPORT_STATUS_PENDING,
            ContentReport.escalation_id.is_(None),
            ContentReport.target_type.in_(("post", "comment")),
        )
        .order_by(ContentReport.created_at.asc(), ContentReport.id.asc())
        .all()
    )
    selected_by_content: dict[tuple[str, int], ContentReport] = {}
    for report in candidate_reports:
        target_key: tuple[str, int] | None = None
        if report.target_type == "post" and report.post and report.post.author_id == owner_id:
            target_key = ("post", report.post.id)
        elif report.target_type == "comment" and report.comment and report.comment.owner_id == owner_id:
            target_key = ("comment", report.comment.id)
        if target_key is not None and target_key not in selected_by_content:
            selected_by_content[target_key] = report
        if len(selected_by_content) >= USER_REVIEW_ESCALATION_CONTENT_LIMIT:
            break

    if len(selected_by_content) < USER_REVIEW_ESCALATION_CONTENT_LIMIT:
        return

    selected_reports = list(selected_by_content.values())
    trigger_contents = [_trigger_content_payload(report) for report in selected_reports]
    escalation = ContentReportEscalation(
        user_id=owner_id,
        reason=f"{USER_REVIEW_ESCALATION_CONTENT_LIMIT} 条不同内容被举报触发账号审查",
        trigger_content_json=json.dumps(trigger_contents, ensure_ascii=False),
    )
    db.add(escalation)
    db.flush()
    for report in selected_reports:
        report.escalation_id = escalation.id
        report.updated_at = local_now()
    db.commit()


def _trigger_content_payload(report: ContentReport) -> dict[str, object]:
    """把触发用户审查的内容举报压缩为可审计 JSON。"""

    if report.target_type == "post" and report.post:
        return {
            "type": "post",
            "id": report.post.id,
            "title": report.post.title,
            "content": report.post.content,
            "reason": report.reason,
            "reported_at": report.created_at.isoformat() if report.created_at else None,
        }
    if report.target_type == "comment" and report.comment:
        return {
            "type": "comment",
            "id": report.comment.id,
            "post_id": report.comment.post_id,
            "content": report.comment.content,
            "reason": report.reason,
            "reported_at": report.created_at.isoformat() if report.created_at else None,
        }
    return {
        "type": report.target_type,
        "id": report.post_id or report.comment_id,
        "reason": report.reason,
        "reported_at": report.created_at.isoformat() if report.created_at else None,
    }


def _resolve_target(
    db: Session,
    target_type: ReportTargetType,
    target_id: int,
) -> tuple[int | None, int | None, int | None, int]:
    """解析举报目标并返回持久化外键和目标归属用户。

    Args:
        db: SQLAlchemy 数据库会话。
        target_type: 被举报目标类型。
        target_id: 被举报目标 ID。

    Returns:
        tuple[int | None, int | None, int | None, int]: 帖子、评论、用户 ID 和目标归属用户 ID。

    Raises:
        ReportTargetNotFoundError: 目标帖子、评论或用户不存在时抛出。
    """

    if target_type == "post":
        post = db.query(Post).filter(Post.id == target_id, Post.moderation_status == "active").first()
        if not post:
            raise ReportTargetNotFoundError("帖子不存在")
        return post.id, None, None, post.author_id

    if target_type == "comment":
        comment = db.query(Comment).filter(
            Comment.id == target_id,
            Comment.moderation_status == "active",
        ).first()
        if not comment:
            raise ReportTargetNotFoundError("评论不存在")
        return None, comment.id, None, comment.owner_id

    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        raise ReportTargetNotFoundError("用户不存在")
    return None, None, user.id, user.id
