# Agent 记忆系统设计规范

> 版本：v1.0
> 日期：2026-04-15
> 状态：设计阶段

---

## 1. 概述

### 1.1 设计目标

为 AI Agent 构建一套**长期记忆存储与召回系统**，使 Agent 在会话之间保持上下文连贯性。

### 1.2 核心问题

- **关系认知缺失**：姬子（`username=银河旅人`）和瓦尔特（`username=人生几何`）按设定是同事，但无法通过网名互相认知
- **记忆无连续性**：每次会话从零开始，不记得历史信息
- **信息过载**：随着时间推移，记忆总量膨胀

### 1.3 设计原则

- **配置统一**：通过 `langgraph/config.py` 从 `.env` 加载，保证扩展性、内聚性、解耦性
- **时间系统**：使用 `time_system.py` 获取时间戳，保证时间一致性
- **所有权隔离**：通过 `owner_id` 元数据过滤
- **LLM 主导分块**：由 LLM 自动完成语义分块
- **时机正确**：记忆召回在"获取信息后、LLM 决策前"注入
- **@tool 装饰器**：使用 LangChain @tool 自动处理函数描述和输出规则

---

## 2. 系统架构

### 2.1 LangGraph 节点流程

```
START → start → get_global_feed → [记忆召回] → llm_decision
                                              ↓
                                        tool_execution
                                              ↓
                                        should_continue
                                           /      \
                              llm_decision    summarize
                                              ↓
                                        [记忆写入] → END
```

### 2.2 组件说明

| 组件 | 职责 |
|------|------|
| **SQLite** | 记忆数据持久化存储 |
| **ChromaDB** | 向量语义检索（用 SQLite 数据构建） |
| **Tantivy** | BM25 关键词检索（用 SQLite 数据构建） |
| **角色映射表** | 每个角色自己的 网名↔角色名 映射 |

### 2.3 配置集成

配置通过 `agent_scheduler/langgraph/config.py` 统一管理：

```python
# agent_scheduler/langgraph/config.py

@dataclass
class MemoryConfig:
    """记忆系统配置"""
    memory_enabled: bool = True
    memory_dir: str = "./data/memories"

    initial_coefficient: float = 0.85
    decay_rate: float = 0.01
    threshold: float = 0.15
    boost_factor: float = 0.25

    recall_limit: int = 5
    recall_vector_results: int = 10
    recall_bm25_results: int = 10

    @classmethod
    def from_env(cls) -> "MemoryConfig":
        _load_env_file()
        return cls(
            memory_enabled=os.environ.get("MEMORY_ENABLED", "true").lower() in ("true", "1", "yes"),
            memory_dir=os.environ.get("MEMORY_DIR", "./data/memories"),
            initial_coefficient=float(os.environ.get("MEMORY_INITIAL_COEFFICIENT", "0.85")),
            decay_rate=float(os.environ.get("MEMORY_DECAY_RATE", "0.01")),
            threshold=float(os.environ.get("MEMORY_THRESHOLD", "0.15")),
            boost_factor=float(os.environ.get("MEMORY_BOOST_FACTOR", "0.25")),
            recall_limit=int(os.environ.get("MEMORY_RECALL_LIMIT", "5")),
            recall_vector_results=int(os.environ.get("MEMORY_RECALL_VECTOR_RESULTS", "10")),
            recall_bm25_results=int(os.environ.get("MEMORY_RECALL_BM25_RESULTS", "10")),
        )
```

### 2.4 时间集成

使用 `agent_scheduler/time_system.py` 获取时间：

```python
from agent_scheduler.time_system import get_time_system

# 获取当前缩放时间戳
ts = get_time_system()
current_timestamp = ts.get_scaled_timestamp()

# 获取缩放后的datetime
current_datetime = ts.get_scaled_time()
```

---

## 3. 数据结构

### 3.1 记忆分块

