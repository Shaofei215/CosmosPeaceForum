# 记忆系统数据模型模块
# 定义记忆分块的数据结构

import uuid
from dataclasses import dataclass, field
from typing import Optional

from agents.agents_scheduler.scheduler.time_system import get_time_system


@dataclass
class MemoryChunk:
    """
    记忆分块数据类

    表示一个独立的记忆单元，由 LLM 以第一人称自主生成。

    Attributes:
        id: UUID，全局唯一标识符
        owner_id: 所属用户 ID（用于所有权隔离）
        content: 记忆内容（LLM 第一人称生成）
        timestamp: 系统时间戳（从 time_system 获取缩放时间，用于衰减计算）
        semantic_timestamp: 语义时间戳（记忆实际产生的时间，用于展示和上下文理解）
        memory_coefficient: 记忆系数 [0.0, 1.0]，越高记忆越重要越容易被想起
    """
    id: str
    owner_id: int
    content: str
    timestamp: float
    memory_coefficient: float
    semantic_timestamp: float = 0.0

    @classmethod
    def create(
        cls,
        owner_id: int,
        content: str,
        memory_coefficient: float = 0.85,
        semantic_timestamp: float = 0.0,
    ) -> "MemoryChunk":
        """
        创建新的记忆分块

        自动生成 UUID 和当前缩放时间戳。

        Args:
            owner_id: 所属用户 ID
            content: 记忆内容，第一人称叙事性描述
            memory_coefficient: 记忆系数 [0.0, 1.0]，默认 0.85
            semantic_timestamp: 语义时间戳，默认为 0 表示与 timestamp 相同

        Returns:
            MemoryChunk: 新创建的记忆分块
        """
        ts = get_time_system()
        system_ts = ts.get_scaled_timestamp()
        if semantic_timestamp == 0.0:
            semantic_timestamp = system_ts
        return cls(
            id=str(uuid.uuid4()),
            owner_id=owner_id,
            content=content,
            timestamp=system_ts,
            memory_coefficient=memory_coefficient,
            semantic_timestamp=semantic_timestamp,
        )

    def to_dict(self) -> dict:
        """
        转换为字典格式（用于数据库存储）

        Returns:
            dict: 包含所有字段的字典
        """
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "content": self.content,
            "timestamp": self.timestamp,
            "semantic_timestamp": self.semantic_timestamp,
            "memory_coefficient": self.memory_coefficient,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryChunk":
        """
        从字典创建记忆分块

        Args:
            data: 包含记忆字段的字典

        Returns:
            MemoryChunk: 记忆分块实例
        """
        return cls(
            id=data["id"],
            owner_id=data["owner_id"],
            content=data["content"],
            timestamp=data["timestamp"],
            memory_coefficient=data["memory_coefficient"],
            semantic_timestamp=data.get("semantic_timestamp", 0.0),
        )

    def __repr__(self) -> str:
        """返回记忆分块的字符串表示"""
        content_preview = self.content[:30] + "..." if len(self.content) > 30 else self.content
        return (
            f"MemoryChunk(id={self.id[:8]}..., "
            f"owner_id={self.owner_id}, "
            f"coefficient={self.memory_coefficient:.2f}, "
            f"content='{content_preview}')"
        )
