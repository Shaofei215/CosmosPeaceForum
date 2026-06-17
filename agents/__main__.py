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
from agents.management.backend.core.config import get_config

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


def start_management_backend():
    """在独立线程中启动 Management Backend"""
    config = get_config()
    logger.info("=" * 60)
    logger.info("Management Backend 启动中...")
    logger.info("=" * 60)
    uvicorn.run(
        "agents.management.backend.main:app",
        host=config.server_host,
        port=config.server_port,
        log_level="warning",
        access_log=False,
    )


def main():
    """
    Agents 主函数

    先启动 Management Backend，再启动 Agent Scheduler。
    """
    config = get_config()
    setup_logging(config.log_level)

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
