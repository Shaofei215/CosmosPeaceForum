# PostgreSQL 配置库合并与备份策略

本文档说明 Imaginary Tree 后续数据库治理方向：哪些数据应该迁移到 PostgreSQL，哪些不应该合并，以及运营时如何做定时备份。

## 结论

建议把“需要长期保存、需要热更新、需要审计和备份”的事实状态统一放入 PostgreSQL，但不要把所有运行期产物都塞进 PostgreSQL。

推荐目标形态：

| 数据 | 建议位置 | 说明 |
| --- | --- | --- |
| app_platform 业务数据 | PostgreSQL: `imaginary_tree` | 用户、帖子、评论、点赞、关注、通知等核心业务数据 |
| app_platform 管理数据 | PostgreSQL: `imaginary_tree`，独立表前缀或 schema | 平台管理员、审计日志、主题配置、用户处罚状态 |
| agents/management 配置数据 | PostgreSQL: `imaginary_tree_management` | Agent 配置、模型配置、Embedding 配置、系统热更新配置、管理后台账号 |
| Agent 长期记忆主记录 | 暂时保留 SQLite，后续单独评估 | 当前与 ChromaDB/Tantivy 三写绑定，迁移优先级低于管理配置库 |
| ChromaDB、Tantivy、搜索索引 | 不合并到 PostgreSQL | 这些是可重建索引或专用存储，不是主事实数据 |
| 日志文件、临时缓存 | 不合并到 PostgreSQL | 后续可接入日志系统或对象存储 |

## 为什么配置库也建议迁到 PostgreSQL

把热更新配置放在 SQLite 里是可行的，但不再是最合适的选择。

热更新真正需要的是：

- 服务运行时可以读取最新配置；
- 管理后台可以写入配置；
- Scheduler 可以感知配置变化并 reload；
- 配置变更可备份、可追踪、可恢复。

这些需求 PostgreSQL 都能满足，而且比 SQLite 更适合当前项目：

- 多进程和多容器访问更稳；
- 备份方式统一；
- 后续可以加审计、事务、权限和迁移；
- 不再依赖本地文件路径和容器挂载；
- 避免多个 SQLite 文件散落在不同目录。

## 不建议直接混成一个数据库的原因

可以共用同一个 PostgreSQL 实例，但不建议所有表无边界混在一起。

推荐至少分两个 database：

```text
imaginary_tree
imaginary_tree_management
```

这样有几个好处：

- 业务库和管理配置库可以独立备份、恢复；
- 管理后台出问题时不直接污染业务库；
- Alembic migration 边界清楚；
- 权限可以分开授权；
- 将来拆服务或迁移云数据库更容易。

如果部署很小，也可以先共用一个 PostgreSQL 实例，只是 database 分开即可。

## 迁移顺序建议

### 第一阶段：已完成或当前目标

- app_platform 业务数据库切换到 PostgreSQL；
- app_platform schema 变更走 Alembic；
- agents/management SQLite 不再启动时补列，先由 Alembic 管 schema；
- memory SQLite 补列逻辑收口成版本化迁移。

### 第二阶段：迁移 management 配置库

目标是把以下表迁到 PostgreSQL 的 `imaginary_tree_management`：

- `admin_users`
- `agent_configs`
- `model_configs`
- `chunk_model_configs`
- `embedding_configs`
- `system_configs`
- `operation_logs`

建议新增：

- `MANAGEMENT_DATABASE_URL=postgresql+psycopg://.../imaginary_tree_management`
- management 专用 Alembic migration；
- 一次性 `sqlite -> postgresql` 数据搬运脚本；
- 搬运后的数据量和关键配置校验。

迁移完成后，Scheduler 继续通过 `ManagementDBClient` 读取配置，但底层实现应从 sqlite3 直连改为 SQLAlchemy/SQLModel，避免绑定 SQLite SQL 方言。

### 第三阶段：评估 Agent memory

Agent memory 当前不是普通配置，它同时涉及：

- SQLite 主记录；
- ChromaDB 向量索引；
- Tantivy BM25 索引。

这部分暂时不建议和配置库一起迁。后续如果要迁 PostgreSQL，应先明确：

- 是否要把 memory chunk 作为长期核心资产；
- 是否需要跨机器共享；
- 是否需要按 Agent 做备份和恢复；
- 是否继续使用 ChromaDB/Tantivy 作为派生索引。

