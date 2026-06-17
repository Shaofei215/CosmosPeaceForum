"""
Agent Scheduler 主入口

启动流程：
1. 初始化内部 HTTP 服务器（供 management 调用）
2. 从 agents/.env 和管理数据库加载配置
3. 构建角色关系映射（从数据库）
4. 为每个 Agent 创建独立调度线程
5. 启动所有调度线程
"""

import sys
import logging
import signal
import threading

from agents.agents_scheduler.scheduler.config import get_scheduler_config
from agents.agents_scheduler.scheduler.relation_map import build_relation_maps_from_db
from agents.agents_scheduler.scheduler.scheduler import AgentSchedulerManager
from agents.agents_scheduler.scheduler.time_system import get_time_system

logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO"):
    """配置日志"""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        force=True,
    )
    logging.getLogger().setLevel(numeric_level)

    from agents.management.backend.services.terminal_log_service import (
        restore_agents_loggers,
        terminal_log_capture,
    )
    restore_agents_loggers()
    terminal_log_capture.start()


def main():
    """
    Scheduler 主函数

    从 agents/.env 和管理数据库加载配置并启动调度器。
    """
    setup_logging()

    logger.info("=" * 60)
    logger.info("Agents Scheduler 启动中...")
    logger.info("=" * 60)

    config = get_scheduler_config()
    logger.info("API 地址: %s", config.api_base_url)
    logger.info("日志级别: %s", config.log_level)

    setup_logging(config.log_level)

    time_system = get_time_system()
    logger.info("当前时间: %s", time_system.get_scaled_time().strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("时间流速: %dx", time_system.get_scale())

    from agents.agents_scheduler.scheduler.internal_server import SchedulerInternalServer
    from agents.management.backend.db_client import get_db_client

    scheduler_manager = AgentSchedulerManager()

    internal_server = SchedulerInternalServer(
        host=config.internal_host,
        port=config.internal_port,
        scheduler_manager=scheduler_manager,
    )
    internal_server.start()

    logger.info("内部接口服务器启动在 %s", config.internal_base_url)

    logger.info("从数据库构建关系映射...")
    relation_map = build_relation_maps_from_db()
    logger.info("关系映射加载完成: %s", relation_map)

    logger.info("调度器正在启动...")
    scheduler_manager.start(relation_map)

    logger.info("=" * 60)
    logger.info("Agents Scheduler 启动完成!")
    logger.info("=" * 60)

    shutdown_started = threading.Event()

    def signal_handler(sig, frame):
        if shutdown_started.is_set():
            logger.warning("再次收到停止信号，立即退出")
            raise SystemExit(0)

        shutdown_started.set()
        logger.info("正在关闭...")
        scheduler_manager.stop(wait=False)
        internal_server.stop(wait=False)
        logger.info("Scheduler 已关闭")
        raise SystemExit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("按 Ctrl+C 停止调度器")

    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
