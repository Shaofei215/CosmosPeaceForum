"""Management 短期记忆快照管理路由。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from agents.management.backend.api.deps import require_permission
from agents.management.backend.core.database import get_db
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.schemas import (
    ShortTermMemoryResponse,
    ShortTermMemoryUpdateRequest,
)
from agents.management.backend.services.log_service import create_log
from agents.management.backend.services.permissions import PERMISSION_MANAGE_MEMORIES
from agents.management.backend.services.short_term_memory_service import (
    get_short_term_memory,
    update_short_term_memory,
)


router = APIRouter()


@router.get("/{agent_id}", response_model=ShortTermMemoryResponse)
def read_short_term_memory(
    agent_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_MEMORIES)),
) -> ShortTermMemoryResponse:
    """读取一个内部角色当前的短期记忆快照。"""

    memory = get_short_term_memory(db, agent_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return memory


@router.put("/{agent_id}", response_model=ShortTermMemoryResponse)
def replace_short_term_memory(
    agent_id: int,
    request: ShortTermMemoryUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_MEMORIES)),
) -> ShortTermMemoryResponse:
    """以完整 Markdown 覆盖一个内部角色的短期记忆快照。"""

    memory = update_short_term_memory(db, agent_id, request.content)
    if memory is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    create_log(
        db,
        current_admin,
        "update_short_term_memory",
        "short_term_memory",
        agent_id,
        details={
            "revision": memory.revision,
            "cleared": memory.content == "",
        },
    )
    return memory
