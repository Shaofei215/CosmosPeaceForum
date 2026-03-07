# LangGraph 超简单讲解

## 📚 核心概念（就这 4 个！）

### 1️⃣ State（状态）- 数据容器

```python
from typing import TypedDict

class AgentState(TypedDict):
    input_text: str      # 输入
    result: str         # 结果
    step_count: int     # 步骤计数
```

**类比理解**：
- State 就是一个**带标签的背包**
- 数据在节点之间传递时，就放在这个背包里
- 每个节点可以往背包里放东西，也可以从背包里拿东西

**对应项目**：
```python
class AISessionState(TypedDict):
    user_config: dict       # 用户配置
    notifications: list     # 通知消息
    posts: list            # 帖子列表
    thoughts: list         # 思考结果
    decisions: dict        # 决策结果
    actions: list          # 执行的行动
```

---

### 2️⃣ Node（节点）- 处理函数

```python
def process_node(state: AgentState):
    # 从背包里拿数据
    input_text = state['input_text']
    
    # 处理逻辑
    result = input_text.upper()
    
    # 往背包里放数据
    return {"result": result, "step_count": 1}
```

**关键点**：
- Node 就是**普通函数**
- 输入：`state`（整个背包）
- 输出：`dict`（要更新的部分）
- **只返回变化的部分**，其他自动保留

**对应项目**：
```python
def think_node(state: AISessionState):
    # 从背包拿帖子
    posts = state['posts']
    
    # LLM 思考
    thoughts = llm_think(posts)
    
    # 往背包放思考结果
    return {"thoughts": thoughts}
```

---

### 3️⃣ Edge（边）- 流程箭头

```python
workflow.add_edge("node1", "node2")
```

**含义**：
- `node1` 执行完 → 执行 `node2`
- 就像流程图里的箭头

**对应项目**：
```python
workflow.add_edge("think", "decide")
# 思考完 → 决策
```

---

### 4️⃣ Graph（图）- 组合起来

```python
from langgraph.graph import StateGraph, END

# 1. 创建图
workflow = StateGraph(AgentState)

# 2. 添加节点
workflow.add_node("node1", process_node)
workflow.add_node("node2", analyze_node)

# 3. 连接边
workflow.add_edge("node1", "node2")
workflow.add_edge("node2", END)  # END 表示结束

# 4. 编译
app = workflow.compile()

# 5. 运行
result = app.invoke({"input_text": "hello"})
```

**执行流程**：
```
输入 → node1 → node2 → END
         ↓       ↓
      处理    分析
```

---

## 🎯 完整示例对比

### 自编版本（当前实现）

```python
class AIBehaviorEngine:
    def execute_login_session(self, user_config):
        # 步骤 1：浏览通知
        notifications = self._browse_notifications(user_config)
        
        # 步骤 2：浏览时间线
        posts = self._browse(user_config)
        
        # 步骤 3：思考
        thoughts = self._think(posts, user_config)
        
        # 步骤 4：决策
        decisions = self._decide(thoughts, user_config)
        
        # 步骤 5：执行
        actions = self._act(decisions, user_config)
        
        return actions
```

**问题**：
- ❌ 状态手动传递（容易出错）
- ❌ 流程硬编码（难以修改）
- ❌ 错误处理分散
- ❌ 难以可视化

---

### LangGraph 版本

```python
# 1. 定义状态
class AISessionState(TypedDict):
    user_config: dict
    notifications: list
    posts: list
    thoughts: list
    decisions: dict
    actions: list

# 2. 定义节点
def browse_notifications_node(state):
    notifications = fetch_notifications(state['user_config'])
    return {"notifications": notifications}

def browse_timeline_node(state):
    posts = fetch_posts(state['user_config'])
    return {"posts": posts}

def think_node(state):
    thoughts = llm_think(state['posts'])
    return {"thoughts": thoughts}

def decide_node(state):
    decisions = llm_decide(state['thoughts'])
    return {"decisions": decisions}

def execute_node(state):
    actions = execute_actions(state['decisions'])
    return {"actions": actions}

# 3. 构建图
workflow = StateGraph(AISessionState)
workflow.add_node("browse_notifications", browse_notifications_node)
workflow.add_node("browse_timeline", browse_timeline_node)
workflow.add_node("think", think_node)
workflow.add_node("decide", decide_node)
workflow.add_node("execute", execute_node)

# 4. 连接
workflow.set_entry_point("browse_notifications")
workflow.add_edge("browse_notifications", "browse_timeline")
workflow.add_edge("browse_timeline", "think")
workflow.add_edge("think", "decide")
workflow.add_edge("decide", "execute")
workflow.add_edge("execute", END)

# 5. 编译和运行
app = workflow.compile()
result = app.invoke({"user_config": user_config})
```

**优势**：
- ✅ 状态自动传递
- ✅ 流程清晰可见
- ✅ 易于修改（改边就行）
- ✅ 可以可视化

