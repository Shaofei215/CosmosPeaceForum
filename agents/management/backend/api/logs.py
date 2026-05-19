"""
Management Backend - 操作日志路由
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.api.deps import require_permission
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.schemas import OperationLogListResponse
from agents.management.backend.services import log_service
from agents.management.backend.services.permissions import PERMISSION_VIEW_LOGS

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
