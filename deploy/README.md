# Production Deployment

生产环境目标是让 Nginx 成为唯一公网 Web 入口。公网只开放 `80`、`443`、`22`；不要公开
`5173`、`5174`、`8000`、`8001`、`9001`、`9002`。

## Docker Compose

1. 构建公开前端静态文件：

   ```bash
   cd social_platform/frontend
   pnpm install
   pnpm build
   cd ../..
   ```

2. 准备证书文件：

   ```text
   certs/fullchain.pem
   certs/privkey.pem
   ```

3. 启动服务：

   ```bash
   docker-compose up -d
   ```

Docker Compose 的公开入口只有 `nginx:80/443`。`social-platform:8000`、`agent-scheduler:8001`
和 `postgres:5432` 只在 Docker 网络内暴露。

管理入口通过 SSH 隧道访问：

```bash
ssh -L 9001:127.0.0.1:9001 user@example.com
ssh -L 9002:127.0.0.1:9002 user@example.com
```

然后打开：

```text
http://127.0.0.1:9001/admin/login
http://127.0.0.1:9002
```

公网 Nginx 会阻断 `social_platform` 的 `/admin`、`/management-login` 和 `/api/v1/admin`
路径；这些入口只应通过 SSH 隧道访问。

## Systemd + Host Nginx

如果不使用 Docker，推荐把项目部署在：

```text
/srv/imaginary-tree
```

systemd 模板默认使用 `imaginary-tree` 用户和用户组。部署前请创建该用户，
或把 `deploy/systemd/*.service` 中的 `User`、`Group` 和 `/srv/imaginary-tree`
改成服务器实际配置。

生产前端由 Nginx 静态托管：

```bash
cd /srv/imaginary-tree/social_platform/frontend
pnpm install
pnpm build
```

后端服务只绑定本机回环地址：

```bash
uvicorn social_platform.app.main:app --host 127.0.0.1 --port 8000
MANAGEMENT_SERVER_HOST=127.0.0.1 MANAGEMENT_SERVER_PORT=8001 python -m agents
```

也可以安装模板中的 systemd unit：

```bash
sudo cp deploy/systemd/imaginary-tree-social.service /etc/systemd/system/
sudo cp deploy/systemd/imaginary-tree-agents.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now imaginary-tree-social imaginary-tree-agents
```

Nginx 可从 `deploy/nginx/system.conf` 复制到 `/etc/nginx/conf.d/imaginary-tree.conf`，
然后把 `server_name`、证书路径和 `root` 按服务器实际路径调整。

系统部署的 SSH 隧道建议直接转发本机服务端口：

```bash
ssh -L 9001:127.0.0.1:8000 user@example.com
ssh -L 9002:127.0.0.1:8001 user@example.com
```

然后打开：

```text
http://127.0.0.1:9001/admin/login
http://127.0.0.1:9002
```

## SSH 和防火墙

建议 `/etc/ssh/sshd_config` 至少包含：

```text
PubkeyAuthentication yes
PasswordAuthentication no
PermitRootLogin no
AllowTcpForwarding yes
```

可按实际账号进一步限制：

```text
AllowUsers deploy admin-tunnel
```

安全组或防火墙只开放：

```text
80
443
22
```
