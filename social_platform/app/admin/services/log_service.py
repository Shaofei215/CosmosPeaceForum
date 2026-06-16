"""管理端操作日志服务。"""

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.models.operation_log import PlatformAdminOperationLog


def create_operation_log(
    db: Session,
    admin: Optional[PlatformAdminUser],
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
) -> PlatformAdminOperationLog:
    """创建一条管理员操作日志但不主动提交事务。"""

    log = PlatformAdminOperationLog(
        operator_id=admin.id if admin else None,
        operator_username=admin.username if admin else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=json.dumps(details or {}, ensure_ascii=False),
    )
    db.add(log)
    return log


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
