# Agent 记忆系统设计规范

> 版本：v2.1
> 日期：2026-04-16
> 状态：已实现

---

## 1. 概述

### 1.1 设计目标

为 AI Agent 构建一套**长期记忆存储与召回系统**，使 Agent 在会话之间保持上下文连贯性，模拟真实角色的"记忆"能力。

### 1.2 核心问题

- **记忆无连续性**：每次会话从零开始，不记得历史信息，角色无记忆。
- **遗忘机制**：重要记忆需要"唤醒"才能被想起，长期未召回的记忆会逐渐遗忘。

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| 配置统一 | 通过 `memory/config.py` 从 `.env` 加载，保证扩展性、内聚性、解耦性 |
| 时间系统 | 使用 `time_system.py` 获取缩放时间戳，保证时间一致性 |
| 所有权隔离 | 通过 `owner_id` 元数据过滤，确保每个角色的记忆独立存储 |
| LLM 主导 | 由 LLM 自动完成语义分块，无需规则引擎 |
| 混合检索 | 结合向量检索（ChromaDB）与关键词检索（Tantivy BM25） |
| 遗忘曲线 | 基于记忆系数的衰减与唤醒机制 |

---

## 2. 系统架构

### 2.1 架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LangGraph 会话流程                              │
│                                                                         │
│  START → start → recall_memory → llm_decision → tool_execution         │
│                                          ↓                              │
│                              (循环 recall_memory)                       │
│                                          ↓                              │
│                                    summarize → END                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         记忆服务层 (MemoryService)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │  write_memory │  │recall_memories│  │ decay_memory │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                           存储与检索层                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│  │     SQLite      │  │    ChromaDB      │  │     Tantivy     │        │
│  │  (持久化存储)    │  │   (向量检索)     │  │   (BM25检索)    │        │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 组件职责

| 组件 | 职责 | 数据类型 |
|------|------|----------|
| **SQLite** | 记忆分块持久化存储、主数据源 | 结构化数据 |
| **ChromaDB** | 向量语义相似度检索 | embedding vectors |
| **Tantivy** | BM25 关键词检索 | 倒排索引 |

### 2.3 数据流

```
会话结束
    ↓
LLM 生成叙事性总结
    ↓
LLM 调用 write_memory 工具（批量写入多条记忆）
    ↓
┌────────────────────────────────────┐
│  三写同步：                          │
│  ├── SQLite（主存储）                │
│  ├── ChromaDB（向量索引）            │
│  └── Tantivy（BM25索引）            │
└────────────────────────────────────┘

每次决策前
    ↓
┌────────────────────────────────────┐
│  构建查询上下文：                     │
│  ├── current_location（当前位置）    │
│  ├── last_tool_result（工具结果）   │
│  └── action_history（工作记忆）     │
└────────────────────────────────────┘
    ↓
┌────────────────────────────────────┐
│  混合检索：                          │
│  ├── ChromaDB 向量检索 → top-k      │
│  └── Tantivy BM25 检索 → top-k     │
│  └── 并集去重 + 系数过滤             │
│  └── 召回时"唤醒"：系数 boost       │
└────────────────────────────────────┘
    ↓
记忆片段注入 Prompt → LLM 决策
```

---

## 3. 混合 RAG 检索架构

### 3.1 为什么需要混合检索

| 检索方式 | 优势 | 劣势 | 适用场景 |
|----------|------|------|----------|
| 向量检索 | 语义相似性、语义泛化 | 难以精确关键词匹配 | "相关内容"的模糊检索 |
| BM25 检索 | 精确关键词匹配、可解释性强 | 无法处理同义词、语义泛化 | 明确实体的精确检索 |

混合检索结合两者优势，通过**并集 + 重排序**获取最优结果。

### 3.2 检索流程

