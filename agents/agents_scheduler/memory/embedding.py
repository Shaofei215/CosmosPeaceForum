# 向量化模块
# 提供文本向量化功能，用于 ChromaDB 向量检索

from typing import List, Optional
import httpx

from agents.agents_scheduler.memory.config import MemoryConfig, get_memory_config


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


def get_embedding_model(config: Optional[MemoryConfig] = None) -> EmbeddingModel:
    """
    获取向量化模型单例

    Args:
        config: 记忆系统配置，默认使用全局配置

    Returns:
        EmbeddingModel: 向量化模型实例
    """
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModel(config)
    return _embedding_model
