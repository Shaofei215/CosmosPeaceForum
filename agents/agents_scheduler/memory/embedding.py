# 向量化模块
# 提供文本向量化功能，用于 ChromaDB 向量检索

import hashlib
import json
import threading
from typing import List, Optional

import httpx

from agents.agents_scheduler.memory.config import MemoryConfig, get_memory_config


def get_embedding_fingerprint(config: MemoryConfig) -> str:
    """
    计算会影响向量语义空间的 Embedding 配置指纹。

    API Key 不参与指纹，轮换凭据不会触发索引模型变更；端点、模型名或维度变化时
    指纹会改变，从而阻止旧向量与新查询向量被静默混用。

    Args:
        config: 记忆系统配置。

    Returns:
        str: 稳定的 SHA-256 十六进制指纹。
    """
    payload = {
        "base_url": config.embedding_base_url.rstrip("/"),
        "model_name": config.embedding_model_name,
        "dimension": config.embedding_dimension,
    }
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class EmbeddingModel:
    """
    向量化模型封装

    通过 HTTP API 调用向量化服务，将文本转换为向量表示。
    支持 OpenAI 兼容的 Embedding API。
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        """
        初始化向量化模型

        Args:
            config: 记忆系统配置，默认使用全局配置
        """
        self.config = config or get_memory_config()
        self.base_url = self.config.embedding_base_url
        self.api_key = self.config.embedding_api_key
        self.model_name = self.config.embedding_model_name
        self.dimension = self.config.embedding_dimension

    async def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的向量表示

        Args:
            text: 要向量化的文本

        Returns:
            List[float]: 向量表示
        """
        if not self.base_url:
            raise ValueError("EMBEDDING_BASE_URL 未配置")

        url = f"{self.base_url}/embeddings"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "input": text,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        # 提取向量
        if "data" in data and len(data["data"]) > 0:
            return data["data"][0]["embedding"]
        else:
            raise ValueError(f"向量化 API 返回异常: {data}")

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取文本向量表示

        Args:
            texts: 要向量化的文本列表

        Returns:
            List[List[float]]: 向量列表
        """
        if not self.base_url:
            raise ValueError("EMBEDDING_BASE_URL 未配置")

        url = f"{self.base_url}/embeddings"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "input": texts,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        # 提取向量列表
        if "data" in data:
            return [item["embedding"] for item in data["data"]]
        else:
            raise ValueError(f"向量化 API 返回异常: {data}")


_embedding_model: Optional[EmbeddingModel] = None
_embedding_model_lock = threading.RLock()


def get_embedding_model(config: Optional[MemoryConfig] = None) -> EmbeddingModel:
    """
    获取向量化模型单例

    Args:
        config: 记忆系统配置，默认使用全局配置

    Returns:
        EmbeddingModel: 向量化模型实例
    """
    global _embedding_model
    with _embedding_model_lock:
        if _embedding_model is None:
            _embedding_model = EmbeddingModel(config)
        return _embedding_model


def reload_embedding_model(config: Optional[MemoryConfig] = None) -> EmbeddingModel:
    """
    使用最新配置重建全局 Embedding 客户端。

    Args:
        config: 可选的记忆配置，默认读取当前配置单例。

    Returns:
        EmbeddingModel: 重建后的 Embedding 客户端。
    """
    global _embedding_model
    with _embedding_model_lock:
        _embedding_model = EmbeddingModel(config)
        return _embedding_model
