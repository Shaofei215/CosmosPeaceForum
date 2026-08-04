"""短期记忆 Scheduler 时间语义单测。"""

from agents.agents_scheduler.short_term_memory.clock import (
    describe_short_term_memory_age,
    project_scheduler_timestamp,
)


def test_project_scheduler_timestamp_respects_scale_and_pause() -> None:
    """管理端编辑时间应沿用持久化缩放锚点而非现实 Unix 时间。"""

    running = project_scheduler_timestamp(
        {
            "scaled_timestamp": 1000.0,
            "real_timestamp": 100.0,
            "scale": 10.0,
            "paused": False,
        },
        real_timestamp=112.0,
    )
    paused = project_scheduler_timestamp(
        {
            "scaled_timestamp": 1000.0,
            "real_timestamp": 100.0,
            "scale": 10.0,
            "paused": True,
        },
        real_timestamp=112.0,
    )

    assert running == 1120.0
    assert paused == 1000.0


def test_describe_short_term_memory_age_uses_semantic_ranges() -> None:
    """短期记忆相对时间覆盖分钟、天和月等常见跨度。"""

    assert describe_short_term_memory_age(995.0, current_timestamp=1000.0) == "刚刚"
    assert describe_short_term_memory_age(820.0, current_timestamp=1000.0) == "3分钟前"
    assert (
        describe_short_term_memory_age(1000.0, current_timestamp=1000.0 + 4 * 86400)
        == "4天前"
    )
    assert (
        describe_short_term_memory_age(1000.0, current_timestamp=1000.0 + 60 * 86400)
        == "2个月前"
    )
