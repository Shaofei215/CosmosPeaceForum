"""通知领域的系统通知用例。

本模块封装公告、用户处罚和内容安全处理等无具体发送者的系统通知，供管理端
适配层和领域事件订阅器复用。
"""

from typing import Iterable

from sqlalchemy.orm import Session

from social_platform.app.domains.notification import application as notification_service


def create_system_notifications(
    db: Session,
    recipient_ids: Iterable[int],
    content: str,
    notification_type: str,
    resource_type: str = "system",
    resource_id: int = 0,
) -> int:
    """批量创建系统通知并返回去重后的接收人数。

    Args:
        db: SQLAlchemy 数据库会话。
        recipient_ids: 接收人 ID 序列，函数会按出现顺序去重。
        content: 通知正文。
        notification_type: 通知类型，如 ``announcement`` 或 ``moderation``。
        resource_type: 关联资源类型。
        resource_id: 关联资源 ID。

    Returns:
        int: 实际写入通知的接收人数。

    Raises:
        数据库写入异常会透传给调用方，由上层事务处理。
    """

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
            truncate_source_content=False,
        )
    return len(unique_recipient_ids)


def create_user_moderation_notice(
    db: Session,
    user_id: int,
    content: str,
) -> None:
    """为单个用户创建管理处罚通知。

    Args:
        db: SQLAlchemy 数据库会话。
        user_id: 被通知用户 ID。
        content: 通知正文。

    Raises:
        数据库写入异常会透传给调用方。
    """

    create_system_notifications(
        db=db,
        recipient_ids=[user_id],
        content=content,
        notification_type="moderation",
        resource_type="user",
        resource_id=user_id,
    )
