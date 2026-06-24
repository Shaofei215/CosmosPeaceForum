"""身份安全领域 API 边界 DTO。"""

from pydantic import BaseModel, EmailStr, Field


class EmailCodeSendRequest(BaseModel):
    """邮箱验证码发送请求。

    Attributes:
        email: 接收验证码的目标邮箱地址。
        invitation_code: 邀请制开启时需要提交的邮箱绑定邀请码。
    """

    email: EmailStr = Field(..., description="邮箱地址")
    invitation_code: str | None = Field(default=None, max_length=64, description="邀请码")


class EmailCodeSendResponse(BaseModel):
    """邮箱验证码发送响应。

    Attributes:
        message: 对外展示的发送结果。
        email: 接收验证码的目标邮箱地址。
        expires_in: 验证码有效期，单位为秒。
    """

    message: str = Field(..., description="响应消息")
    email: EmailStr = Field(..., description="目标邮箱")
    expires_in: int = Field(..., description="验证码有效期（秒）")


class PasswordResetRequest(BaseModel):
    """密码重置验证码发送请求。

    Attributes:
        email: 已绑定并完成验证的邮箱地址。
    """

    email: EmailStr = Field(..., description="已绑定的邮箱地址")


class PasswordResetConfirmRequest(BaseModel):
    """密码重置确认请求。

    Attributes:
        email: 已绑定并完成验证的邮箱地址。
        code: 用户收到的 6 位邮箱验证码。
        new_password: 通过验证后要写入的新密码。
    """

    email: EmailStr = Field(..., description="邮箱地址")
    code: str = Field(..., min_length=6, max_length=6, description="6位数字验证码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")
