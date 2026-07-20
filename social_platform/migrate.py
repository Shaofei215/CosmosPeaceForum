"""在统一日志环境中执行公开平台数据库迁移。"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from social_platform.app.core.config import get_settings
from social_platform.app.core.logging import configure_logging


logger = logging.getLogger(__name__)


def main() -> None:
    """配置日志并将公开平台数据库升级到最新版本。"""

    settings = get_settings()
    configure_logging(
        level=settings.LOG_LEVEL,
        log_dir=settings.LOG_DIR,
        retention_days=settings.LOG_RETENTION_DAYS,
        segment_max_mb=settings.LOG_SEGMENT_MAX_MB,
        max_total_mb=settings.LOG_MAX_TOTAL_MB,
    )
    config = Config(str(Path(__file__).resolve().parent / "alembic.ini"))
    config.attributes["configure_logger"] = False
    logger.info("公开平台数据库迁移开始", extra={"event": "migration.start", "component": "migration"})
    try:
        command.upgrade(config, "head")
    except Exception:
        logger.exception(
            "公开平台数据库迁移失败",
            extra={"event": "migration.error", "component": "migration"},
        )
        raise
    logger.info("公开平台数据库迁移完成", extra={"event": "migration.complete", "component": "migration"})


if __name__ == "__main__":
    main()
