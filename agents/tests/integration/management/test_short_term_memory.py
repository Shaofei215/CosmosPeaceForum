"""Management 短期记忆快照服务集成测试。"""

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from agents.management.backend.models.agent_config import AgentConfig
from agents.management.backend.models.scheduler_time_state import SchedulerTimeState
from agents.management.backend.models.short_term_memory import ShortTermMemory
from agents.management.backend.services.short_term_memory_service import (
    delete_short_term_memory,
    get_short_term_memory,
    update_short_term_memory,
)


def test_short_term_memory_service_replaces_snapshot_and_can_clear() -> None:
    """管理端编辑应只保留当前 Markdown，并使用 Scheduler 缩放时间。"""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        agent = AgentConfig(
            name="观察者",
            username="observer",
            total_login_count=4,
            last_login_timestamp=480.0,
        )
        db.add(agent)
        db.add(
            SchedulerTimeState(
                scaled_timestamp=500.0,
                real_timestamp=100.0,
                scale=60.0,
                paused=True,
            )
        )
        db.commit()
        db.refresh(agent)
        assert agent.id is not None

        empty = get_short_term_memory(db, agent.id)
        first = update_short_term_memory(db, agent.id, "# 栏目\n\n下一篇追踪署名争论")
        cleared = update_short_term_memory(db, agent.id, "")

        assert empty is not None
        assert empty.content == ""
        assert empty.revision == 0
        assert first is not None
        assert first.content.startswith("# 栏目")
        assert first.revision == 1
        assert first.updated_at == 500.0
        assert first.updated_login_count == 4
        assert cleared is not None
        assert cleared.content == ""
        assert cleared.revision == 2

        assert delete_short_term_memory(db, agent.id) is True
        db.commit()
        assert db.get(ShortTermMemory, agent.id) is None
    engine.dispose()


def test_short_term_memory_service_rejects_missing_agent() -> None:
    """短期记忆始终从属于真实的内部角色配置。"""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        assert get_short_term_memory(db, 999) is None
        assert update_short_term_memory(db, 999, "unexpected") is None
    engine.dispose()
