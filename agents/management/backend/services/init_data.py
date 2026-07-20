"""
Management Backend - 数据库初始化服务
首次启动时填充默认数据
"""

import logging
import sys
from sqlmodel import Session

from agents.management.backend.core.config import get_config
from agents.management.backend.core.database import get_session_local
from agents.management.backend.services.auth_service import init_default_admin
from agents.management.backend.services.prompt_service import init_default_prompt_configs
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
            config = get_config()
            if config.admin_password_was_generated:
                # 敏感凭据绕过应用日志体系，避免写入终端缓冲和 JSONL。
                print(
                    f"角色管理器初始管理员 {config.admin_username} 的初始密码: "
                    f"{config.admin_password}",
                    file=sys.stderr,
                    flush=True,
                )
        else:
            logger.info("管理员账号已存在")

        config_count = init_default_configs(session)
        if config_count > 0:
            logger.info("已创建 %d 条默认系统配置", config_count)
        else:
            logger.info("系统配置已存在")

        prompt_config_count = init_default_prompt_configs(session)
        if prompt_config_count > 0:
            logger.info("已创建 %d 条默认提示词配置", prompt_config_count)
        else:
            logger.info("提示词配置已存在")

    finally:
        session.close()
