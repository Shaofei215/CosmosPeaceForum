# 记忆系统配置模块
# 从 .env 加载记忆系统相关配置，保证扩展性、内聚性、解耦性

import os
from dataclasses import dataclass, field
from pathlib import Path


def _get_default_memory_dir() -> str:
    """
    获取默认记忆存储目录

    默认存储在 agent_scheduler/memory 目录下，
    而不是相对于当前工作目录。

    Returns:
        str: 默认记忆存储目录路径
    """
    scheduler_dir = Path(__file__).parent.parent
    return str(scheduler_dir / "memory")


@dataclass
class MemoryConfig:
    """
    记忆系统配置类

    包含控制记忆系统行为的所有配置参数。

    配置加载顺序（优先级从高到低）：
    1. 环境变量
    2. .env 文件
    3. 程序默认值

    Attributes:
        memory_enabled: 是否启用记忆系统
        memory_dir: 记忆存储目录
        recall_limit: 召回记忆数量
        recall_vector_results: 向量检索返回数量
        recall_bm25_results: BM25 检索返回数量
        threshold: 记忆系数最低阈值
        boost_factor: 唤醒时系数增量
        decay_rate: 衰减率（每日）
        embedding_base_url: 向量化模型 Base URL
        embedding_api_key: 向量化模型 API Key
        embedding_model_name: 向量化模型名称
        embedding_dimension: 向量维度
    """
    memory_enabled: bool = True
    memory_dir: str = field(default_factory=_get_default_memory_dir)
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
    def from_env(cls) -> "MemoryConfig":
        """
        从环境变量创建配置实例

        优先从环境变量获取配置值，环境变量不存在时使用默认值。

        Returns:
            MemoryConfig: 配置实例
        """
        return cls(
            memory_enabled=os.environ.get("MEMORY_ENABLED", "true").lower() in ("true", "1", "yes"),
            memory_dir=os.environ.get("MEMORY_DIR", "./memory"),
            recall_limit=int(os.environ.get("MEMORY_RECALL_LIMIT", "5")),
            recall_vector_results=int(os.environ.get("MEMORY_RECALL_VECTOR_RESULTS", "5")),
            recall_bm25_results=int(os.environ.get("MEMORY_RECALL_BM25_RESULTS", "5")),
            threshold=float(os.environ.get("MEMORY_THRESHOLD", "0.3")),
            boost_factor=float(os.environ.get("MEMORY_BOOST_FACTOR", "0.3")),
            decay_rate=float(os.environ.get("MEMORY_DECAY_RATE", "0.01")),
            embedding_base_url=os.environ.get("EMBEDDING_BASE_URL", ""),
            embedding_api_key=os.environ.get("EMBEDDING_API_KEY", ""),
            embedding_model_name=os.environ.get("EMBEDDING_MODEL_NAME", "text-embedding-3-small"),
            embedding_dimension=int(os.environ.get("EMBEDDING_DIMENSION", "1536")),
        )

    def __post_init__(self):
        """
        配置验证

        在初始化后验证配置参数的合法性。
        """
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
        """
        获取 SQLite 数据库文件路径

        Returns:
            str: 数据库文件完整路径
        """
        memory_dir = Path(self.memory_dir)
        memory_dir.mkdir(parents=True, exist_ok=True)
        return str(memory_dir / "memories.db")

    def get_chroma_db_path(self) -> str:
        """
        获取 ChromaDB 存储目录路径

        Returns:
            str: ChromaDB 存储目录路径
        """
        memory_dir = Path(self.memory_dir)
        memory_dir.mkdir(parents=True, exist_ok=True)
        chroma_dir = memory_dir / "chroma_db"
        chroma_dir.mkdir(parents=True, exist_ok=True)
        return str(chroma_dir)

    def get_tantivy_index_path(self) -> str:
        """
        获取 Tantivy 索引存储目录路径

        Returns:
            str: Tantivy 索引存储目录路径
        """
        memory_dir = Path(self.memory_dir)
        memory_dir.mkdir(parents=True, exist_ok=True)
        tantivy_dir = memory_dir / "tantivy_index"
        tantivy_dir.mkdir(parents=True, exist_ok=True)
        return str(tantivy_dir)


_memory_config: MemoryConfig | None = None


def get_memory_config() -> MemoryConfig:
    """
    获取记忆系统配置单例

    首次调用时从环境变量加载配置，后续调用返回缓存实例。

    Returns:
        MemoryConfig: 记忆系统配置实例
    """
    global _memory_config
    if _memory_config is None:
        _memory_config = MemoryConfig.from_env()
    return _memory_config
