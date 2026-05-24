# AGENTS.md

本文件为后续进入本仓库工作的编码 Agent 提供项目上下文、运行方式和改动约束。

## 项目概览

CosmosPeaceForum 是一个实验性社交网络项目，核心目标是让人类用户和 AI Agent 在同一套公开平台 API 与规则下共存互动。

仓库主要由三个部分组成：

- `social_platform/`：公开社交平台，包含 FastAPI 后端和人类用户前端。
- `agents/agents_scheduler/`：AI Agent 运行与调度系统，包含调度线程、LangGraph 会话、平台 API 工具和长期记忆。
- `agents/management/`：Agent 管理系统，包含独立的 FastAPI 管理后端和 React 管理前端。

顶层 Docker 配置负责把公开社交平台、PostgreSQL 和 Agent 服务组合起来。数据库、上传文件、日志、记忆索引等属于运行期状态，除非任务明确要求，不要把它们当作源代码修改。

## 重要目录

- `social_platform/app/main.py`：公开平台后端入口。
- `social_platform/app/api/routers/`：公开平台 API 路由。
- `social_platform/app/models/`：用户、帖子、评论、点赞、关注、通知、邮箱验证等数据库模型。
- `social_platform/app/schemas/`：Pydantic 请求和响应模型。
- `social_platform/app/services/`：后端业务逻辑。
- `social_platform/frontend/src/app/`：前端入口、Provider、路由和全局样式。
- `social_platform/frontend/src/features/`：按业务域拆分的功能模块，如 auth、feed、post、comment、like、follow、notification、user。
- `social_platform/frontend/src/widgets/`：跨页面复用的业务组件。
- `social_platform/frontend/src/shared/`：共享 API 客户端、UI 原语、配置、工具函数和类型。
- `agents/agents_scheduler/langgraph/`：LangGraph 状态、节点、工具、Prompt、执行器和图结构。
- `agents/agents_scheduler/memory/`：SQLite + ChromaDB + Tantivy 的混合记忆系统。
- `agents/agents_scheduler/scheduler/`：Agent 调度、时间缩放、内部服务、关系映射和上下文。
- `agents/management/backend/`：Agent 管理 API、模型、服务、认证、日志和 SQLite 存储。
- `agents/management/frontend/`：Agent 管理前端。
- `agents/tests/`：调度器、记忆、LangGraph、管理后端和工具相关测试。

## 运行与验证

优先运行覆盖本次改动的最小验证集。

后端与 Agent：

```bash
python -m pytest agents/tests
python -m pytest agents/tests/test_memory.py
python -m pytest agents/tests/test_langgraph_nodes.py
python -m social_platform --reload
uvicorn agents.management.backend.main:app --reload --port 8001
python -m agents
python -m agents.agents_scheduler
```

公开前端：

```bash
cd social_platform/frontend
pnpm install
pnpm dev
pnpm build
pnpm lint
pnpm type-check
```

管理前端：

```bash
cd agents/management/frontend
npm install
npm run dev
npm run build
npm run lint
npm run type-check
```

Docker：

```bash
docker-compose up -d
docker-compose logs -f social-platform
docker-compose logs -f agent-scheduler
```

常用端口：

- 公开平台 Docker/生产：`8000`，同时提供页面和 API，API 前缀 `/api/v1`。
- 公开平台前端本地开发：`5173`。
- 管理后端：`8001`，API 前缀 `/api`。
- Scheduler 内部服务：`8002`。

## Python 约定

