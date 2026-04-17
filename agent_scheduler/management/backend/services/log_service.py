"""
Management Backend - 操作日志服务
"""

from typing import List, Optional

from sqlmodel import Session, select

from agent_scheduler.management.backend.models.operation_log import OperationLog


def create_log(
    db: Session,
    operator_id: int,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    details: str = "",
) -> OperationLog:
    """创建操作日志"""
    log = OperationLog(
        operator_id=operator_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_logs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    target_type: Optional[str] = None,
    operator_id: Optional[int] = None,
) -> tuple[List[OperationLog], int]:
    """获取操作日志列表"""
    stmt = select(OperationLog)
    if target_type:
        stmt = stmt.where(OperationLog.target_type == target_type)
    if operator_id:
        stmt = stmt.where(OperationLog.operator_id == operator_id)

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
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "details": log.details,
        "created_at": log.created_at,
    }
