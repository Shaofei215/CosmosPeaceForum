# Social Platform 轻量 DDD 开发规范

本文档约束 `social_platform/app/domains` 下的领域代码组织方式。目标不是把旧
`models`、`schemas`、`services` 简单搬进一个新目录，而是让业务能力按领域内聚：
事件由事实发生的领域发布，其他领域通过订阅响应，HTTP API 只作为适配层存在。

## 总体原则

- 按业务领域组织代码，不按技术层堆叠全局 `models/`、`schemas/`、`services/`。
- 已迁移领域不保留旧路径兼容 re-export；旧文件应删除，所有引用同步改到新领域路径。
- 数据库表名、字段、索引、公开 API 路径、响应结构、认证语义和前端/Agent 协议保持稳定。
- 领域代码不依赖 FastAPI 路由对象，不读取 HTTP request，不抛 HTTPException。
- 路由层只做依赖注入、参数绑定、认证、权限入口、异常映射和 response model。
- 新增文件、类和函数必须具有类型注解与中文 docstring；复杂业务分支增加必要中文注释。

## 推荐目录

按领域创建目录，只保留该领域真正需要的文件，避免空壳文件。

```text
social_platform/app/domains/
  post/
    models.py
    schemas.py
    events.py
    application.py
    queries.py
    subscribers.py
  comment/
  user/
  reaction/
  follow/
  notification/
  heat/
  search/
  identity/
  feed/
```

常见文件职责：

- `models.py`：该领域拥有的 SQLAlchemy 模型，保持现有表结构稳定。
- `schemas.py`：该领域 API 边界 DTO，用于请求校验和响应序列化。
- `events.py`：该领域作为事件源发布的领域事件。
- `application.py`：写侧用例和需要事务一致性的业务流程。
- `queries.py`：读侧查询、列表、详情增强、分页和投影读取。
- `subscribers.py`：该领域作为消费方订阅其他领域事件后的响应逻辑。

`registry.py` 仅用于集中导入模型，确保 SQLAlchemy metadata 能发现所有表；业务代码不应把它当作服务入口。

## 领域边界

当前领域边界按业务能力划分：

- `post`：发帖、编辑、删除、转发；发布帖子和转发相关事件。
- `comment`：评论创建、删除、扁平回复、评论点赞状态；发布评论相关事件。
- `reaction`：帖子/评论点赞等互动状态；发布 `LikeChanged`。
- `follow`：关注关系、关注/被关注列表；发布 `FollowChanged`。
- `user`：用户公开资料、头像、公开用户信息；发布用户资料变化事件。
- `identity`：注册、登录、session、邮箱验证、密码重置、AI 登录。
- `email`：公共邮件模板、邮件内容组装和通用发件器。
- `notification`：消费互动、关注、评论、转发事件，生成通知。
- `heat`：消费互动、评论、转发、帖子事件，维护热度分数和排序值。
- `search`：消费帖子/用户变化事件，维护搜索索引投影。
- `feed`：读模型上下文，组合帖子、关注、互动状态生成信息流。

跨领域调用应尽量通过事件或明确的 application/query 接口完成。不要让消费方反向修改事件源领域的内部状态。

## Model 定义规则

- 模型放在拥有该事实的领域中，例如 `Post` 属于 `post.models`，`Follow` 属于 `follow.models`。
- 表名、字段、索引和关系名默认保持兼容，除非任务明确要求数据库迁移。
- 模型只表达持久化结构、关系和必要的轻量属性；复杂业务流程放在 `application.py`。
- 跨领域 relationship 可以存在，但业务代码应优先通过领域 application/query 表达意图。
- 不在模型层发布领域事件，不在模型层提交事务。

## Schema 定义规则

`schemas.py` 保存该领域的 API 边界 DTO，而不是数据库事实模型。

- 请求 DTO：例如 `PostCreate`、`CommentUpdate`，表达外部输入。
- 响应 DTO：例如 `PostResponse`、`NotificationListResponse`，表达公开 API 输出。
- 读模型 DTO：例如搜索结果、feed item、分页 meta。
- schema 可以引用其他领域的公开响应片段，但避免把大量内部 ORM 关系暴露为公共契约。
- API 路由的 `response_model` 应引用领域 schema；路由自身不再定义业务 DTO。

如果某个 DTO 只服务于单个 HTTP 入口，仍可放在对应领域的 `schemas.py`，不要回到全局 `app/schemas`。

## Application 与 Query 分工

`application.py` 放写侧用例：

