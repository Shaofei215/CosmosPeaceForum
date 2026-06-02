"""
Management Backend - 操作日志路由
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.api.deps import require_permission
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.schemas import OperationLogListResponse, TerminalLogListResponse
from agents.management.backend.services import log_service
from agents.management.backend.services.permissions import PERMISSION_VIEW_LOGS
from agents.management.backend.services.terminal_log_service import terminal_log_capture

router = APIRouter()


@router.get("/", response_model=OperationLogListResponse)
def list_logs(
    skip: int = 0,
    limit: int = 100,
    agent_id: int | None = Query(None),
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_VIEW_LOGS)),
):
    """获取操作日志列表"""
    items, total = log_service.list_logs(
        db,
        skip,
        limit,
        target_type=target_type or ("agent" if agent_id is not None else None),
        target_id=agent_id,
        action=action,
    )
    responses = [log_service.log_to_response(log) for log in items]
    return OperationLogListResponse(items=responses, total=total)


@router.get("/terminal", response_model=TerminalLogListResponse)
def terminal_logs(
    count: int = Query(200, ge=1, le=1000),
    level: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    role: str | None = Query(default=None),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_VIEW_LOGS)),
):
    """获取最近的终端日志，用于管理端轮询刷新。"""
    items, total = terminal_log_capture.recent(
        count=count,
        level=level,
        keyword=keyword,
        role=role,
    )
    return TerminalLogListResponse(items=items, total=total)


@router.delete("/terminal")
def clear_terminal_logs(
    current_admin: AdminUser = Depends(require_permission(PERMISSION_VIEW_LOGS)),
):
    """清空终端日志。"""
    terminal_log_capture.clear()
    return {"message": "终端日志已清空"}
