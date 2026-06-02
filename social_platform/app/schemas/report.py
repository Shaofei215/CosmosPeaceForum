from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ContentReportCreate(BaseModel):
    target_type: Literal["post", "comment"]
    target_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        reason = value.strip()
        if not reason:
            raise ValueError("举报原因不能为空")
        return reason


class ContentReportResponse(BaseModel):
    id: int
    status: str
    message: str
