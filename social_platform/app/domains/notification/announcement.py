"""通知领域的公告发布用例。"""

from typing import Optional

from sqlalchemy.orm import Session

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.services.log_service import create_operation_log
from social_platform.app.domains.notification.system import create_system_notifications
from social_platform.app.domains.user.models import User


def publish_announcement(
    db: Session,
    content: str,
    admin: PlatformAdminUser,
    recipient_ids: Optional[list[int]] = None,
) -> int:
    """发布系统公告并记录管理员操作日志。

    Args:
        db: SQLAlchemy 数据库会话。
        content: 公告正文。
        admin: 执行发布的管理员。
        recipient_ids: 可选接收人 ID；为空时发送给所有用户。

    Returns:
        int: 实际接收公告的用户数量。

    Raises:
        ValueError: 指定接收人中存在不存在的用户时抛出。
    """

    if recipient_ids is None:
        recipient_ids = [row[0] for row in db.query(User.id).all()]
    else:
        requested_ids = list(dict.fromkeys(recipient_ids))
        existing_ids = {
            row[0]
            for row in db.query(User.id).filter(User.id.in_(requested_ids)).all()
        }
        missing_ids = sorted(set(requested_ids) - existing_ids)
        if missing_ids:
            raise ValueError(f"用户不存在：{', '.join(str(user_id) for user_id in missing_ids)}")
        recipient_ids = requested_ids

    recipient_count = create_system_notifications(
        db=db,
        recipient_ids=recipient_ids,
        content=content,
        notification_type="announcement",
    )
    create_operation_log(
        db,
        admin,
        action="publish_announcement",
        target_type="announcement",
        target_id=None,
        details={"recipient_count": recipient_count},
    )
    db.commit()
    return recipient_count
