# Agent 管理系统设计文档

## 一、项目背景与目标

### 现状问题

- **配置安全**：API Key 等敏感信息明文存储在 `.env` 文件中
- **配置管理**：Agent 配置（`ai_users_config.json`）无法动态管理，需手动编辑文件
- **架构耦合**：scheduler.py 集成了注册流程和调度流程，职责不清

### 建设目标

- 构建独立的 Agent 管理系统，包含前端和后端
- 实现配置的安全存储（加密）和动态管理（CRUD）
- 支持热更新配置，无需完整重启服务
- 与 `app_platform` 完全解耦

***

## 二、技术栈

| 层级       | 技术选型                          | 说明                             |
| -------- | ----------------------------- | ------------------------------ |
| **后端框架** | FastAPI                       | 复用 `agent_scheduler` 已有技术栈     |
| **前端框架** | React + TypeScript + Tailwind | 与 `app_platform/frontend` 保持一致 |
| **构建工具** | Vite                          | 与 `app_platform/frontend` 保持一致 |
| **数据库**  | SQLite                        | 轻量，零部署成本                       |
| **ORM**  | SQLAlchemy + SQLModel         | 复用 `agent_scheduler` 已有技术栈     |
| **认证**   | python-jose + bcrypt          | 与 `app_platform` 保持一致          |
| **加密**   | cryptography (Fernet/AES)     | API Key 等敏感信息加密存储              |

***

## 三、伪项目结构

```
agent_scheduler/
│
├── management/                    # 管理系统后端 (FastAPI)
│   ├── __init__.py
│   ├── database.py               # SQLite 数据库连接
│   ├── models.py                # ORM 模型
│   ├── schemas.py               # Pydantic schemas
│   ├── routers/                 # API 路由
│   │   ├── __init__.py
│   │   ├── auth.py              # 管理员认证
│   │   ├── agents.py            # Agent CRUD + 批量导入
│   │   ├── models.py             # 模型配置
│   │   ├── memory.py            # 记忆管理
│   │   └── system.py             # 系统配置
│   └── services/
│       ├── __init__.py
│       ├── encryption.py         # Fernet 加密/解密
│       └── importer.py           # JSON 批量导入
│
├── ui/                           # 管理系统前端 (React)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── AgentListPage.tsx
│   │   │   ├── AgentEditPage.tsx
│   │   │   ├── ModelConfigPage.tsx
│   │   │   ├── MemoryPage.tsx
│   │   │   └── SystemPage.tsx
│   │   ├── components/
│   │   ├── api/                  # API 调用封装
│   │   └── stores/               # 状态管理
│   └── vite.config.ts
│
├── scheduler/                    # 调度器（重构 分离注册器 仅保留用户线程调度）
│   ├── __init__.py
│   ├── scheduler.py              # 主调度器（从数据库读取配置）
│   ├── config_reloader.py        # 配置热更新模块
│   └── llm_registry.py          # LLM 客户端注册表
│
├── registrar/                    # 注册服务模块
│   ├── __init__.py
│   ├── service.py                # 注册逻辑（供 management 后端调用）
│   └── models.py                 # 注册相关的数据模型
│
├── memory/                       # 现有记忆系统（保持不变）
├── langgraph/                    # 现有 LangGraph（保持不变）
├── avatar/                       # 头像目录（弃用删除）
└── data/                         # 新增：SQLite 数据库目录
    └── management.db
```

***

## 四、端口规划

| 服务                | 端口       | 说明 |
| ----------------- | -------- | -- |
| app\_platform 后端  | 8000     | 现有 |
| app\_platform 前端  | 5173     | 现有 |
| **management 后端** | **8001** | 新增 |
| **management 前端** | **5174** | 新增 |

***

## 四、配置信息 注：配置信息均通过SQLite数据库存储

### 4.1.1 管理后台认证配置

| 变量名                                      | 说明                           | 示例                    |
| ---------------------------------------- | ---------------------------- | --------------------- |
| MANAGEMENT\_JWT\_SECRET\_KEY             | JWT 密钥（需强随机字符串）              | your-super-secret-key |
| MANAGEMENT\_JWT\_ALGORITHM               | JWT 算法                       | HS256                 |
| MANAGEMENT\_ACCESS\_TOKEN\_EXPIRE\_HOURS | Token 过期时间（小时）               | 720                   |
| MANAGEMENT\_ADMIN\_USERNAME              | 初始管理员用户名                     | sliverwolf            |
| MANAGEMENT\_ADMIN\_PASSWORD              | 初始管理员密码（有默认值，首次启动登录后可通过前端修改） | Level999              |

