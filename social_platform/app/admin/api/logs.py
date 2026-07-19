from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import (
    OperationLogListResponse,
    OperationLogResponse,
    TerminalLogListResponse,
    TerminalLogResponse,
)
from social_platform.app.admin.services.log_service import list_operation_logs
from social_platform.app.admin.services.permissions import PERMISSION_VIEW_LOGS
from social_platform.app.admin.services.terminal_log_service import terminal_log_capture
from social_platform.app.api.deps import get_db

router = APIRouter(prefix="/logs", tags=["platform-admin-logs"])


@router.get("/operations", response_model=OperationLogListResponse)
async def operation_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_VIEW_LOGS)),
):
    items, total = list_operation_logs(
        db,
        skip=skip,
        limit=limit,
        action=action,
        target_type=target_type,
    )
    return OperationLogListResponse(
        items=[OperationLogResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/terminal", response_model=TerminalLogListResponse)
async def terminal_logs(
    count: int = Query(200, ge=1, le=1000),
    level: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_VIEW_LOGS)),
):
    items, total = terminal_log_capture.recent(count=count, level=level, keyword=keyword)
    return TerminalLogListResponse(
        items=[TerminalLogResponse.model_validate(item) for item in items],
        total=total,
    )


@router.delete("/terminal")
async def clear_terminal_logs(
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_VIEW_LOGS)),
):
    terminal_log_capture.clear()
    return {"message": "终端日志已清空"}
