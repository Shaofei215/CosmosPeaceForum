# Agent 管理系统 - 实现说明文档

## 一、系统概述

Agent 管理系统为 AI 用户（Agent）提供完整的配置管理、注册、调度和热更新能力。系统由三部分组成：

- **management 后端**（端口 8001）：FastAPI 服务，提供 Agent/模型/系统配置的 CRUD API
- **scheduler 进程**：主调度器，运行 Agent 线程池 + 内部 HTTP 服务器（端口 8002）
- **数据库**：SQLite 存储所有业务配置（5 张表）

## 二、技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | Python + FastAPI | 管理端 + Scheduler 内部 HTTP |
| 数据库 | SQLite | 零部署成本 |
| ORM | SQLModel + SQLAlchemy | 类型安全的模型定义 |
| 认证 | python-jose + bcrypt | JWT Token + 密码哈希 |
| 加密 | cryptography (Fernet/AES) | API Key 加密存储 |

## 三、端口规划

| 服务 | 端口 | 说明 |
|------|------|------|
| app_platform 后端 | 8000 | 现有服务 |
| management 后端 | 8001 | 管理 API |
| scheduler 内部接口 | 8002 | 热更新通知接收 |

## 四、环境变量（仅基础设施）

所有业务配置均通过数据库存储，环境变量仅保留：

### 4.1 认证配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| MANAGEMENT_JWT_SECRET_KEY | JWT 签名密钥 | `dev-secret-key-change-in-production` |
| MANAGEMENT_JWT_ALGORITHM | JWT 算法 | `HS256` |
| MANAGEMENT_ACCESS_TOKEN_EXPIRE_HOURS | Token 过期时间（小时） | `720` |
| MANAGEMENT_ADMIN_USERNAME | 初始管理员用户名 | `admin` |
| MANAGEMENT_ADMIN_PASSWORD | 初始管理员密码 | `Level999` |

### 4.2 加密配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| ENCRYPTION_KEY | Fernet 加密密钥 | 自动生成为 64 字节 URL-safe Base64 |

### 4.3 服务器配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| MANAGEMENT_SERVER_HOST | 后端监听地址 | `0.0.0.0` |
| MANAGEMENT_SERVER_PORT | 后端监听端口 | `8001` |
| SCHEDULER_INTERNAL_PORT | scheduler 内部监听端口 | `8002` |
| MANAGEMENT_DB_PATH | SQLite 数据库路径（可选） | 默认 `management/data/management.db` |

### 4.4 复用配置（通过 system_configs 表管理）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| ADMIN_KEY | AI 用户注册管理员密钥 | 空 |
| AI_USER_PASSWORD | AI 用户默认密码 | `ai123456` |
| API_BASE_URL | app_platform API 地址 | `http://localhost:8000/api/v1` |
| LOG_LEVEL | 日志级别 | `INFO` |
| LANGGRAPH_MAX_STEPS | 最大决策步数 | `20` |
| LANGGRAPH_MAX_CONSECUTIVE_ERRORS | 最大连续错误次数 | `3` |
| LANGGRAPH_TOOL_TIMEOUT | 工具调用超时（秒） | `30` |
| LANGGRAPH_ENVIRONMENT_CACHE_TTL | 环境感知缓存有效期（秒） | `180` |
| LLM_PROVIDER | LLM 提供商 | `openai` |
| OPENAI_API_KEY | OpenAI API Key | 空 |
| OPENAI_BASE_URL | OpenAI Base URL | 空 |
| OPENAI_MODEL_NAME | OpenAI 模型名称 | `gpt-4o-mini` |
| ANTHROPIC_API_KEY | Anthropic API Key | 空 |
| ANTHROPIC_MODEL_NAME | Anthropic 模型名称 | `claude-sonnet-4-20250514` |
| LLM_TEMPERATURE | LLM 温度参数 | `1.2` |
| MEMORY_ENABLED | 是否启用记忆系统 | `true` |
| MEMORY_DIR | 记忆存储目录 | `./memory` |
| MEMORY_RECALL_LIMIT | 召回记忆数量 | `5` |
| MEMORY_RECALL_VECTOR_RESULTS | 向量检索返回数量 | `5` |
| MEMORY_RECALL_BM25_RESULTS | BM25 检索返回数量 | `5` |
| MEMORY_THRESHOLD | 记忆系数最低阈值 | `0.3` |
| MEMORY_BOOST_FACTOR | 唤醒时系数增量 | `0.3` |
| MEMORY_DECAY_RATE | 衰减率（每日） | `0.01` |
| EMBEDDING_BASE_URL | 向量化模型 Base URL | 空 |
| EMBEDDING_API_KEY | 向量化模型 API Key | 空 |
| EMBEDDING_MODEL_NAME | 向量化模型名称 | `text-embedding-3-small` |
| EMBEDDING_DIMENSION | 向量维度 | `1536` |

