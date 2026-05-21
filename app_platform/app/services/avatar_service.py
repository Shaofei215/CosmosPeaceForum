# 头像上传业务逻辑层
# 处理头像文件的上传、存储和访问
import os
import uuid
from typing import Optional
from urllib.parse import unquote

import aiofiles
from fastapi import HTTPException, UploadFile

from app_platform.app.core.config import get_settings
from app_platform.app.core.paths import get_avatar_upload_dir


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


def get_avatar_file_extension(content_type: str) -> str:
    mime_to_ext = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/webp': 'webp',
    }
    return mime_to_ext[content_type]


def get_unique_avatar_filename(user_id: int, content_type: str) -> str:
    file_ext = get_avatar_file_extension(content_type)
    return f"avatar_{user_id}_{uuid.uuid4().hex[:8]}.{file_ext}"


async def read_avatar_content(file: UploadFile) -> bytes:
    settings = get_settings()
    content = await file.read()
    if len(content) > settings.MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"图片大小不能超过 {settings.MAX_AVATAR_SIZE // (1024 * 1024)}MB"
        )
    return content


async def save_local_avatar_file(content: bytes, filename: str) -> str:
    upload_dir = get_avatar_upload_dir_path()
    file_path = os.path.join(upload_dir, filename)

    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            await out_file.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"文件保存失败：{str(e)}"
        )

    return f"uploads/avatars/{filename}"


def get_object_storage_client():
    settings = get_settings()

    try:
        import boto3
        from botocore.config import Config
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="对象存储需要安装 boto3 依赖"
        ) from e

    addressing_style = "path" if settings.OBJECT_STORAGE_FORCE_PATH_STYLE else "auto"
    return boto3.client(
        "s3",
        endpoint_url=settings.OBJECT_STORAGE_ENDPOINT_URL,
        aws_access_key_id=settings.OBJECT_STORAGE_ACCESS_KEY_ID,
        aws_secret_access_key=settings.OBJECT_STORAGE_SECRET_ACCESS_KEY,
        region_name=settings.OBJECT_STORAGE_REGION,
        config=Config(s3={"addressing_style": addressing_style}),
    )


def build_object_avatar_key(filename: str) -> str:
    settings = get_settings()
    prefix = settings.OBJECT_STORAGE_AVATAR_PREFIX
    return f"{prefix}/{filename}" if prefix else filename


def build_object_avatar_url(object_key: str) -> str:
    settings = get_settings()
    if settings.OBJECT_STORAGE_PUBLIC_BASE_URL:
        return f"{settings.OBJECT_STORAGE_PUBLIC_BASE_URL}/{object_key}"

    return (
        f"{settings.OBJECT_STORAGE_ENDPOINT_URL}/"
        f"{settings.OBJECT_STORAGE_BUCKET}/{object_key}"
    )


async def save_object_avatar_file(content: bytes, filename: str, content_type: str) -> str:
    settings = get_settings()
    object_key = build_object_avatar_key(filename)
    put_kwargs = {
        "Bucket": settings.OBJECT_STORAGE_BUCKET,
        "Key": object_key,
        "Body": content,
        "ContentType": content_type,
    }
    if settings.OBJECT_STORAGE_PUBLIC_READ:
        put_kwargs["ACL"] = "public-read"

    try:
        get_object_storage_client().put_object(**put_kwargs)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"对象存储上传失败：{str(e)}"
        )

    return build_object_avatar_url(object_key)


def is_local_avatar_url(avatar_url: str) -> bool:
    normalized_url = avatar_url.lstrip("/")
    return (
        not avatar_url.startswith(("http://", "https://"))
        and normalized_url.startswith("uploads/avatars/")
    )


def get_object_key_from_avatar_url(avatar_url: str) -> Optional[str]:
    settings = get_settings()
    bucket = settings.OBJECT_STORAGE_BUCKET
    if not bucket:
        return None

    bases = []
    if settings.OBJECT_STORAGE_PUBLIC_BASE_URL:
        bases.append(settings.OBJECT_STORAGE_PUBLIC_BASE_URL.rstrip("/"))
    if settings.OBJECT_STORAGE_ENDPOINT_URL:
        bases.append(f"{settings.OBJECT_STORAGE_ENDPOINT_URL.rstrip('/')}/{bucket}")

    for base in bases:
        prefix = f"{base}/"
        if avatar_url.startswith(prefix):
            return unquote(avatar_url[len(prefix):])

    object_prefix = settings.OBJECT_STORAGE_AVATAR_PREFIX.strip("/")
    if object_prefix and avatar_url.startswith(f"{object_prefix}/"):
        return avatar_url

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
    allowed_mime_types = set(settings.ALLOWED_AVATAR_TYPES)
    if file.content_type not in allowed_mime_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式：{file.content_type}"
        )

    content = await read_avatar_content(file)
    unique_filename = get_unique_avatar_filename(user_id, file.content_type)

    if settings.AVATAR_STORAGE_STRATEGY == "object_storage":
        return await save_object_avatar_file(content, unique_filename, file.content_type)

    return await save_local_avatar_file(content, unique_filename)


async def delete_avatar_file(avatar_url: Optional[str]) -> None:
    """
    删除旧的头像文件

    Args:
        avatar_url: 头像文件的相对路径
    """
    if not avatar_url:
        return

    if is_local_avatar_url(avatar_url):
        upload_dir = get_avatar_upload_dir()
        file_path = os.path.join(upload_dir, os.path.basename(avatar_url))

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        return

    object_key = get_object_key_from_avatar_url(avatar_url)
    if not object_key:
        return

    try:
        settings = get_settings()
        get_object_storage_client().delete_object(
            Bucket=settings.OBJECT_STORAGE_BUCKET,
            Key=object_key,
        )
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
