"""管理端操作日志服务。"""

import json
from datetime import timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.models.operation_log import PlatformAdminOperationLog
from social_platform.app.core.logging import get_log_context
from social_platform.app.core.timezone import local_now


def create_operation_log(
    db: Session,
    admin: Optional[PlatformAdminUser],
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
) -> PlatformAdminOperationLog:
    """创建一条管理员操作日志但不主动提交事务。"""

    enriched_details = dict(details or {})
    context = get_log_context()
    for key in ("request_id", "client_ip"):
        if context.get(key) is not None:
            enriched_details.setdefault(key, context[key])

    log = PlatformAdminOperationLog(
        operator_id=admin.id if admin else None,
        operator_username=admin.username if admin else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=json.dumps(enriched_details, ensure_ascii=False),
    )
    db.add(log)
    return log


def cleanup_expired_operation_logs(db: Session, retention_days: int) -> int:
    """删除超过保留期限的平台管理员审计日志。

    Args:
        db: 当前数据库会话。
        retention_days: 最长保留天数。

    Returns:
        int: 实际删除的审计记录数。
    """

    cutoff = local_now() - timedelta(days=retention_days)
    deleted = (
        db.query(PlatformAdminOperationLog)
        .filter(PlatformAdminOperationLog.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted)


def list_operation_logs(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
) -> tuple[list[PlatformAdminOperationLog], int]:
    """分页读取管理员操作日志。"""

    query = db.query(PlatformAdminOperationLog)
    if action:
        query = query.filter(PlatformAdminOperationLog.action == action)
    if target_type:
        query = query.filter(PlatformAdminOperationLog.target_type == target_type)
    total = query.count()
    items = (
        query.order_by(PlatformAdminOperationLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total
