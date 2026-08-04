"""内部角色短期记忆快照模型。

短期记忆与管理端角色配置一一对应，只保存当前 Markdown 快照，不进入长期记忆
的分块、向量或关键词索引。
"""

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class ShortTermMemory(SQLModel, table=True):
    """保存一个内部角色当前仍然认可的短期记忆快照。"""

    __tablename__ = "short_term_memories"  # type: ignore[assignment]

    id: int = Field(primary_key=True, foreign_key="agent_configs.id")
    content: str = Field(default="", sa_column=Column(Text, nullable=False))
    revision: int = Field(default=1, ge=1)
    updated_at: float
    updated_login_count: int = Field(default=0, ge=0)
