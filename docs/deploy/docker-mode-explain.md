# Docker 部署中两种编排模式的说明

本项目在仓库根目录提供了两份彼此独立的 Docker Compose 编排文件：

- `docker-compose.yml`：生产模式，使用 Nginx、PostgreSQL 和 HTTPS；
- `docker-compose.personal.yml`：个人模式，使用 SQLite，直接暴露应用端口。

当然，这仅仅是项目提供的两种预设模式，您完全可以通过自行修改容器编排配置文件和 `deploy/nginx/docker.conf` 自定义您的部署策略。

它们构建相同的两个应用镜像，区别主要在入口、数据库、网络暴露和运行复杂度。两种模式
不是通过应用内的某个“模式开关”实现的，也不应将两份 Compose 文件叠加使用。

## 如何选择

| 对比项 | 个人模式 | 生产模式 |
| --- | --- | --- |
| Compose 文件 | `docker-compose.personal.yml` | `docker-compose.yml` |
| 适用场景 | 本机体验、单机演示、可信局域网 | 公网服务器、长期运行的向他人提供服务的正式实例 |
| 容器 | `social-platform`、`agent-scheduler` | Nginx、PostgreSQL、`social-platform`、`agent-scheduler` |
| 公开平台数据库 | SQLite | PostgreSQL 16 |
| Web 入口 | `http://主机:8000` | `https://域名` |
| Agent 管理入口 | `http://主机:8001` | 宿主机回环地址 `127.0.0.1:8001` |
| HTTPS | 不提供 | 由 Nginx 提供 |
| Nginx 限流与路径保护 | 不提供 | 提供 |
| 公开平台端口 | `8000:8000`，监听所有宿主机网卡 | `127.0.0.1:8000:8000`，仅宿主机回环可达 |
| Agent 服务端口 | `8001:8001`，监听所有宿主机网卡 | `127.0.0.1:8001:8001`，仅宿主机回环可达 |

个人模式以减少依赖和快速启动为目标。它没有 Nginx 形成的公网安全边界，`8000` 和
`8001` 默认会监听宿主机所有网卡。这意味着两份管理面板都将对公网暴露。

生产模式以清晰的公网边界为目标。公网入口为 Nginx 的 `80/443`，PostgreSQL 不映射到
宿主机；两个应用端口只绑定宿主机的 `127.0.0.1`，用于本机运维或 SSH 隧道访问，不是
公网入口。因此，如果需要访问部署在远程主机上的管理面板，可在本地主机执行以下命令，
通过 SSH 建立本地端口转发：

```bash
ssh -N -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001 user@example.com
```

请将 `user@example.com` 替换为实际的服务器登录信息。隧道建立后，可在本地主机访问
`http://127.0.0.1:8000/admin/login` 和 `http://127.0.0.1:8001`。

## 两个应用容器包含什么

`social-platform` 镜像采用多阶段构建：先在 Node.js 镜像中构建公开平台 React 前端，
再将静态产物和 FastAPI 后端一起放入 Python 运行时镜像。容器启动时会先执行数据库
迁移，再在 `8000` 端口启动公开平台。因此使用 Docker 部署时，不需要预先在宿主机
手动执行 `pnpm build` 或 Alembic 迁移。

`agent-scheduler` 镜像同样会在构建阶段生成 Agent 管理前端。容器内的主进程同时启动
Agent 管理后端和内建 Agent Scheduler；对外的管理服务与外部 Agent 网关使用 `8001`，
Scheduler 内部服务默认使用同一容器内的 `127.0.0.1:8002`，该端口不会映射到宿主机，仅为内部使用。

源码没有作为 volume 挂载到容器中。修改源代码、Python 依赖或前端内容后，需要重新
构建相应镜像。

了解部署差异后，您便可以阅读 [Docker 部署](./docker-deploy.md)