```python
async def recall_memories(
    self,
    owner_id: int,
    context: str,
    current_time: float = None,
    limit: int = 5
) -> list[tuple[MemoryChunk, str]]:
    """
    混合检索召回记忆

    1. 并行执行向量检索和 BM25 检索
    2. 合并结果集（并集）
    3. 按记忆系数过滤
    4. 按系数排序返回 top-k
    5. 召回时"唤醒"：系数 boost
    """
    # 向量检索 - 语义相似
    query_embedding = get_embedding(context)
    vector_results = self.vector_store.query(
        query_embedding=query_embedding,
        owner_id=owner_id,
        n_results=config.recall_vector_results  # 如 5
    )

    # BM25 检索 - 关键词匹配
    bm25_results = self.bm25_index.search(
        query=context,
        owner_id=owner_id,
        limit=config.recall_bm25_results  # 如 5
    )

    # 并集去重
    all_ids = set(r["id"] for r in vector_results) | set(r["id"] for r in bm25_results)

    # 获取实际数据 + 系数过滤
    all_memories = []
    for memory_id in all_ids:
        chunk = await self.db.get_memory(memory_id)
        if chunk and chunk.memory_coefficient >= config.threshold:  # 如 0.3
            all_memories.append(chunk)

    # 按系数降序排序
    all_memories.sort(key=lambda x: x.memory_coefficient, reverse=True)

    # 唤醒机制：召回时 boost 系数
    for chunk in all_memories[:limit]:
        chunk.memory_coefficient = min(1.0, chunk.memory_coefficient + config.boost_factor)
        await self.db.update_memory(chunk)
        self.vector_store.update_vector(chunk.id, {"memory_coefficient": chunk.memory_coefficient})

    return result
```

### 3.3 检索配置参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `recall_vector_results` | 向量检索返回数量 | 5 |
| `recall_bm25_results` | BM25 检索返回数量 | 5 |
| `recall_limit` | 最终返回数量 | 5 |
| `threshold` | 记忆系数最低阈值 | 0.3 |
| `boost_factor` | 唤醒时系数增量 | 0.3 |

---

## 4. LLM 自主第一人称记忆分块

### 4.1 分块原则

记忆分块由 LLM 自主完成，遵循以下原则：

1. **第一人称**：记忆内容以"我"为主语，符合 Agent 视角
2. **语义完整**：每个分块是一个完整的记忆单元
3. **长度适中**：单条记忆长度 50-200 字
4. **批量写入**：LLM 一次性生成多条记忆，通过 `memories` 列表传入

### 4.2 分块工具定义

```python
@tool
def write_memory(
    memories: list,
    reason: str = "用户想要将重要经历写入长期记忆",
    summary: str = ""
) -> ToolResult:
    """
    将记忆写入长期记忆库

    【重要！】注意！如果提示词中未提及调用此工具，此工具严禁被调用！

    进入总结节点后，提示词提示LLM 调用此工具将本次会话的重要经历写入记忆库。
    LLM 将总结内容分成 n 个语义完整的记忆片段，一次性传入。

    注意：
    - 每条记忆应以"我"为主语，第一人称描述
    - 每次调用可写入多条记忆，每条记忆分块上限200字，每个分块都必须有完整的上下文叙事与人际关系叙事。
    - memories 是一个列表，每个元素是一个字典，包含 content 和 memory_coefficient

    Args:
        memories: 记忆列表，每个元素是 {"content": "记忆内容", "memory_coefficient": 0.85}
        reason: 调用原因
        summary: 对当前视野的第一人称总结

    Returns:
        ToolResult: 包含操作结果和记忆ID列表
    """
```

### 4.3 分块提示词（Summarize 节点）

```markdown
## 记忆写入指令

你刚刚结束了在「星际和平论坛」的会话。请根据本次会话的操作历史，调用 write_memory 工具
生成你认为有必要的 n 条记忆片段，一次性写入你的长期记忆库。

要求：
1. 每条记忆以"我"为主语，第一人称描述
2. 内容应包含：你看到了什么、你做了什么、你的感受或想法
3. 单条记忆长度 50-200 字
4. 记忆应是语义完整独立单元
5. 调用 write_memory 工具时，memories 参数是一个列表，每个元素是：
   {"content": "记忆内容", "memory_coefficient": 0.85}
6. memory_coefficient 范围 0.0-1.0，越高记忆越重要越容易被想起，默认 0.75

示例调用：
write_memory(memories=[
    {"content": "我在论坛上看到了关于镜流新角色的讨论，姬子姐姐对这个角色很感兴趣", "memory_coefficient": 0.85},
    {"content": "今天我在论坛上发了一篇帖子，得到了很多回复", "memory_coefficient": 0.75}
])

请调用 write_memory 工具写入所有重要记忆。
```

### 4.4 分块数据结构