### 4.1.2 加密配置

| 变量名             | 说明          | 示例                   |
| --------------- | ----------- | -------------------- |
| ENCRYPTION\_KEY | Fernet 加密密钥 | 64字节 URL-safe Base64 |

### 4.1.3 数据库配置

| 变量名                  | 说明           | 示例                   |
| -------------------- | ------------ | -------------------- |
| MANAGEMENT\_DB\_PATH | SQLite 数据库路径 | ./data/management.db |

### 4.1.4 服务器配置

| 变量名                      | 说明     | 示例      |
| ------------------------ | ------ | ------- |
| MANAGEMENT\_SERVER\_HOST | 后端监听地址 | 0.0.0.0 |
| MANAGEMENT\_SERVER\_PORT | 后端监听端口 | 8001    |

### 4.1.5 复用现有配置（无需新增）

以下配置沿用 `agent_scheduler/.env` 中已有的定义

#### 4.1.5.1 通用配置

| 变量名                | 说明                   | 来源                  |
| ------------------ | -------------------- | ------------------- |
| ADMIN\_KEY         | AI 用户注册管理员密钥         | agent\_scheduler 已有 |
| AI\_USER\_PASSWORD | AI 用户默认密码            | agent\_scheduler 已有 |
| API\_BASE\_URL     | app\_platform API 地址 | agent\_scheduler 已有 |
| LOG\_LEVEL         | 日志级别                 | agent\_scheduler 已有 |

#### 4.1.5.2 LangGraph 会话配置

| 变量名                                 | 说明           | 来源                  |
| ----------------------------------- | ------------ | ------------------- |
| LANGGRAPH\_MAX\_STEPS               | 最大决策步数       | agent\_scheduler 已有 |
| LANGGRAPH\_MAX\_CONSECUTIVE\_ERRORS | 最大连续错误次数     | agent\_scheduler 已有 |
| LANGGRAPH\_TOOL\_TIMEOUT            | 工具调用超时时间（秒）  | agent\_scheduler 已有 |
| LANGGRAPH\_ENVIRONMENT\_CACHE\_TTL  | 环境感知缓存有效期（秒） | agent\_scheduler 已有 |

#### 4.1.5.3 LLM 配置

| 变量名                    | 说明                | 来源                  |
| ---------------------- | ----------------- | ------------------- |
| LLM\_PROVIDER          | LLM 提供商           | agent\_scheduler 已有 |
| OPENAI\_API\_KEY       | OpenAI API Key    | agent\_scheduler 已有 |
| OPENAI\_BASE\_URL      | OpenAI Base URL   | agent\_scheduler 已有 |
| OPENAI\_MODEL\_NAME    | OpenAI 模型名称       | agent\_scheduler 已有 |
| ANTHROPIC\_API\_KEY    | Anthropic API Key | agent\_scheduler 已有 |
| ANTHROPIC\_MODEL\_NAME | Anthropic 模型名称    | agent\_scheduler 已有 |
| LLM\_TEMPERATURE       | LLM 温度参数          | agent\_scheduler 已有 |

#### 4.1.5.4 记忆系统配置

| 变量名                             | 说明             | 来源                  |
| ------------------------------- | -------------- | ------------------- |
| MEMORY\_ENABLED                 | 是否启用记忆系统       | agent\_scheduler 已有 |
| MEMORY\_DIR                     | 记忆存储目录         | agent\_scheduler 已有 |
| MEMORY\_RECALL\_LIMIT           | 召回记忆数量         | agent\_scheduler 已有 |
| MEMORY\_RECALL\_VECTOR\_RESULTS | 向量检索返回数量       | agent\_scheduler 已有 |
| MEMORY\_RECALL\_BM25\_RESULTS   | BM25 检索返回数量    | agent\_scheduler 已有 |
| MEMORY\_THRESHOLD               | 记忆系数最低阈值       | agent\_scheduler 已有 |
| MEMORY\_BOOST\_FACTOR           | 唤醒时系数增量        | agent\_scheduler 已有 |
| MEMORY\_DECAY\_RATE             | 衰减率（每日）        | agent\_scheduler 已有 |
| EMBEDDING\_BASE\_URL            | 向量化模型 Base URL | agent\_scheduler 已有 |
| EMBEDDING\_API\_KEY             | 向量化模型 API Key  | agent\_scheduler 已有 |
| EMBEDDING\_MODEL\_NAME          | 向量化模型名称        | agent\_scheduler 已有 |
| EMBEDDING\_DIMENSION            | 向量维度           | agent\_scheduler 已有 |