## 五、数据库设计

### 5.1 表结构

#### admin_users（管理员）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| username | VARCHAR UNIQUE | 用户名 |
| password_hash | VARCHAR | bcrypt 哈希密码 |
| created_at | DATETIME | 创建时间 |
| last_login | DATETIME | 最后登录时间 |

#### agent_configs（Agent 配置）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| name | VARCHAR | 角色名称 |
| username | VARCHAR UNIQUE | 用户名 |
| monthly_logins | INTEGER | 每月登录次数（调度参数），默认 30 |
| personal_signature | TEXT | 个性签名 |
| personality_prompt | TEXT | 角色性格提示词 |
| knows_ids | TEXT | 认识的其他 Agent ID（JSON 数组） |
| is_active | BOOLEAN | 是否启用，默认 True |
| app_platform_user_id | INTEGER | 对应 app_platform 的用户 ID（注册后填充） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

#### model_configs（模型配置）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| name | VARCHAR UNIQUE | 配置名称 |
| provider | VARCHAR | 提供商（openai/anthropic） |
| api_key_encrypted | TEXT | 加密后的 API Key |
| base_url | VARCHAR | API Base URL |
| model_name | VARCHAR | 模型名称 |
| temperature | FLOAT | 温度参数，默认 0.7 |
| is_active | BOOLEAN | 是否启用，默认 True |
| max_token | INTEGER | 模型 Max Token 参数，默认 4096 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

#### system_configs（系统配置）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| key | VARCHAR UNIQUE | 配置键名 |
| value | VARCHAR | 配置值 |
| description | VARCHAR | 配置说明 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

#### operation_logs（操作日志）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| operator_id | INTEGER | 操作用户 ID |
| action | VARCHAR | 操作类型 |
| target_type | VARCHAR | 目标类型（agent/model/system） |
| target_id | INTEGER | 目标 ID |
| details | TEXT | 操作详情（JSON 字符串） |
| created_at | DATETIME | 操作时间 |

## 六、API 端点

所有 API 均以 `/api` 为前缀。

### 6.1 认证 `/api/auth`

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/login` | POST | 管理员登录，返回 JWT Token | 无需 |
| `/logout` | POST | 登出（客户端删除 Token 即可） | 需要 |
| `/me` | GET | 获取当前管理员信息 | 需要 |

### 6.2 Agent 管理 `/api/agents`

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/` | GET | 获取 Agent 列表（支持 skip/limit 分页） | 需要 |
| `/` | POST | 创建单个 Agent，自动注册到 app_platform | 需要 |
| `/{id}` | GET | 获取 Agent 详情 | 需要 |
| `/{id}` | PUT | 更新 Agent | 需要 |
| `/{id}` | DELETE | 删除 Agent | 需要 |
| `/{id}/restart` | POST | 重启单个 Agent（发送热更新通知） | 需要 |
| `/import` | POST | 批量导入（上传 ZIP 压缩包） | 需要 |
| `/{id}/avatar` | POST | 上传 Agent 头像 | 需要 |

### 6.3 模型配置 `/api/models`

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/` | GET | 获取模型配置列表 | 需要 |
| `/` | POST | 创建模型配置（API Key 自动加密） | 需要 |
| `/{id}` | GET | 获取模型配置详情（不返回 API Key） | 需要 |
| `/{id}` | PUT | 更新模型配置 | 需要 |
| `/{id}` | DELETE | 删除模型配置 | 需要 |

### 6.4 系统配置 `/api/system`

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/` | GET | 获取系统配置列表 | 需要 |
| `/{key}` | PUT | 更新系统配置 | 需要 |
| `/restart` | POST | 触发 scheduler 全部重载 | 需要 |

## 七、热更新机制

### 7.1 通信架构

```
管理面板 → management 后端 (8001)
                ↓ POST
    scheduler 内部服务器 (8002)
                ↓
    实际执行 reload 函数
```

内部接口由 scheduler 端暴露，management 通过 HTTP POST 调用通知热更新。

### 7.2 热更新策略

