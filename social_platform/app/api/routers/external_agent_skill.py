"""提供按当前部署配置渲染的外部 Agent Skill 下载接口。

路由公开返回 zip，不要求登录，也不接收或持久化任何账号凭据。
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Response

from social_platform.app.core.config import get_settings
from social_platform.app.services.external_agent_skill import (
    SKILL_DOWNLOAD_PATH,
    SkillPackage,
    build_skill_package,
    create_skill_build_config,
)


router = APIRouter()


@lru_cache(maxsize=1)
def get_runtime_skill_package() -> SkillPackage:
    """根据进程启动时加载的部署配置构建并缓存公共 Skill 包。

    Returns:
        SkillPackage: 当前部署的 zip 和下载文件名。

    Raises:
        ValueError: 平台名称或公开 URL 配置无效。
        FileNotFoundError: Skill 模板缺失。
    """

    settings = get_settings()
    config = create_skill_build_config(
        platform_display_name=settings.PLATFORM_DISPLAY_NAME,
        platform_english_name=settings.PLATFORM_ENGLISH_NAME,
        public_frontend_url=settings.SOCIAL_PLATFORM_FRONTEND_URL,
        api_v1_prefix=settings.API_V1_PREFIX,
        external_agent_api_base_url=settings.EXTERNAL_AGENT_API_BASE_URL,
    )
    return build_skill_package(config)


def _zip_response(package: SkillPackage) -> Response:
    """把内存中的 Skill zip 转换为带安全下载文件名的 HTTP 响应。

    Args:
        package: 已渲染的公共 Skill 包。

    Returns:
        Response: ``application/zip`` 下载响应。
    """

    return Response(
        content=package.archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{package.download_filename}"',
        },
    )


@router.get(SKILL_DOWNLOAD_PATH, include_in_schema=False)
def download_skill() -> Response:
    """返回当前部署的公共 Skill zip。

    Returns:
        Response: 当前部署渲染后的 zip 下载响应。
    """

    return _zip_response(get_runtime_skill_package())
