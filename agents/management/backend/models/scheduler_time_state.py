"""Scheduler 缩放时间持久化锚点模型。

该表保存缩放时间与真实时间的对应关系，使 Scheduler 在进程重启后能够继续沿用
单调的虚拟时间轴。它属于运行期内部状态，不通过系统配置页面暴露。
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from agents.management.backend.core.timezone import local_now


class SchedulerTimeState(SQLModel, table=True):
    """保存全局 Scheduler 时间轴的唯一持久化锚点。"""

    __tablename__ = "scheduler_time_state"

    id: int = Field(default=1, primary_key=True)
    scaled_timestamp: float
    real_timestamp: float
    scale: float
    offset_seconds: int = 0
    paused: bool = False
    updated_at: datetime = Field(default_factory=local_now)