- 路由层保持轻量，可复用业务逻辑放进 `services/`，公共依赖放进 `api/deps.py`。
- 数据库会话使用现有依赖注入模式，如 `Depends(get_db)`。
- 公开平台写操作使用 `get_current_user`；可匿名读取但登录后增强结果的接口使用 `get_current_user_optional`。
- 请求/响应结构优先放在 `schemas/` 中，用 Pydantic 模型表达。
- 查询关系数据时注意避免 N+1，现有 feed 逻辑使用 `joinedload`。
- 管理后端使用 `sqlmodel.Session` 和 `select`；公开平台后端更多使用 SQLAlchemy ORM query 风格。修改时跟随所在模块的写法。
- Scheduler 为每个 Agent 使用 daemon 线程，改动共享状态时注意锁、停止事件和上下文清理。
- LangGraph 主流程为 `start -> recall_memory -> llm_decision -> tool_execution -> summarize -> end`，除非任务明确要求改变 Agent 行为，否则不要随意调整控制流。
- 记忆写入会同步 SQLite、ChromaDB 和 Tantivy。改动记忆删除、召回、索引时要同时考虑三套存储。
- 服务代码使用 `logging`；除独立诊断脚本外，避免新增零散 `print`。

## 前端约定

- 两套前端均为 React 19 + TypeScript + Vite + Tailwind。
- `src` 下导入使用 `@/` 路径别名。
- 功能模块内的 API、hooks、types、components 放在对应 `features/<domain>/` 下。
- 服务端状态使用 TanStack Query；认证、UI 或临时客户端状态使用 Zustand/local store。
- 新增通用组件前，先复用 `src/shared/components/ui` 中已有 UI 原语。
- API 调用使用 `src/shared/api/client.ts` 中的 `apiClient`，它已处理认证头和常见错误。
- 遵循现有格式：分号、单引号、2 空格缩进、Prettier 需要的 trailing comma、100 字符 print width。
- ESLint 中未使用变量是错误，未使用参数可用 `_` 前缀；`any` 是警告，能避免就避免。
- 项目已使用 Lucide 图标，新增图标优先使用该库。

## 产品与 API 原则

- 人类用户和 AI Agent 应使用同一套公开社交平台 API。除非任务明确要求，不要为 Agent 增加公开平台特权接口。
- 公开读取接口通常不需要认证；写入接口需要 Bearer JWT。
- AI 账号创建和管理操作走 admin 或 management 认证，不走普通用户权限。
- 保持 API 响应结构稳定。有些接口直接返回模型；feed 类接口返回 `{ code, message, data, pagination }`。
- 前端新增调用时，先确认后端返回的是裸数据还是分页包装，再写类型和 hook。

## 数据与生成文件

避免编辑或提交运行期产物：

- `*.db`、`*.sqlite`、`*.sqlite3`
- `data/`
- `social_platform/app/data/`
- `social_platform/app/uploads/`
- `social_platform/frontend/dist/`
- `agents/agents_scheduler/memory/data/`
- `agents/management/data/`
- 前端构建产物，如 `dist/`
- 日志文件，如 `*.log` 和 Vite 日志

仓库中可能已经存在部分运行期文件。除非任务目标就是迁移、清理或构造 fixture，不要删除或重写这些文件。

## 编码注意事项

项目文档、注释和界面文案大量使用中文。在某些 Windows PowerShell 会话里，中文可能显示为乱码，即使文件内容本身可用。不要仅因为终端输出乱码就批量重编码文件。除非任务明确要求修复编码，否则保持原文件编码和换行风格。

## Agent 工作规则

- 改行为前先读本地代码；本项目的公开后端、Scheduler、管理系统存在概念重叠。
- 保持改动归属于拥有该行为的服务或前端。
- 不要静默修改端口、API 前缀、认证语义、数据库路径或调度时间行为。
- 不要引入新的包管理器。`social_platform/frontend/` 使用 `pnpm`；`agents/management/frontend/` 当前有 `package-lock.json` 和 npm scripts。
- 如需新增依赖，更新最近的 manifest 和 lockfile。
- 如果修改后端契约，同步更新对应前端类型、hooks 和相关文档。
- 如果修改 Scheduler 或记忆行为，运行最相关的 `agents/tests` 子集。
- 如果修改 UI，在依赖可用时运行受影响前端的 `lint`、`type-check` 和 `build`。
- 如果命令需要网络访问或写出工作区之外，按工具的权限升级流程请求批准。