- 创建、更新、删除、toggle、注册、登录等会改变事实状态的操作。
- 负责权限前置检查之外的核心业务规则。
- 负责调用 `publish_domain_event` 发布领域事件。
- 负责事务边界，优先使用 `commit_session`、`rollback_session` 或 `unit_of_work`。

`queries.py` 放读侧用例：

- 列表、详情、搜索结果组装、分页、当前用户增强状态。
- 不发布领域事件。
- 不执行会改变事实状态的副作用。

在迁移早期，如果某个领域暂时只有 `application.py`，可以先保留；当查询逻辑变厚时应拆出 `queries.py`。

## 领域事件模型

所有领域事件统一继承 `shared.events.DomainEvent`。

```python
from dataclasses import dataclass

from social_platform.app.shared.events import DomainEvent


@dataclass(frozen=True)
class PostCreated(DomainEvent):
    """帖子创建事件，由 post 领域发布。"""

    post_id: int
    author_id: int
```

事件定义规则：

- 事件由事件源领域定义。例如 `LikeChanged` 属于 `reaction.events`，`FollowChanged` 属于 `follow.events`。
- 消费方只订阅事件，不反向拥有事件类型。
- 事件名描述已经发生的领域事实，生命周期事件使用 `Created/Updated/Deleted`。
- toggle 类行为使用原子状态变化事件，不拆成两套方向事件。
- 事件只携带轻量、可复制的数据，例如资源 ID、操作者 ID、owner ID、必要快照。
- 事件中不要携带 ORM 对象，尤其不要把懒加载关系传给 `after_commit` 处理器。

toggle 事件必须表达前后状态：

```python
@dataclass(frozen=True)
class LikeChanged(DomainEvent):
    """点赞状态变化事件，由 reaction 或评论点赞用例发布。"""

    target_type: str
    target_id: int
    actor_id: int
    owner_id: int
    previous_state: bool
    current_state: bool
    post_id: int | None = None
```

推荐事件：

- `reaction.events.LikeChanged(previous_state, current_state, target_type, target_id, actor_id, owner_id, post_id | None)`
- `follow.events.FollowChanged(previous_state, current_state, follower_id, following_id)`
- `post.events.PostCreated/PostUpdated/PostDeleted/RepostCreated`
- `comment.events.CommentCreated/CommentDeleted`
- `user.events.UserCreated/UserUpdated/UserDeleted`

禁止继续新增方向事件：

- `PostLiked` / `PostUnliked`
- `CommentLiked` / `CommentUnliked`
- `UserFollowed` / `UserUnfollowed`

订阅者应根据 `previous_state` 和 `current_state` 自行判断是否响应。例如 notification 只在 `False -> True` 时生成点赞或关注通知。

## 事件发布规则

事件由写侧 application 在事实状态已经改变后发布。

```python
publish_domain_event(
    db,
    LikeChanged(
        target_type="post",
        target_id=post_id,
        actor_id=user_id,
        owner_id=post.author_id,
        previous_state=False,
        current_state=True,
        post_id=post_id,
    ),
)
```

发布规则：

- 如果事件需要新对象 ID，先 `db.flush()`，再发布事件。
- 同一事务内的计数、通知、热度等一致性副作用交给 `before_commit` 订阅者。
- 可重建投影或外部副作用交给 `after_commit` 订阅者。
- 发布事件的 application 仍然负责提交或回滚事务。
- 发布方不得直接调用通知、热度、搜索等消费方服务。
- 回滚后未提交事件会由事件总线清理，不应产生 `after_commit` 副作用。

## 事件总线概念

事件总线位于 `social_platform/app/shared/events.py`，是进程内同步领域事件总线。

核心 API：

- `DomainEvent`：所有领域事件的基类。
- `publish_domain_event(session, event)`：发布事件。
- `subscribe_domain_event(event_type, handler, phase=...)`：注册订阅处理器。
- `EventPhase`：事件处理阶段，当前支持 `before_commit` 和 `after_commit`。

处理阶段：

- `before_commit`：发布时立即执行，使用当前事务和当前数据库会话。
- `after_commit`：事件暂存在 `session.info`，事务提交成功后由 SQLAlchemy `after_commit` 钩子分发。

`before_commit` 适合：

- 创建通知记录。
- 修正计数。
- 刷新热度分数。
- 其他必须与主写操作同事务成功或失败的数据库副作用。

`after_commit` 适合：

- 搜索索引投影。
- SSE/长连接刷新信号。
- 分析统计。
- 推荐、feed、analytics 等可重建投影。
- 外部系统调用。

注意：

