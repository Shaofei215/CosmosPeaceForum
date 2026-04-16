# ChromaDB 向量检索层
# 提供基于向量语义相似度的记忆检索功能

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
import numpy as np

from agent_scheduler.memory.config import MemoryConfig


class VectorStore:
    """
    ChromaDB 向量存储封装类

    提供基于向量语义相似度的记忆检索功能。
    使用余弦相似度计算向量距离。

    所有操作都通过 owner_id 实现所有权隔离。
    """

    def __init__(self, config: MemoryConfig):
        """
        初始化 ChromaDB 客户端和 Collection

        Args:
            config: 记忆系统配置
        """
        self.config = config
        self.client = chromadb.PersistentClient(
            path=config.get_chroma_db_path(),
            settings=Settings(anonymized_telemetry=False)
        )

        self.collection = self.client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"}
        )

    def add_vector(
        self,
        memory_id: str,
        owner_id: int,
        embedding: List[float],
        metadata: Optional[Dict] = None
    ) -> None:
        """
        添加向量到索引

        Args:
            memory_id: 记忆 ID
            owner_id: 用户 ID
            embedding: 向量表示
            metadata: 附加元数据
        """
        meta = metadata or {}
        meta["owner_id"] = owner_id

        self.collection.add(
            embeddings=[embedding],
            ids=[memory_id],
            metadatas=[meta]
        )

    def query(
        self,
        query_embedding: List[float],
        owner_id: int,
        n_results: int = 5
    ) -> List[Dict]:
        """
        向量相似度检索

        Args:
            query_embedding: 查询向量
            owner_id: 用户 ID（用于所有权过滤）
            n_results: 返回结果数量

        Returns:
            List[Dict]: 检索结果列表，每个结果包含 id, metadata, distance
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where={"owner_id": owner_id}
        )

        memories = []
        if results["ids"] and results["ids"][0]:
            for i, memory_id in enumerate(results["ids"][0]):
                memories.append({
                    "id": memory_id,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                })

        return memories

    def update_vector(
        self,
        memory_id: str,
        metadata: Optional[Dict] = None,
        embedding: Optional[List[float]] = None
    ) -> None:
        """
        更新向量元数据或向量本身

        Args:
            memory_id: 记忆 ID
            metadata: 新的元数据
            embedding: 新的向量
        """
        update_kwargs = {"ids": [memory_id]}
        if metadata:
            update_kwargs["metadatas"] = [metadata]
        if embedding:
            update_kwargs["embeddings"] = [embedding]

        self.collection.update(**update_kwargs)

    def delete_vector(self, memory_id: str) -> None:
        """
        删除向量

        Args:
            memory_id: 要删除的记忆 ID
        """
        self.collection.delete(ids=[memory_id])

    def get_vector_count(self, owner_id: Optional[int] = None) -> int:
        """
        获取向量数量

        Args:
            owner_id: 用户 ID（可选，如果提供则只统计该用户的向量）

        Returns:
            int: 向量数量
        """
        if owner_id is not None:
            results = self.collection.get(
                where={"owner_id": owner_id}
            )
            return len(results["ids"]) if results["ids"] else 0
        return self.collection.count()
