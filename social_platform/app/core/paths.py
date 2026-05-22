# 路径配置模块
# 集中管理应用中的路径配置
import os

def get_app_dir() -> str:
    """
    获取 social_platform 目录的绝对路径

    Returns:
        str: social_platform 目录的绝对路径
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_platform_dir() -> str:
    """
    获取 social_platform 目录的绝对路径。

    Returns:
        str: social_platform 目录的绝对路径
    """
    return os.path.dirname(get_app_dir())


def get_upload_dir() -> str:
    """
    获取 uploads 目录的绝对路径（相对于 social_platform/app）

    Returns:
        str: uploads 目录的绝对路径
    """
    return os.path.join(get_app_dir(), "uploads")


def get_avatar_upload_dir() -> str:
    """
    获取头像上传目录的绝对路径

    Returns:
        str: uploads/avatars 目录的绝对路径
    """
    return os.path.join(get_upload_dir(), "avatars")


def get_search_index_dir() -> str:
    """
    获取平台搜索索引目录。

    Returns:
        str: social_platform/app/data/search 目录的绝对路径
    """
    return os.path.join(get_app_dir(), "data", "search")


def get_frontend_dist_dir() -> str:
    """
    获取公开平台前端生产构建目录。

    Returns:
        str: social_platform/frontend/dist 目录的绝对路径
    """
    return os.path.join(get_platform_dir(), "frontend", "dist")