- `before_commit` 处理器抛错会阻止主事务提交。
- `after_commit` 处理器抛错会记录日志，不应破坏已提交事务。
- `after_commit` 处理器必须尽量幂等，可以重复 upsert/delete。
- 订阅器不要主动 `commit()` 当前业务事务；事务边界由 application 控制。

## 订阅规则

订阅器放在消费方领域。

```python
from social_platform.app.domains.reaction.events import LikeChanged
from social_platform.app.shared.events import subscribe_domain_event


def handle_like_changed(db: Session, event: LikeChanged) -> None:
    """消费点赞状态变化事件，生成通知或维护投影。"""


def register_notification_subscribers() -> None:
    """注册通知领域订阅器。"""

    subscribe_domain_event(LikeChanged, handle_like_changed, phase="before_commit")
```

订阅组织规则：

- `notification/subscribers.py` 订阅互动、关注、评论、转发事件来生成通知。
- `heat/subscribers.py` 订阅互动、评论、转发、帖子事件来刷新热度。
- `search/subscribers.py` 订阅帖子/用户变更事件来维护搜索投影。
- 未来 `feed`、`analytics`、`recommendation` 也应各自放置订阅器。

注册规则：

- 每个消费方领域提供 `register_xxx_subscribers()`。
- `domains/bootstrap.py` 统一导入并调用所有注册函数。
- 注册函数必须幂等；重复调用不应重复注册同一处理器。
- application 启动和事件发布入口可以调用 `ensure_domain_event_handlers_registered()` 确保订阅器已注册。

## API Router 规则

API 路由保留在 `social_platform/app/api/routers`，作为 HTTP adapter。

路由层允许做：

- FastAPI `Depends` 注入。
- 参数绑定和 response model 声明。
- 当前用户认证、基础权限入口。
- 捕获领域异常并映射为 HTTP status。
- 调用领域 application/query。

路由层不允许做：

- 直接维护点赞、关注、评论、通知、热度等业务状态。
- 直接发布领域事件。
- 直接调用其他领域消费方服务来制造副作用。
- 编写复杂排序、计数、投影维护规则。

## 迁移流程

每次迁移尽量完成一个领域闭环，而不是只搬文件。

建议步骤：

1. 明确该领域拥有的模型、schema、application、query、events、subscribers。
2. 将模型和 schema 移入领域目录，保持表结构和 API 响应兼容。
3. 将写侧用例移入 `application.py`，读侧逻辑移入 `queries.py`。
4. 在事件源领域定义事件，并在写侧用例中发布。
5. 在消费方领域新增或更新订阅器。
6. 从发布方删除对通知、热度、搜索等消费方服务的直接调用。
7. 更新 API、admin、tests、Agent 调用中的 import。
8. 删除已迁移的旧 `app/models`、`app/schemas`、`app/services` 文件，不创建 re-export。
9. 增加或更新最小测试，确认 API 行为和事件副作用稳定。

## 测试要求

领域迁移至少覆盖本次改动的最小测试集。

事件测试应覆盖：

- 事件 payload 的关键字段，尤其是 `previous_state` 和 `current_state`。
- toggle 订阅者只在目标状态变化方向符合要求时响应。
- `before_commit` 副作用与主事务一起提交或回滚。
- `after_commit` 投影只在提交成功后执行，回滚不执行。

领域行为测试应覆盖：

- 公开 API 响应结构保持兼容。
- 数据库计数和关系状态保持兼容。
- 搜索、热度、通知不再由事件源服务直接调用，而是由订阅器维护。
- identity 注册、登录、session、验证码等认证语义保持兼容。

常用最小验证命令：

```bash
python -m pytest social_platform/tests/test_domain_events.py
python -m pytest social_platform/tests/test_comment_service_flat_threads.py
python -m pytest social_platform/tests/test_search_service.py
```

涉及认证、通知、feed、moderation 时，应追加对应测试文件。

## 代码评审检查清单

提交前逐项确认：

- 新代码是否按业务领域归属，而不是按技术层放回全局目录？
- 事件是否由事件源领域定义和发布？
- 订阅器是否放在消费方领域？
- toggle 行为是否使用 `Changed` 事件并携带前后状态？
- `before_commit` 和 `after_commit` 阶段是否选择正确？
- 发布方是否还直接调用 notification、heat、search 等消费方服务？
- 路由层是否保持轻量？
- schema 是否位于领域目录，并保持公开 API 兼容？
- 已迁移旧文件是否删除，且没有新增 re-export？
- 新增函数、类、文件是否有类型注解和中文 docstring？
- 是否运行了覆盖本次迁移的最小测试？
