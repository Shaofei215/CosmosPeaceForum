"""
记忆衰减后台调度器。

该线程由 AgentSchedulerManager 统一管理，定期调用 MemoryService
的增量衰减逻辑。执行间隔使用现实秒，衰减量使用缩放时间差。
"""

import asyncio
import logging
import threading

from agents.agents_scheduler.memory.config import get_memory_config
from agents.agents_scheduler.memory.service import get_memory_service

logger = logging.getLogger(__name__)


class MemoryDecayScheduler(threading.Thread):
    """
    按固定现实时间间隔执行记忆衰减的 daemon 线程。

    配置每轮动态读取，因此系统配置热更新后不需要重启该线程。
    """

    def __init__(self) -> None:
        """
        初始化衰减线程和停止事件。

        Returns:
            None: 初始化完成后直接返回。
        """
        super().__init__(daemon=True, name="memory-decay")
        self._stop_event = threading.Event()

    def stop(self, wait: bool = True, timeout: float = 5.0) -> None:
        """
        请求停止衰减线程。

        Args:
            wait: 是否等待线程退出。
            timeout: 最长等待秒数。

        Returns:
            None: 停止请求发出后直接返回。
        """
        self._stop_event.set()
        if wait and self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=timeout)

    def run(self) -> None:
        """
        运行衰减循环，每轮等待当前配置的现实秒数。

        Returns:
            None: 收到停止事件后退出。
        """
        logger.info("记忆衰减调度线程已启动")
        while not self._stop_event.is_set():
            interval = get_memory_config().decay_interval_seconds
            if self._stop_event.wait(interval):
                break
            self._run_decay_once()
        logger.info("记忆衰减调度线程已停止")

    def _run_decay_once(self) -> None:
        """
        执行一次全局记忆增量衰减。

        Returns:
            None: 衰减完成或异常已记录时直接返回。
        """
        try:
            deleted_ids = asyncio.run(get_memory_service().decay_memories())
            logger.info("记忆衰减任务完成: 删除%d条", len(deleted_ids))
        except Exception as exc:
            logger.exception("记忆衰减任务失败: %s", exc)