```python
@dataclass
class MemoryChunk:
    id: str                    # UUID，全局唯一
    owner_id: int              # 所属用户 ID（用于所有权隔离）
    content: str                # 记忆内容（LLM 第一人称生成）
    timestamp: float           # 时间戳（从 time_system 获取缩放时间）
    memory_coefficient: float  # 记忆系数 [0.0, 1.0]

    @classmethod
    def create(cls, owner_id: int, content: str, memory_coefficient: float = 0.85) -> "MemoryChunk":
        ts = get_time_system()
        return cls(
            id=str(uuid.uuid4()),
            owner_id=owner_id,
            content=content,
            timestamp=ts.get_scaled_timestamp(),
            memory_coefficient=memory_coefficient
        )
```

---

## 5. 记忆分块相关服务

### 5.1 记忆所有权隔离

每个 Agent 的记忆通过 `owner_id` 严格隔离，检索时自动过滤：

```python
# ChromaDB 检索时自动携带 owner_id 过滤
def query(self, query_embedding: list[float], owner_id: int, n_results: int = 5) -> list[dict]:
    results = self.collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where={"owner_id": owner_id}  # 所有权过滤
    )
    return memories

# Tantivy BM25 检索时自动携带 owner_id 过滤
def search(self, query: str, owner_id: int, limit: int = 5) -> list[dict]:
    # 在搜索结果中过滤 owner_id
    results = []
    for doc_address in top_docs.hits:
        doc = searcher.doc(doc_address.doc_id)
        doc_owner_id = doc.get_first("owner_id")
        if doc_owner_id == owner_id:
            results.append({...})
    return results
```

### 5.2 记忆系数衰减

基于遗忘曲线理论，记忆系数随时间自然衰减。衰减可通过定时任务或每次召回时检查：

```python
async def decay_memories(self, decay_rate: float = 0.01) -> list[str]:
    """
    记忆衰减

    所有记忆的系数按时间差衰减。时间差越大，衰减越多。
    低于阈值的记忆将被删除。

    Args:
        decay_rate: 每次衰减率，默认 0.01

    Returns:
        list[str]: 被删除的记忆 ID 列表
    """
    ts = get_time_system()
    current_time = ts.get_scaled_timestamp()

    # 获取所有记忆
    all_memories = await self.db.get_all_memories()

    deleted_ids = []
    for chunk in all_memories:
        time_delta = current_time - chunk.timestamp
        # 衰减量与时间差成正比
        decay_amount = decay_rate * (time_delta / 86400)  # 按天计算
        chunk.memory_coefficient -= decay_amount

        if chunk.memory_coefficient < self.config.threshold:
            await self.delete_memory(chunk.id)
            deleted_ids.append(chunk.id)
        else:
            await self.db.update_memory(chunk)
            self.vector_store.update_vector(chunk.id, {"memory_coefficient": chunk.memory_coefficient})

    return deleted_ids
```

### 5.3 记忆唤醒（Boost）

召回记忆时，系统自动"唤醒"该记忆，临时提升其记忆系数：

```python
# 在 recall_memories 中调用
for chunk in all_memories[:limit]:
    # 唤醒：召回时 boost 系数
    new_coef = min(1.0, chunk.memory_coefficient + config.boost_factor)
    if new_coef != chunk.memory_coefficient:
        chunk.memory_coefficient = new_coef
        await self.db.update_memory(chunk)
        self.vector_store.update_vector(chunk.id, {"memory_coefficient": new_coef})
```

### 5.4 记忆移除

记忆移除发生在系数低于阈值时，由衰减服务触发：

```python
async def delete_memory(self, memory_id: str) -> None:
    """删除记忆，同时从三个存储中移除"""
    await self.db.delete_memory(memory_id)
    self.vector_store.delete_vector(memory_id)
    self.bm25_index.delete_doc(memory_id)

# 在 decay_memories 中调用
if chunk.memory_coefficient < self.config.threshold:
    await self.delete_memory(chunk.id)
    deleted_ids.append(chunk.id)
```

### 5.5 记忆服务完整接口

```python
class MemoryService:
    _instance: Optional["MemoryService"] = None

    async def write_memory(
        self,
        content: str,
        owner_id: int,
        memory_coefficient: float = 0.85
    ) -> str:
        """写入记忆（三写同步）"""

    async def recall_memories(
        self,
        owner_id: int,
        context: str,
        current_time: float = None,
        limit: int = 5
    ) -> list[tuple[MemoryChunk, str]]:
        """混合检索召回记忆"""

    async def decay_memories(self, decay_rate: float = 0.01) -> list[str]:
        """记忆衰减与垃圾回收"""

    async def delete_memory(self, memory_id: str) -> None:
        """删除单条记忆"""

    async def clear_user_memories(self, owner_id: int) -> int:
        """清除用户所有记忆（谨慎使用）"""
```

