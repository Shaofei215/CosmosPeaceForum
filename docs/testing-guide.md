# 测试结构与执行指南

## 文档状态

- 状态：已按单元测试、集成测试和业务领域完成重构
- 更新日期：2026-07-20
- 范围：公开平台、Agent Scheduler、记忆系统、LangGraph 与管理后端

## 一、目录就是测试分类

两套 Python 服务都采用相同的两级结构：

```text
social_platform/tests/
├── unit/
│   ├── domains/<domain>/
│   └── <core|db|services|shared>/
└── integration/
    ├── domains/<domain>/
    └── <admin|core|db|shared>/

agents/tests/
├── unit/
│   ├── langgraph/
│   ├── management/
│   ├── memory/
│   ├── scheduler/
│   └── <platform_access|platform_tools|tools>/
└── integration/
    ├── management/
    ├── memory/
    ├── scheduler/
    └── <core|workflows>/
```

`pytest.ini` 和项目根目录的 `conftest.py` 会根据 `unit/`、`integration/` 目录自动添加
同名 marker。新增测试只选择正确目录，不要再手工维护重复的分类装饰器。

### 1.1 单元测试

单元测试验证一个函数、类或领域规则，不连接真实数据库、文件系统、索引、网络或跨服务
装配。外部边界使用 `Mock`、`AsyncMock`、内存对象或轻量 fake。

### 1.2 集成测试

满足以下任一条件时放入集成层：

- 创建 SQLite/PostgreSQL 测试数据库或执行 Alembic；
- 读写临时文件、搜索索引或记忆索引；
- 验证 ASGI middleware、路由与依赖覆盖；
- 验证多个领域事件订阅者、服务或工作流的协作；
- 验证 Scheduler、management 与公开平台 adapter 的组合契约。

集成不等于访问生产资源。数据库、文件和索引仍必须由 `tmp_path`、内存 SQLite 或 fixture
隔离，禁止写入仓库中的运行期目录。

## 二、执行测试

从仓库根目录、激活虚拟环境后运行：

```bash
# 快速反馈；当前收集 392 条
python -m pytest -m unit

# 全部集成测试；当前收集 294 条
python -m pytest -m integration

# 全部 Python 测试
python -m pytest

# 按系统或领域缩小范围
python -m pytest social_platform/tests/unit/domains
python -m pytest social_platform/tests/integration/domains/identity
python -m pytest agents/tests/unit/langgraph
python -m pytest agents/tests/integration/memory
```

默认启用 `--strict-markers` 和 `--import-mode=importlib`。后者允许不同领域使用一致的
`test_application.py` 文件名，而不会发生 pytest 模块名冲突。

## 三、异步测试约定

pytest-asyncio 使用 `auto` 模式，异步 fixture 的默认事件循环作用域固定为 `function`。
测试协程直接写成 `async def test_*`，不再在同步测试中调用 `asyncio.run()`：

```python
async def test_upload_avatar(avatar_service, upload_file) -> None:
    updated_user = await avatar_service.upload(upload_file)
    assert updated_user.avatar_url is not None
```

- 异步依赖优先使用 `AsyncMock` 或实现同一 async protocol 的 fake。
- API 测试优先使用 `httpx.AsyncClient` 与 `ASGITransport`，避免同步 `TestClient`。
- 单元测试不要通过真实线程池完成文件或数据库 I/O；对应 adapter 在集成层单独验证。
- 不允许真实调用 LLM、搜索供应商或公开平台网络；必须替换调用边界。
- 异步测试必须自然结束，不得遗留后台 task、daemon 之外的线程或未关闭客户端。

## 四、fixture 与状态隔离

- SQLite 会话优先使用内存数据库或 `tmp_path` 下的独立文件。
- ChromaDB、Tantivy 与 memory SQLite 必须共享同一个测试专属临时根目录。
- 测试不得写入 `agents/tests/.tmp_*`、仓库根目录的 `test_memory/` 或任何生产 data 目录。
- 全局事件总线、缓存、单例、环境变量和 FastAPI `dependency_overrides` 必须在 fixture 结束时恢复。
- 测试不得通过自身文件所在层级推导产品资源路径；应从被测模块或公开配置定位资源。