```python
# memory/chunk.py

from dataclasses import dataclass
from agent_scheduler.time_system import get_time_system

@dataclass
class MemoryChunk:
    """记忆分块"""
    id: str                    # UUID
    owner_id: int              # 所属用户 ID（过滤用）
    content: str                # 记忆内容（LLM 第一人称生成）
    timestamp: float            # 时间戳（从 time_system 获取）
    memory_coefficient: float   # 记忆系数 [0.0, 1.0]

    @classmethod
    def create(cls, owner_id: int, content: str, memory_coefficient: float = 0.85) -> "MemoryChunk":
        """工厂方法：创建新记忆，自动获取时间戳"""
        ts = get_time_system()
        return cls(
            id=str(uuid.uuid4()),
            owner_id=owner_id,
            content=content,
            timestamp=ts.get_scaled_timestamp(),
            memory_coefficient=memory_coefficient
        )
```

### 3.2 SQLite 表结构

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    timestamp REAL NOT NULL,
    memory_coefficient REAL NOT NULL,
    INDEX idx_owner_id (owner_id),
    INDEX idx_memory_coefficient (memory_coefficient)
);
```

---

## 4. 记忆写入（Summarize 节点）

### 4.1 工具定义（@tool）

```python
# langgraph/tools.py

from langchain_core.tools import tool
from agent_scheduler.langgraph.config import get_default_config

@tool
def memorize(
    content: str,
    memory_coefficient: float = None
) -> str:
    """
    将重要信息写入长期记忆

    Args:
        content: 要记忆的内容，第一人称视角
        memory_coefficient: 记忆系数，范围 [0.0, 1.0]，值越大记忆越持久。
                            如果不指定，使用配置中的默认值 (0.85)
    """
    config = get_default_config()

    if memory_coefficient is None:
        memory_coefficient = config.memory.initial_coefficient

    owner_id = get_current_user_id()

    # 异步写入记忆
    from agent_scheduler.memory.service import get_memory_service
    service = get_memory_service()

    memory_id = await service.write_memory(
        content=content,
        owner_id=owner_id,
        memory_coefficient=memory_coefficient
    )

    return f"记忆已保存 (ID: {memory_id})"
```

---

## 5. 记忆召回与注入

### 5.1 召回时机

```
get_global_feed → [记忆召回] → llm_decision
                   ↑
         获取信息后、LLM决策前
```

### 5.2 召回节点

```python
# langgraph/nodes.py

from agent_scheduler.langgraph.config import get_default_config
from agent_scheduler.time_system import get_time_system
from agent_scheduler.memory.service import get_memory_service

async def recall_memory_node(state: SessionState) -> SessionState:
    """
    记忆召回节点

    在 get_global_feed 之后、llm_decision 之前执行
    """
    config = get_default_config()

    if not config.memory.memory_enabled:
        return state

    ts = get_time_system()
    current_time = ts.get_scaled_timestamp()
    current_time_desc = ts.format_scaled_time()

    owner_id = state.get("user_id")
    if not owner_id:
        return state

    # 构建当前上下文（用于检索）
    current_context = state.get("current_view", "")

    service = get_memory_service()
    recalled = await service.recall_memories(
        owner_id=owner_id,
        context=current_context,
        current_time=current_time,
        limit=config.memory.recall_limit
    )

    # 构建记忆注入文本
    if recalled:
        memory_lines = ["## 相关记忆"]
        for chunk, time_desc in recalled:
            memory_lines.append(f"[记忆片段 - {time_desc}]")
            memory_lines.append(chunk.content)
            memory_lines.append("---")

        state["recalled_memories"] = "\n".join(memory_lines)
    else:
        state["recalled_memories"] = ""

    return state
```

### 5.3 时间描述计算

```python
# memory/time_utils.py

from agent_scheduler.time_system import get_time_system

def calculate_time_description(timestamp: float) -> str:
    """
    根据时间戳计算人类可读的时间描述

    使用 time_system 的缩放时间计算差值

    Args:
        timestamp: 记忆写入时的时间戳

    Returns:
        str: 时间描述，如"1小时前"、"3天前"、"2个月前"
    """
    ts = get_time_system()
    current_time = ts.get_scaled_timestamp()
    delta_seconds = current_time - timestamp

    if delta_seconds < 60:
        return "刚刚"
    elif delta_seconds < 3600:
        minutes = int(delta_seconds / 60)
        return f"{minutes}分钟前" if minutes > 1 else "1分钟前"
    elif delta_seconds < 86400:
        hours = int(delta_seconds / 3600)
        return f"{hours}小时前" if hours > 1 else "1小时前"
    elif delta_seconds < 2592000:
        days = int(delta_seconds / 86400)
        return f"{days}天前" if days > 1 else "1天前"
    elif delta_seconds < 31536000:
        months = int(delta_seconds / 2592000)
        return f"{months}个月前" if months > 1 else "1个月前"
    else:
        years = int(delta_seconds / 31536000)
        return f"{years}年前" if years > 1 else "1年前"
