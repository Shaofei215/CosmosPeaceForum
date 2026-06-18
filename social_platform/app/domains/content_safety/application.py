"""内容安全领域公开举报用例。"""

from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.content_safety.models import ContentReport
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User


ReportTargetType = Literal["post", "comment", "user"]
REPORT_STATUS_PENDING = "pending"


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
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
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
    return report


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
        post = db.query(Post).filter(Post.id == target_id).first()
        if not post:
            raise ReportTargetNotFoundError("帖子不存在")
        return post.id, None, None, post.author_id

    if target_type == "comment":
        comment = db.query(Comment).filter(Comment.id == target_id).first()
        if not comment:
            raise ReportTargetNotFoundError("评论不存在")
        return None, comment.id, None, comment.owner_id

    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        raise ReportTargetNotFoundError("用户不存在")
    return None, None, user.id, user.id
