"""内容安全领域公开 API DTO。"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ContentReportCreate(BaseModel):
    """创建举报请求。"""

    target_type: Literal["post", "comment", "user"]
    target_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        """校验举报原因不为空白字符串。"""

        reason = value.strip()
        if not reason:
            raise ValueError("举报原因不能为空")
        return reason


class ContentReportResponse(BaseModel):
    """创建举报后的公开响应。"""

    id: int
    status: str
    message: str


class ModerationAppealCreate(BaseModel):
    """创建或覆盖管理处罚申诉的公开请求。"""

    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        """校验申诉理由不为空白字符串。"""

        reason = value.strip()
        if not reason:
            raise ValueError("申诉理由不能为空")
        return reason


class ModerationAppealResponse(BaseModel):
    """创建或覆盖申诉后的公开响应。"""

    id: int
    status: str
    message: str