```

### 5.4 注入 Prompt

```markdown
## 相关记忆
[记忆片段 - {time_description}]
{memory_content}

---
```

---

## 6. 人际关系映射

### 6.1 问题

帖子数据中作者是 `username`（网名），Agent 不认识这些网名对应的角色。

### 6.2 映射设计

**每位角色有各自独立的映射表**：

```python
# memory/relation_map.py

from typing import Dict

def load_relation_maps(ai_users_config: list[dict]) -> Dict[int, Dict[str, str]]:
    """
    从 AI 用户配置加载关系映射表

    生成每位角色认识的"网名 → 角色名"映射

    Args:
        ai_users_config: AI 用户配置列表

    Returns:
        Dict[int, Dict[str, str]]: {角色ID: {网名: 角色名}}
    """
    relation_maps = {}

    for user in ai_users_config:
        user_id = user["id"]
        username = user["username"]
        name = user["name"]

        # 该角色认识其他所有 AI 用户
        relations = {}
        for other_user in ai_users_config:
            if other_user["id"] != user_id:
                relations[other_user["username"]] = other_user["name"]

        relation_maps[user_id] = relations

    return relation_maps
```

### 6.3 拓展注入（不是替换）

**原始数据**：
```
作者：银河旅人
内容：今天的咖啡不错 @人生几何
```

**标准化后（姬子视角）**：
```
作者：银河旅人（姬子）
内容：今天的咖啡不错 @人生几何（瓦尔特）
```

### 6.4 标准化函数

```python
# memory/standardizer.py

from typing import Dict

def expand_username_in_text(text: str, relation_map: Dict[str, str]) -> str:
    """拓展文本中的用户名"""
    for username, display_name in relation_map.items():
        text = text.replace(f"@{username}", f"@{username}（{display_name}）")
    return text

def standardize_posts(posts: list[dict], owner_id: int, relation_maps: Dict[int, Dict[str, str]]) -> list[dict]:
    """标准化帖子列表"""
    relation_map = relation_maps.get(owner_id, {})

    result = []
    for post in posts:
        standardized = post.copy()

        author = standardized.get("author_username", "")
        if author in relation_map:
            standardized["author_username"] = f"{author}（{relation_map[author]}）"

        if "content" in standardized:
            standardized["content"] = expand_username_in_text(standardized["content"], relation_map)

        result.append(standardized)

    return result
```

### 6.5 注入时机

**方案 A**：在 `tools.py` 的工具函数返回数据时标准化

```python
# tools.py 中
@tool
def get_global_feed(...) -> ToolResult:
    raw_data = _get_global_feed(...)
    owner_id = get_current_user_id()
    standardized = standardize_posts(raw_data.get("data", []), owner_id, GLOBAL_RELATION_MAPS)
    return ToolResult(action="...", data={"data": standardized, **raw_data})
```

**方案 B**：在 Prompt 构建时标准化

```python
# prompts.py 或 nodes.py 中
def build_system_prompt(state: SessionState) -> str:
    owner_id = state.get("user_id")

    # 标准化当前上下文中的数据
    if "current_view" in state:
        standardized = standardize_posts(state["current_view"], owner_id, GLOBAL_RELATION_MAPS)
    else:
        standardized = state.get("current_view", "")

    return f"你是一个角色...\n\n当前信息：{standardized}"
```

---

## 7. SQLite 实现（数据存储）

### 7.1 存储封装

```python
# memory/db_store.py

import aiosqlite
from pathlib import Path
from agent_scheduler.langgraph.config import get_default_config