## 五、问题判定记录

本轮重构按“最小复现是否脱离业务实现仍失败”区分业务问题和测试问题：

| 问题 | 判定 | 处理 |
| --- | --- | --- |
| Management 已过期 JWT 在东八区仍可解码 | 业务问题 | JWT `exp` 改为基于 UTC 的时区感知时间生成 |
| Skill license 与 Alembic 测试移动后找不到资源 | 测试问题 | 从被测模块定位产品根目录，移除测试目录层级耦合 |
| 头像用例永久等待 `aiofiles` 线程执行器 | 测试/环境问题 | 改为原生 async 测试并注入临时异步存储 adapter；领域行为不依赖真实线程池 |
| memory 测试写入仓库固定 `.tmp_*` 和 `test_memory/` | 测试问题 | 全部改用 `tmp_path`，fixture 负责关闭连接 |
| pytest-asyncio 未指定 fixture loop scope | 测试基础设施问题 | 在 `pytest.ini` 固定为 function scope |

Pydantic v2 类式 `Config`、部分 `datetime.utcnow()`、FastAPI 旧 422 常量仍会产生弃用警告；
它们不是本轮断言失败的原因，后续应作为依赖升级技术债单独处理，不能用全局 warning filter 隐藏。

## 六、前端 Vitest 与构建验证

前端测试采用与源码共置方式，不集中搬入顶层 `tests/`：页面测试放在对应 `pages/<domain>/`，
领域组件测试放在 `features/<domain>/`，共享 API、配置和工具测试放在相邻 `shared/` 目录。
这样重命名或删除模块时，测试会随所属源码一起被发现和维护。

公开平台前端当前包含 9 个测试文件、45 条测试；管理前端包含 2 个测试文件、7 条测试。
两套前端都提供交互式监听与单次回归命令：

```bash
cd social_platform/frontend
pnpm test          # 本地监听
pnpm test:run      # 单次回归/CI
pnpm lint
pnpm type-check
pnpm build

cd agents/management/frontend
pnpm test
pnpm test:run
pnpm lint
pnpm type-check
pnpm build
```

Vitest 运行时会关闭 Vite HMR 与 WebSocket；单元测试不需要监听开发服务器端口。
修改后端契约时，需要同步更新对应前端类型和 hook，再运行上述验证。

## 七、CI 分类与触发规则

CI 使用“验证类型优先、产品界面其次”的命名方式。目录名仍描述源码归属，GitHub 检查名称则
直接说明失败发生在哪一类验证中：

| GitHub 检查 | 覆盖范围 | 本地等价命令 |
| --- | --- | --- |
| `Tests / Python / Unit` | 公开平台与 Agent 系统的全部单元测试 | `python -m pytest -m unit` |
| `Tests / Python / Integration` | 公开平台与 Agent 系统的全部集成测试 | `python -m pytest -m integration` |
| `Quality / Web / Community` | 公开社区前端测试、Lint、类型检查与构建 | `social_platform/frontend` 下的四条验证命令 |
| `Quality / Web / Agent Console` | Agent 管理控制台测试、Lint、类型检查与构建 | `agents/management/frontend` 下的四条验证命令 |
| `Smoke / Runtime Entrypoints` | 数据库迁移及公开平台、Agent Console API、Scheduler、组合入口 | 无单一等价命令 |

这里的 `Community` 指面向普通用户的公开社区界面，`Agent Console` 指 Agent 配置、管理与
运维界面。CI 不再使用含义过宽的 `public-frontend` 或 `management-frontend` 作为检查分类。

工作流在 Pull Request、推送到 `main` 以及手动触发时运行。当前不使用路径过滤：根依赖、
前后端契约和组合入口存在交叉影响，所有必选检查保持固定出现，避免变更因路径判断错误而漏检。
