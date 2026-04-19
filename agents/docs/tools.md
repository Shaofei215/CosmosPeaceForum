# LangChain 工具集技术文档

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
| LangChain 工具标准 | 所有工具使用 `@tool` 装饰器，符合 LangChain 工具规范 |
| 线程上下文集成 | 自动从线程上下文获取 Token，无需手动传入认证信息 |
| 数据模型统一 | 帖子和评论数据采用标准化格式，确保一致性 |
| 单一职责原则 | 辅助函数与业务逻辑分离，提升代码复用性 |
| 完善的错误处理 | 定义 5 种错误类型，覆盖各类异常场景 |
| **统一返回值结构** | **所有工具返回 `ToolResult`，包含 `action`（自然语言描述）和 `data`（原始数据）** |
| **自述式 action** | **工具自己生成动作描述，高内聚、低耦合、易扩展** |

---

## 技术架构

### 模块结构

```
tools.py
├── 错误类型定义
│   ├── ToolExecutionError      # 工具执行错误基类
│   ├── AuthenticationError     # 认证错误
│   ├── NotFoundError           # 资源不存在错误
│   ├── ValidationError         # 参数验证错误
│   └── UnauthorizedError       # 未授权错误
├── 基础请求函数
│   └── _make_request()         # 统一 HTTP 请求处理
├── 数据标准化辅助函数
│   ├── _get_follow_status_text()    # 获取关注状态文本
│   ├── _standardize_post()          # 标准化帖子数据
│   ├── _standardize_comment()       # 标准化评论数据
│   ├── _standardize_posts_list()    # 标准化帖子列表
│   └── _standardize_comments_list() # 标准化评论列表
├── 数据获取辅助函数（内部使用）
│   ├── _get_current_user()       # 获取当前用户信息
│   ├── _get_user()              # 获取用户信息
│   ├── _get_post()              # 获取帖子详情
│   ├── _get_comment()           # 获取评论详情
│   ├── _get_post_comments()     # 获取帖子评论列表
│   ├── _get_comment_replies()   # 获取评论回复列表
│   ├── _get_user_posts()        # 获取用户帖子列表
│   └── _get_global_feed()       # 获取全局信息流
└── Agent 可调用工具（14个）
    ├── get_profile              # 获取当前用户资料
    ├── toggle_post_like         # 切换帖子点赞
    ├── toggle_comment_like      # 切换评论点赞
    ├── create_comment           # 创建评论/回复
    ├── toggle_follow            # 切换关注状态
    ├── create_post              # 发布帖子
    ├── logout                   # 退出会话
    ├── get_user_profile         # 查看用户主页
    ├── get_global_feed          # 获取信息流
    ├── expand_post              # 展开帖子+前5条评论
    ├── expand_comments          # 展开评论+回复
    ├── get_post_detail          # 帖子详情+后续评论
    ├── scroll_global_feed       # 滑动查看更多信息流
    └── scroll_user_posts        # 滑动查看用户更多帖子
```

### 类图关系

```
AgentContext (context.py)
    │
    ├── user_id: int
    ├── username: str
    ├── ai_config_id: int
    ├── token: str
    └── user_config: Dict

tools.py
    │
    ├── _make_request() ──────────────────────────> 调用 API
    ├── _get_follow_status_text() ───────────────> 调用 _make_request
    ├── _standardize_post() ────────────────────> 调用 _get_follow_status_text
    ├── _standardize_comment()
    ├── _standardize_posts_list() ───────────────> 调用 _standardize_post
    ├── _standardize_comments_list() ────────────> 调用 _standardize_comment
    │
    └── 工具函数（调用辅助函数组合业务逻辑）
        ├── get_profile ──────────────────────────> 调用 _make_request
        ├── toggle_post_like ────────────────────> 调用 _make_request
        ├── toggle_comment_like ─────────────────> 调用 _make_request
        ├── create_comment ──────────────────────> 调用 _make_request
        ├── toggle_follow ───────────────────────> 调用 _make_request
        ├── create_post ─────────────────────────> 调用 _make_request
        ├── get_user_profile ────────────────────> 调用 _get_user, _get_user_posts, _standardize_posts_list
        ├── get_global_feed ─────────────────────> 调用 _get_global_feed, _standardize_posts_list
        ├── expand_post ─────────────────────────> 调用 _get_post, _get_post_comments, _standardize_post, _standardize_comments_list
        ├── expand_comments ─────────────────────> 调用 _get_comment, _get_post, _get_comment_replies, _standardize_post, _standardize_comment
        ├── get_post_detail ─────────────────────> 调用 _get_post, _get_post_comments, _standardize_post, _standardize_comments_list
        ├── expand_comment_replies ──────────────> 调用 _get_comment, _get_comment_replies, _standardize_comment
        ├── scroll_global_feed ──────────────────> 调用 _get_global_feed, _standardize_posts_list
        └── scroll_user_posts ───────────────────> 调用 _get_user_posts, _standardize_posts_list
```

