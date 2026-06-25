"""管理处罚申诉用例。

本模块连接公开通知申诉入口和管理端申诉处理流程。公开端只能基于本人收到的
处罚通知创建或覆盖待处理申诉；管理端按内容或用户维度读取、通过或拒绝申诉。
"""

from datetime import datetime
from typing import Literal, Optional

from sqlalchemy.orm import Session, joinedload

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import ModerationAppealItemResponse
from social_platform.app.admin.services.log_service import create_operation_log
from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.content_safety.admin_application import (
    restore_comment_as_admin,
    restore_post_as_admin,
)
from social_platform.app.domains.content_safety.models import ModerationAppeal
from social_platform.app.domains.notification.models import Notification
from social_platform.app.domains.notification.system import create_system_notifications
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User


AppealScope = Literal["content", "user"]
APPEAL_STATUS_PENDING = "pending"
APPEAL_STATUS_APPROVED = "approved"
APPEAL_STATUS_REJECTED = "rejected"


def create_or_update_appeal(
    db: Session,
    notification_id: int,
    appellant: User,
    reason: str,
) -> ModerationAppeal:
    """基于处罚通知创建申诉，待处理申诉再次提交时覆盖理由。

    Args:
        db: SQLAlchemy 数据库会话。
        notification_id: 用户收到的处罚通知 ID。
        appellant: 当前申诉用户。
        reason: 申诉理由，调用方已做长度校验。

    Returns:
        ModerationAppeal: 新建或更新后的申诉记录。

    Raises:
        ValueError: 通知不存在、通知不可申诉或申诉目标不属于当前用户时抛出。
    """

    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.recipient_id == appellant.id,
        Notification.type == "moderation",
    ).first()
    if not notification:
        raise ValueError("处罚通知不存在")
    if notification.resource_type not in {"post", "comment", "user"}:
        raise ValueError("该通知不支持申诉")
    if not _notification_targets_appellant(db, notification, appellant.id):
        raise ValueError("该通知不支持申诉")

    appeal = db.query(ModerationAppeal).filter(
        ModerationAppeal.notification_id == notification.id
    ).first()
    action_label = _build_action_label(notification)
    moderation_reason = _extract_moderation_reason(notification.source_content)
    if appeal and appeal.status == APPEAL_STATUS_PENDING:
        appeal.appeal_reason = reason
        appeal.action_label = action_label
        appeal.moderation_reason = moderation_reason
        appeal.updated_at = datetime.utcnow()
    elif appeal:
        raise ValueError("该申诉已处理，不能再次提交")
    else:
        appeal = ModerationAppeal(
            notification_id=notification.id,
            appellant_id=appellant.id,
            target_type=notification.resource_type,
            target_id=notification.resource_id,
            action_label=action_label,
            moderation_reason=moderation_reason,
            appeal_reason=reason,
            status=APPEAL_STATUS_PENDING,
        )
        db.add(appeal)
    db.commit()
    db.refresh(appeal)
    return appeal


def get_notification_appeal_statuses(
    db: Session,
    notification_ids: list[int],
) -> dict[int, str]:
    """批量读取通知对应申诉状态，供通知列表响应附加按钮状态。"""

    if not notification_ids:
        return {}
    return {
        item.notification_id: item.status
        for item in db.query(ModerationAppeal)
        .filter(ModerationAppeal.notification_id.in_(notification_ids))
        .all()
    }


def is_notification_appealable(db: Session, notification: Notification, user_id: int) -> bool:
    """判断当前用户收到的处罚通知是否允许创建申诉。"""

    if notification.type != "moderation":
        return False
    if notification.source_content and notification.source_content.startswith("你的申诉已"):
        return False
    if notification.resource_type not in {"post", "comment", "user"}:
        return False
    return _notification_targets_appellant(db, notification, user_id)


def list_pending_appeals(
    db: Session,
    scope: AppealScope,
    skip: int,
    limit: int,
    keyword: Optional[str] = None,
) -> tuple[list[ModerationAppealItemResponse], int]:
    """分页读取待处理申诉列表。

    Args:
        db: SQLAlchemy 数据库会话。
        scope: 内容申诉或用户申诉。
        skip: 分页偏移。
        limit: 分页大小。
        keyword: 申诉人、目标内容或理由关键词。

    Returns:
        tuple[list[ModerationAppealItemResponse], int]: 当前页申诉和总数。
    """

    target_types = ["post", "comment"] if scope == "content" else ["user"]
    query = db.query(ModerationAppeal).options(joinedload(ModerationAppeal.appellant)).filter(
        ModerationAppeal.status == APPEAL_STATUS_PENDING,
        ModerationAppeal.target_type.in_(target_types),
    )
    items = query.order_by(ModerationAppeal.updated_at.desc(), ModerationAppeal.id.desc()).all()
    responses = [_serialize_appeal(db, item) for item in items]
    keyword_value = keyword.strip().lower() if keyword else None
    if keyword_value:
        responses = [
            item for item in responses
            if keyword_value in (item.appellant_username or "").lower()
            or keyword_value in item.target_label.lower()
            or keyword_value in (item.target_content or "").lower()
            or keyword_value in (item.moderation_reason or "").lower()
            or keyword_value in item.appeal_reason.lower()
        ]
    total = len(responses)
    return responses[skip:skip + limit], total


def approve_content_appeal(db: Session, appeal_id: int, admin: PlatformAdminUser) -> None:
    """通过内容申诉并恢复对应归档内容。"""

    appeal = _get_pending_appeal(db, appeal_id, scope="content")
    if appeal.target_type == "comment":
        restore_comment_as_admin(db, appeal.target_id, admin)
    else:
        restore_post_as_admin(db, appeal.target_id, admin)
    _mark_appeal_resolved(
        db,
        appeal_id=appeal_id,
        admin=admin,
        status=APPEAL_STATUS_APPROVED,
        notification="你的申诉已通过，相关内容已恢复公开。",
    )


