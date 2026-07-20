"""Management Backend - 操作日志服务"""

import json
from datetime import timedelta
from typing import Any, List, Optional

from sqlmodel import Session, select

from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.models.operation_log import OperationLog
from agents.logging_config import get_log_context
from agents.management.backend.core.timezone import local_now


def create_log(
    db: Session,
    admin: Optional[AdminUser],
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    details: Optional[dict[str, Any] | str] = None,
) -> OperationLog:
    """创建操作日志"""
    if isinstance(details, str):
        try:
            parsed_details = json.loads(details) if details else {}
        except json.JSONDecodeError:
            parsed_details = {"message": details}
    else:
        parsed_details = dict(details or {})
    context = get_log_context()
    for key in ("request_id", "client_ip"):
        if context.get(key) is not None:
            parsed_details.setdefault(key, context[key])
    details_value = json.dumps(parsed_details, ensure_ascii=False)
    log = OperationLog(
        operator_id=admin.id if admin else None,
        operator_username=admin.username if admin else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details_value,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def cleanup_expired_logs(db: Session, retention_days: int) -> int:
    """删除超过保留期限的 Management 管理审计日志。"""

    cutoff = local_now() - timedelta(days=retention_days)
    expired = list(db.exec(select(OperationLog).where(OperationLog.created_at < cutoff)).all())
    for item in expired:
        db.delete(item)
    db.commit()
    return len(expired)


def list_logs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    operator_id: Optional[int] = None,
    action: Optional[str] = None,
) -> tuple[List[OperationLog], int]:
    """获取操作日志列表"""
    stmt = select(OperationLog)
    if target_type:
        stmt = stmt.where(OperationLog.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(OperationLog.target_id == target_id)
    if operator_id:
        stmt = stmt.where(OperationLog.operator_id == operator_id)
    if action:
        stmt = stmt.where(OperationLog.action == action)

    count_stmt = stmt
    total = len(db.exec(count_stmt).all())

    stmt = stmt.order_by(OperationLog.created_at.desc()).offset(skip).limit(limit)
    items = db.exec(stmt).all()
    return list(items), total


def log_to_response(log: OperationLog) -> dict:
    """将日志转换为响应字典"""
    return {
        "id": log.id,
        "operator_id": log.operator_id,
        "operator_username": log.operator_username,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "details": log.details,
        "created_at": log.created_at,
    }
