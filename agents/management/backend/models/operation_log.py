"""
Management Backend - 操作日志模型
对应 operation_logs 表
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class OperationLog(SQLModel, table=True):
    """操作日志"""

    __tablename__ = "operation_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    operator_id: Optional[int] = Field(default=None, index=True)
    operator_username: Optional[str] = Field(default=None, max_length=50)
    action: str = Field(max_length=100)
    target_type: str = Field(max_length=50)  # agent / model / system
    target_id: Optional[int] = Field(default=None)
    details: str = Field(default="")  # JSON 字符串
    created_at: datetime = Field(default_factory=datetime.utcnow)
