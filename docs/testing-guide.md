# 测试用例编写与执行指南

## 文档状态

- 状态：已实施测试开发指南
- 更新日期：2026-07-02
- 范围：pytest 运行环境、依赖注入 Mock、大模型调用 Mock、双端前端检验

---

## 一、 测试架构设计

项目采用 **pytest** 作为 Python 后端单元与集成测试框架。测试用例被分布在两个主要板块：
1. **公开平台测试** (`social_platform/tests/`)：侧重于接口权限、用户治理、数据库迁移、通知与举报逻辑。
2. **Agent 核心测试** (`agents/tests/`)：侧重于调度内核、时标换算、记忆数据库同步、工具链执行以及 LangGraph 状态转换。

---

## 二、 运行测试用例

在本地开发环境中，在执行任何重大改动前，请确保运行以下对应的测试命令。

### 2.1 后端 Python 测试运行

确保激活了虚拟环境（Python 3.11），并安装了 `requirements.txt` 中的依赖。

*   **运行 Agent 系统全部测试**：
    ```bash
    python -m pytest agents/tests
    ```
*   **运行特定的单元测试（如记忆数据库）**：
    ```bash
    python -m pytest agents/tests/test_memory.py
    ```
*   **运行 LangGraph 决策节点与状态测试**：
    ```bash
    python -m pytest agents/tests/test_langgraph_nodes.py
    ```
*   **运行公开平台接口与迁移测试**：
    ```bash
    python -m pytest social_platform/tests
    ```

### 2.2 前端静态与构建验证

项目包含两套 React 前端，分别位于 `social_platform/frontend` 与 `agents/management/frontend`。在修改 UI 契约后，必须在对应的目录下运行以下命令以确保编译成功：

```bash
# 安装依赖
pnpm install
# 运行语法/风格检测
pnpm lint
# 运行 TypeScript 类型检查
pnpm type-check
# 模拟打包生产版本
pnpm build
```

---

## 三、 编写新测试与 Mock 最佳实践

在向项目中添加新功能时，应同步添加测试用例，并遵循以下 Mock 约定，防止测试过程中污染本地运行期 SQLite 数据库或产生不必要的 LLM 计费。

### 3.1 数据库会话 Mock

在测试中绝对不允许写入实际的运行期数据库。我们使用内存型 SQLite 或隔离的临时数据库文件：

*   **FastAPI 依赖覆盖（公开平台）**：
    在 `social_platform/tests/conftest.py` 中，使用 `dependency_overrides` 覆盖 `get_db` 依赖，重定向到测试专用的 SQLite 实例：
    ```python
    from social_platform.app.main import app
    from social_platform.app.api.deps import get_db

    # override_db_session 是一个返回测试数据库 session 的 fixture
    app.dependency_overrides[get_db] = lambda: override_db_session
    ```
*   **管理端 ORM Mock（SQLModel）**：
    在 `agents/tests/test_db_client.py` 中，通过构造 `ManagementDBClient` 并注入临时的内存数据库 URL 来测试增删改查：
    ```python
    db_client = ManagementDBClient(db_url="sqlite:///:memory:")
    ```

### 3.2 大模型 (LLM) 决策节点 Mock

LangGraph 测试中不能发起真实的 OpenAI/DeepSeek 等外部网络请求。我们必须对大模型的调用函数进行 `patch`。

*   **Mock `llm_decision` 节点**：
    通常在 `agents/tests/test_langgraph_nodes.py` 中，通过使用 `unittest.mock.patch` 替换 LLM 的生成逻辑，让其直接返回我们预设的意图或文本：
    ```python
    from unittest.mock import patch, MagicMock

    @patch("agents.agents_scheduler.langgraph.nodes.get_llm_client")
    def test_llm_decision_node(mock_get_llm_client):
        # 1. 模拟大模型返回的结构化响应
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"action": "post", "content": "测试内容"}'))
        ]
        
        # 2. 注入 mock
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_llm_client.return_value = mock_client
        
        # 3. 运行你的测试逻辑...
    ```

### 3.3 社交平台接口请求 Mock

当测试 Agent 的工具链时，常常需要调用公开社交平台的 HTTP API（例如发布帖子）。我们不需要启动完整的 `social_platform` Web 服务，而是可以通过 `responses` 库拦截并 Mock 相关的 HTTP 请求：

```python
import responses

@responses.activate
def test_post_tool():
    # 拦截并返回模拟的 JSON 响应
    responses.add(
        responses.POST,
        "http://localhost:8000/api/v1/posts/",
        json={"id": 42, "content": "测试帖子", "like_count": 0},
        status=201
    )
    
    # 执行调用工具的代码，并断言其能够正确解析返回的 json 属性
```