## 备份策略

需要定时备份，而且建议新增独立的数据库备份脚本或备份服务。

不建议把备份逻辑放进 FastAPI 后端、Scheduler 或业务定时任务里。数据库备份是运维职责，应独立于业务进程运行，这样即使后端服务异常，备份仍然可以执行。

推荐结构：

```text
ops/
  backup/
    backup_postgres.sh
    restore_postgres.sh
```

如果暂时不想新增 `ops/` 目录，也可以先把脚本放在 `scripts/backup_postgres.sh`，但长期建议集中到 `ops/backup/`。

## 备份频率

开发或实验环境：

- 每天一次全量备份；
- 每次数据库 migration 前手动备份一次。

小规模线上环境：

- 每天一次全量备份；
- 保留最近 7 天每日备份；
- 保留最近 4 周每周备份；
- 重要发版前额外备份。

更正式的线上环境：

- 每天全量备份；
- 开启 WAL 归档或云数据库 PITR；
- 定期做恢复演练。

## 备份脚本建议

`backup_postgres.sh` 应至少做这些事：

- 使用 `pg_dump` 导出指定 database；
- 文件名带时间戳；
- 备份目录可配置；
- 成功后压缩；
- 删除超出保留期的旧备份；
- 失败时返回非 0 exit code，方便 cron/systemd 告警。

示例逻辑：

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"

docker-compose exec -T postgres pg_dump \
  -U imaginary_tree \
  imaginary_tree \
  | gzip > "$BACKUP_DIR/imaginary_tree-$TIMESTAMP.sql.gz"

docker-compose exec -T postgres pg_dump \
  -U imaginary_tree \
  imaginary_tree_management \
  | gzip > "$BACKUP_DIR/imaginary_tree_management-$TIMESTAMP.sql.gz"

find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
```

注意：上面的 `imaginary_tree_management` 需要等 management 配置库迁到 PostgreSQL 后才启用。迁移前，management SQLite 仍需单独备份。

## management SQLite 过渡期备份

在 management 配置库迁入 PostgreSQL 前，仍要备份：

```bash
agents/management/data/management.db
```

可以在 PostgreSQL 备份脚本里临时加：

```bash
cp agents/management/data/management.db \
  "$BACKUP_DIR/management-$TIMESTAMP.db"
gzip "$BACKUP_DIR/management-$TIMESTAMP.db"
```

等 management 迁到 PostgreSQL 后，再删除这段 SQLite 备份逻辑。

## 定时方式

推荐用宿主机 cron 或 systemd timer，不推荐用业务容器里的 APScheduler。

cron 示例：

```cron
15 3 * * * cd /path/to/imaginary-tree && BACKUP_DIR=/data/backups ./ops/backup/backup_postgres.sh
```

systemd timer 更适合长期运行的服务器，因为日志、失败状态和重试更清楚。

## 恢复演练

备份没有恢复演练就不算真正可用。建议至少每月做一次：

1. 新建一个空数据库；
2. 从最新备份恢复；
3. 跑应用 smoke test；
4. 检查用户数、帖子数、评论数、配置项数量；
5. 记录恢复耗时和问题。

恢复命令示例：

```bash
gunzip -c backups/postgres/imaginary_tree-20260522-030000.sql.gz \
  | docker-compose exec -T postgres psql -U imaginary_tree -d imaginary_tree
```

## 发版前检查清单

涉及数据库变更时：

- 先备份；
- 确认 Alembic revision 已提交；
- 在临时库跑 `alembic upgrade head`；
- 确认应用启动不再创建表或补列；
- 发版后检查 `alembic_version`；
- 验证核心接口和管理后台配置读取。

## 当前还需要做的事

- 编写 management `sqlite -> postgresql` 数据迁移脚本；
- 将 `ManagementDBClient` 从 sqlite3 改为 SQLAlchemy/SQLModel；
- 新增 `ops/backup/backup_postgres.sh` 和 `ops/backup/restore_postgres.sh`；
- 为备份目录加入 `.gitignore`；
- 在部署文档里补充 cron/systemd timer 配置；
- 做一次旧 app_platform SQLite 到 PostgreSQL 的数据迁移决策：如果旧数据要保留，需要专门搬运。
