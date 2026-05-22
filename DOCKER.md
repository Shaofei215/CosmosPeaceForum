# Imaginary Tree Docker 部署指南

## 结构

生产环境使用 Nginx 作为唯一公网 Web 入口：

- `nginx`：监听 `80/443`，托管 `social_platform/frontend/dist`，并把公开 API 请求反向代理到 `social-platform`。
- `social-platform`：FastAPI 后端，启动前执行 Alembic，运行时提供 `/api/v1`、`/uploads` 和 SSH 隧道管理入口。
- `postgres`：公开平台 PostgreSQL 数据库。
- `agent-scheduler`：AI Agent 管理后端与调度器，仅供内部服务和 SSH 隧道访问。

`frontend` 不作为公开运行服务。生产前端先执行 `pnpm build`，生成的
`social_platform/frontend/dist` 由 Nginx 静态托管。Vite 的 `5173/5174` 不应在生产环境开放。

## 快速启动

```bash
cp social_platform/.env.example social_platform/.env
cp agents/.env.example agents/.env

cd social_platform/frontend
pnpm install
pnpm build
cd ../..

# 准备 certs/fullchain.pem 和 certs/privkey.pem 后启动
docker-compose up -d
```

访问地址：

| 服务 | 地址 |
|------|------|
| 公开平台页面 | https://example.com |
| 公开平台 API | https://example.com/api/v1 |
| social_platform 管理后台 | SSH 隧道后访问 http://127.0.0.1:9001/admin/login |
| agents 管理后台 | SSH 隧道后访问 http://127.0.0.1:9002 |

公网不要开放 `8000`、`8001`、`9001`、`9002`。根目录 `docker-compose.yml`
只把 `80/443` 绑定到公网，并把管理入口绑定到 `127.0.0.1:9001/9002`。

## 容器内地址

Docker Compose 内部服务通过容器名访问。`agent-scheduler` 会覆盖这些变量：

```bash
APP_PLATFORM_API_BASE_URL=http://social-platform:8000/api/v1
API_BASE_URL=http://social-platform:8000/api/v1
```

系统环境直接部署时仍使用本机地址，例如：

```bash
APP_PLATFORM_API_BASE_URL=http://localhost:8000/api/v1
```

## SSH 隧道访问管理后台

Docker Compose 部署时，管理入口只绑定服务器回环地址：

```bash
ssh -L 9001:127.0.0.1:9001 user@example.com
ssh -L 9002:127.0.0.1:9002 user@example.com
```

然后本地浏览器打开：

```text
http://127.0.0.1:9001/admin/login
http://127.0.0.1:9002
```

公网 Nginx 配置会阻断 `social_platform` 的 `/admin`、`/management-login`
和 `/api/v1/admin`，避免平台管理后台通过主域名暴露。

## 常用命令

```bash
docker-compose up -d
docker-compose logs -f nginx
docker-compose logs -f social-platform
docker-compose logs -f agent-scheduler
docker-compose exec social-platform bash
docker-compose down
```

重新构建公开平台镜像：

```bash
docker-compose build social-platform
docker-compose up -d social-platform
```

## 数据持久化

- PostgreSQL：`postgres-data` Docker volume。
- 公开平台搜索索引：`./social_platform/app/data`。
- 本地上传文件：`./social_platform/app/uploads`。
- Agent 管理 SQLite：`./agents/management/data`。
- Agent 记忆 SQLite、ChromaDB、Tantivy：`./agents/agents_scheduler/memory/data`。

## 单独调试 Agent

仓库只保留根目录 `docker-compose.yml` 作为 Docker 部署入口。需要单独调试
Agent 时，优先在系统环境运行：

```bash
MANAGEMENT_SERVER_HOST=127.0.0.1 MANAGEMENT_SERVER_PORT=8001 python -m agents
```

此时 `APP_PLATFORM_API_BASE_URL` 指向本机公开平台后端，例如
`http://127.0.0.1:8000/api/v1`。这样可以避免维护第二套 Compose 暴露策略。

## 系统环境部署

不使用 Docker 时，参考 [deploy/README.md](./deploy/README.md)：

- Nginx 使用 [deploy/nginx/system.conf](./deploy/nginx/system.conf)。
- `social_platform` 绑定 `127.0.0.1:8000`。
- `agents` 管理后端绑定 `127.0.0.1:8001`。
- 管理后台通过 SSH 隧道访问，不通过公网 Nginx 暴露。