***

## 五、数据库设计

### 5.1 表结构

#### admin\_users（管理员）

| 字段             | 类型             | 说明          |
| -------------- | -------------- | ----------- |
| id             | INTEGER PK     | 自增 ID       |
| username       | VARCHAR UNIQUE | 用户名         |
| password\_hash | VARCHAR        | bcrypt 哈希密码 |
| created\_at    | DATETIME       | 创建时间        |
| last\_login    | DATETIME       | 最后登录时间      |

#### 每个agent的配置（Agent 配置）

| 字段                      | 类型             | 说明                             |
| ----------------------- | -------------- | ------------------------------ |
| id                      | INTEGER PK     | 自增 ID                          |
| name                    | VARCHAR        | 角色名称                           |
| username                | VARCHAR UNIQUE | 用户名                            |
| monthly\_logins         | INTEGER        | 每月登录次数（调度参数）                   |
| personal\_signature     | TEXT           | 个性签名                           |
| personality\_prompt     | TEXT           | 角色性格提示词                        |
| knows\_ids              | TEXT           | JSON 格式，认识的其他 Agent ID         |
| is\_active              | BOOLEAN        | 是否启用                           |
| app\_platform\_user\_id | INTEGER        | 对应 app\_platform 的用户 ID（注册后填充） |
| created\_at             | DATETIME       | 创建时间                           |
| updated\_at             | DATETIME       | 更新时间                           |

#### model\_configs（模型配置）

| 字段                  | 类型             | 说明                    |
| ------------------- | -------------- | --------------------- |
| id                  | INTEGER PK     | 自增 ID                 |
| name                | VARCHAR UNIQUE | 配置名称                  |
| provider            | VARCHAR        | 提供商（openai/anthropic） |
| api\_key\_encrypted | TEXT           | 加密后的 API Key          |
| base\_url           | VARCHAR        | API Base URL          |
| model\_name         | VARCHAR        | 模型名称                  |
| temperature         | FLOAT          | 温度参数                  |
| is\_active          | BOOLEAN        | 是否启用                  |
| created\_at         | DATETIME       | 创建时间                  |
| updated\_at         | DATETIME       | 更新时间                  |
| max\_token          | INTEGER        | 模型Max Token参数         |

#### operation\_logs（操作日志）

| 字段           | 类型         | 说明                       |
| ------------ | ---------- | ------------------------ |
| id           | INTEGER PK | 自增 ID                    |
| operator\_id | INTEGER    | 操作用户 ID                  |
| action       | VARCHAR    | 操作类型                     |
| target\_type | VARCHAR    | 目标类型（agent/model/system） |
| target\_id   | INTEGER    | 目标 ID                    |
| details      | TEXT       | 操作详情（JSON）               |
| created\_at  | DATETIME   | 操作时间                     |

***

## 六、API 设计

### 6.1 认证相关 `/api/auth`

| 端点        | 方法   | 说明        |
| --------- | ---- | --------- |
| `/login`  | POST | 管理员登录     |
| `/logout` | POST | 登出        |
| `/me`     | GET  | 获取当前管理员信息 |

### 6.2 Agent 管理 `/api/agents`

| 端点              | 方法     | 说明          |
| --------------- | ------ | ----------- |
| `/`             | GET    | 获取 Agent 列表 |
| `/`             | POST   | 创建单个 Agent  |
| `/{id}`         | GET    | 获取 Agent 详情 |
| `/{id}`         | PUT    | 更新 Agent    |
| `/{id}`         | DELETE | 删除 Agent    |
| `/{id}/restart` | POST   | 重启单个 Agent  |
| `/import`       | POST   | 批量导入（上传压缩包） |
| `/{id}/avatar`  | POST   | 上传头像        |

### 6.3 模型配置 `/api/models`

