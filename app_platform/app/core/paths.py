# 路径配置模块
# 集中管理应用中的路径配置
import os

def get_app_dir() -> str:
    """
    获取 app_platform 目录的绝对路径

    Returns:
        str: app_platform 目录的绝对路径
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_upload_dir() -> str:
    """
    获取 uploads 目录的绝对路径（相对于 app_platform）

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
