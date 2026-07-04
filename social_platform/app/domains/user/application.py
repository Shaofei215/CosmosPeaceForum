"""用户领域应用服务。"""

from __future__ import annotations

import os
import re
import unicodedata
import uuid
from typing import Any, Protocol
from urllib.parse import unquote

import aiofiles
from sqlalchemy.orm import Session

from social_platform.app.core.config import get_settings
from social_platform.app.core.paths import get_avatar_upload_dir
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.events import UserDeleted, UserUpdated
from social_platform.app.domains.user.models import User
from social_platform.app.domains.user.schemas import CompleteProfileRequest, UserUpdate
from social_platform.app.shared.events import publish_domain_event
from social_platform.app.shared.unit_of_work import commit_session, rollback_session

# ZWNJ、ZWJ 用于正常文字塑形和组合 emoji，签名校验时予以保留。
_ALLOWED_BIO_FORMAT_CHARACTERS = frozenset({"\u200c", "\u200d"})


class AvatarUploadFile(Protocol):
    """头像上传文件协议，供 HTTP adapter 与领域用例之间传递文件内容。"""

    content_type: str | None

    async def read(self) -> bytes:
        """读取上传文件的完整二进制内容。

        Returns:
            bytes: 上传文件内容。
        """

        ...


class UserNotFoundError(Exception):
    """用户不存在异常。"""

    def __init__(self) -> None:
        """初始化用户领域应用服务中的异常或服务对象，保存后续处理需要的上下文。"""
        super().__init__("用户不存在")


class UserPermissionError(Exception):
    """用户权限异常。"""

    def __init__(self) -> None:
        """初始化用户领域应用服务中的异常或服务对象，保存后续处理需要的上下文。"""
        super().__init__("无权修改此用户")


class UsernameValidationError(Exception):
    """用户名校验异常。"""

    def __init__(self, message: str) -> None:
        """初始化用户领域应用服务中的异常或服务对象，保存后续处理需要的上下文。"""
        super().__init__(message)


class BioValidationError(Exception):
    """个人签名校验异常。"""

    def __init__(self, message: str) -> None:
        """初始化个人签名校验异常。

        Args:
            message: 对外展示的签名校验失败原因。
        """

        super().__init__(message)


class ProfileAlreadyCompletedError(Exception):
    """资料已经完善异常。"""

    def __init__(self) -> None:
        """初始化用户领域应用服务中的异常或服务对象，保存后续处理需要的上下文。"""
        super().__init__("用户名已设置，无法再次修改")


class AvatarValidationError(Exception):
    """头像文件校验异常。"""

    def __init__(self, message: str) -> None:
        """初始化头像校验异常。

        Args:
            message: 对外展示的校验失败原因。
        """

        super().__init__(message)


class AvatarStorageError(Exception):
    """头像文件存储异常。"""

    def __init__(self, message: str) -> None:
        """初始化头像存储异常。

        Args:
            message: 对外展示的存储失败原因。
        """

        super().__init__(message)


def _validate_username(username: str | None) -> str:
    """校验并规范化用户名。

    Args:
        username: 待校验用户名。

    Returns:
        str: 去除首尾空白后的用户名。

    Raises:
        UsernameValidationError: 当用户名为空或格式不合法时抛出。
    """

    if username is None:
        raise UsernameValidationError("用户名不能为空")

    normalized = username.strip()
    if not re.fullmatch(r"[a-zA-Z0-9_一-龥]+", normalized):
        raise UsernameValidationError("用户名只能包含字母、数字、下划线和中文")
    return normalized


def _validate_bio(bio: str | None) -> str | None:
    """校验并规范化个人签名。

    签名允许多语言、标点和 emoji。ZWNJ、ZWJ 可用于正常文字塑形和组合 emoji，
    其余控制字符与 Unicode 格式字符可能隐藏内容或改变显示顺序，因此拒绝。

    Args:
        bio: 待校验的可选个人签名。

    Returns:
        str | None: 去除首尾空白后的签名；未提供时返回 None。

    Raises:
        BioValidationError: 当签名仅含不可见内容或包含危险控制字符时抛出。
    """

    if bio is None:
        return None

    normalized = bio.strip()
    if not normalized:
        return ""

    has_visible_character = False
    for character in normalized:
        category = unicodedata.category(character)
        if category == "Cc" or (
            category == "Cf" and character not in _ALLOWED_BIO_FORMAT_CHARACTERS
        ):
            raise BioValidationError("个人签名不能包含控制字符或不可见字符")
        if not character.isspace() and category not in {"Cc", "Cf"}:
            has_visible_character = True

    if not has_visible_character:
        raise BioValidationError("个人签名不能只包含空白或不可见字符")
    return normalized


