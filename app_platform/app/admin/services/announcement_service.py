from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app_platform.app.admin.models.admin_user import PlatformAdminUser
from app_platform.app.admin.schemas import AdminAnnouncementRequest
from app_platform.app.admin.services.log_service import create_operation_log
from app_platform.app.models.user import User
from app_platform.app.services import notification_service


def create_system_notifications(
    db: Session,
    recipient_ids: Iterable[int],
    content: str,
    notification_type: str,
    resource_type: str = "system",
    resource_id: int = 0,
) -> int:
    unique_recipient_ids = list(dict.fromkeys(recipient_ids))
    for recipient_id in unique_recipient_ids:
        notification_service.create_notification(
            db=db,
            recipient_id=recipient_id,
            sender_id=None,
            notification_type=notification_type,
            resource_type=resource_type,
            resource_id=resource_id,
            source_content=content,
        )
    return len(unique_recipient_ids)


def create_user_moderation_notice(
    db: Session,
    user_id: int,
    content: str,
) -> None:
    create_system_notifications(
        db=db,
        recipient_ids=[user_id],
        content=content,
        notification_type="moderation",
        resource_type="user",
        resource_id=user_id,
    )


def publish_announcement(
    db: Session,
    request: AdminAnnouncementRequest,
    admin: PlatformAdminUser,
    recipient_ids: Optional[list[int]] = None,
) -> int:
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
        content=request.content,
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
