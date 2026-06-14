"""用户领域头像应用服务测试。

该模块验证头像文件校验、存储、副作用清理与用户资料事件在 user 领域中的聚合行为。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from social_platform.app.admin.models import admin_user  # noqa: F401
from social_platform.app.db.session import Base
from social_platform.app.domains import registry as domain_models  # noqa: F401
from social_platform.app.domains.user import application as user_application
from social_platform.app.domains.user.events import UserUpdated
from social_platform.app.domains.user.models import User
from social_platform.app.shared.events import domain_event_bus


@dataclass
class FakeAvatarUploadFile:
    """测试用头像上传文件，模拟 FastAPI UploadFile 的最小协议。"""

    content_type: str | None
    content: bytes

    async def read(self) -> bytes:
        """读取测试上传文件内容。

        Returns:
            bytes: 预设的文件内容。
        """

        return self.content


@pytest.fixture()
def db_session():
    """创建内存数据库会话，供用户头像领域测试使用。"""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def avatar_settings():
    """构造头像测试所需的最小配置对象。"""

    return SimpleNamespace(
        ALLOWED_AVATAR_TYPES=["image/jpeg", "image/png", "image/gif", "image/webp"],
        MAX_AVATAR_SIZE=5 * 1024 * 1024,
        AVATAR_STORAGE_STRATEGY="local",
        OBJECT_STORAGE_ENDPOINT_URL=None,
        OBJECT_STORAGE_ACCESS_KEY_ID=None,
        OBJECT_STORAGE_SECRET_ACCESS_KEY=None,
        OBJECT_STORAGE_BUCKET=None,
        OBJECT_STORAGE_REGION="us-east-1",
        OBJECT_STORAGE_PUBLIC_BASE_URL=None,
        OBJECT_STORAGE_AVATAR_PREFIX="avatars",
        OBJECT_STORAGE_FORCE_PATH_STYLE=True,
        OBJECT_STORAGE_PUBLIC_READ=False,
        SERVER_HOST="0.0.0.0",
        SERVER_PORT=8000,
    )


@pytest.fixture()
def avatar_environment(monkeypatch, tmp_path, avatar_settings):
    """将头像领域服务隔离到临时上传目录和测试配置。"""

    upload_dir = tmp_path / "uploads" / "avatars"
    monkeypatch.setattr(user_application, "get_settings", lambda: avatar_settings)
    monkeypatch.setattr(user_application, "get_avatar_upload_dir", lambda: str(upload_dir))
    return upload_dir


def _create_user(db_session, username: str = "avatar_user") -> User:
    """创建并提交测试用户。

    Args:
        db_session: 当前测试数据库会话。
        username: 测试用户名。

    Returns:
        User: 已提交的测试用户。
    """

    user = User(username=username)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_upload_user_avatar_rejects_unsupported_mime_type(
    db_session,
    avatar_environment,
) -> None:
    """不支持的头像 MIME 类型会被领域校验拒绝，且不修改用户头像。"""

    user = _create_user(db_session)
    file = FakeAvatarUploadFile(content_type="text/plain", content=b"not-image")

    with pytest.raises(user_application.AvatarValidationError) as exc_info:
        asyncio.run(user_application.upload_user_avatar(db_session, user, file))

    assert "不支持的图片格式" in str(exc_info.value)
    assert avatar_environment.exists() is False
    assert db_session.query(User).filter(User.id == user.id).one().avatar_url is None


def test_upload_user_avatar_rejects_oversized_file(
    db_session,
    avatar_environment,
    avatar_settings,
) -> None:
    """超过配置大小限制的头像文件会被拒绝，且不会写入本地文件。"""

    avatar_settings.MAX_AVATAR_SIZE = 1024 * 1024
    user = _create_user(db_session)
    file = FakeAvatarUploadFile(content_type="image/png", content=b"x" * (1024 * 1024 + 1))

    with pytest.raises(user_application.AvatarValidationError) as exc_info:
        asyncio.run(user_application.upload_user_avatar(db_session, user, file))

    assert str(exc_info.value) == "图片大小不能超过 1MB"
    assert avatar_environment.exists() is False
    assert db_session.query(User).filter(User.id == user.id).one().avatar_url is None


def test_upload_user_avatar_writes_file_updates_user_and_publishes_event(
    db_session,
    avatar_environment,
) -> None:
    """本地头像上传会写入文件、更新用户头像 URL 并发布用户更新事件。"""

    captured: list[UserUpdated] = []
    domain_event_bus.subscribe(UserUpdated, lambda _, event: captured.append(event))
    user = _create_user(db_session)
    file = FakeAvatarUploadFile(content_type="image/png", content=b"avatar-bytes")

    updated_user = asyncio.run(user_application.upload_user_avatar(db_session, user, file))

    assert updated_user.avatar_url is not None
    assert updated_user.avatar_url.startswith(f"uploads/avatars/avatar_{user.id}_")
    assert updated_user.avatar_url.endswith(".png")
    saved_file = avatar_environment / updated_user.avatar_url.rsplit("/", 1)[-1]
    assert saved_file.read_bytes() == b"avatar-bytes"
    saved_avatar_url = db_session.query(User).filter(User.id == user.id).one().avatar_url
    assert saved_avatar_url == updated_user.avatar_url
    assert captured[-1].user_id == user.id


def test_delete_user_avatar_clears_user_and_removes_local_file(
    db_session,
    avatar_environment,
) -> None:
    """删除头像会清空用户头像 URL，并尽力删除旧的本地头像文件。"""

    captured: list[UserUpdated] = []
    domain_event_bus.subscribe(UserUpdated, lambda _, event: captured.append(event))
    avatar_environment.mkdir(parents=True)
    old_file = avatar_environment / "old-avatar.jpg"
    old_file.write_bytes(b"old-avatar")
    user = _create_user(db_session, username="avatar_delete_user")
    user.avatar_url = "uploads/avatars/old-avatar.jpg"
    db_session.commit()

    updated_user = asyncio.run(user_application.delete_user_avatar(db_session, user))

    assert updated_user.avatar_url is None
    assert db_session.query(User).filter(User.id == user.id).one().avatar_url is None
    assert old_file.exists() is False
    assert captured[-1].user_id == user.id
