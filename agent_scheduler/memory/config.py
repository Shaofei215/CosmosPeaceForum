"""
记忆系统配置模块

所有业务配置均通过 management 数据库抽象层加载（system_configs 表）
"""

from dataclasses import dataclass
from pathlib import Path

from agent_scheduler.management.backend.db_client import get_db_client


MEMORY_DIR = Path(__file__).parent / "data"


@dataclass
class MemoryConfig:
    """
    记忆系统配置类

    所有业务配置均从 management 数据库加载，无环境变量 fallback。
    """
    memory_enabled: bool = True
    recall_limit: int = 5
    recall_vector_results: int = 5
    recall_bm25_results: int = 5
    threshold: float = 0.3
    boost_factor: float = 0.3
    decay_rate: float = 0.01
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model_name: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    @classmethod
    def from_db(cls) -> "MemoryConfig":
        """从数据库加载配置"""
        db = get_db_client()

        def _get(key: str, default: str) -> str:
            val = db.get_system_config(key)
            return val if val else default

        return cls(
            memory_enabled=_get("MEMORY_ENABLED", "true").lower() in ("true", "1", "yes"),
            recall_limit=int(_get("MEMORY_RECALL_LIMIT", "5")),
            recall_vector_results=int(_get("MEMORY_RECALL_VECTOR_RESULTS", "5")),
            recall_bm25_results=int(_get("MEMORY_RECALL_BM25_RESULTS", "5")),
            threshold=float(_get("MEMORY_THRESHOLD", "0.3")),
            boost_factor=float(_get("MEMORY_BOOST_FACTOR", "0.3")),
            decay_rate=float(_get("MEMORY_DECAY_RATE", "0.01")),
            embedding_base_url=_get("EMBEDDING_BASE_URL", ""),
            embedding_api_key=_get("EMBEDDING_API_KEY", ""),
            embedding_model_name=_get("EMBEDDING_MODEL_NAME", "text-embedding-3-small"),
            embedding_dimension=int(_get("EMBEDDING_DIMENSION", "1536")),
        )

    def __post_init__(self):
        """配置验证"""
        if self.recall_limit <= 0:
            raise ValueError("recall_limit 必须大于 0")
        if self.recall_vector_results <= 0:
            raise ValueError("recall_vector_results 必须大于 0")
        if self.recall_bm25_results <= 0:
            raise ValueError("recall_bm25_results 必须大于 0")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold 必须在 0.0 到 1.0 之间")
        if not 0.0 <= self.boost_factor <= 1.0:
            raise ValueError("boost_factor 必须在 0.0 到 1.0 之间")
        if self.decay_rate <= 0:
            raise ValueError("decay_rate 必须大于 0")
        if self.embedding_dimension <= 0:
            raise ValueError("embedding_dimension 必须大于 0")

    def get_memory_db_path(self) -> str:
        """获取 SQLite 数据库文件路径"""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        return str(MEMORY_DIR / "memories.db")

    def get_chroma_db_path(self) -> str:
        """获取 ChromaDB 存储目录路径"""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        chroma_dir = MEMORY_DIR / "chroma_db"
        chroma_dir.mkdir(parents=True, exist_ok=True)
        return str(chroma_dir)

    def get_tantivy_index_path(self) -> str:
        """获取 Tantivy 索引存储目录路径"""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        tantivy_dir = MEMORY_DIR / "tantivy_index"
        tantivy_dir.mkdir(parents=True, exist_ok=True)
        return str(tantivy_dir)


_memory_config: MemoryConfig | None = None


def get_memory_config() -> MemoryConfig:
    """获取记忆系统配置单例"""
    global _memory_config
    if _memory_config is None:
        _memory_config = MemoryConfig.from_db()
    return _memory_config


def reload_memory_config():
    """重载记忆系统配置（热更新）"""
    global _memory_config
    _memory_config = MemoryConfig.from_db()
    return _memory_config
