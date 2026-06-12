from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from social_platform.app.domains.comment.models import Comment
from social_platform.app.models.content_report import ContentReport
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User


ReportTargetType = Literal["post", "comment"]
REPORT_STATUS_PENDING = "pending"


class ReportTargetNotFoundError(ValueError):
    pass


class SelfReportError(ValueError):
    pass


def create_content_report(
    db: Session,
    reporter: User,
    target_type: ReportTargetType,
    target_id: int,
    reason: str,
) -> ContentReport:
    post_id, comment_id, owner_id = _resolve_target(db, target_type, target_id)
    if owner_id == reporter.id:
        raise SelfReportError("不能举报自己的内容")

    query = db.query(ContentReport).filter(
        ContentReport.reporter_id == reporter.id,
        ContentReport.status == REPORT_STATUS_PENDING,
    )
    if target_type == "post":
        query = query.filter(ContentReport.post_id == post_id)
    else:
        query = query.filter(ContentReport.comment_id == comment_id)

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
) -> tuple[int | None, int | None, int]:
    if target_type == "post":
        post = db.query(Post).filter(Post.id == target_id).first()
        if not post:
            raise ReportTargetNotFoundError("帖子不存在")
        return post.id, None, post.author_id

    comment = db.query(Comment).filter(Comment.id == target_id).first()
    if not comment:
        raise ReportTargetNotFoundError("评论不存在")
    return None, comment.id, comment.owner_id
