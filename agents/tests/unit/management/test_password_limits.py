"""验证公开注册与两套管理员创建流程的密码长度边界。

这些模型是三处前端提交账号密码时的最终后端契约，必须统一接受 8–32 位密码。
"""

from typing import Type

import pytest
from pydantic import BaseModel, ValidationError

from agents.management.backend.schemas import (
    AdminCreateRequest as ManagementAdminCreateRequest,
)
from agents.management.backend.schemas import (
    AdminProfileUpdateRequest as ManagementAdminProfileUpdateRequest,
)
from social_platform.app.admin.schemas import (
    AdminCreateRequest as PlatformAdminCreateRequest,
)
from social_platform.app.admin.schemas import (
    AdminProfileUpdateRequest as PlatformAdminProfileUpdateRequest,
)
from social_platform.app.schemas.auth import UserRegister


PASSWORD_MODELS = [
    (UserRegister, {}, "password"),
    (PlatformAdminCreateRequest, {"username": "admin"}, "password"),
    (
        PlatformAdminProfileUpdateRequest,
        {"current_password": "initial-password"},
        "new_password",
    ),
    (ManagementAdminCreateRequest, {"username": "admin"}, "password"),
    (
        ManagementAdminProfileUpdateRequest,
        {"current_password": "initial-password"},
        "new_password",
    ),
]


@pytest.mark.parametrize(("model", "base_payload", "password_field"), PASSWORD_MODELS)
def test_password_models_accept_boundary_lengths(
    model: Type[BaseModel],
    base_payload: dict[str, object],
    password_field: str,
) -> None:
    """验证三类账号流程都接受 8 位和 32 位密码。

    Args:
        model: 待验证的 Pydantic 请求模型。
        base_payload: 除密码外的必填请求字段。
        password_field: 模型中的密码字段名。
    """

    for length in (8, 32):
        payload = {**base_payload, password_field: "p" * length}

        parsed = model(**payload)

        assert getattr(parsed, password_field) == "p" * length


@pytest.mark.parametrize(("model", "base_payload", "password_field"), PASSWORD_MODELS)
def test_password_models_reject_out_of_range_lengths(
    model: Type[BaseModel],
    base_payload: dict[str, object],
    password_field: str,
) -> None:
    """验证三类账号流程都拒绝少于 8 位或超过 32 位的密码。

    Args:
        model: 待验证的 Pydantic 请求模型。
        base_payload: 除密码外的必填请求字段。
        password_field: 模型中的密码字段名。
    """

    for length in (7, 33):
        payload = {**base_payload, password_field: "p" * length}

        with pytest.raises(ValidationError):
            model(**payload)
