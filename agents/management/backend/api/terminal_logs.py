"""
Management Backend - 终端日志路由
"""

import json
import asyncio
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from agents.management.backend.api.deps import require_permission
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.schemas import TerminalLogListResponse
from agents.management.backend.services.permissions import PERMISSION_VIEW_LOGS
from agents.management.backend.services.terminal_log_service import terminal_log_capture

router = APIRouter()


@router.get("/", response_model=TerminalLogListResponse)
def get_terminal_logs(
    skip: int = 0,
    limit: int = 200,
    level: str = Query(None),
    keyword: str = Query(None),
    role: str = Query(None),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_VIEW_LOGS)),
):
    """获取终端日志列表"""
    logs, total = terminal_log_capture.get_logs(
        skip=skip,
        limit=limit,
        level=level,
        keyword=keyword,
        role=role,
    )
    return TerminalLogListResponse(items=logs, total=total)


@router.get("/recent")
def get_recent_terminal_logs(
    count: int = 50,
    role: str = Query(None),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_VIEW_LOGS)),
):
    """获取最近的终端日志"""
    logs = terminal_log_capture.get_recent_logs(count=count, role=role)
    return {"items": logs, "total": len(logs)}


@router.get("/stream")
def stream_terminal_logs(
    current_admin: AdminUser = Depends(require_permission(PERMISSION_VIEW_LOGS)),
):
    """SSE 流式推送终端日志"""

    async def event_stream():
        current_logs = terminal_log_capture.get_recent_logs(0)
        last_count = len(current_logs)

        yield f"event: init\ndata: {json.dumps({'message': 'Terminal log stream started'}, ensure_ascii=False)}\n\n"

        while True:
            current_logs = terminal_log_capture.get_recent_logs(0)
            if len(current_logs) > last_count:
                for log in current_logs[last_count:]:
                    yield f"event: log\ndata: {json.dumps(log, ensure_ascii=False)}\n\n"
                last_count = len(current_logs)

            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/clear")
def clear_terminal_logs(
    current_admin: AdminUser = Depends(require_permission(PERMISSION_VIEW_LOGS)),
):
    """清空终端日志"""
    terminal_log_capture.clear()
    return {"message": "终端日志已清空"}
