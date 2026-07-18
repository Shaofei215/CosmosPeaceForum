"""验证 Management 管理员中文用户名与永久移除行为。"""

from datetime import timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from agents.management.backend.api.admins import delete_admin
from agents.management.backend.core.timezone import local_now
from agents.management.backend.models.admin_session import AdminSession
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.models.operation_log import OperationLog
from agents.management.backend.schemas import AdminCreateRequest, AdminProfileUpdateRequest


def _admin(username: str, *, is_super_admin: bool = False) -> AdminUser:
    """构造无需真实密码校验的管理员测试实体。

    Args:
        username: 管理员用户名。
        is_super_admin: 是否赋予超级管理员身份。

    Returns:
        AdminUser: 尚未写入数据库的管理员实体。
    """

    return AdminUser(
        username=username,
        password_hash="unused-test-hash",
        permissions='["manage_admins"]',
        is_super_admin=is_super_admin,
    )


@pytest.fixture
def admin_db() -> Session:
    """创建隔离的内存数据库会话，并在用例结束后释放连接。

    Yields:
        Session: 已创建管理员、会话和日志表的 SQLModel 会话。
    """

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_admin_requests_accept_short_chinese_username() -> None:
    """创建与首次设置契约均应接受少于三个字符的中文用户名。"""

    create_request = AdminCreateRequest(username="张三", password="password")
    profile_request = AdminProfileUpdateRequest(current_password="old", username="李四")

    assert create_request.username == "张三"
    assert profile_request.username == "李四"


def test_admin_username_is_trimmed() -> None:
    """管理员用户名应在唯一性检查和保存前移除首尾空白。"""

    request = AdminCreateRequest(username="  中文管理员  ", password="password")

    assert request.username == "中文管理员"


def test_admin_username_stops_at_thirty_character_contract() -> None:
    """后端应接受 30 个字符，并拒绝绕过前端提交的第 31 个字符。"""

    accepted = AdminCreateRequest(username="管" * 30, password="password")

    assert len(accepted.username) == 30
    with pytest.raises(ValidationError):
        AdminCreateRequest(username="管" * 31, password="password")


def test_delete_admin_removes_sessions_and_keeps_audit_log(admin_db: Session) -> None:
    """永久移除管理员时应同步移除其会话，并保留操作者审计日志。"""

    current_admin = _admin("当前管理员", is_super_admin=True)
    target_admin = _admin("待移除管理员")
    admin_db.add(current_admin)
    admin_db.add(target_admin)
    admin_db.commit()
    admin_db.refresh(current_admin)
    admin_db.refresh(target_admin)
    assert current_admin.id is not None
    assert target_admin.id is not None

    admin_db.add(
        AdminSession(
            session_id="target-session",
            admin_id=target_admin.id,
            refresh_token_hash="a" * 64,
            expires_at=local_now() + timedelta(hours=1),
        )
    )
    admin_db.commit()

    response = delete_admin(target_admin.id, admin_db, current_admin)

    assert response == {"message": "管理员已删除"}
    assert admin_db.get(AdminUser, target_admin.id) is None
    assert admin_db.exec(
        select(AdminSession).where(AdminSession.admin_id == target_admin.id)
    ).first() is None
    log = admin_db.exec(select(OperationLog).where(OperationLog.action == "delete_admin")).one()
    assert log.operator_username == "当前管理员"
    assert "待移除管理员" in log.details


def test_delete_admin_rejects_current_account(admin_db: Session) -> None:
    """永久移除接口必须拒绝操作者删除自己的当前账号。"""

    current_admin = _admin("当前管理员", is_super_admin=True)
    admin_db.add(current_admin)
    admin_db.commit()
    admin_db.refresh(current_admin)
    assert current_admin.id is not None

    with pytest.raises(HTTPException) as exc_info:
        delete_admin(current_admin.id, admin_db, current_admin)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "不能删除当前账号"
