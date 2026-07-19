"""公开平台管理员边界与请求契约回归测试。"""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from social_platform.app.admin.api.admins import (
    _ensure_permission_delegation,
    _ensure_super_admin_boundary,
)
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import AdminCreateRequest, AdminUpdateRequest
from social_platform.app.admin.services import auth_service


def _admin(*, permissions: list[str], is_super_admin: bool = False) -> PlatformAdminUser:
    """构造无需数据库的管理员权限测试实体。"""

    return PlatformAdminUser(
        id=1,
        username="operator",
        password_hash="unused",
        permissions=auth_service.dump_permissions(permissions),
        is_active=True,
        is_super_admin=is_super_admin,
        must_change_credentials=False,
    )


def test_non_super_admin_cannot_cross_super_admin_boundary() -> None:
    operator = _admin(permissions=["manage_admins"])
    target = _admin(permissions=[], is_super_admin=True)

    with pytest.raises(HTTPException) as create_error:
        _ensure_super_admin_boundary(operator, requested_super_admin=True)
    with pytest.raises(HTTPException):
        _ensure_super_admin_boundary(operator, target_admin=target)
    assert create_error.value.status_code == 403


def test_non_super_admin_can_only_change_owned_permissions() -> None:
    operator = _admin(permissions=["manage_admins", "view_dashboard"])

    _ensure_permission_delegation(operator, ["view_dashboard"])
    with pytest.raises(HTTPException) as error:
        _ensure_permission_delegation(operator, ["manage_content"])
    with pytest.raises(HTTPException):
        _ensure_permission_delegation(
            operator,
            ["view_dashboard"],
            existing_permissions=["view_dashboard", "manage_content"],
        )
    assert error.value.status_code == 403


def test_admin_username_is_trimmed_and_limited_to_thirty_characters() -> None:
    request = AdminCreateRequest(username="  a  ", password="12345678")
    assert request.username == "a"
    with pytest.raises(ValidationError):
        AdminCreateRequest(username="a" * 31, password="12345678")


def test_admin_update_rejects_password_takeover_field() -> None:
    with pytest.raises(ValidationError):
        AdminUpdateRequest.model_validate({"new_password": "attacker-password"})
