import sys
import logging
import threading
import time as time_module
from io import TextIOWrapper

import uvicorn

from agents.agents_scheduler.__main__ import main as scheduler_main
from agents.logging_config import configure_logging
from agents.management.backend.core.config import get_config

logger = logging.getLogger(__name__)

BANNER: str = r"""
 ██████╗██████╗ ███████╗ ██████╗ ██████╗ ██╗   ██╗███╗   ███╗
██╔════╝██╔══██╗██╔════╝██╔═══██╗██╔══██╗██║   ██║████╗ ████║
██║     ██████╔╝█████╗  ██║   ██║██████╔╝██║   ██║██╔████╔██║
██║     ██╔═══╝ ██╔══╝  ██║   ██║██╔══██╗██║   ██║██║╚██╔╝██║
╚██████╗██║     ██║     ╚██████╔╝██║  ██║╚██████╔╝██║ ╚═╝ ██║
 ╚═════╝╚═╝     ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝

                      CosmosPeaceForum
                      愿全宇宙 和平交流
""".strip("\n")


def setup_logging(log_level: str = "INFO"):
    """使用 Management 与 Scheduler 共享配置初始化日志。"""
    config = get_config()
    configure_logging(
        level=log_level,
        log_dir=config.log_dir,
        retention_days=config.log_retention_days,
        segment_max_mb=config.log_segment_max_mb,
        max_total_mb=config.log_max_total_mb,
    )

    from agents.management.backend.services.terminal_log_service import terminal_log_capture

    terminal_log_capture.start()


def start_management_backend():
    """在独立线程中启动管理器"""
    config = get_config()
    logger.info("管理器正在启动...")
    uvicorn.run(
        "agents.management.backend.main:app",
        host=config.server_host,
        port=config.server_port,
        log_level=config.log_level.lower(),
        log_config=None,
        access_log=False,
    )


def main():
    """
    Agents 主函数

    先启动 Management Backend，再启动 Agent Scheduler。
    """
    config = get_config()
    setup_logging(config.log_level)

    logger.info("\n%s", BANNER)
    logger.info("正在启动 Agents ...")

    mgmt_thread = threading.Thread(target=start_management_backend, daemon=True)
    mgmt_thread.start()

    time_module.sleep(2)

    scheduler_main()
    


if __name__ == "__main__":
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)
    main()
