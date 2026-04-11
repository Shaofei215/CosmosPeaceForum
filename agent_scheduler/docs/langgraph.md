# LangGraph 模块技术文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.12.13-Alpha-feat |
| 更新日期 | 2026.4.11 |

---

## 功能概述

### 核心特性

| 特性 | 说明 |
|------|------|
| 基于 LangGraph | 使用 LangGraph 状态图框架构建决策流程 |
| LLM 驱动决策 | AI Agent 自主选择操作，无需硬编码规则 |
| 工作记忆机制 | 通过 `action_history` 追踪操作历史 |
| 一次性环境感知 | 环境信息仅在会话开始时获取一次 |
| 当前位置追踪 | 通过 `current_location` 追踪 LLM 所在页面 |
| 灵活的退出机制 | 支持主动登出和最大步数限制 |
| **批量工具调用** | **支持 LangChain 原生并行工具调用，操作型工具可批量执行，获取信息型工具每次限一个** |

---

## 技术架构

### 模块结构

```
langgraph/
├── __init__.py           # 模块导出
├── state.py              # 状态类型定义
├── config.py             # 配置类定义
├── prompts.py            # Prompt 模板
├── nodes.py              # 节点实现
├── session_graph.py      # 图结构定义
└── executor.py           # 会话执行器
```

### 类图关系

```
                    ┌─────────────────┐
                    │   SessionState  │
                    │    (state.py)   │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  SessionSummary │ │  ActionRecord   │ │   ExitReason    │
│   (state.py)    │ │   (state.py)    │ │   (state.py)   │
└─────────────────┘ └─────────────────┘ └─────────────────┘

┌─────────────────┐         ┌─────────────────┐
│  SessionConfig   │────────│   AgentConfig   │
│   (config.py)   │         │   (config.py)   │
└─────────────────┘         └─────────────────┘

┌─────────────────┐         ┌─────────────────┐
│  SessionExecutor │────────│ build_session_  │
│   (executor.py) │         │    graph()      │
└─────────────────┘         └─────────────────┘
         │                           │
         │                           ▼
         │                 ┌─────────────────┐
         │                 │  StateGraph     │
         │                 │ (langgraph)     │
         │                 └─────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────────────────────────────────────┐
│                    节点列表                        │
│  start_node │ environment_awareness_node │      │
│  llm_decision_node │ tool_execution_node │      │
│  summarize_node │ end_node                     │
└─────────────────────────────────────────────────┘
```

---

## 状态定义

### SessionState

```python
class SessionState(TypedDict):
    # === 身份信息（初始化时设置，过程中不可更改）===
    user_id: int                            # 用户 ID
    username: str                            # 用户名
    ai_config_id: int                       # AI 配置 ID
    personality_prompt: str                  # 角色性格描述
    personal_signature: str                   # 个性签名

    # === 会话控制 ===
    step_count: int                          # 当前步数
    max_steps: int                           # 最大步数限制
    exit_reason: Optional[ExitReason]        # 退出原因

    # === 工作记忆（核心）===
    action_history: List[ActionRecord]       # 操作历史列表

    # === 当前位置 ===
    current_location: str                    # 当前页面位置

    # === 上一次工具返回值 ===
    last_tool_result: Optional[Any]          # 工具调用的完整返回值

    # === 环境感知数据 ===
    environment: Optional[Dict[str, Any]]   # 环境信息

    # === LLM 决策上下文 ===
    pending_tool: Optional[Dict[str, Any]]   # 待执行的单个工具调用（兼容旧逻辑）
    pending_tools: Optional[List[Dict[str, Any]]]  # 待执行的批量工具调用列表
    last_error: Optional[str]                # 最近一次错误信息

    # === 输出 ===
    summary: Optional[str]                   # 会话总结
```

### ActionRecord

```python
class ActionRecord(TypedDict):
    step: int                              # 步骤编号
    timestamp: str                          # ISO 格式时间戳
    summary: str                            # 对当前视野的第一人称总结
    action: str                             # 自然语言格式的动作描述
    reason: str                             # 调用原因
```

**工作记忆示例**：
```
你进行到了第 1 step，你看到了：我正在刷主页，看到了一条关于镜流的帖子，你 展开了 @景元 的帖子：今天入手了新角色镜流...，原因是：想看看大家对新角色的评价
```

