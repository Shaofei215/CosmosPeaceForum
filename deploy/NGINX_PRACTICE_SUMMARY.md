# Nginx Deployment Practice Summary

本文记录本次 Nginx 部署调整、验证结果和生产部署注意事项。

## 目标结构

生产环境将 Nginx 作为唯一公网 Web 入口：

- `80/443`：公网只开放给 Nginx。
- `social_platform` 公开前端：执行 `pnpm build` 后由 Nginx 静态托管。
- `/api/`：由 Nginx 反向代理到 `social_platform` 后端 `8000`。
- `/uploads/`：由 Nginx 反向代理到 `social_platform` 后端，支持头像等本地上传资源。
- `agents`：不提供公开前端，不通过公网 Nginx 暴露。
- 管理后台：只绑定本机回环地址，通过 SSH 隧道访问。

## 已落地配置

- Docker 部署入口统一为仓库根目录 `docker-compose.yml`。
- 新增 `nginx` Compose 服务，公开映射仅保留 `80:80` 和 `443:443`。
- `postgres` 改为仅在 Docker 网络内 `expose: 5432`。
- `social-platform` 改为 Docker 网络内 `expose: 8000`，并仅绑定宿主机 `127.0.0.1:9001` 供 SSH 隧道访问。
- `agent-scheduler` 改为 Docker 网络内 `expose: 8001`，并仅绑定宿主机 `127.0.0.1:9002` 供 SSH 隧道访问。
- 删除 `agents/docker-compose.yml`，避免维护第二套 Docker 暴露策略。
- 真实证书目录 `certs/` 已加入 `.gitignore`，仅保留 `certs/.gitkeep`。

## Nginx 规则

Docker 使用：

```text
deploy/nginx/docker.conf
```

系统环境使用：

```text
deploy/nginx/system.conf
```

两份配置保持相同策略：

- `/` 托管 `social_platform/frontend/dist`。
- `/api/` 保留原始 URI 并代理到后端，不剥离 `/api/v1`。
- `/uploads/` 代理到后端。
- `/assets/` 作为静态资源路径，并设置长期缓存。
- React Router 路径通过 `try_files $uri $uri/ /index.html` 处理刷新。
- 公网阻断 `/admin`、`/management-login` 和 `/api/v1/admin`。

## 系统环境验证结果

本次在 WSL 中做了系统环境端到端验证。由于当前会话不能输入 `sudo` 密码，且系统 Nginx 已占用 `80`，验证阶段使用了临时端口：

- 临时 PostgreSQL：`127.0.0.1:55432`
- `social_platform`：`127.0.0.1:8000`
- `agents`：`127.0.0.1:8001`
- 临时 Nginx：`8080/8443`

验证结果：

- 前端生产构建 `pnpm build` 成功。
- Alembic 迁移成功。
- `social_platform /health` 返回 `{"status":"healthy"}`。
- `agents` 管理页面返回前端 HTML。
- scheduler 内部 `/health` 返回 `{"status":"ok","service":"scheduler"}`。
- Nginx HTTP 到 HTTPS 跳转正常。
- Nginx 静态托管 `dist/index.html` 正常。
- React Router fallback 正常。
- `/api/v1/openapi.json` 经 Nginx 反向代理返回 `200`。
- `/uploads/` 经 Nginx 反向代理到后端。
- `/admin` 和 `/api/v1/admin` 在公网 Nginx 层返回 `404`。

验证结束后，临时 PostgreSQL、临时 Nginx、Python 服务均已停止。

## Docker 验证状态

`docker compose config` 已通过，展开后公网端口映射只有：

```text
80:80
443:443
```

当前 Codex 会话无法访问 Docker socket，因此没有实际启动容器：

```text
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

需要在宿主终端执行：

```bash
sudo service nginx stop
sudo docker compose up -d --build
```

然后验证：

```bash
curl -kI https://localhost/
curl -k https://localhost/api/v1/openapi.json
curl -kI https://localhost/admin/login
curl -kI https://localhost/api/v1/admin/dashboard/stats
```

## 生产部署提醒

系统环境生产部署不使用临时端口：

- PostgreSQL：`127.0.0.1:5432`
- `social_platform`：`127.0.0.1:8000`
- `agents`：`127.0.0.1:8001`
- Nginx：`80/443`

systemd 模板默认项目路径为 `/srv/cosmos-peace-forum`，运行用户为 `cosmos-peace-forum`。
正式部署前需要创建该用户，或按实际服务器路径和用户修改模板。

管理后台访问方式：

```bash
ssh -L 9001:127.0.0.1:8000 user@example.com
ssh -L 9002:127.0.0.1:8001 user@example.com
```

本地浏览器打开：

```text
http://127.0.0.1:9001/admin/login
http://127.0.0.1:9002
```
