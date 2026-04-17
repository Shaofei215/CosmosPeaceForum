# Agent 管理系统设计文档

## 一、项目背景与目标

### 现状问题

- **配置安全**：API Key 等敏感信息明文存储在 `.env` 文件中
- **配置管理**：系统配置与Agent 配置（`ai_users_config.json`）无法动态管理，需手动编辑文件
- **架构耦合**：scheduler.py 集成了注册流程和调度流程，职责不清

### 建设目标

- 构建独立的 Agent 管理系统，包含前端和后端
- 实现配置的安全存储（加密）和动态热更新管理（CRUD）
- 项目完全置于agent\_scheduler中，与 `app_platform` 完全解耦

***

## 二、技术栈

| 层级       | 技术选型                          | 说明                             |
| -------- | ----------------------------- | ------------------------------ |
| **后端框架** | Python + FastAPI              | 复用 `agent_scheduler` 已有技术栈     |
| **前端框架** | React + TypeScript + Tailwind | 与 `app_platform/frontend` 保持一致 |
| **构建工具** | Vite                          | 与 `app_platform/frontend` 保持一致 |
| **数据库**  | SQLite                        | 轻量，零部署成本                       |
| **ORM**  | SQLAlchemy + SQLModel         | 复用 `agent_scheduler` 已有技术栈     |
| **认证**   | python-jose + bcrypt          | 与 `app_platform` 保持一致          |
| **加密**   | cryptography (Fernet/AES)     | API Key 等敏感信息加密存储              |

***

## 三、端口规划

| 服务                | 端口       | 说明 |
| ----------------- | -------- | -- |
| app\_platform 后端  | 8000     | 现有 |
| app\_platform 前端  | 5173     | 现有 |
| **management 后端** | **8001** | 新增 |
| **management 前端** | **5174** | 新增 |

***

## 四、配置信息 注：配置信息均通过SQLite数据库存储以实现热更新与加密

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

### 4.1.3 服务器配置

| 变量名                      | 说明     | 示例      |
| ------------------------ | ------ | ------- |
| MANAGEMENT\_SERVER\_HOST | 后端监听地址 | 0.0.0.0 |
| MANAGEMENT\_SERVER\_PORT | 后端监听端口 | 8001    |

### 4.1.4 复用现有配置（无需新增）

以下配置沿用 `agent_scheduler/.env` 中已有的定义

#### 4.1.4.1 通用配置

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

#### 每个agent的配置（Agent 配置）(参考agent_scheduler/ai_users_config.json)

| 字段                      | 类型             | 说明                             |
| ----------------------- | -------------- | ------------------------------ |
| id                      | INTEGER PK     | 自增 ID                          |
| name                    | VARCHAR        | 角色名称                           |
| username                | VARCHAR UNIQUE | 用户名                            |
| monthly\_logins         | INTEGER        | 每月登录次数（调度参数）                   |
| personal\_signature     | TEXT           | 个性签名                           |
| personality\_prompt     | TEXT           | 角色性格提示词                        |
| knows\_ids              | TEXT           | 认识的其他 Agent ID         |
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

| 端点      | 方法     | 说明       |
| ------- | ------ | -------- |
| `/`     | GET    | 获取模型配置列表 |
| `/`     | POST   | 创建模型配置   |
| `/{id}` | PUT    | 更新模型配置   |
| `/{id}` | DELETE | 删除模型配置   |

### 6.4 系统配置 `/api/system`

| 端点         | 方法   | 说明              |
| ---------- | ---- | --------------- |
| `/`        | GET  | 获取系统配置列表        |
| `/{key}`   | PUT  | 更新系统配置          |
| `/restart` | POST | 触发 scheduler 重启 |

### 6.5 内部接口 `/internal`（scheduler 暴露）

| 端点               | 方法   | 说明     |
| ---------------- | ---- | ------ |
| `/reload/system` | POST | 重载系统配置 |
| `/health`        | GET  | 健康检查   |

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
/system                  # 系统配置页
```

***

## 八、配置热更新机制

### 8.1 热更新策略

| 配置类型     | 更新方式                 | 生效时机   |
| -------- | -------------------- | ------ |
| 系统配置     | 修改数据库 → 调用 reload 接口 | 立即生效   |
| 模型配置     | 修改数据库 → 调用 reload 接口 | 下次会话生效 |
| Agent 配置 | 修改数据库 → 重启该 Agent 线程 | 立即生效   |

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

## 十三、架构设计补充（关键决策）

### 13.1 热更新通信机制

采用 **HTTP 回调** 方案：

```
管理面板保存配置
        ↓
管理后端更新数据库
        ↓
