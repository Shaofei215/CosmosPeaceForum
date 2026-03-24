# 🐳 Herta-Tree Docker 部署指南

## 📋 目录

- [快速开始](#快速开始)
- [开发环境](#开发环境)
- [生产环境](#生产环境)
- [常用命令](#常用命令)
- [故障排查](#故障排查)

---

## 🚀 快速开始

### 1. 环境准备

确保已安装：
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，修改必要配置
# 特别注意修改 JWT_SECRET_KEY 和 ADMIN_KEY
```

### 3. 启动服务

**开发模式（推荐开发使用）：**

```bash
# 启动后端 + 前端开发服务器
docker-compose --profile dev up -d

# 访问地址：
# - 前端: http://localhost:5173
# - 后端 API: http://localhost:8000
# - API 文档: http://localhost:8000/docs
```

**生产模式：**

```bash
# 启动后端 + 前端生产构建
docker-compose --profile prod up -d

# 访问地址：
# - 前端: http://localhost
# - 后端 API: http://localhost:8000
```

---

## 💻 开发环境

### 服务架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend Dev  │────▶│    Backend      │────▶│    SQLite DB    │
│    :5173        │     │    :8000        │     │   /app/data     │
│  (Vite dev)     │     │  (FastAPI)      │     │  (持久化卷)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 开发特性

- ✅ **热重载**：代码修改自动刷新
- ✅ **源码映射**：支持调试
- ✅ **独立数据库**：数据持久化在 `./data` 目录

### 开发命令

```bash
# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend-dev

# 进入容器调试
docker-compose exec backend bash
docker-compose exec frontend-dev sh

# 重启服务
docker-compose restart backend
```

---

## 🏭 生产环境

### 服务架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     Nginx       │────▶│    Backend      │────▶│    SQLite DB    │
│     :80         │     │    :8000        │     │   /app/data     │
│  (静态文件)      │     │  (FastAPI)      │     │  (持久化卷)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 生产优化

- ✅ **多阶段构建**：减小镜像体积
- ✅ **Nginx 服务**：高效静态文件服务
- ✅ **Gzip 压缩**：减少传输体积
- ✅ **静态缓存**：长期缓存静态资源

### 生产部署

```bash
# 1. 修改环境变量
vim .env
# 设置 DEBUG=false
# 修改 JWT_SECRET_KEY 和 ADMIN_KEY 为强密码

# 2. 启动生产环境
docker-compose --profile prod up -d

# 3. 查看状态
docker-compose ps
```

---

## 🛠️ 常用命令

### 基础操作

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 停止并删除数据卷（慎用）
docker-compose down -v

# 查看日志
docker-compose logs -f [service]

# 查看状态
docker-compose ps
```

### 数据管理

```bash
# 备份数据库
cp -r data data-backup-$(date +%Y%m%d)

# 查看数据库文件
ls -lh data/

# 进入数据库（需要安装 sqlite3）
sqlite3 data/herta_tree.db
```

### 镜像管理

```bash
# 查看镜像
docker images | grep herta

# 删除镜像
docker rmi herta-tree-backend herta-tree-frontend

# 清理未使用镜像
docker image prune
```

---

## 🔧 故障排查

### 常见问题

#### 1. 端口被占用

```bash
# 错误：bind: address already in use
# 解决：修改 .env 中的端口配置或停止占用端口的进程

# 查看端口占用
lsof -i :8000
lsof -i :5173
lsof -i :80

# 停止占用进程
kill -9 <PID>
```

#### 2. 数据库权限错误

```bash
# 错误：unable to open database file
# 解决：检查 data 目录权限

chmod 755 data
chmod 644 data/herta_tree.db
```

#### 3. 前端无法连接后端

```bash
# 检查后端健康状态
curl http://localhost:8000/health

# 查看后端日志
docker-compose logs backend

# 检查 CORS 配置（开发环境）
# 确保 vite.config.ts 中的代理配置正确
```

#### 4. 镜像构建失败

```bash
# 清理构建缓存
docker-compose build --no-cache

# 检查网络连接（需要下载基础镜像）
docker pull python:3.11-slim
docker pull node:20-alpine
```

### 调试技巧

```bash
# 查看容器详细信息
docker inspect herta-backend

# 查看网络配置
docker network ls
docker network inspect herta-network

# 进入容器执行命令
docker-compose exec backend python -c "from app.main import app; print(app)"

# 测试数据库连接
docker-compose exec backend python -c "from app.db.session import engine; print(engine)"
```

---

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | Docker Compose 主配置 |
| `.env` | 环境变量配置（需自行创建） |
| `.env.example` | 环境变量模板 |
| `app_platform/Dockerfile` | 后端生产镜像 |
| `frontend/Dockerfile` | 前端生产镜像 |
| `frontend/Dockerfile.dev` | 前端开发镜像 |
| `frontend/nginx.conf` | Nginx 配置 |
| `app_platform/.dockerignore` | 后端构建忽略文件 |
| `frontend/.dockerignore` | 前端构建忽略文件 |

---

## 🔒 安全建议

1. **修改默认密钥**：生产环境必须修改 `JWT_SECRET_KEY` 和 `ADMIN_KEY`
2. **关闭调试模式**：生产环境设置 `DEBUG=false`
3. **使用 HTTPS**：生产环境建议配合反向代理使用 HTTPS
4. **定期备份**：定期备份 `./data` 目录中的数据库文件
5. **限制访问**：使用防火墙限制端口访问

---

## 📚 参考链接

- [FastAPI 部署文档](https://fastapi.tiangolo.com/deployment/)
- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)

---

*Happy Dockerizing! 🐳*
