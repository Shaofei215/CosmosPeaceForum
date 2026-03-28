# 头像上传工具模块
# 处理头像文件的上传、存储和访问
import os
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException
from typing import Optional

from app.core.config import get_settings
from app.core.paths import get_avatar_upload_dir


def get_avatar_upload_dir_path() -> str:
    """
    获取头像上传目录的绝对路径

    Returns:
        str: 头像上传目录的绝对路径
    """
    upload_dir = get_avatar_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def validate_avatar_file(file: UploadFile) -> None:
    """
    验证头像文件的类型和大小

    Args:
        file: 上传的文件对象

    Raises:
        HTTPException: 文件类型或大小不合法时抛出
    """
    settings = get_settings()

    if file.content_type not in settings.ALLOWED_AVATAR_TYPES:
        allowed_types_str = ', '.join(settings.ALLOWED_AVATAR_TYPES)
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式，请上传以下格式之一：{allowed_types_str}"
        )

    return None


async def save_avatar_file(file: UploadFile, user_id: int) -> str:
    """
    保存头像文件到服务器

    Args:
        file: 上传的文件对象
        user_id: 用户ID，用于生成文件名

    Returns:
        str: 保存后的文件访问路径（相对路径）

    Raises:
        HTTPException: 文件保存失败时抛出
    """
    settings = get_settings()
    upload_dir = get_avatar_upload_dir_path()

    mime_to_ext = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/webp': 'webp',
    }
    file_ext = mime_to_ext.get(file.content_type, 'jpg')

    unique_filename = f"avatar_{user_id}_{uuid.uuid4().hex[:8]}.{file_ext}"
    file_path = os.path.join(upload_dir, unique_filename)

    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            if len(content) > settings.MAX_AVATAR_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"图片大小不能超过 {settings.MAX_AVATAR_SIZE // (1024 * 1024)}MB"
                )
            await out_file.write(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"文件保存失败：{str(e)}"
        )

    # 返回相对路径，用于存储在数据库中
    # 格式：uploads/avatars/avatar_1_xxx.jpg
    relative_path = f"uploads/avatars/{unique_filename}"
    return relative_path


async def delete_avatar_file(avatar_url: Optional[str]) -> None:
    """
    删除旧的头像文件

    Args:
        avatar_url: 头像文件的相对路径
    """
    if not avatar_url:
        return

    upload_dir = get_avatar_upload_dir()
    file_path = os.path.join(upload_dir, os.path.basename(avatar_url))

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass


def get_avatar_url(file_path: str) -> str:
    """
    获取头像的完整访问URL

    Args:
        file_path: 头像文件的相对路径

    Returns:
        str: 头像的完整访问URL
    """
    settings = get_settings()
    return f"http://{settings.SERVER_HOST}:{settings.SERVER_PORT}{file_path}"
