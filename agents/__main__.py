"""
Agents 主入口

启动流程：
1. 启动 Management Backend (FastAPI, 端口 8001)
2. 启动 Agent Scheduler（调用 agents_scheduler.__main__.main）
"""

import sys
import logging
import signal
import threading
import time as time_module

import uvicorn

from agents.agents_scheduler.__main__ import main as scheduler_main

logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO"):
    """配置日志"""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    from agents.management.backend.services.terminal_log_service import terminal_log_capture
    terminal_log_capture.start()


def start_management_backend():
    """在独立线程中启动 Management Backend"""
    logger.info("=" * 60)
    logger.info("Management Backend 启动中...")
    logger.info("=" * 60)
    uvicorn.run(
        "agents.management.backend.main:app",
        host="0.0.0.0",
        port=8001,
        log_level="warning",
        access_log=False,
    )


def main():
    """
    Agents 主函数

    先启动 Management Backend，再启动 Agent Scheduler。
    """
    setup_logging()

    logger.info("=" * 60)
    logger.info(" Agents 启动中...")
    logger.info("=" * 60)

    mgmt_thread = threading.Thread(target=start_management_backend, daemon=True)
    mgmt_thread.start()

    time_module.sleep(2)

    scheduler_main()
    


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