def approve_user_appeal(db: Session, appeal_id: int, admin: PlatformAdminUser) -> None:
    """标记用户申诉通过并发送结果通知。

    用户处罚的具体恢复由管理端复用用户处理对话框完成，本函数只关闭申诉单并通知用户。
    """

    appeal = _get_pending_appeal(db, appeal_id, scope="user")
    _mark_appeal_resolved(
        db,
        appeal_id=appeal.id,
        admin=admin,
        status=APPEAL_STATUS_APPROVED,
        notification="你的申诉已通过，账号处理已更新。",
    )


def reject_appeal(db: Session, appeal_id: int, admin: PlatformAdminUser, reason: str) -> None:
    """拒绝申诉，不改变原处罚或归档状态，并通知申诉用户。"""

    appeal = _get_pending_appeal(db, appeal_id)
    _mark_appeal_resolved(
        db,
        appeal_id=appeal.id,
        admin=admin,
        status=APPEAL_STATUS_REJECTED,
        reject_reason=reason,
        notification=f"你的申诉已被拒绝。\n原因：{reason}",
    )


def _notification_targets_appellant(db: Session, notification: Notification, user_id: int) -> bool:
    """确认处罚通知对应的处理对象确实属于申诉用户。"""

    if notification.resource_type == "user":
        return notification.resource_id == user_id
    if notification.resource_type == "post":
        return db.query(Post.id).filter(
            Post.id == notification.resource_id,
            Post.author_id == user_id,
        ).first() is not None
    if notification.resource_type == "comment":
        return db.query(Comment.id).filter(
            Comment.id == notification.resource_id,
            Comment.owner_id == user_id,
        ).first() is not None
    return False


def _build_action_label(notification: Notification) -> str:
    """根据通知目标构建管理端处理操作说明。"""

    if notification.resource_type == "user":
        return "用户管控"
    if notification.resource_type == "comment":
        return "归档评论"
    return "归档内容"


def _extract_moderation_reason(content: Optional[str]) -> Optional[str]:
    """从处罚通知正文中提取原因文本。"""

    if not content or "原因：" not in content:
        return None
    return content.split("原因：", 1)[1].strip() or None


def _serialize_appeal(db: Session, appeal: ModerationAppeal) -> ModerationAppealItemResponse:
    """把申诉模型转换为管理端列表 DTO。"""

    target_label = f"{appeal.target_type} #{appeal.target_id}"
    target_content = None
    if appeal.target_type == "post":
        post = db.query(Post).filter(Post.id == appeal.target_id).first()
        if post:
            target_label = "帖子/文章 #" + str(post.id)
            target_content = post.content
    elif appeal.target_type == "comment":
        comment = db.query(Comment).filter(Comment.id == appeal.target_id).first()
        if comment:
            target_label = "评论 #" + str(comment.id)
            target_content = comment.content
    else:
        user = db.query(User).filter(User.id == appeal.target_id).first()
        if user:
            target_label = "@" + (user.username or f"user_{user.id}")
            target_content = user.bio
    return ModerationAppealItemResponse(
        id=appeal.id,
        notification_id=appeal.notification_id,
        appellant_id=appeal.appellant_id,
        appellant_username=appeal.appellant.username if appeal.appellant else None,
        target_type=appeal.target_type,
        target_id=appeal.target_id,
        target_label=target_label,
        target_content=target_content,
        action_label=appeal.action_label,
        moderation_reason=appeal.moderation_reason,
        appeal_reason=appeal.appeal_reason,
        status=appeal.status,
        created_at=appeal.created_at,
        updated_at=appeal.updated_at,
    )


def _get_pending_appeal(
    db: Session,
    appeal_id: int,
    scope: Optional[AppealScope] = None,
) -> ModerationAppeal:
    """读取待处理申诉，并按需要限制内容或用户范围。"""

    query = db.query(ModerationAppeal).filter(
        ModerationAppeal.id == appeal_id,
        ModerationAppeal.status == APPEAL_STATUS_PENDING,
    )
    if scope == "content":
        query = query.filter(ModerationAppeal.target_type.in_(["post", "comment"]))
    elif scope == "user":
        query = query.filter(ModerationAppeal.target_type == "user")
    appeal = query.first()
    if not appeal:
        raise ValueError("待处理申诉不存在")
    return appeal


def _mark_appeal_resolved(
    db: Session,
    appeal_id: int,
    admin: PlatformAdminUser,
    status: str,
    notification: str,
    reject_reason: Optional[str] = None,
) -> None:
    """关闭申诉、记录操作日志并发送处理结果通知。"""

    appeal = db.query(ModerationAppeal).filter(ModerationAppeal.id == appeal_id).first()
    if not appeal:
        raise ValueError("申诉不存在")
    appeal.status = status
    appeal.reject_reason = reject_reason
    appeal.resolved_at = datetime.utcnow()
    appeal.resolved_by_admin_id = admin.id
    appeal.updated_at = datetime.utcnow()
    create_system_notifications(
        db=db,
        recipient_ids=[appeal.appellant_id],
        content=notification,
        notification_type="moderation",
        resource_type=appeal.target_type,
        resource_id=appeal.target_id,
    )
    create_operation_log(
        db,
        admin,
        action=f"{status}_moderation_appeal",
        target_type="moderation_appeal",
        target_id=appeal.id,
        details={"reject_reason": reject_reason},
    )
    db.commit()