def _ensure_username_unique(db: Session, username: str, user_id: int) -> None:
    """确认用户名未被其他用户占用。

    Args:
        db: 当前数据库会话。
        username: 待检查用户名。
        user_id: 当前用户 ID。

    Raises:
        UsernameValidationError: 当用户名已存在时抛出。
    """

    existing_user = db.query(User).filter(User.username == username, User.id != user_id).first()
    if existing_user:
        raise UsernameValidationError("用户名已存在")


def _get_avatar_upload_dir_path() -> str:
    """获取头像上传目录并确保目录存在。

    Returns:
        str: 头像上传目录的绝对路径。
    """

    upload_dir = get_avatar_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _validate_avatar_file(file: AvatarUploadFile) -> str:
    """校验头像文件类型。

    Args:
        file: 上传的头像文件。

    Returns:
        str: 已校验的 MIME 类型。

    Raises:
        AvatarValidationError: 文件类型不在允许列表内时抛出。
    """

    settings = get_settings()
    allowed_types = set(settings.ALLOWED_AVATAR_TYPES)
    if file.content_type not in allowed_types:
        allowed_types_str = ", ".join(settings.ALLOWED_AVATAR_TYPES)
        raise AvatarValidationError(f"不支持的图片格式，请上传以下格式之一：{allowed_types_str}")
    return file.content_type


def _get_avatar_file_extension(content_type: str) -> str:
    """根据头像 MIME 类型返回文件扩展名。

    Args:
        content_type: 已校验的头像 MIME 类型。

    Returns:
        str: 文件扩展名，不包含点号。
    """

    mime_to_ext = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
    }
    return mime_to_ext[content_type]


def _get_unique_avatar_filename(user_id: int, content_type: str) -> str:
    """生成当前用户头像文件名。

    Args:
        user_id: 上传头像的用户 ID。
        content_type: 已校验的头像 MIME 类型。

    Returns:
        str: 带随机后缀的头像文件名。
    """

    file_ext = _get_avatar_file_extension(content_type)
    return f"avatar_{user_id}_{uuid.uuid4().hex[:8]}.{file_ext}"


async def _read_avatar_content(file: AvatarUploadFile) -> bytes:
    """读取并校验头像文件大小。

    Args:
        file: 上传的头像文件。

    Returns:
        bytes: 头像文件内容。

    Raises:
        AvatarValidationError: 文件大小超过配置限制时抛出。
    """

    settings = get_settings()
    content = await file.read()
    if len(content) > settings.MAX_AVATAR_SIZE:
        max_size_mb = settings.MAX_AVATAR_SIZE // (1024 * 1024)
        raise AvatarValidationError(f"图片大小不能超过 {max_size_mb}MB")
    return content


async def _save_local_avatar_file(content: bytes, filename: str) -> str:
    """保存头像文件到本地上传目录。

    Args:
        content: 头像文件内容。
        filename: 目标头像文件名。

    Returns:
        str: 头像文件的公开相对访问路径。

    Raises:
        AvatarStorageError: 本地文件写入失败时抛出。
    """

    upload_dir = _get_avatar_upload_dir_path()
    file_path = os.path.join(upload_dir, filename)

    try:
        async with aiofiles.open(file_path, "wb") as out_file:
            await out_file.write(content)
    except Exception as exc:
        raise AvatarStorageError(f"文件保存失败：{str(exc)}") from exc

    return f"uploads/avatars/{filename}"


def _get_object_storage_client() -> Any:
    """创建对象存储客户端。

    Returns:
        Any: boto3 S3 兼容客户端。

    Raises:
        AvatarStorageError: boto3 依赖缺失时抛出。
    """

    settings = get_settings()

    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise AvatarStorageError("对象存储需要安装 boto3 依赖") from exc

    addressing_style = "path" if settings.OBJECT_STORAGE_FORCE_PATH_STYLE else "auto"
    return boto3.client(
        "s3",
        endpoint_url=settings.OBJECT_STORAGE_ENDPOINT_URL,
        aws_access_key_id=settings.OBJECT_STORAGE_ACCESS_KEY_ID,
        aws_secret_access_key=settings.OBJECT_STORAGE_SECRET_ACCESS_KEY,
        region_name=settings.OBJECT_STORAGE_REGION,
        config=Config(s3={"addressing_style": addressing_style}),
    )