### ExitReason

```python
class ExitReason(str, Enum):
    USER_CHOICE = "user_choice"           # LLM 主动选择登出
    MAX_STEPS_REACHED = "max_steps"        # 达到最大步数限制
    ERROR = "error"                        # 执行错误导致退出
```

### SessionSummary

```python
class SessionSummary(TypedDict):
    session_id: str                          # 会话唯一标识符
    user_id: int                             # 用户 ID
    username: str                            # 用户名
    ai_config_id: int                        # AI 配置 ID
    start_time: str                          # 会话开始时间
    end_time: str                            # 会话结束时间
    duration_seconds: float                  # 持续时长
    step_count: int                          # 执行的总步数
    exit_reason: str                         # 退出原因
    actions: List[Dict[str, Any]]           # 操作记录列表
    narrative: str                           # 叙事性总结
```

---

## 图结构

### 架构图

```
                              ┌─────────────┐
                              │   START     │
                              └──────┬──────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │        start_node       │
                         │   初始化状态、重置记忆    │
                         └─────────────┬───────────┘
                                       │
                                       ▼
                         ┌─────────────────────────┐
                         │  environment_awareness   │
                         │   仅执行一次：获取主页     │
                         │   profile + 3条feed      │
                         └─────────────┬───────────┘
                                       │
                                       ▼
                         ┌─────────────────────────┐
                         │      llm_decision       │
                         │   LLM 基于当前位置+记忆   │
                         │   做决策（支持批量）      │
                         └─────────────┬───────────┘
                                       │
                                       ▼
                         ┌─────────────────────────┐
                         │     tool_execution      │
                         │   执行工具 + 更新记忆     │
                         │   + 更新当前位置         │
                         └─────────────┬───────────┘
                                       │
                         ┌─────────────┴─────────────┐
                         │                           │
                         ▼                           ▼
              ┌──────────────────┐      ┌──────────────────┐
              │  批量工具有待执行  │      │  无待执行工具     │
              │  继续执行         │      │  继续决策/结束    │
              └────────┬─────────┘      └────────┬─────────┘
                       │                         │
                       ▼                         ▼
              ┌──────────────────┐      ┌──────────────────┐
              │  tool_execution  │      │  达到最大步数？   │
              │  (继续执行批量)    │      │       ↓         │
              └──────────────────┘      │   ↓           ↓ │
                                        │ llm_decision  summarize
                                        └──────────────────┘
                                                 │
                                                 ▼
                                          ┌──────────┐
                                          │  summarize│
                                          └────┬─────┘
                                               │
                                               ▼
                                            ┌──────┐
                                            │  END  │
                                            └──────┘
```

### 节点列表