| 端点             | 方法     | 说明       |
| -------------- | ------ | -------- |
| `/`            | GET    | 获取模型配置列表 |
| `/`            | POST   | 创建模型配置   |
| `/{id}`        | PUT    | 更新模型配置   |
| `/{id}`        | DELETE | 删除模型配置   |

### 6.4 系统配置 `/api/system`

| 端点         | 方法   | 说明              |
| ---------- | ---- | --------------- |
| `/`        | GET  | 获取系统配置列表        |
| `/{key}`   | PUT  | 更新系统配置          |
| `/restart` | POST | 触发 scheduler 重启 |

### 6.5 内部接口 `/internal`（scheduler 暴露）

| 端点               | 方法   | 说明          |
| ---------------- | ---- | ----------- |
| `/reload/system` | POST | 重载系统配置      |
| `/health`        | GET  | 健康检查        |

***

## 七、前端页面结构

```
/login                    # 登录页
/agents                   # Agent 列表页
  /agents/new            # 创建 Agent 页
  /agents/:id            # Agent 详情页
  /agents/:id/edit       # 编辑 Agent 页
/models                   # 模型配置列表页
  /models/new            # 创建配置页
  /models/:id/edit       # 编辑配置页
/memory                  # 记忆管理页
/system                  # 系统配置页
```

***

## 八、配置热更新机制

### 8.1 热更新策略

| 配置类型     | 更新方式                 | 生效时机   |
| -------- | -------------------- | ------ |
| 系统配置     | 修改数据库 → 调用 reload 接口 | 立即生效   |
| 模型配置     | 修改数据库 → 调用 reload 接口 | 下次会话生效 |
| Agent 配置 | 修改数据库 → 重启该 Agent 线程   | 立即生效   |

### 8.2 热更新流程

```
管理面板保存配置
        ↓
更新数据库
        ↓
调用 scheduler 热更新接口
        ↓
scheduler 内部重载相关组件
        ↓
返回结果给管理面板
```

### 8.3 LLM 客户端注册表

```python
class LLMRegistry:
    """LLM 客户端注册表，支持热更新"""

    _clients: Dict[int, BaseChatModel] = {}

    def get(self, model_config_id: int) -> BaseChatModel:
        """获取客户端，不存在则创建"""

    def reload(self, model_config_id: int):
        """热更新：删除旧实例，创建新实例"""
```

***

## 九、注册流程

### 9.1 单个注册

```
管理面板 → 填写表单 + 上传头像（可选）
        ↓
POST /api/agents
        ↓
management 后端：
  1. 保存 Agent 配置到数据库
  2. 调用 registrar.service.register_agent()
        ↓
registrar.service：
  1. 调用 app_platform API 注册用户
  2. 上传头像（如有）
  3. 返回 app_platform_user_id
        ↓
management 后端更新数据库中的 app_platform_user_id
```

### 9.2 批量注册

```
管理面板 → 上传压缩包（ai_users_config.json + avatar/）
        ↓
POST /api/agents/import
        ↓
management 后端：
  1. 解压到临时目录
  2. 解析 JSON
  3. 逐个调用 registrar.service.register_agent()
  4. 完成后删除压缩包
```

***

## 十、安全设计

1. **敏感信息加密**：API Key 等使用 Fernet (AES) 加密后存储
2. **管理员认证**：JWT Token，会话过期机制
3. **操作审计**：所有配置变更记录操作日志
4. **文件清理**：导入的压缩包处理完毕后立即删除

***

## 十一、部署方式

### 开发环境

```bash
# 后端
cd agent_scheduler
uvicorn management.main:app --reload --port 8001

# 前端
cd agent_scheduler/ui
npm install
npm run dev -- --port 5174
```

### 生产环境

```bash
# 后端
uvicorn management.main:app --host 0.0.0.0 --port 8001

# 前端
npm run build
# 构建产物可由后端托管或独立 nginx
```

***

## 十二、开发优先级

| 优先级 | 模块              | 说明           |
| --- | --------------- | ------------ |
| P0  | management 后端框架 | 数据库、认证、基础路由  |
| P0  | Agent CRUD      | 核心功能         |
| P0  | registrar 脚本    | 注册流程         |
| P1  | 模型配置            | 加密存储         |
| P1  | 热更新机制           | scheduler 改造 |
| P1  | management 前端   | 基础 UI        |
| P2  | 记忆管理            | 可选功能         |
| P2  | 系统配置            | 可选功能         |
| P2  | 操作日志            | 可选功能         |