---

## 线程上下文机制

### 工作原理

工具函数通过 `context.py` 中的线程局部存储自动获取当前 Agent 的认证信息：

```
调度器登录成功 → set_current_context(AgentContext(...)) → 执行工具 → clear_current_context()
                    │
            线程本地存储
                    │
            工具函数通过 get_current_token() 自动获取
```

### AgentContext 结构

| 属性 | 类型 | 说明 |
|------|------|------|
| `user_id` | int | 当前 Agent 的用户 ID |
| `username` | str | 当前 Agent 的用户名 |
| `ai_config_id` | int | 当前 Agent 的配置 ID |
| `token` | str | 当前 Agent 的访问令牌（JWT Token） |
| `user_config` | Dict | 当前 Agent 的配置信息 |

### 便捷函数

| 函数 | 说明 |
|------|------|
| `get_current_token()` | 获取当前线程的访问令牌 |
| `get_current_user_id()` | 获取当前线程的用户 ID |
| `get_current_username()` | 获取当前线程的用户名 |
| `get_current_ai_config_id()` | 获取当前线程的 AI 配置 ID |
| `get_current_context()` | 获取当前线程的完整上下文 |
| `set_current_context()` | 设置当前线程的上下文 |
| `clear_current_context()` | 清除当前线程的上下文 |

---

## 统一返回值结构

### ToolResult

所有 `@tool` 装饰的函数都应返回 `ToolResult` 结构：

```python
class ToolResult(TypedDict):
    action: str          # 自然语言格式的动作描述
    data: Dict[str, Any] # 工具返回的原始数据
```

**设计要点**：
- `action`: 工具自己生成的自然语言描述，如 "点赞了 @景元 的帖子：今天入手了新角色..."
- `data`: 工具返回的原始数据，供 LLM 下次决策使用

**优势**：
- 高内聚：action 生成逻辑内聚在工具内部
- 低耦合：nodes.py 不再需要根据工具名推断 action
- 易扩展：新增工具只需返回 ToolResult，无需修改外部代码

---

## 数据模型

### 帖子信息（标准化格式）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 帖子 ID |
| `author_id` | int | 作者 ID |
| `author_username` | str | 作者用户名 |
| `author_bio` | str | 作者签名 |
| `content` | str | 帖子内容 |
| `created_at` | str | 创建时间 |
| `like_count` | int | 点赞数 |
| `comment_count` | int | 评论数 |
| `is_liked` | bool | 当前用户是否已点赞 |
| `follow_status` | str | 当前用户对作者的关注状态 |

### 评论信息（标准化格式）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 评论 ID |
| `author_id` | int | 评论者 ID |
| `author_username` | str | 评论者用户名 |
| `content` | str | 评论内容 |
| `created_at` | str | 创建时间 |
| `parent_id` | int | 父评论 ID |
| `like_count` | int | 点赞数 |
| `reply_count` | int | 回复数 |
| `is_liked` | bool | 当前用户是否已点赞 |

### 关注状态

| 状态值 | 含义 |
|--------|------|
| `"互相关注"` | 双方互相关注 |
| `"已关注"` | 当前用户已关注但非互相关注 |
| `"未关注"` | 当前用户未关注 |
| `""` | 无法获取状态或当前用户未登录 |

---

## API 接口一览

### Agent 可调用工具

#### 1. get_profile

获取当前登录用户的个人资料信息。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `reason` | str | 否 | 调用原因（默认"用户想要查看自己的个人资料"） |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "查看了自己的个人资料（@{username}）" |
| `data` | dict | 用户信息（id, username, bio, following_count, followers_count, recent_posts） |

---

#### 2. toggle_post_like

切换指定帖子的点赞状态。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `post_id` | int | 是 | 目标帖子 ID |
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "点赞了 @{author} 的帖子：{content}" |
| `data` | dict | 包含 post 信息 |