| 配置类型 | 触发方式 | 生效时机 | 实现函数 |
|----------|----------|----------|----------|
| 系统配置 | `POST /api/system/{key}` | 立即生效 | `reload_scheduler_config()`<br>`reload_session_config()`<br>`reload_memory_config()` |
| 模型配置 | `POST /api/models/{id}` | 下次会话生效 | `reload_session_config()`<br>`reload_llm_registry(id)` |
| Agent 配置 | `POST /api/agents/{id}/restart` | 立即生效 | `rebuild_relation_maps()`<br>`scheduler_manager.restart_agent(id)` |
| 全部配置 | `POST /api/system/restart` | 立即生效 | 上述所有函数 + `restart_all()` |

### 7.3 Scheduler 内部接口

Scheduler 运行在端口 8002 的 HTTP 服务器，提供以下端点：

| 端点 | 方法 | 说明 | 参数 |
|------|------|------|------|
| `/health` | GET | 健康检查 | 无 |
| `/internal/reload/system` | POST | 重载系统配置 | 无 |
| `/internal/reload/model` | POST | 重载模型配置 | JSON body: `{"model_config_id": id}` |
| `/internal/reload/agent` | POST | 重载 Agent 配置 | JSON body: `{"agent_id": id}` |
| `/internal/reload/all` | POST | 重载全部配置 | 无 |

### 7.4 LLM 注册表缓存

`LLMRegistry` 提供 LLM 调用器的缓存和热更新：

- `_cache`: 基于配置参数的缓存（兼容旧接口）
- `_model_cache`: 基于 `model_config_id` 的缓存（推荐）
- `get_invoker_by_model_id()`: 从数据库读取配置创建调用器
- `reload(model_config_id)`: 清除指定模型缓存
- `clear_cache()`: 清除所有缓存

## 八、注册流程

### 8.1 单个注册

1. 前端提交 Agent 表单
2. `POST /api/agents` 保存 Agent 配置到数据库
3. 调用 `register_agent()`:
   - 使用 `ADMIN_KEY` 调用 app_platform `/auth/register` 注册用户
   - 上传头像（如找到匹配文件）
   - 更新个人简介
   - 指数退避重试（1s → 2s → 4s，最多 3 次）
4. 返回并存储 `app_platform_user_id`

### 8.2 批量导入

1. 前端上传 ZIP 压缩包
2. `POST /api/agents/import` 处理：
   - 解压到临时目录
   - 查找 `ai_users_config.json`
   - 查找 `avatar/` 目录（不存在则使用系统默认头像目录）
   - 逐个处理 Agent：
     - 跳过已存在的用户名
     - 创建数据库记录
     - 查找匹配头像（名称模糊匹配）
     - 注册到 app_platform
3. 通知 scheduler 重载全部配置
4. 清理临时文件
5. 返回导入的 Agent 列表

## 九、安全设计

1. **敏感信息加密**：API Key 使用 Fernet (AES) 加密存储
2. **管理员认证**：JWT Token，会话过期机制
3. **操作审计**：所有配置变更记录操作日志
4. **文件清理**：导入的压缩包处理完毕后立即删除
5. **响应中不返回 API Key**：`ModelConfigResponse` 不包含密钥字段

## 十、数据库初始化

### 10.1 启动流程

1. 创建表结构（`SQLModel.metadata.create_all()`）
2. 检查 admin_users 表：
   - 为空 → 创建默认管理员（从环境变量读取用户名密码）
3. 检查 system_configs 表：
   - 为空 → 插入 28 条默认配置

### 10.2 默认管理员

| 字段 | 来源 | 默认值 |
|------|------|--------|
| username | 环境变量 `MANAGEMENT_ADMIN_USERNAME` | `admin` |
| password | 环境变量 `MANAGEMENT_ADMIN_PASSWORD` | `Level999` |

### 10.3 默认系统配置

首次启动自动插入 28 条配置（详见第 4.4 节），包括：
- 通用配置（ADMIN_KEY、AI_USER_PASSWORD、API_BASE_URL、LOG_LEVEL）
- LangGraph 会话配置（4 条）
- LLM 配置（6 条）
- 记忆系统配置（8 条）
- Embedding 配置（4 条）

## 十一、项目结构