---

## 6. 与 Agent 流程的集成

### 6.1 记忆召回时机

**关键设计**：记忆召回发生在每次 `llm_decision` 之前，而不是单独的节点。

```
start → recall_memory → llm_decision → tool_execution
                                  ↓
                    (should_continue_edge)
                                  ↓
                    recall_memory → llm_decision → ...
                                  ↓
                               summarize
```

**查询上下文构建**（在 `llm_decision_node` 中）：

```python
# 构建查询上下文（与 build_decision_prompt 保持一致）
context_parts = [current_location]

# 添加 last_tool_result
last_result = state.get("last_tool_result")
if last_result and isinstance(last_result, dict):
    action = last_result.get("action", "")
    if action:
        context_parts.append(action)

# 添加 action_history（工作记忆）的关键信息
action_history = state.get("action_history", [])
if action_history:
    for record in action_history[-3:]:  # 取最近 3 条
        summary = record.get("summary", "")
        action = record.get("action", "")
        if summary:
            context_parts.append(f"我{action}了：{summary[:30]}")
        elif action:
            context_parts.append(f"我{action}了")

query_context = "；".join(context_parts)
```

### 6.2 记忆召回节点（简化）

`recall_memory_node` 只负责初始化，实际检索在 `llm_decision_node` 中进行：

```python
# langgraph/nodes.py

def recall_memory_node(state: SessionState) -> SessionState:
    """
    记忆召回节点（初始化）

    只是标记位置，实际检索在 llm_decision_node 中进行。
    这样可以利用完整的上下文（current_location + last_tool_result + action_history）进行检索。
    """
    state["recalled_memories"] = ""
    return state
```

### 6.3 记忆写入（Summarize 节点）

会话结束时，在 Summarize 节点中：

1. LLM 生成叙事性会话总结
2. LLM 调用 `write_memory` 工具批量写入记忆
3. 节点执行工具调用

```python
def summarize_node(state: SessionState, llm_invoker: Callable) -> SessionState:
    """
    总结节点

    1. 生成叙事性会话总结
    2. LLM 调用 write_memory 工具写入记忆库
    3. 执行工具调用
    """
    # ... 构建 prompt ...

    response = llm_invoker(system_prompt, user_prompt)

    # 检查 LLM 是否返回了工具调用
    if hasattr(response, 'tool_calls') and response.tool_calls:
        tools_map = {t.name.lower(): t for t in get_social_tools()}

        for tc in response.tool_calls:
            tool_name = tc.get("name", "").lower()
            tool_args = tc.get("args", {})

            if tool_name in tools_map:
                # 直接调用函数
                result = tools_map[tool_name].func(**tool_args)

    # ...
```

### 6.4 Prompt 注入格式

召回的记忆以以下格式注入到 LLM Prompt：

```markdown
## 相关记忆
[记忆片段 - 3天前]
我在论坛上看到了关于镜流新角色的讨论，姬子姐姐对这个角色很感兴趣。

---
[记忆片段 - 1周前]
今天在论坛上看到了丹恒发的一篇帖子，讲的是下层区的搏击俱乐部。

---
```

### 6.5 时间描述计算

记忆召回时附带时间描述，帮助 LLM 理解事件的时序性：

```python
def calculate_time_description(timestamp: float, current_time: float = None) -> str:
    """
    根据时间戳计算人类可读的时间描述

    使用 time_system 获取缩放时间，保证时间一致性。
    """
    if current_time is None:
        ts = get_time_system()
        current_time = ts.get_scaled_timestamp()

    delta_seconds = current_time - timestamp

    if delta_seconds < 0:
        return "未来"
    elif delta_seconds < 60:
        return "刚刚"
    elif delta_seconds < 3600:
        return f"{int(delta_seconds / 60)}分钟前"
    elif delta_seconds < 86400:
        return f"{int(delta_seconds / 3600)}小时前"
    elif delta_seconds < 2592000:
        return f"{int(delta_seconds / 86400)}天前"
    elif delta_seconds < 31536000:
        return f"{int(delta_seconds / 2592000)}个月前"
    else:
        return f"{int(delta_seconds / 31536000)}年前"
```

---

## 7. 数据结构

### 7.1 SQLite 表结构

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

### 7.2 ChromaDB Collection 配置

```python
collection = client.get_or_create_collection(
    name="memories",
    metadata={"hnsw:space": "cosine"}  # 余弦相似度
)
```

### 7.3 Tantivy Schema

