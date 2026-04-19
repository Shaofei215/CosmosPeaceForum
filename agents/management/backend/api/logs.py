"""
Management Backend - 操作日志路由
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.api.deps import get_current_admin
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.schemas import OperationLogListResponse
from agents.management.backend.services import log_service

router = APIRouter()


@router.get("/", response_model=OperationLogListResponse)
def list_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取操作日志列表"""
    items, total = log_service.list_logs(db, skip, limit)
    responses = [log_service.log_to_response(log) for log in items]
    return OperationLogListResponse(items=responses, total=total)