---

## 🔀 条件分支（重要！）

### 场景：根据是否有通知决定流程

```python
def check_notifications(state):
    if state['notifications']:
        return "process_notifications"
    else:
        return "browse_timeline"

workflow.add_conditional_edges(
    "check_notifications",  # 从哪个节点出来
    check_notifications,     # 条件函数
    {
        "process_notifications": "process_notifications_node",
        "browse_timeline": "browse_timeline_node"
    }
)
```

**流程图**：
```
                /→ process_notifications_node
check_notifications
                \→ browse_timeline_node
```

---

## 📊 对比总结

| 方面 | 自编实现 | LangGraph |
|------|---------|-----------|
| **状态传递** | 手动 `self.state = xxx` | 自动传递 |
| **流程控制** | `if/else` 嵌套 | 声明式边 |
| **可视化** | ❌ 无法可视化 | ✅ 自动生成 |
| **调试** | 打印日志 | 内置追踪 |
| **修改流程** | 改代码 | 改边配置 |
| **类型安全** | ❌ 容易出错 | ✅ TypedDict |

---

## 💡 项目迁移示例

### 当前代码（ai_behavior.py 第 64-167 行）

```python
def execute_login_session(self, user_config):
    # 处理通知
    notifications = self._browse_notifications(user_config)
    if notifications:
        actions = self._process_notifications(notifications)
        self._act_notifications(actions)
    
    # 浏览时间线
    posts = self._browse(user_config)
    if not posts:
        return {"success": False}
    
    # 思考
    thoughts = self._think(posts, user_config)
    
    # 决策
    decisions = self._decide(thoughts, user_config)
    
    # 执行
    results = self._act(decisions, user_config)
    
    return results
```

### LangGraph 版本

```python
# 状态
class AISessionState(TypedDict):
    user_config: dict
    notifications: list
    posts: list
    thoughts: list
    decisions: dict
    actions: list
    success: bool

# 节点
def check_notifications_node(state):
    notifications = fetch_notifications(state['user_config'])
    return {"notifications": notifications}

def should_process(state):
    return "process" if state['notifications'] else "skip"

def browse_node(state):
    posts = fetch_posts(state['user_config'])
    if not posts:
        return {"success": False}
    return {"posts": posts, "success": True}

def think_node(state):
    thoughts = llm_think(state['posts'])
    return {"thoughts": thoughts}

def decide_node(state):
    decisions = llm_decide(state['thoughts'])
    return {"decisions": decisions}

def execute_node(state):
    actions = execute_actions(state['decisions'])
    return {"actions": actions}

# 图
workflow = StateGraph(AISessionState)
workflow.add_node("check", check_notifications_node)
workflow.add_node("process", process_notifications_node)
workflow.add_node("browse", browse_node)
workflow.add_node("think", think_node)
workflow.add_node("decide", decide_node)
workflow.add_node("execute", execute_node)

workflow.set_entry_point("check")
workflow.add_conditional_edges("check", should_process, {
    "process": "process",
    "skip": "browse"
})
workflow.add_edge("process", "browse")
workflow.add_edge("browse", "think")
workflow.add_edge("think", "decide")
workflow.add_edge("decide", "execute")
workflow.add_edge("execute", END)

app = workflow.compile()
```

---

## 🎓 学习要点总结

### 必须掌握的（5 个）

1. **State = TypedDict** - 数据容器
2. **Node = Function** - 处理函数
3. **Edge = add_edge()** - 连接箭头
4. **Conditional Edge = add_conditional_edges()** - 条件分支
5. **运行 = app.invoke(input)** - 执行图

### 不需要一开始就学的

- ❌ 复杂的检查点配置
- ❌ 子图（SubGraph）
- ❌ 多 Agent 协作
- ❌ 自定义检查点

---

## 🚀 下一步

理解了基础后，我们可以：

1. **创建实际项目文件** - `behavior_engine/langgraph_engine.py`
2. **逐个节点迁移** - 从 `_browse` 开始
3. **测试对比** - 确保功能一致
4. **添加高级功能** - 检查点、可视化等

---

## ❓ 常见问题

**Q: State 里的 list 怎么处理？**
```python
# LangGraph 会合并（append），不是覆盖
return {"notifications": ["notif1", "notif2"]}
# 下次又返回
return {"notifications": ["notif3"]}
# 最终：["notif1", "notif2", "notif3"]
```

**Q: 如何覆盖而不是追加？**
```python
# 在 State 定义时指定
from typing import Annotated
from langgraph.graph import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]  # 追加
    result: str  # 覆盖（默认）
```

**Q: 如何调试？**
```python
# 打印每个节点的输入输出
def debug_node(state):
    print(f"输入：{state}")
    result = process(state)
    print(f"输出：{result}")
    return result
```

---

**就这么简单！核心就 4 个概念，掌握了就可以开始写了！**