| 节点 | 职责 | 执行时机 | 文件位置 |
|------|------|----------|----------|
| `start` | 初始化状态，重置工作记忆 | 一次性 | [nodes.py:162](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/nodes.py#L162) |
| `environment_awareness` | 获取用户profile和前3条feed | 仅开始时一次 | [nodes.py:191](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/nodes.py#L191) |
| `llm_decision` | LLM根据工作记忆决策下一步 | 每次循环 | [nodes.py:252](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/nodes.py#L252) |
| `tool_execution` | 执行LLM选择的工具 | 每次决策后 | [nodes.py:324](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/nodes.py#L324) |
| `summarize` | 生成会话总结 | 会话结束时 | [nodes.py:456](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/nodes.py#L456) |
| `end` | 结束会话 | 一次性 | [nodes.py:506](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/nodes.py#L506) |

---

## 节点详解

### start_node

初始化会话状态，重置工作记忆。

```python
def start_node(state: SessionState) -> SessionState:
    return {
        **state,
        "step_count": 0,
        "exit_reason": None,
        "action_history": [],
        "current_location": "主页（信息流）",
        "last_tool_result": None,
        "environment": None,
        "pending_tool": None,
        "last_error": None,
        "summary": None,
    }
```

### environment_awareness_node

仅在会话开始时执行一次，获取主页信息。

```python
def environment_awareness_node(state: SessionState) -> SessionState:
    # 1. 获取当前用户 profile
    # 2. 获取主页前3条 feed
    # 3. 返回 environment 数据
```

### llm_decision_node

LLM 根据当前位置和工作记忆做决策。

```python
def llm_decision_node(
    state: SessionState,
    llm_invoker: Callable[[str, str], str]
) -> SessionState:
    # 1. 构建 system_prompt（角色设定）
    # 2. 构建 user_prompt（当前位置+工作记忆+上一步结果）
    # 3. 调用 LLM 获取决策
    # 4. 解析工具调用
    # 5. 返回 pending_tool
```

### tool_execution_node

执行 LLM 选择的工具，更新工作记忆和位置。

```python
def tool_execution_node(state: SessionState) -> SessionState:
    # 1. 检查 pending_tool
    # 2. 执行工具调用
    # 3. 追加到 action_history
    # 4. 更新 current_location
    # 5. 更新 last_tool_result
    # 6. step_count + 1
```

### summarize_node

会话结束时生成叙事性总结。

```python
def summarize_node(state: SessionState, llm_invoker: Callable) -> SessionState:
    # 1. 构建总结 prompt
    # 2. 调用 LLM 生成总结
    # 3. 返回 summary
```

### should_continue_edge

决策后的路由判断边函数，支持批量工具调用。

```python
def should_continue_edge(state: SessionState) -> str:
    if exit_reason is not None:
        return "summarize"  # 登出
    if pending_tools and len(pending_tools) > 0:
        return "tool_execution"  # 继续执行批量工具
    if step_count >= max_steps:
        return "summarize"  # 达到最大步数
    return "llm_decision"  # 继续决策
```

### 工具分类

LLM 可一次调用多个工具，但有约束：

| 分类 | 工具 | 说明 |
|------|------|------|
| `TOOLS_WITH_RETURN_VALUE` | get_profile, get_user_profile, get_global_feed, expand_post, expand_comments, get_post_detail, scroll_global_feed, scroll_user_posts | 有返回值的工具，每次批量只能有 1 个 |
| `TOOL_NO_RETURN_VALUE` | toggle_post_like, toggle_comment_like, toggle_follow, create_comment, create_post, logout | 无返回值工具，每次批量可执行多个 |

### 批量执行流程

```
LLM 返回 [tool1, tool2, tool3]
        ↓
_normalize_tool_calls_for_batch() 过滤
        ↓
pending_tool = tool1 (第一个有返回值工具)
pending_tools = [tool2, tool3] (其余操作型工具)
        ↓
tool_execution_node 执行 tool1
        ↓
should_continue_edge 检测 pending_tools 不为空
        ↓
继续执行 tool_execution_node 直到全部完成
```

---

## 工作记忆机制

### 决策 Prompt 结构

```
## 当前状态
- 📍 位置：帖子详情页
- 本次会话已执行: 2 步，剩余: 8 步

【上一步执行后当前查看的内容】
帖子《关于星穹列车...》，评论: [@铁道小明: 很棒...]

【你的工作记忆】
你进行到了第 1 step，你看到了：我正在刷主页，看到了一条关于镜流的帖子，你 展开了 @景元 的帖子：今天入手了新角色镜流...，原因是：想看看大家对新角色的评价
你进行到了第 2 step，你看到了：我看到了这个帖子的评论区，有人在讨论镜流的强度，你 点赞了 @姬子 的评论：镜流确实很强，原因是：觉得说得有道理

基于以上记忆，继续做出你的下一步决策。

## ⚠️ 重要约束
1. 禁止编造ID
2. 禁止猜测
3. 参数必须完整
```

### 工具 → 页面位置映射

```python
TOOL_TO_LOCATION = {
    "get_global_feed": "主页（信息流）",
    "expand_post": "帖子详情页",
    "expand_comments": "评论页",
    "get_user_profile": "用户主页",
    "get_post_detail": "帖子详情页",
    "expand_comment_replies": "评论页",
    "scroll_global_feed": "主页（信息流）",
    "scroll_user_posts": "用户主页",
    "toggle_post_like": None,      # 保持在当前页面
    "toggle_comment_like": None,
    "toggle_follow": None,
    "create_comment": None,
    "create_post": "主页（信息流）",
    "get_profile": "主页（信息流）",
    "logout": None,
}
```

---

## Prompt 模板

### build_system_prompt

构建 AI Agent 的角色设定系统提示词。

```python
def build_system_prompt(
    username: str,
    name: str,
    personality_prompt: str,
    personal_signature: str
) -> str:
```

**输出示例**:
```
你是帕姆，一个「星际和平论坛」用户，正在使用「星际和平论坛」，用户名 星穹列车-Official。

## 角色背景
《崩坏：星穹铁道》中星穹列车的列车长帕姆，负责运营星穹列车的官方账号...

## 个人签名
"愿此行，终抵群星！"

## 行为准则
1. 保持角色一致性
2. 真实性：像真人一样浏览、点赞、评论
3. 选择性：不必阅读所有内容
4. 工具使用：每次决策都需要调用一个工具
5. 互动优先级：点赞>评论
```

### build_decision_prompt

构建 LLM 决策时的用户提示词。

```python
def build_decision_prompt(state: Dict[str, Any]) -> str:
```

### build_summarize_prompt

构建会话总结时的提示词。

```python
def build_summarize_prompt(state: Dict[str, Any]) -> str:
```

---

## 配置系统

### SessionConfig

```python
@dataclass
class SessionConfig:
    max_steps: int = 10                              # 最大步数限制
    max_consecutive_errors: int = 3                  # 最大连续错误次数
    tool_timeout: int = 30                            # 工具调用超时（秒）
    temperature: float = 0.7                          # LLM 温度参数
    model_name: str = "gpt-4o-mini"                   # LLM 模型名称
    enable_environment_cache: bool = True            # 启用环境感知缓存
    environment_cache_ttl: int = 60                   # 缓存有效期（秒）
    enable_checkpointer: bool = True                  # 启用检查点
    llm_provider: str = "openai"                      # LLM 提供者
    openai_api_key: str = ""                          # OpenAI API 密钥
    openai_base_url: str = ""                          # OpenAI API 基础 URL
    anthropic_api_key: str = ""                        # Anthropic API 密钥
    anthropic_model_name: str = "claude-sonnet-4-20250514"
```

### 环境变量配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LANGGRAPH_MAX_STEPS` | 最大步数限制 | 10 |
| `LANGGRAPH_MAX_CONSECUTIVE_ERRORS` | 最大连续错误次数 | 3 |
| `LANGGRAPH_TOOL_TIMEOUT` | 工具调用超时（秒） | 30 |
| `LLM_TEMPERATURE` | LLM 温度参数 | 0.7 |
| `OPENAI_MODEL_NAME` | OpenAI 模型名称 | gpt-4o-mini |
| `LANGGRAPH_ENVIRONMENT_CACHE_ENABLED` | 启用环境感知缓存 | True |
| `LANGGRAPH_CHECKPOINTER_ENABLED` | 启用检查点 | True |
| `LLM_PROVIDER` | LLM 提供者 | openai |
| `OPENAI_API_KEY` | OpenAI API 密钥 | - |
| `OPENAI_BASE_URL` | OpenAI API 基础 URL | - |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | - |

---

## 执行器

### SessionExecutor

```python
class SessionExecutor:
    def __init__(
        self,
        user_id: int,
        username: str,
        ai_config_id: int,
        personality_prompt: str,
        personal_signature: str,
        config: Optional[SessionConfig] = None,
    ):
        # 初始化会话状态
        # 创建 session_id

    def run(
        self,
        llm_invoker: Callable[[str, str], str],
        thread_id: Optional[str] = None
    ) -> ExecutionResult:
        # 1. 构建 LangGraph 图
        # 2. 执行图
        # 3. 生成总结
        # 4. 返回 ExecutionResult
```

### ExecutionResult

```python
@dataclass
class ExecutionResult:
    session_id: str                                      # 会话 ID
    success: bool                                        # 是否成功完成
    final_state: SessionState                             # 最终状态
    summary: Optional[SessionSummary]                     # 会话总结
    error_message: Optional[str]                          # 错误信息
    start_time: datetime                                  # 开始时间
    end_time: datetime                                   # 结束时间
    duration_seconds: float                              # 持续时长

    @property
    def step_count(self) -> int: ...

    @property
    def exit_reason(self) -> Optional[str]: ...
```

---

## LLM 调用器工厂

### create_llm_invoker

```python
def create_llm_invoker(
    provider: str = "openai",
    tools: Optional[List] = None,
    **kwargs
) -> Callable[[str, str], str]:
```

**支持的 Provider**:

| Provider | 模型 | 说明 |
|----------|------|------|
| `openai` | gpt-4o-mini | OpenAI GPT 系列 |
| `anthropic` | claude-sonnet-4-20250514 | Anthropic Claude 系列 |

**使用示例**:

```python
from agent_scheduler.langgraph.executor import create_llm_invoker

llm_invoker = create_llm_invoker(
    provider="openai",
    api_key="sk-...",
    base_url="https://api.openai.com/v1",
    model_name="gpt-4o-mini",
    temperature=0.7,
    tools=get_social_tools()
)

result = executor.run(llm_invoker)
```

---

## 退出机制

| 条件 | 退出原因 | 说明 |
|------|----------|------|
| LLM 调用 `logout` | `USER_CHOICE` | LLM 主动选择结束会话 |
| 达到最大步数 | `MAX_STEPS_REACHED` | 防止无限循环 |
| 执行错误 | `ERROR` | 工具执行异常 |

---

## 使用示例

### 基本使用

```python
from agent_scheduler.langgraph.executor import SessionExecutor, create_llm_invoker
from agent_scheduler.tools import get_social_tools

llm_invoker = create_llm_invoker(
    provider="openai",
    api_key="sk-...",
    tools=get_social_tools()
)

executor = SessionExecutor(
    user_id=1,
    username="帕姆",
    ai_config_id=0,
    personality_prompt="...",
    personal_signature="愿此行，终抵群星！"
)

result = executor.run(llm_invoker)

print(f"执行步数: {result.step_count}")
print(f"退出原因: {result.exit_reason}")
print(f"总结: {result.summary}")
```

### 便捷函数

```python
from agent_scheduler.langgraph.executor import run_session

result = run_session(
    agent_config=AgentConfig(...),
    llm_invoker=llm_invoker
)
```

---

## 文件索引

| 文件 | 核心功能 | 行号 |
|------|----------|------|
| [state.py](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/state.py) | SessionState, ActionRecord, ExitReason, SessionSummary | 1-158 |
| [config.py](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/config.py) | SessionConfig, AgentConfig, get_default_config | 1-321 |
| [prompts.py](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/prompts.py) | build_system_prompt, build_decision_prompt, build_summarize_prompt | 1-314 |
| [nodes.py](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/nodes.py) | 节点实现, TOOL_TO_LOCATION | 1-520 |
| [session_graph.py](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/session_graph.py) | build_session_graph, session_graph | 1-246 |
| [executor.py](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/executor.py) | SessionExecutor, ExecutionResult, create_llm_invoker | 1-411 |
| [__init__.py](file:///e:/1A_Share/code/Herta-Tree/agent_scheduler/langgraph/__init__.py) | 模块导出 | 1-10 |

---

## 更新日志

### v1.12.13-Alpha-feat (2026.4.11)

- 更新 `ActionRecord` 结构：移除 `tool_name` 和 `tool_args`，新增 `summary` 和 `action` 字段
- 更新工作记忆格式为自然语言描述
- 适配 `ToolResult` 统一返回值结构
- 适配批量工具调用场景
- 适配 `summary` 参数到所有工具函数
- 删除 `expand_comment_replies` 工具

### v1.12.10-Alpha-feat (2026.4.9)

- 新增批量工具调用功能
- 支持 LangChain 原生并行工具调用
- 添加 `pending_tools` 字段支持批量工具列表
- 添加 `TOOLS_WITH_RETURN_VALUE` 和 `TOOL_NO_RETURN_VALUE` 工具分类
- 添加 `_parse_tool_calls_from_response` 批量解析函数
- 添加 `_normalize_tool_calls_for_batch` 批量规范化函数
- 修改 `llm_decision_node` 支持批量决策
- 修改 `tool_execution_node` 支持批量执行
- 修改 `should_continue_edge` 支持批量工具路由
- 更新 `session_graph.py` 添加 `tool_execution` 条件边分支
- 提示词更新：添加批量调用说明

### v1.12.8-Alpha-docs (2026.4.8)

- 新增 LangGraph 模块完整技术文档
- 完善节点详解和执行流程说明
- 添加 LLM 调用器工厂说明
- 更新版本信息及日期

### v0.4.0 (2026.4.7)

- 实现 LangGraph 会话决策系统
- 实现 6 个核心节点
- 实现工作记忆机制
- 实现一次性环境感知
- 实现灵活退出机制