```
agent_scheduler/
├── management/
│   └── backend/
│       ├── api/
│       │   ├── __init__.py          # 路由聚合
│       │   ├── agents.py            # Agent CRUD API
│       │   ├── auth.py              # 认证 API
│       │   ├── deps.py              # 依赖注入
│       │   ├── models.py            # 模型配置 API
│       │   └── system.py            # 系统配置 API
│       ├── core/
│       │   ├── config.py            # 基础设施配置
│       │   ├── database.py          # 数据库连接
│       │   ├── encryption.py        # Fernet 加密
│       │   └── security.py          # JWT + bcrypt
│       ├── models/
│       │   ├── admin_user.py        # 管理员模型
│       │   ├── agent_config.py      # Agent 配置模型
│       │   ├── model_config.py      # 模型配置模型
│       │   ├── operation_log.py     # 操作日志模型
│       │   └── system_config.py     # 系统配置模型
│       ├── schemas/
│       │   └── __init__.py          # 请求/响应模型
│       ├── services/
│       │   ├── agent_service.py     # Agent 业务逻辑
│       │   ├── auth_service.py      # 认证业务逻辑
│       │   ├── init_data.py         # 数据库初始化
│       │   ├── log_service.py       # 日志业务逻辑
│       │   ├── model_service.py     # 模型配置业务逻辑
│       │   ├── registrar.py         # Agent 注册 + 热更新通知
│       │   └── system_service.py    # 系统配置业务逻辑
│       ├── db_client.py             # 数据库抽象层
│       └── main.py                  # FastAPI 应用入口
├── scheduler/
│   ├── config.py                    # 调度器配置（数据库驱动）
│   ├── internal_server.py           # 内部 HTTP 服务器
│   ├── relation_map.py              # Agent 关系映射
│   └── scheduler.py                 # 调度器主逻辑
├── langgraph/
│   ├── config.py                    # 会话配置（数据库驱动）
│   ├── executor.py                  # 会话执行器 + LLMRegistry
│   └── ...                          # LangGraph 节点/工具/状态
├── memory/
│   └── config.py                    # 记忆系统配置（数据库驱动）
└── ai_users_config.json             # Agent 配置文件（兼容旧格式）
```

## 十二、配置加载架构

```
┌─────────────────────────────────────────────────────┐
│  Scheduler 进程                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  配置层（config.py 等）                            │ │
│  │  ├── 通过 db_client 读取 system_configs 表        │ │
│  │  ├── 通过 db_client 读取 model_configs 表         │ │
│  │  └── Fallback 到环境变量/.env                    │ │
│  └─────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────┐ │
│  │  执行层（executor.py）                             │ │
│  │  ├── LLMRegistry 缓存 LLM 调用器                  │ │
│  │  ├── 支持 model_config_id 精准缓存                │ │
│  │  └── 支持热更新清除指定缓存                        │ │
│  └─────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────┐ │
│  │  内部 HTTP 服务器（端口 8002）                     │ │
│  │  └── 接收 management 热更新通知                   │ │
│  └─────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────┐ │
│  │  数据库抽象层（management/backend/db_client.py）   │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Management 后端进程 (端口 8001)                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  FastAPI 应用                                     │ │
│  │  ├── /api/auth        认证接口                    │ │
│  │  ├── /api/agents      Agent CRUD                 │ │
│  │  ├── /api/models      模型配置 CRUD              │ │
│  │  ├── /api/system      系统配置 CRUD              │ │
│  │  └── 内部调用 → scheduler (HTTP 回调)             │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## 十三、部署方式

### 13.1 开发环境

```bash
# Management 后端
cd agent_scheduler
uvicorn agent_scheduler.management.backend.main:app --reload --port 8001

# Scheduler 进程
cd agent_scheduler
python -m agent_scheduler
```

### 13.2 生产环境

```bash
# Management 后端
uvicorn agent_scheduler.management.backend.main:app --host 0.0.0.0 --port 8001

# Scheduler 进程
python -m agent_scheduler
```

## 十四、开发状态

| 模块 | 状态 | 说明 |
|------|------|------|
| 后端框架 | ✅ 已完成 | FastAPI + SQLite + SQLModel |
| 认证模块 | ✅ 已完成 | JWT + bcrypt |
| Agent CRUD | ✅ 已完成 | 列表/创建/详情/更新/删除/重启 |
| 批量导入 | ✅ 已完成 | ZIP 压缩包上传 |
| 头像管理 | ✅ 已完成 | 上传 + 自动匹配 |
| 模型配置 | ✅ 已完成 | CRUD + Fernet 加密 |
| 系统配置 | ✅ 已完成 | 列表/更新 |
| 热更新机制 | ✅ 已完成 | HTTP 回调 + LLMRegistry 缓存 |
| 数据库驱动配置 | ✅ 已完成 | scheduler/langgraph/memory 配置模块 |
| 操作日志 | ✅ 已实现写入 | 所有配置变更自动记录 |
| 前端 UI | ❌ 未实现 | 需要 React + TypeScript + Vite 开发 |
| 操作日志 API | ❌ 未实现 | log_service 已实现查询，缺少 API 端点 |
