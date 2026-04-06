# 线程上下文技术文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.12.1-Alpha-feat |
| 更新日期 | 2026.4.6 |

---

## 功能概述

### 核心特性

| 特性 | 说明 |
|------|------|
| 线程安全 | 使用 `threading.local()` 确保每个线程有独立的上下文实例 |
| 自动管理 | 登录时自动设置上下文，退出时自动清理 |
| Token 复用 | 工具函数自动从上下文获取 Token，无需重复传递 |
| 单一实例 | 每个线程同时只有一个 AgentContext 实例 |

---

## 技术实现

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        主线程                                │
│  AgentSchedulerManager                                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     调度线程 1                               │
│  AIUserScheduler                                           │
│  ├── login_user() → 获取 Token                             │
│  ├── set_current_context(AgentContext)                     │
│  │                      │                                  │
│  │                      ▼                                  │
│  │              ┌──────────────┐                         │
│  │              │ _thread_local │ ← 线程局部存储          │
│  │              │   .context   │                          │
│  │              └──────────────┘                         │
│  │                      │                                  │
│  │                      ▼                                  │
│  │              ┌──────────────┐                         │
│  │              │ 工具函数调用  │                          │
│  │              │ get_token()  │ → 自动获取               │
│  │              └──────────────┘                         │
│  │                      │                                  │
│  └── clear_current_context()                               │
└─────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     调度线程 2                               │
│  AIUserScheduler (另一个用户)                               │
│  └── 同上流程...                                           │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件

```
context.py
├── AgentContext          # Agent 执行上下文数据类
├── _thread_local        # threading.local() 实例
└── 便捷函数              # get/set/clear_current_*()
```

---

## API 接口一览

### AgentContext 类

Agent 执行上下文数据类，用于存储当前 Agent 的认证信息和配置。

#### 构造函数参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | int | 否 | 当前 Agent 的用户 ID |
| `username` | str | 否 | 当前 Agent 的用户名 |
| `ai_config_id` | int | 否 | 当前 Agent 的配置 ID |
| `token` | str | 否 | 当前 Agent 的访问令牌（JWT Token） |
| `user_config` | Dict | 否 | 当前 Agent 的配置信息字典 |

#### 类属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `user_id` | int | 当前 Agent 的用户 ID |
| `username` | str | 当前 Agent 的用户名 |
| `ai_config_id` | int | 当前 Agent 的配置 ID |
| `token` | str | 当前 Agent 的访问令牌（JWT Token） |
| `user_config` | Dict | 当前 Agent 的配置信息字典 |

---

### 便捷函数

#### get_current_context()

获取当前线程的 Agent 上下文。

**返回**: `Optional[AgentContext]` - 当前线程的上下文对象，如果未设置则返回 `None`

---

#### set_current_context(context)

设置当前线程的 Agent 上下文。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `context` | AgentContext | 是 | Agent 上下文对象 |

---

#### clear_current_context()

清除当前线程的 Agent 上下文。

在 Agent 完成执行或调度器停止时调用，清理线程本地存储。

---

#### get_current_token()

获取当前线程的访问令牌。

**返回**: `Optional[str]` - 当前线程的 JWT Token，如果未设置则返回 `None`

---

#### get_current_user_id()

获取当前线程的用户 ID。

**返回**: `Optional[int]` - 当前 Agent 的用户 ID，如果未设置则返回 `None`

---

#### get_current_username()

获取当前线程的用户名。

**返回**: `Optional[str]` - 当前 Agent 的用户名，如果未设置则返回 `None`

---

#### get_current_ai_config_id()

获取当前线程的 AI 配置 ID。

**返回**: `Optional[int]` - 当前 Agent 的配置 ID，如果未设置则返回 `None`

---

## 使用示例

### 基本使用

```python
from agent_scheduler.context import (
    AgentContext,
    set_current_context,
    clear_current_context,
    get_current_token,
    get_current_user_id,
)

# 设置上下文
context = AgentContext(
    user_id=123,
    username="test_user",
    ai_config_id=1,
    token="jwt_token_here",
    user_config={"name": "测试用户"}
)
set_current_context(context)

# 获取上下文信息
print(get_current_user_id())  # 123
print(get_current_token())    # jwt_token_here

# 清理上下文
clear_current_context()
```

### 在调度器中使用

```python
from agent_scheduler.context import (
    AgentContext,
    set_current_context,
    clear_current_context,
)
from agent_scheduler.scheduler import login_user

def scheduling_loop():
    # 登录获取 Token
    login_success, token, _ = login_user(username, password)

    if login_success and token:
        # 设置上下文
        set_current_context(AgentContext(
            user_id=user_id,
            username=username,
            ai_config_id=config_id,
            token=token,
            user_config={}
        ))

        # 执行工具调用（自动使用上下文中的 token）
        trigger_login_event(username, time_system)

        # 清理上下文
        clear_current_context()
```

### 在工具函数中使用

```python
from agent_scheduler.context import get_current_token

def _make_request(endpoint, token=None):
    # 如果未提供 token，自动从上下文获取
    if token is None:
        token = get_current_token()

    if not token:
        raise UnauthorizedError("未找到有效的认证令牌")

    # 发送请求...
    return requests.get(endpoint, headers={"Authorization": f"Bearer {token}"})
```

---

## 线程安全说明

### 实现原理

使用 Python 标准库的 `threading.local()` 实现线程局部存储：

```python
import threading

_thread_local = threading.local()

def set_current_context(context):
    _thread_local.context = context

def get_current_context():
    return getattr(_thread_local, 'context', None)
```

### 线程隔离

每个线程都有独立的 `_thread_local.context` 属性，线程之间互不干扰：

```
线程 1: _thread_local.context = AgentContext(user_id=1, ...)
线程 2: _thread_local.context = AgentContext(user_id=2, ...)
线程 3: _thread_local.context = None
```

### 注意事项

1. **上下文必须显式设置**: 工具函数不会自动创建上下文，需要调度器显式调用 `set_current_context()`
2. **及时清理**: 调度完成后应调用 `clear_current_context()` 避免内存泄漏
3. **线程局部存储限制**: 上下文只在同一线程内有效，跨线程访问无效

---

## 与 tools.py 的集成

### 自动 Token 获取

tools.py 中的工具函数通过 `get_current_token()` 自动从上下文获取认证信息：

```
工具函数调用
    │
    ▼
_make_request()
    │
    ├── token = get_current_token()  ← 自动获取
    │
    ▼
    ├─ Token 存在 → 正常请求
    └─ Token 不存在 → 抛出 UnauthorizedError
```

### 上下文设置时机

在 `scheduler.py` 的调度循环中：

```python
def _scheduling_loop(self):
    while self.running:
        # 登录
        login_success, token, _ = login_user(username, password)

        if login_success and token:
            # 设置上下文
            set_current_context(AgentContext(
                user_id=self._registered_user_id,
                username=username,
                ai_config_id=self.user_config.id,
                token=token,
                user_config={...}
            ))

            # 触发登录事件（工具调用）
            trigger_login_event(username, self.time_system)

            # 清理上下文
            clear_current_context()
```

---

## 更新日志

### v1.12.1-Alpha-feat (2026.4.6)

- 新增线程上下文模块 `context.py`
- 实现 `AgentContext` 数据类
- 实现 `threading.local()` 线程局部存储
- 提供 7 个便捷函数
- 被 `tools.py` 集成，实现自动 Token 获取
- 被 `scheduler.py` 集成，实现登录上下文管理
