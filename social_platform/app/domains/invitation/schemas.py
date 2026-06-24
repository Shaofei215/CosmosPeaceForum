"""注册邀请码 API DTO。

本模块定义管理端生成、列表展示邀请码，以及公开注册流程读取配置时使用的响应结构。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class InvitationCodeCreateRequest(BaseModel):
    """管理端创建邀请码请求。

    Attributes:
        email: 邀请码绑定的注册邮箱。
        prefix: 可编辑的邀请码前缀，后端会规范化为大写。
    """

    email: EmailStr = Field(..., description="邀请码绑定邮箱")
    prefix: str = Field(default="", max_length=16, description="邀请码前缀")

    @field_validator("prefix")
    @classmethod
    def normalize_prefix(cls, value: str) -> str:
        """规范化前缀输入。

        Args:
            value: 管理员提交的前缀。

        Returns:
            str: 去除首尾空白后的前缀。
        """

        return value.strip()


class InvitationCodeResponse(BaseModel):
    """管理端邀请码列表项。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    code: str
    prefix: str
    status: Literal["unused", "used"]
    created_at: datetime
    updated_at: datetime
    created_by_admin_id: int | None
    created_by_admin_username: str | None
    used_by_user_id: int | None
    used_by_username: str | None
    used_at: datetime | None


class InvitationRegistrationConfigResponse(BaseModel):
    """公开注册页的邀请码配置响应。"""

    enabled: bool = Field(..., description="是否开启邀请制注册")

