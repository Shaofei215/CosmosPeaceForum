"""
Management Backend - 数据库初始化服务
首次启动时填充默认数据
"""

import logging
from sqlmodel import Session

from agents.management.backend.core.database import get_session_local
from agents.management.backend.services.auth_service import init_default_admin
from agents.management.backend.services.system_service import init_default_configs

logger = logging.getLogger(__name__)


def initialize_database():
    """
    初始化数据库数据
    - 创建默认管理员账号
    - 创建默认系统配置
    """
    session = get_session_local()()
    try:
        admin_created = init_default_admin(session)
        if admin_created:
            logger.info("默认管理员账号已创建")
        else:
            logger.info("管理员账号已存在")

        config_count = init_default_configs(session)
        if config_count > 0:
            logger.info("已创建 %d 条默认系统配置", config_count)
        else:
            logger.info("系统配置已存在")

    finally:
        session.close()
