# 邮箱验证数据验证模型（Pydantic Schemas）
# 定义邮箱验证相关的请求和响应格式
from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class EmailCodeSendRequest(BaseModel):
    """
    邮箱验证码发送请求模型

    用户请求发送验证码到指定邮箱
    """
    email: EmailStr = Field(
        ...,
        description="邮箱地址"
    )


class EmailCodeSendResponse(BaseModel):
    """
    验证码发送响应模型

    返回验证码发送结果信息
    """
    message: str = Field(
        ...,
        description="响应消息"
    )
    email: EmailStr = Field(
        ...,
        description="目标邮箱"
    )
    expires_in: int = Field(
        ...,
        description="验证码有效期（秒）"
    )


class PasswordResetRequest(BaseModel):
    """
    密码重置请求模型

    用户请求通过邮箱重置密码
    """
    email: EmailStr = Field(
        ...,
        description="已绑定的邮箱地址"
    )


class PasswordResetConfirmRequest(BaseModel):
    """
    密码重置确认请求模型

    用户提交新密码和验证码完成密码重置
    """
    email: EmailStr = Field(
        ...,
        description="邮箱地址"
    )
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6位数字验证码"
    )
    new_password: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="新密码"
    )
