# 记忆系统测试用例
# 测试记忆系统的核心功能

import pytest
import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from agents.agents_scheduler.memory.config import MemoryConfig
from agents.agents_scheduler.memory.models import MemoryChunk
from agents.agents_scheduler.memory.database import MemoryDB


class TestMemoryConfig:
    """测试记忆系统配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = MemoryConfig()
        assert config.memory_enabled is True
        assert config.recall_limit == 5
        assert config.threshold == 0.1
        assert config.boost_factor == 0.1
        assert config.decay_rate == 0.01

    def test_config_validation(self):
        """测试配置验证"""
        with pytest.raises(ValueError):
            MemoryConfig(recall_limit=0)

        with pytest.raises(ValueError):
            MemoryConfig(threshold=1.5)

        with pytest.raises(ValueError):
            MemoryConfig(boost_factor=-0.1)


class TestMemoryChunk:
    """测试记忆分块数据模型"""

    def test_create_memory_chunk(self):
        """测试创建记忆分块"""
        chunk = MemoryChunk.create(
            owner_id=42,
            content="我在论坛上看到了关于镜流新角色的讨论",
            memory_coefficient=0.85
        )

        assert chunk.owner_id == 42
        assert chunk.content == "我在论坛上看到了关于镜流新角色的讨论"
        assert chunk.memory_coefficient == 0.85
        assert chunk.id is not None
        assert chunk.timestamp > 0

    def test_to_dict_and_from_dict(self):
        """测试字典转换"""
        chunk = MemoryChunk.create(
            owner_id=42,
            content="测试内容",
            memory_coefficient=0.75
        )

        data = chunk.to_dict()
        assert data["owner_id"] == 42
        assert data["content"] == "测试内容"
        assert data["memory_coefficient"] == 0.75

        restored = MemoryChunk.from_dict(data)
        assert restored.id == chunk.id
        assert restored.owner_id == chunk.owner_id
        assert restored.content == chunk.content


class TestMemoryDB:
    """测试 SQLite 数据库操作"""

    def setup_method(self):
        """每个测试前初始化"""
        self.config = MemoryConfig(memory_dir="./test_memory")
        self.db = MemoryDB(self.config)

    def teardown_method(self):
        """每个测试后清理"""
        self.db.close()
        # 清理测试目录
        import shutil
        test_dir = Path("./test_memory")
        if test_dir.exists():
            shutil.rmtree(test_dir)

    @pytest.mark.asyncio
    async def test_add_and_get_memory(self):
        """测试添加和获取记忆"""
        chunk = MemoryChunk.create(
            owner_id=42,
            content="测试记忆内容",
            memory_coefficient=0.85
        )

        await self.db.add_memory(chunk)
        retrieved = await self.db.get_memory(chunk.id)

        assert retrieved is not None
        assert retrieved.id == chunk.id
        assert retrieved.content == chunk.content
        assert retrieved.owner_id == chunk.owner_id

    @pytest.mark.asyncio
    async def test_update_memory(self):
        """测试更新记忆"""
        chunk = MemoryChunk.create(
            owner_id=42,
            content="原始内容",
            memory_coefficient=0.85
        )

        await self.db.add_memory(chunk)

        # 更新记忆系数
        chunk.memory_coefficient = 0.95
        chunk.content = "更新后的内容"
        await self.db.update_memory(chunk)

        retrieved = await self.db.get_memory(chunk.id)
        assert retrieved.memory_coefficient == 0.95
        assert retrieved.content == "更新后的内容"

    @pytest.mark.asyncio
    async def test_delete_memory(self):
        """测试删除记忆"""
        chunk = MemoryChunk.create(
            owner_id=42,
            content="待删除的记忆",
            memory_coefficient=0.85
        )

        await self.db.add_memory(chunk)
        await self.db.delete_memory(chunk.id)

        retrieved = await self.db.get_memory(chunk.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_user_memories(self):
        """测试获取用户记忆"""
        # 添加多个用户的记忆
        for i in range(3):
            chunk = MemoryChunk.create(
                owner_id=42,
                content=f"用户42的记忆{i}",
                memory_coefficient=0.85
            )
            await self.db.add_memory(chunk)

        for i in range(2):
            chunk = MemoryChunk.create(
                owner_id=99,
                content=f"用户99的记忆{i}",
                memory_coefficient=0.85
            )
            await self.db.add_memory(chunk)

        user42_memories = await self.db.get_user_memories(42)
        assert len(user42_memories) == 3

        user99_memories = await self.db.get_user_memories(99)
        assert len(user99_memories) == 2

    @pytest.mark.asyncio
    async def test_clear_user_memories(self):
        """测试清除用户记忆"""
        for i in range(3):
            chunk = MemoryChunk.create(
                owner_id=42,
                content=f"用户42的记忆{i}",
                memory_coefficient=0.85
            )
            await self.db.add_memory(chunk)

        count = await self.db.clear_user_memories(42)
        assert count == 3

        user42_memories = await self.db.get_user_memories(42)
        assert len(user42_memories) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