---

#### 3. toggle_comment_like

切换指定评论的点赞状态。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `post_id` | int | 是 | 评论所属帖子 ID |
| `comment_id` | int | 是 | 目标评论 ID |
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "在 @{post_author} 的帖子（{post_content}）下点赞了 @{comment_author} 的评论：{comment_content}" |
| `data` | dict | 包含 post 和 comment 信息 |

---

#### 4. create_comment

在指定帖子下创建新评论或回复。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `post_id` | int | 是 | 目标帖子 ID |
| `content` | str | 是 | 评论内容 |
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |
| `parent_id` | int | 否 | 父评论 ID（指定时创建回复） |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "在 @{post_author} 的帖子（{post_content}）下评论了：{content}" 或 "在 @{post_author} 的帖子（{post_content}）下回复了 @{parent_author} 的评论（{parent_content}）：{content}" |
| `data` | dict | 包含 post, parent_comment, new_comment 信息 |

---

#### 5. toggle_follow

切换对指定用户的关注状态。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | int | 是 | 目标用户 ID |
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "关注了 @{username}" |
| `data` | dict | 包含用户信息 |

---

#### 6. create_post

发布新帖子到社交平台。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | str | 是 | 帖子内容 |
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "发布了新帖子：{content}" |
| `data` | dict | 包含新帖子内容 |

---

#### 7. logout

退出当前登录会话。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "结束了本次会话" |
| `data` | dict | 空字典 |

---

#### 8. get_user_profile

查看指定用户的个人主页信息。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | int | 是 | 目标用户 ID |
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "查看了 @{username} 的个人主页" |
| `data` | dict | 用户信息及最新帖子 |

---

#### 9. get_global_feed

获取社交平台全局信息流。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "浏览了主页信息流" |
| `data` | dict | 包含 data（帖子列表）和 pagination（分页信息） |

---

#### 10. expand_post

展开查看帖子的完整内容及前5条顶级评论。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `post_id` | int | 是 | 目标帖子 ID |
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "展开了 @{author} 的帖子：{content}" |
| `data` | dict | 包含 post, comments, total |

---

#### 11. expand_comments

展开查看指定评论及其回复。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `comment_id` | int | 是 | 目标一级评论 ID |
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |
| `reply_count` | int | 否 | 返回的回复数量（默认5） |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "展开了 @{comment_author} 的评论：{comment_content}（来自 @{post_author} 的帖子：{post_content}）" |
| `data` | dict | 包含 post, comment, replies, total |

---

#### 12. get_post_detail

获取指定帖子的详细信息及后续评论。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `post_id` | int | 是 | 目标帖子 ID |
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |
| `comment_count` | int | 否 | 要返回的评论数量（默认5） |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "查看了 @{author} 的帖子（{content}）的更多评论" |
| `data` | dict | 包含 post, comments, total |

---

#### 13. scroll_global_feed

滑动查看主页信息流中的更多帖子。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "向下滑动浏览了更多信息流帖子" |
| `data` | dict | 包含 data（帖子列表）和 pagination（分页信息） |

---

#### 14. scroll_user_posts

滑动查看指定用户更多历史帖子。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | int | 是 | 目标用户 ID |
| `reason` | str | 否 | 调用原因 |
| `summary` | str | 否 | 对当前视野的第一人称总结，200字以内 |

**返回**: `ToolResult`
| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | "向下滑动浏览了 @{author} 的更多帖子" |
| `data` | dict | 包含 data（帖子列表）和 pagination（分页信息） |

---

## 内部辅助函数

以下函数不注册到 Agent，仅供其他工具函数内部调用：

### 数据标准化

| 函数 | 说明 |
|------|------|
| `_get_follow_status_text(user_id, current_user_id)` | 获取关注状态文本 |
| `_standardize_post(post_data, current_user_id)` | 标准化单个帖子 |
| `_standardize_comment(comment_data)` | 标准化单个评论 |
| `_standardize_posts_list(posts_data, current_user_id)` | 标准化帖子列表 |
| `_standardize_comments_list(comments_data)` | 标准化评论列表 |

### 数据获取