def _build_object_avatar_key(filename: str) -> str:
    """构造对象存储头像 key。

    Args:
        filename: 头像文件名。

    Returns:
        str: 对象存储中的头像 key。
    """

    settings = get_settings()
    prefix = settings.OBJECT_STORAGE_AVATAR_PREFIX
    return f"{prefix}/{filename}" if prefix else filename


def _build_object_avatar_url(object_key: str) -> str:
    """构造对象存储头像公开访问 URL。

    Args:
        object_key: 对象存储中的头像 key。

    Returns:
        str: 头像公开访问 URL。
    """

    settings = get_settings()
    if settings.OBJECT_STORAGE_PUBLIC_BASE_URL:
        return f"{settings.OBJECT_STORAGE_PUBLIC_BASE_URL}/{object_key}"

    return (
        f"{settings.OBJECT_STORAGE_ENDPOINT_URL}/"
        f"{settings.OBJECT_STORAGE_BUCKET}/{object_key}"
    )


async def _save_object_avatar_file(content: bytes, filename: str, content_type: str) -> str:
    """保存头像文件到对象存储。

    Args:
        content: 头像文件内容。
        filename: 目标头像文件名。
        content_type: 已校验的头像 MIME 类型。

    Returns:
        str: 对象存储头像公开访问 URL。

    Raises:
        AvatarStorageError: 对象存储上传失败时抛出。
    """

    settings = get_settings()
    object_key = _build_object_avatar_key(filename)
    put_kwargs: dict[str, object] = {
        "Bucket": settings.OBJECT_STORAGE_BUCKET,
        "Key": object_key,
        "Body": content,
        "ContentType": content_type,
    }
    if settings.OBJECT_STORAGE_PUBLIC_READ:
        put_kwargs["ACL"] = "public-read"

    try:
        _get_object_storage_client().put_object(**put_kwargs)
    except AvatarStorageError:
        raise
    except Exception as exc:
        raise AvatarStorageError(f"对象存储上传失败：{str(exc)}") from exc

    return _build_object_avatar_url(object_key)


def _is_local_avatar_url(avatar_url: str) -> bool:
    """判断头像 URL 是否指向本地上传目录。

    Args:
        avatar_url: 用户当前头像 URL。

    Returns:
        bool: 如果是本地头像路径则返回 True。
    """

    normalized_url = avatar_url.lstrip("/")
    return (
        not avatar_url.startswith(("http://", "https://"))
        and normalized_url.startswith("uploads/avatars/")
    )


def _get_object_key_from_avatar_url(avatar_url: str) -> str | None:
    """从头像 URL 中解析对象存储 key。

    Args:
        avatar_url: 用户当前头像 URL。

    Returns:
        str | None: 可解析时返回对象存储 key，否则返回 None。
    """

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


async def _save_avatar_file(file: AvatarUploadFile, user_id: int) -> str:
    """保存头像文件到当前配置的存储后端。

    Args:
        file: 上传的头像文件。
        user_id: 上传头像的用户 ID。

    Returns:
        str: 保存后的头像访问路径或 URL。

    Raises:
        AvatarValidationError: 文件类型或大小不合法时抛出。
        AvatarStorageError: 文件保存失败时抛出。
    """

    settings = get_settings()
    content_type = _validate_avatar_file(file)
    content = await _read_avatar_content(file)
    unique_filename = _get_unique_avatar_filename(user_id, content_type)

    if settings.AVATAR_STORAGE_STRATEGY == "object_storage":
        return await _save_object_avatar_file(content, unique_filename, content_type)

    return await _save_local_avatar_file(content, unique_filename)


async def _delete_avatar_file(avatar_url: str | None) -> None:
    """尽力删除头像文件。

    Args:
        avatar_url: 头像文件相对路径或对象存储 URL。
    """

    if not avatar_url:
        return

    if _is_local_avatar_url(avatar_url):
        upload_dir = get_avatar_upload_dir()
        file_path = os.path.join(upload_dir, os.path.basename(avatar_url))

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        return

    object_key = _get_object_key_from_avatar_url(avatar_url)
    if not object_key:
        return

    try:
        settings = get_settings()
        _get_object_storage_client().delete_object(
            Bucket=settings.OBJECT_STORAGE_BUCKET,
            Key=object_key,
        )
    except Exception:
        pass


def get_avatar_url(file_path: str) -> str:
    """获取头像完整访问 URL。

    Args:
        file_path: 头像文件相对路径。

    Returns:
        str: 头像完整访问 URL。
    """

    settings = get_settings()
    return f"http://{settings.SERVER_HOST}:{settings.SERVER_PORT}{file_path}"