class MemoryDB:
    def __init__(self, db_path: str = None):
        config = get_default_config()
        self.db_path = db_path or os.path.join(config.memory.memory_dir, "memories.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        """初始化数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    owner_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    memory_coefficient REAL NOT NULL
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_owner_id ON memories(owner_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_memory_coefficient ON memories(memory_coefficient)")
            await db.commit()

    async def add_memory(self, chunk: "MemoryChunk") -> None:
        """添加记忆"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO memories (id, owner_id, content, timestamp, memory_coefficient)
                VALUES (?, ?, ?, ?, ?)
            """, (chunk.id, chunk.owner_id, chunk.content, chunk.timestamp, chunk.memory_coefficient))
            await db.commit()

    async def get_memory(self, memory_id: str) -> Optional["MemoryChunk"]:
        """获取单个记忆"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT id, owner_id, content, timestamp, memory_coefficient
                FROM memories WHERE id = ?
            """, (memory_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return MemoryChunk(
                        id=row[0], owner_id=row[1], content=row[2],
                        timestamp=row[3], memory_coefficient=row[4]
                    )
                return None

    async def update_memory(self, chunk: "MemoryChunk") -> None:
        """更新记忆"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE memories SET content = ?, timestamp = ?, memory_coefficient = ?
                WHERE id = ?
            """, (chunk.content, chunk.timestamp, chunk.memory_coefficient, chunk.id))
            await db.commit()

    async def delete_low_coefficient(self, threshold: float) -> list[str]:
        """删除低于阈值的记忆"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT id FROM memories WHERE memory_coefficient < ?", (threshold,)) as cursor:
                rows = await cursor.fetchall()
                deleted_ids = [row[0] for row in rows]
            await db.execute("DELETE FROM memories WHERE memory_coefficient < ?", (threshold,))
            await db.commit()
            return deleted_ids
```

---

## 8. ChromaDB 实现（向量检索）

### 8.1 向量存储封装

```python
# memory/vector_store.py

import chromadb
from chromadb.config import Settings
from agent_scheduler.langgraph.config import get_default_config

class VectorStore:
    def __init__(self, persist_directory: str = None, collection_name: str = "memories"):
        config = get_default_config()
        persist_dir = persist_directory or os.path.join(config.memory.memory_dir, "chromadb")

        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_vector(self, memory_id: str, owner_id: int, embedding: list[float], metadata: dict) -> None:
        self.collection.add(
            ids=[memory_id],
            embeddings=[embedding],
            metadatas=[{"owner_id": owner_id, **metadata}]
        )

    def query(self, query_embedding: list[float], owner_id: int, n_results: int = 5) -> list[dict]:
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where={"owner_id": owner_id}
        )

        memories = []
        for i in range(len(results["ids"][0])):
            memories.append({
                "id": results["ids"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })
        return memories

    def update_vector(self, memory_id: str, metadata: dict) -> None:
        self.collection.update(ids=[memory_id], metadatas=[metadata])

    def delete_vector(self, memory_id: str) -> None:
        self.collection.delete(ids=[memory_id])
```

### 8.2 向量化函数

```python
# memory/embeddings.py

from openai import OpenAI

def get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """获取文本的向量嵌入"""
    client = OpenAI()
    response = client.embeddings.create(input=text, model=model)
    return response.data[0].embedding
```

---

## 9. Tantivy 实现（BM25 检索）

### 9.1 BM25 检索封装

```python
# memory/bm25_store.py

import tantivy
import os
from agent_scheduler.langgraph.config import get_default_config

class BM25Index:
    def __init__(self, index_directory: str = None):
        config = get_default_config()
        self.index_dir = index_directory or os.path.join(config.memory.memory_dir, "tantivy")
        os.makedirs(self.index_dir, exist_ok=True)

        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_text_field("id", stored=True)
        schema_builder.add_text_field("content", stored=True)
        schema_builder.add_u64_field("owner_id", stored=True)
        self.schema = schema_builder.build()

        index_path = os.path.join(self.index_dir, "index")
        if os.path.exists(index_path):
            self.index = tantivy.Index.open(self.schema, index_path)
        else:
            self.index = tantivy.Index.create_in_dir(self.index_dir, self.schema)

        self.writer = None
        self.searcher = None

    def _get_writer(self, heap_size: int = 128) -> tantivy.IndexWriter:
        if self.writer is None:
            self.writer = self.index.writer(heap_size)
        return self.writer

    def _get_searcher(self) -> tantivy.Searcher:
        if self.searcher is None:
            self.searcher = self.index.searcher()
        return self.searcher

    def add_doc(self, memory_id: str, content: str, owner_id: int) -> None:
        writer = self._get_writer()
        doc = tantivy.Document(id=memory_id, content=content, owner_id=owner_id)
        writer.add_document(doc)
        writer.commit()

    def search(self, query: str, owner_id: int, limit: int = 5) -> list[dict]:
        searcher = self._get_searcher()
        query_parser = tantivy.QueryParser.for_index(self.index, ["content"])
        parsed_query = query_parser.parse_query(query)
        filter_str = f"owner_id:{owner_id}"

        search_results = searcher.search(parsed_query, filter_query=filter_str, top_n=limit)

        results = []
        for score, doc_address in search_results.hits:
            doc = searcher.doc(doc_address)
            results.append({"id": doc["id"], "score": score})
        return results

    def delete_doc(self, memory_id: str) -> None:
        writer = self._get_writer()
        writer.delete_term(f"id:{memory_id}")
        writer.commit()
```

---

## 10. 完整记忆服务

### 10.1 记忆服务整合

```python
# memory/service.py

import os
from typing import Optional
from memory.db_store import MemoryDB
from memory.vector_store import VectorStore
from memory.bm25_store import BM25Index
from memory.embeddings import get_embedding
from memory.standardizer import standardize_posts
from memory.time_utils import calculate_time_description
from memory.chunk import MemoryChunk
from agent_scheduler.langgraph.config import get_default_config
from agent_scheduler.time_system import get_time_system

class MemoryService:
    _instance: Optional["MemoryService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        config = get_default_config()
        self.memory_dir = config.memory.memory_dir
        self.relation_maps = {}

        self.db = MemoryDB()
        self.vector_store = VectorStore()
        self.bm25_index = BM25Index()

        self._initialized = True

    async def initialize(self) -> None:
        await self.db.initialize()

    def set_relation_maps(self, relation_maps: dict) -> None:
        self.relation_maps = relation_maps

    async def write_memory(
        self,
        content: str,
        owner_id: int,
        memory_coefficient: float = 0.85
    ) -> str:
        """写入记忆"""
        ts = get_time_system()
        timestamp = ts.get_scaled_timestamp()

        chunk = MemoryChunk(
            id=str(uuid.uuid4()),
            owner_id=owner_id,
            content=content,
            timestamp=timestamp,
            memory_coefficient=memory_coefficient
        )

        # 写入 SQLite
        await self.db.add_memory(chunk)

        # 同步到 ChromaDB
        embedding = get_embedding(content)
        self.vector_store.add_vector(
            memory_id=chunk.id,
            owner_id=owner_id,
            embedding=embedding,
            metadata={"timestamp": timestamp, "memory_coefficient": memory_coefficient}
        )

        # 同步到 Tantivy
        self.bm25_index.add_doc(
            memory_id=chunk.id,
            content=content,
            owner_id=owner_id
        )

        return chunk.id

    async def recall_memories(
        self,
        owner_id: int,
        context: str,
        current_time: float = None,
        limit: int = 5
    ) -> list[tuple[MemoryChunk, str]]:
        """召回记忆"""
        config = get_default_config()
        ts = get_time_system()

        if current_time is None:
            current_time = ts.get_scaled_timestamp()

        # 向量检索
        query_embedding = get_embedding(context)
        vector_results = self.vector_store.query(
            query_embedding=query_embedding,
            owner_id=owner_id,
            n_results=config.memory.recall_vector_results
        )

        # BM25 检索
        bm25_results = self.bm25_index.search(
            query=context,
            owner_id=owner_id,
            limit=config.memory.recall_bm25_results
        )

        # 合并结果
        all_ids = set(r["id"] for r in vector_results) | set(r["id"] for r in bm25_results)

        # 获取实际数据
        all_memories = []
        for memory_id in all_ids:
            chunk = await self.db.get_memory(memory_id)
            if chunk and chunk.memory_coefficient >= config.memory.threshold:
                all_memories.append(chunk)

        # 按系数排序
        all_memories.sort(key=lambda x: x.memory_coefficient, reverse=True)

        # 唤醒 + 时间描述
        result = []
        for chunk in all_memories[:limit]:
            new_coef = min(1.0, chunk.memory_coefficient + config.memory.boost_factor)
            if new_coef != chunk.memory_coefficient:
                chunk.memory_coefficient = new_coef
                await self.db.update_memory(chunk)
                self.vector_store.update_vector(chunk.id, {"memory_coefficient": new_coef})

            time_desc = calculate_time_description(chunk.timestamp)
            result.append((chunk, time_desc))

        return result


def get_memory_service() -> MemoryService:
    return MemoryService()
```

---

## 11. 模块划分

```
agent_scheduler/
├── memory/
│   ├── __init__.py
│   ├── chunk.py            # MemoryChunk
│   ├── db_store.py          # SQLite 存储
│   ├── vector_store.py      # ChromaDB
│   ├── bm25_store.py        # Tantivy BM25
│   ├── embeddings.py        # 向量化
│   ├── service.py           # 记忆服务整合（单例）
│   ├── standardizer.py      # 数据标准化
│   └── time_utils.py        # 时间描述计算
├── langgraph/
│   ├── config.py            # 统一配置（MemoryConfig）
│   ├── nodes.py             # recall_memory_node
│   └── tools.py             # memorize @tool
└── time_system.py           # 时间系统
```

---

## 12. 实现计划

### Phase 1：基础设施
- [ ] 创建 `memory/` 模块
- [ ] 在 `config.py` 添加 `MemoryConfig`
- [ ] 实现 SQLite 存储 (`db_store.py`)
- [ ] 实现 ChromaDB 封装 (`vector_store.py`)
- [ ] 实现 Tantivy 封装 (`bm25_store.py`)
- [ ] 实现向量化函数 (`embeddings.py`)

### Phase 2：核心功能
- [ ] 实现 `MemoryChunk` 数据类 (`chunk.py`)
- [ ] 实现时间描述计算 (`time_utils.py`)
- [ ] 实现记忆服务 (`service.py`)
- [ ] 实现数据标准化 (`standardizer.py`)
- [ ] 新增 `memorize` @tool

### Phase 3：集成
- [ ] 新增 `recall_memory_node` 节点
- [ ] 修改 session_graph 图结构
- [ ] 接入标准化到 tools.py
- [ ] 加载关系映射表

### Phase 4：测试
- [ ] 单角色记忆测试
- [ ] 多角色记忆隔离测试

---

## 13. 附录

### 13.1 .env 配置项

```bash
# 记忆系统配置
MEMORY_ENABLED=true
MEMORY_DIR=./data/memories

# 记忆衰减参数
MEMORY_INITIAL_COEFFICIENT=0.85
MEMORY_DECAY_RATE=0.01
MEMORY_THRESHOLD=0.15
MEMORY_BOOST_FACTOR=0.25

# 召回参数
MEMORY_RECALL_LIMIT=5
MEMORY_RECALL_VECTOR_RESULTS=10
MEMORY_RECALL_BM25_RESULTS=10
```

### 13.2 架构总结

```
┌─────────────────────────────────────────────────────────────┐
│                    agent_scheduler/                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐      ┌─────────────────┐            │
│  │   time_system   │      │  langgraph/     │            │
│  │   (时间系统)     │      │    config.py    │            │
│  └─────────────────┘      │  (统一配置)      │            │
│           │               └─────────────────┘            │
│           │                        │                       │
│           ▼                        ▼                       │
│  ┌─────────────────────────────────────────┐               │
│  │           MemoryService (单例)            │               │
│  └─────────────────────────────────────────┘               │
│           │               │               │               │
│           ▼               ▼               ▼               │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐           │
│  │  SQLite   │   │ ChromaDB  │   │  Tantivy │           │
│  │  (存储)    │   │ (向量检索) │   │ (BM25检索) │           │
│  └───────────┘   └───────────┘   └───────────┘           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

*文档结束*