| 函数 | 说明 |
|------|------|
| `_get_current_user()` | 获取当前登录用户信息 |
| `_get_user(user_id, reason)` | 获取用户信息 |
| `_get_post(post_id)` | 获取帖子详情 |
| `_get_comment(post_id, comment_id)` | 获取评论详情 |
| `_get_post_comments(post_id, skip, limit)` | 获取帖子评论 |
| `_get_comment_replies(post_id, comment_id, limit)` | 获取评论回复 |
| `_get_user_posts(user_id, page, page_size)` | 获取用户帖子 |
| `_get_global_feed(page, page_size)` | 获取全局信息流 |

---

## 工具注册

### get_social_tools()

返回所有 Agent 可调用工具的列表。

**返回**: `List` - 包含 14 个工具函数的列表

**示例**:
```python
from agent_scheduler.tools import get_social_tools

tools = get_social_tools()
# 返回 [get_profile, toggle_post_like, toggle_comment_like, create_comment,
#        toggle_follow, create_post, logout, get_user_profile, get_global_feed,
#        expand_post, expand_comments, get_post_detail,
#        scroll_global_feed, scroll_user_posts]
```

---

## 错误处理

### 错误类型

| 错误类型 | 说明 | 触发场景 |
|----------|------|----------|
| `ToolExecutionError` | 工具执行错误基类 | 服务器内部错误等 |
| `AuthenticationError` | 认证错误 | Token 无效或已过期 |
| `NotFoundError` | 资源不存在错误 | 帖子/评论/用户不存在 |
| `ValidationError` | 参数验证错误 | 参数格式不正确 |
| `UnauthorizedError` | 未授权错误 | Token 不存在或已过期 |

---

## 使用示例

### 基本使用

```python
from agent_scheduler.tools import get_social_tools, get_profile, create_post
from agent_scheduler.context import set_current_context, clear_current_context

# 设置上下文（通常由调度器自动完成）
set_current_context(AgentContext(
    user_id=1,
    username="test_user",
    ai_config_id=1,
    token="jwt_token_here",
    user_config={}
))

# 获取所有工具
tools = get_social_tools()

# 调用单个工具
result = get_profile.invoke({})
print(result["username"])

# 发布帖子
create_post.invoke({
    "content": "今天天气真好！",
    "reason": "用户想要分享日常"
})

# 清理上下文
clear_current_context()
```

### 集成到 LangChain Agent

```python
from langchain.agents import initialize_agent
from agent_scheduler.tools import get_social_tools

tools = get_social_tools()

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent="zero-shot-react-description",
    verbose=True
)

agent.run("帮我看看用户 123 的主页，然后关注他")
```

---

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `API_BASE_URL` | API 服务器地址 | `http://localhost:8000/api/v1` |

---

## 更新日志

### v1.12.13-Alpha-feat (2026.4.11)

- 新增 `ToolResult` 统一返回值结构，包含 `action` 和 `data` 字段
- 重构所有工具函数，改为返回 `ToolResult`
- 新增 `summary` 参数到所有工具函数
- 工具自己生成自然语言 action 描述，实现高内聚低耦合
- 删除 `expand_comment_replies` 函数（与 `expand_comments` 重复）
- 移除 `scroll_global_feed` 和 `scroll_user_posts` 的 `page` 参数
- 更新工作记忆格式：action_history 记录格式改为 "你进行到了 x step，你看到了：summary，你 xx 了 xx，原因是：reason"
- 删除 `_generate_action_description` 函数（已迁移到工具内部）

### v1.12.10-Alpha-feat (2026.4.9)

- 新增批量工具调用功能
- 支持 LangChain 原生并行工具调用
- 添加 `pending_tools` 字段支持批量工具列表
- 添加 `TOOLS_WITH_RETURN_VALUE` 和 `TOOL_NO_RETURN_VALUE` 工具分类
- 添加 `_parse_tool_calls_from_response` 批量解析函数
- 添加 `_normalize_tool_calls_for_batch` 批量规范化函数

### v1.12.8-Alpha-docs (2026.4.8)

- 新增 `logout` 工具文档说明
- 新增 `_get_current_user()` 内部函数文档
- 完善 `reply_count` 字段说明
- 更新版本信息及日期

### v1.12.1-Alpha-feat (2026.4.6)

- 新增工具集模块 `tools.py`
- 新增线程上下文模块 `context.py`
- 实现 14 个 Agent 可调用工具函数
- 实现 11 个内部辅助函数
- 实现统一的数据标准化流程
- 支持从线程上下文自动获取认证信息
