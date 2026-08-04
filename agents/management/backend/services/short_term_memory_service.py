"""短期记忆当前快照的管理端服务。"""

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from agents.agents_scheduler.short_term_memory.clock import project_scheduler_timestamp
from agents.management.backend.models.agent_config import AgentConfig
from agents.management.backend.models.scheduler_time_state import SchedulerTimeState
from agents.management.backend.models.short_term_memory import ShortTermMemory
from agents.management.backend.schemas import ShortTermMemoryResponse


def get_short_term_memory(
    db: Session,
    agent_id: int,
) -> ShortTermMemoryResponse | None:
    """读取角色的短期记忆，尚未建立时返回显式空状态。

    Args:
        db: Management 数据库会话。
        agent_id: 内部角色配置 ID。

    Returns:
        ShortTermMemoryResponse | None: 角色不存在时返回 ``None``；否则返回当前快照。
    """

    agent = db.get(AgentConfig, agent_id)
    if agent is None:
        return None

    memory = db.get(ShortTermMemory, agent_id)
    if memory is None:
        return ShortTermMemoryResponse(agent_id=agent_id, content="")
    return _to_response(memory)


def update_short_term_memory(
    db: Session,
    agent_id: int,
    content: str,
) -> ShortTermMemoryResponse | None:
    """原子增加 revision 并完整覆盖角色短期记忆。

    Args:
        db: Management 数据库会话。
        agent_id: 内部角色配置 ID。
        content: 保存后的完整 Markdown；空字符串表示清空。

    Returns:
        ShortTermMemoryResponse | None: 角色不存在时返回 ``None``，否则返回新版本。
    """

    agent = db.get(AgentConfig, agent_id)
    if agent is None:
        return None

    updated_at = _current_scaled_timestamp(db, agent)
    updated_login_count = max(0, int(agent.total_login_count or 0))
    memory_table = ShortTermMemory.__table__  # type: ignore[attr-defined]
    statement = (
        update(memory_table)
        .where(memory_table.c.id == agent_id)
        .values(
            content=content,
            revision=memory_table.c.revision + 1,
            updated_at=updated_at,
            updated_login_count=updated_login_count,
        )
    )
    result = db.exec(statement)
    if result.rowcount == 0:
        db.add(
            ShortTermMemory(
                id=agent_id,
                content=content,
                revision=1,
                updated_at=updated_at,
                updated_login_count=updated_login_count,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            # 另一写入方可能刚刚创建了同一角色的首个版本；回滚后按已有记录递增。
            db.rollback()
            db.exec(statement)
            db.commit()
    else:
        db.commit()

    db.expire_all()
    memory = db.get(ShortTermMemory, agent_id)
    if memory is None:
        raise RuntimeError("短期记忆提交成功后无法读取")
    return _to_response(memory)


def delete_short_term_memory(db: Session, agent_id: int) -> bool:
    """删除角色配置前清理其短期记忆当前快照。

    Args:
        db: Management 数据库会话。
        agent_id: 即将删除的内部角色配置 ID。

    Returns:
        bool: 原先存在快照时返回 ``True``。
    """

    memory = db.get(ShortTermMemory, agent_id)
    if memory is None:
        return False
    db.delete(memory)
    db.flush()
    return True


def _current_scaled_timestamp(db: Session, agent: AgentConfig) -> float:
    """从持久化 Scheduler 锚点计算管理端编辑发生的缩放时间。"""

    state = db.get(SchedulerTimeState, 1)
    fallback_query = select(func.max(AgentConfig.last_login_timestamp))
    latest_login_timestamp = db.exec(fallback_query).one() or agent.last_login_timestamp or 0.0
    if state is None:
        return project_scheduler_timestamp(
            None,
            fallback_timestamp=float(latest_login_timestamp),
        )
    return project_scheduler_timestamp(
        {
            "scaled_timestamp": state.scaled_timestamp,
            "real_timestamp": state.real_timestamp,
            "scale": state.scale,
            "paused": state.paused,
        },
        fallback_timestamp=float(latest_login_timestamp),
    )


def _to_response(memory: ShortTermMemory) -> ShortTermMemoryResponse:
    """将短期记忆持久化模型转换成稳定 API 响应。"""

    return ShortTermMemoryResponse(
        agent_id=memory.id,
        content=memory.content,
        revision=memory.revision,
        updated_at=memory.updated_at,
        updated_login_count=memory.updated_login_count,
    )