def _get_user_for_avatar_update(db: Session, current_user: User) -> User:
    """读取当前用户的持久化对象，供头像更新用例使用。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。

    Returns:
        User: 数据库中的当前用户对象。

    Raises:
        UserNotFoundError: 当前用户在数据库中不存在时抛出。
    """

    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise UserNotFoundError()
    return user


async def upload_user_avatar(db: Session, current_user: User, file: AvatarUploadFile) -> User:
    """上传并更新当前用户头像。

    该用例先保存新头像文件，再提交用户头像 URL 变更；提交成功后尽力清理旧头像文件。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        file: 上传的头像文件。

    Returns:
        User: 更新头像后的用户对象。

    Raises:
        UserNotFoundError: 当前用户在数据库中不存在时抛出。
        AvatarValidationError: 文件类型或大小不合法时抛出。
        AvatarStorageError: 文件保存失败时抛出。
    """

    user = _get_user_for_avatar_update(db, current_user)
    old_avatar_url = user.avatar_url
    avatar_url = await _save_avatar_file(file, user.id)

    try:
        user.avatar_url = avatar_url
        publish_domain_event(db, UserUpdated(user_id=user.id))
        commit_session(db)
    except Exception:
        rollback_session(db)
        await _delete_avatar_file(avatar_url)
        raise

    db.refresh(user)
    await _delete_avatar_file(old_avatar_url)
    return user


async def delete_user_avatar(db: Session, current_user: User) -> User:
    """删除当前用户头像并恢复为空头像状态。

    该用例先提交数据库头像字段清空，再尽力删除旧头像文件，避免文件已删但数据库仍引用旧路径。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。

    Returns:
        User: 删除头像后的用户对象。

    Raises:
        UserNotFoundError: 当前用户在数据库中不存在时抛出。
    """

    user = _get_user_for_avatar_update(db, current_user)
    old_avatar_url = user.avatar_url

    try:
        user.avatar_url = None
        publish_domain_event(db, UserUpdated(user_id=user.id))
        commit_session(db)
    except Exception:
        rollback_session(db)
        raise

    db.refresh(user)
    await _delete_avatar_file(old_avatar_url)
    return user


def update_user(db: Session, current_user: User, user_id: int, user_update: UserUpdate) -> User:
    """更新用户资料并发布用户更新事件。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        user_id: 待更新用户 ID。
        user_update: 用户更新请求数据。

    Returns:
        User: 更新后的用户对象。
    """

    if current_user.id != user_id:
        raise UserPermissionError()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError()

    update_data = user_update.model_dump(exclude_unset=True)
    if "username" in update_data:
        username = _validate_username(update_data["username"])
        _ensure_username_unique(db, username, user_id)
        update_data["username"] = username
    if "bio" in update_data:
        update_data["bio"] = _validate_bio(update_data["bio"])

    for field, value in update_data.items():
        setattr(user, field, value)

    publish_domain_event(db, UserUpdated(user_id=user.id))
    commit_session(db)
    db.refresh(user)
    return user


def complete_profile(
    db: Session,
    current_user: User,
    user_id: int,
    profile_data: CompleteProfileRequest,
) -> User:
    """完善注册后的用户资料。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        user_id: 待完善资料的用户 ID。
        profile_data: 完善资料请求数据。

    Returns:
        User: 更新后的用户对象。
    """

    if current_user.id != user_id:
        raise UserPermissionError()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError()

    if user.username and not user.username.startswith("用户_"):
        raise ProfileAlreadyCompletedError()

    username = _validate_username(profile_data.username)
    _ensure_username_unique(db, username, user_id)
    user.username = username
    if profile_data.bio is not None:
        user.bio = _validate_bio(profile_data.bio)
    if profile_data.avatar_url is not None:
        user.avatar_url = profile_data.avatar_url

    publish_domain_event(db, UserUpdated(user_id=user.id))
    commit_session(db)
    db.refresh(user)
    return user


def delete_user(db: Session, current_user: User, user_id: int) -> None:
    """删除用户并发布用户删除事件。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        user_id: 待删除用户 ID。
    """

    if current_user.id != user_id:
        raise UserPermissionError()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError()

    post_ids = tuple(row[0] for row in db.query(Post.id).filter(Post.author_id == user_id).all())
    db.delete(user)
    publish_domain_event(db, UserDeleted(user_id=user_id, post_ids=post_ids))
    commit_session(db)