```python
schema_builder = tantivy.SchemaBuilder()
schema_builder.add_text_field("id", stored=True)
schema_builder.add_text_field("content", stored=True)
schema_builder.add_unsigned_field("owner_id", stored=True)
schema = schema_builder.build()
```

**注意**：Tantivy 0.24.0 使用 `add_unsigned_field` 而非 `add_u64_field`。

---

## 8. 配置参数

### 8.1 记忆系统配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `memory_enabled` | 是否启用记忆系统 | true |
| `memory_dir` | 记忆存储目录 | `agent_scheduler/memory/` |
| `recall_limit` | 召回记忆数量 | 5 |
| `recall_vector_results` | 向量检索返回数 | 5 |
| `recall_bm25_results` | BM25 检索返回数 | 5 |
| `threshold` | 记忆系数最低阈值 | 0.3 |
| `boost_factor` | 唤醒时系数增量 | 0.3 |
| `decay_rate` | 衰减率（每日） | 0.01 |
| `embedding_model` | 向量化模型相关配置 | Base URL, API Key等 |

**注意**：`memory_dir` 默认值相对于 `agent_scheduler` 目录，而非当前工作目录。

### 8.2 环境变量配置示例

```bash
# 是否启用记忆系统
MEMORY_ENABLED=true

# 记忆存储目录
MEMORY_DIR=./agent_scheduler/memory

# 召回记忆数量
MEMORY_RECALL_LIMIT=5

# 向量检索返回数量
MEMORY_RECALL_VECTOR_RESULTS=5

# BM25 检索返回数量
MEMORY_RECALL_BM25_RESULTS=5

# 记忆系数最低阈值（低于此值的记忆会被删除）
MEMORY_THRESHOLD=0.3

# 唤醒时系数增量（召回时 boost）
MEMORY_BOOST_FACTOR=0.3

# 衰减率（每日）
MEMORY_DECAY_RATE=0.01

# 向量化模型配置
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=your-api-key
EMBEDDING_MODEL_NAME=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

---

## 9. 存储实现

### 9.1 SQLite 封装

```python
class MemoryDB:
    async def add_memory(self, chunk: MemoryChunk) -> None
    async def get_memory(self, memory_id: str) -> Optional[MemoryChunk]
    async def update_memory(self, chunk: MemoryChunk) -> None
    async def delete_memory(self, memory_id: str) -> None
    async def get_all_memories(self) -> list[MemoryChunk]
    async def get_user_memories(self, owner_id: int) -> list[MemoryChunk]
    async def clear_user_memories(self, owner_id: int) -> int
```

### 9.2 ChromaDB 封装

```python
class VectorStore:
    def add_vector(self, memory_id: str, owner_id: int, embedding: list[float], metadata: dict) -> None
    def query(self, query_embedding: list[float], owner_id: int, n_results: int) -> list[dict]
    def update_vector(self, memory_id: str, metadata: dict) -> None
    def delete_vector(self, memory_id: str) -> None
    def get_vector_count(self, owner_id: int = None) -> int
```

### 9.3 Tantivy BM25 封装

```python
class BM25Index:
    def add_doc(self, memory_id: str, content: str, owner_id: int) -> None
    def search(self, query: str, owner_id: int, limit: int) -> list[dict]
    def delete_doc(self, memory_id: str) -> None
    def get_doc_count(self, owner_id: int = None) -> int
```

**注意**：Tantivy 0.24.0 API 变化：
- 使用 `index.parse_query()` 替代 `QueryParser`
- 使用 `doc.get_first("field")` 替代 `doc["field"][0]`
- 搜索结果通过 `.hits` 访问，返回 `SearchResult`

---

## 10. 文件结构

```
agent_scheduler/
├── memory/
│   ├── __init__.py
│   ├── config.py          # 记忆系统配置
│   ├── models.py          # 数据模型
│   ├── database.py        # SQLite 存储层
│   ├── vector_store.py    # ChromaDB 向量存储
│   ├── bm25_index.py      # Tantivy BM25 索引
│   ├── embedding.py       # 向量化模型封装
│   ├── utils.py          # 工具函数
│   ├── service.py         # 记忆服务核心
│   └── tests/
│       └── test_memory.py
└── langgraph/
    ├── nodes.py           # 包含 recall_memory_node, summarize_node
    ├── tools.py           # 包含 write_memory 工具
    └── prompts.py        # 包含 build_summarize_prompt
```

---

*文档版本：v2.1 | 更新日期：2026.4.16*