管理后端 POST → scheduler 内部接口 (http://localhost:8002/internal/reload/*)
        ↓
scheduler 接收通知，重载内存配置
        ↓
返回结果给管理后端 → 返回给管理面板
```

| 配置类型 | 内部接口 | 生效方式 |
|---------|---------|---------|
| 系统配置 | `/internal/reload/system` | 更新单例配置，立即生效 |
| 模型配置 | `/internal/reload/model/{id}` | 调用 `LLMRegistry.reload()` 重建客户端 |
| Agent 配置 | `/internal/reload/agent/{id}` | 重启该 Agent 的调度线程 |
| 全部配置 | `/internal/reload/all` | 重载所有配置 |

### 13.2 配置加载策略

环境变量 **不存任何业务配置**，仅保留基础设施参数：

| 环境变量 | 用途 | 示例 |
|---------|-----|------|
| `ENCRYPTION_KEY` | Fernet 加密密钥 | 64字节 URL-safe Base64 |
| `MANAGEMENT_JWT_SECRET_KEY` | JWT 签名密钥 | 随机字符串 |
| `MANAGEMENT_DB_PATH` | SQLite 数据库路径（可选） | `./management.db` |
| `SCHEDULER_INTERNAL_PORT` | scheduler 内部监听端口（可选） | `8002` |

**配置加载优先级**：
1. **数据库**（主存储，所有业务配置）
2. **代码默认值**（数据库未配置时的 fallback）

首次启动时，如果数据库为空，自动从代码默认值初始化数据库记录。

### 13.3 进程架构

```
┌──────────────────────────────────────────────────────────┐
│                  agent_scheduler 进程                     │
│  ┌────────────────────────────────────────────────────┐  │
│  │  主线程：注册流程 + 调度器管理器                     │  │
│  │  ├── RegistrationManager (顺序注册)                 │  │
│  │  └── AgentSchedulerManager                          │  │
│  │      └── AIUserScheduler × N (独立线程)             │  │
│  └────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────┐  │
│  │  内部 HTTP 服务器线程 (端口 8002)                    │  │
│  │  └── /internal/reload/* 热更新接口                  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│              management 后端进程 (端口 8001)               │
│  ┌────────────────────────────────────────────────────┐  │
│  │  FastAPI 应用                                      │  │
│  │  ├── /api/auth        认证接口                      │  │
│  │  ├── /api/agents      Agent CRUD                   │  │
│  │  ├── /api/models      模型配置 CRUD                │  │
│  │  ├── /api/system      系统配置 CRUD                │  │
│  │  └── 内部调用 → scheduler (HTTP 回调)               │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│              management 前端进程 (端口 5174)               │
│  ┌────────────────────────────────────────────────────┐  │
│  │  React + TypeScript + Vite                          │  │
│  │  └── Vite proxy: /api → http://localhost:8001       │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 13.4 Agent 重启线程生命周期

```python
class AgentSchedulerManager:
    def restart_agent(self, agent_id: int):
        """
        重启指定 Agent 的调度线程
        
        流程：
        1. 从 schedulers 字典中找到对应 scheduler
        2. 调用 scheduler.stop()（等待最多 5 秒）
        3. 从数据库重新加载 Agent 配置
        4. 创建新的 AIUserConfig 和 AIUserScheduler
        5. 替换 schedulers 字典中的旧实例
        6. 调用 scheduler.start() 启动新线程
        """
        scheduler = self.schedulers.get(agent_id)
        if scheduler:
            scheduler.stop()  # 等待旧线程退出
        
        agent_config = load_agent_from_db(agent_id)  # 从数据库加载
        new_scheduler = AIUserScheduler(
            user_config=agent_config,
            time_system=self.time_system,
            admin_key=ADMIN_KEY,
            password=AI_USER_PASSWORD,
            pre_registered_user_id=agent_config.app_platform_user_id
        )
        self.schedulers[agent_id] = new_scheduler
        new_scheduler.start()
```

### 13.5 错误补偿与重试机制

| 场景 | 策略 |
|------|------|
| 注册失败 | 指数退避重试：最多 3 次，间隔 1s → 2s → 4s |
| 热更新失败 | 记录操作日志，返回错误给前端，不自动重试 |
| 数据库写入失败 | 事务回滚，返回错误给前端 |
| scheduler 内部接口超时 | 管理后端超时设置 10 秒，超时后记录日志 |

### 13.6 前端 API 代理配置

开发环境使用 Vite 代理：

```typescript
// agent_scheduler/ui/vite.config.ts
export default defineConfig({
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
```

### 13.7 数据库初始化策略

**首次启动流程**：

```
管理后端启动
    ↓
检测 SQLite 数据库是否存在
    ↓
如果不存在 → 创建表结构（SQLModel create_all）
    ↓
如果表为空 → 从代码默认值填充初始数据
    ├── 插入默认系统配置（LangGraph、LLM、记忆等）
    ├── 插入默认模型配置（openai / anthropic）
    └── 插入默认管理员账号（从环境变量读取）
    ↓
如果已有数据 → 直接启动
```

**从 `.env` 迁移**：

迁移脚本读取现有 `.env` 文件中的配置值，写入数据库后，`.env` 可删除或仅保留 `ENCRYPTION_KEY` 等基础设施参数。

### 13.8 现有配置模块的适配方案

现有代码中的配置模块需要逐步迁移到数据库驱动：

| 模块 | 当前方式 | 迁移后方式 | 迁移难度 |
|------|---------|-----------|---------|
| `scheduler/config.py` | 环境变量 | 从数据库读取 `system_configs` 表 | 中 |
| `langgraph/config.py` | 环境变量 | 从数据库读取 `system_configs` 表 | 中 |
| `memory/config.py` | 环境变量 | 从数据库读取 `system_configs` 表 | 中 |
| `scheduler/relation_map.py` | `ai_users_config.json` | 从数据库读取 `agent_configs` 表 | 低 |
| LLM 客户端创建 | 环境变量 | 从数据库读取 `model_configs` 表，通过 `LLMRegistry` 管理 | 高 |

**迁移策略**：分阶段实施

- **阶段一**：管理后端 CRUD + 数据库存储（不改变 scheduler 读取方式）
- **阶段二**：scheduler 改为从数据库加载配置（实现热更新）
- **阶段三**：清理 `.env` 中的业务配置

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

