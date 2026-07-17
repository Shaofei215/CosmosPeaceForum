"""
记忆系统配置模块

所有业务配置均通过 management 数据库抽象层加载（system_configs 表）
"""

import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from agents.management.backend.db_client import get_db_client


MEMORY_DIR = Path(__file__).parent / "data"


@dataclass
class MemoryConfig:
    """
    记忆系统配置类

    所有业务配置均从 management 数据库加载，无环境变量 fallback。
    """
    memory_enabled: bool = True
    recall_limit: int = 5
    recall_vector_results: int = 20
    recall_bm25_results: int = 20
    recall_max_candidates: int = 200
    rrf_rank_constant: int = 60
    importance_weight: float = 0.3
    threshold: float = 0.1
    boost_factor: float = 0.1
    boost_cooldown_seconds: int = 86400
    decay_rate: float = 0.01
    decay_interval_seconds: int = 300
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model_name: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    memory_dir: str | None = None

    @classmethod
    def from_db(cls) -> "MemoryConfig":
        """从数据库加载配置"""
        db = get_db_client()

        def _get(key: str, default: str) -> str:
            val = db.get_system_config(key)
            return val if val else default

        embedding_config = db.get_active_embedding_config()

        return cls(
            memory_enabled=_get("MEMORY_ENABLED", "true").lower() in ("true", "1", "yes"),
            recall_limit=int(_get("MEMORY_RECALL_LIMIT", "5")),
            recall_vector_results=int(_get("MEMORY_RECALL_VECTOR_RESULTS", "20")),
            recall_bm25_results=int(_get("MEMORY_RECALL_BM25_RESULTS", "20")),
            recall_max_candidates=int(_get("MEMORY_RECALL_MAX_CANDIDATES", "200")),
            rrf_rank_constant=int(_get("MEMORY_RRF_RANK_CONSTANT", "60")),
            importance_weight=float(_get("MEMORY_IMPORTANCE_WEIGHT", "0.3")),
            threshold=float(_get("MEMORY_THRESHOLD", "0.1")),
            boost_factor=float(_get("MEMORY_BOOST_FACTOR", "0.1")),
            boost_cooldown_seconds=int(_get("MEMORY_BOOST_COOLDOWN_SECONDS", "86400")),
            decay_rate=float(_get("MEMORY_DECAY_RATE", "0.01")),
            decay_interval_seconds=int(_get("MEMORY_DECAY_INTERVAL_SECONDS", "300")),
            embedding_base_url=embedding_config.get("base_url", "") if embedding_config else "",
            embedding_api_key=embedding_config.get("api_key", "") if embedding_config else "",
            embedding_model_name=embedding_config.get("model_name", "text-embedding-3-small") if embedding_config else "text-embedding-3-small",
            embedding_dimension=int(embedding_config.get("dimension", "1536")) if embedding_config else 1536,
        )

    def __post_init__(self):
        """配置验证"""
        if self.recall_limit <= 0:
            raise ValueError("recall_limit 必须大于 0")
        if self.recall_vector_results <= 0:
            raise ValueError("recall_vector_results 必须大于 0")
        if self.recall_bm25_results <= 0:
            raise ValueError("recall_bm25_results 必须大于 0")
        if self.recall_max_candidates <= 0:
            raise ValueError("recall_max_candidates 必须大于 0")
        if self.rrf_rank_constant <= 0:
            raise ValueError("rrf_rank_constant 必须大于 0")
        if not 0.0 <= self.importance_weight <= 1.0:
            raise ValueError("importance_weight 必须在 0.0 到 1.0 之间")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold 必须在 0.0 到 1.0 之间")
        if not 0.0 <= self.boost_factor <= 1.0:
            raise ValueError("boost_factor 必须在 0.0 到 1.0 之间")
        if self.boost_cooldown_seconds < 0:
            raise ValueError("boost_cooldown_seconds 不能小于 0")
        if not math.isfinite(self.decay_rate) or self.decay_rate <= 0:
            raise ValueError("decay_rate 必须大于 0")
        if self.decay_interval_seconds <= 0:
            raise ValueError("decay_interval_seconds 必须大于 0")
        if self.embedding_dimension <= 0:
            raise ValueError("embedding_dimension 必须大于 0")

    def get_memory_db_path(self) -> str:
        """获取 SQLite 数据库文件路径"""
        memory_dir = Path(self.memory_dir) if self.memory_dir else MEMORY_DIR
        memory_dir.mkdir(parents=True, exist_ok=True)
        return str(memory_dir / "memories.db")

    def get_chroma_db_path(self) -> str:
        """获取 ChromaDB 存储目录路径"""
        memory_dir = Path(self.memory_dir) if self.memory_dir else MEMORY_DIR
        memory_dir.mkdir(parents=True, exist_ok=True)
        chroma_dir = memory_dir / "chroma_db"
        chroma_dir.mkdir(parents=True, exist_ok=True)
        return str(chroma_dir)

    def get_tantivy_index_path(self) -> str:
        """获取 Tantivy 索引存储目录路径"""
        memory_dir = Path(self.memory_dir) if self.memory_dir else MEMORY_DIR
        memory_dir.mkdir(parents=True, exist_ok=True)
        tantivy_dir = memory_dir / "tantivy_index"
        tantivy_dir.mkdir(parents=True, exist_ok=True)
        return str(tantivy_dir)


_memory_config: MemoryConfig | None = None
_memory_config_lock = threading.RLock()


def get_memory_config() -> MemoryConfig:
    """获取记忆系统配置单例"""
    global _memory_config
    with _memory_config_lock:
        if _memory_config is None:
            _memory_config = MemoryConfig.from_db()
        return _memory_config


def reload_memory_config(config: Optional[MemoryConfig] = None) -> MemoryConfig:
    """
    提交新的记忆系统配置单例。

    Args:
        config: 已完成兼容性校验的配置；未提供时直接从数据库加载。

    Returns:
        MemoryConfig: 当前已提交的配置实例。
    """
    global _memory_config
    with _memory_config_lock:
        _memory_config = config or MemoryConfig.from_db()
        return _memory_config
