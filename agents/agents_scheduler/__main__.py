"""
Agent Scheduler 主入口

启动流程：
1. 初始化内部 HTTP 服务器（供 management 调用）
2. 从管理数据库加载启用的 Agent 配置
3. 构建角色关系映射（从数据库）
4. 为每个 Agent 创建独立调度线程
5. 启动所有调度线程
"""

import sys
import logging
import signal

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
    )


def main():
    """
    Scheduler 主函数

    从管理数据库加载配置并启动调度器。
    """
    setup_logging()

    print("\n" + "=" * 60)
    print("AI Agent Scheduler 启动中...")
    print("=" * 60)

    config = get_scheduler_config()
    print(f"[配置] API 地址: {config.api_base_url}")
    print(f"[配置] 日志级别: {config.log_level}")

    setup_logging(config.log_level)

    time_system = get_time_system()
    print(f"[时间] 当前时间: {time_system.get_scaled_time().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[时间] 时间流速: {time_system.get_scale()}x")

    from agents.agents_scheduler.scheduler.internal_server import SchedulerInternalServer
    from agents.management.backend.db_client import get_db_client

    scheduler_manager = AgentSchedulerManager()

    internal_port = 8002
    internal_server = SchedulerInternalServer(port=internal_port, scheduler_manager=scheduler_manager)
    internal_server.start()

    print(f"\n[内部接口] 服务器启动在 http://127.0.0.1:{internal_port}")

    print("\n[角色关系] 从数据库构建关系映射...")
    relation_map = build_relation_maps_from_db()
    print(f"[角色关系] 加载完成: {relation_map}")

    print("\n[调度器] 正在启动...")
    scheduler_manager.start(relation_map)

    print(f"\n{'=' * 60}")
    print("AI Agent Scheduler 启动完成!")
    print(f"{'=' * 60}\n")

    def signal_handler(sig, frame):
        print("\n\n收到退出信号，正在关闭...")
        scheduler_manager.stop()
        internal_server.stop()
        print("Scheduler 已关闭")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("按 Ctrl+C 停止调度器")

    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
