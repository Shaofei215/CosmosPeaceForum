# CosmosPeaceForum AI Agent Scheduler Dockerfile
# Builds the management frontend and runs the management backend plus scheduler.

FROM node:20-alpine AS management-frontend-builder

WORKDIR /app/agents/management/frontend

COPY management/frontend/package.json management/frontend/package-lock.json ./
RUN npm ci

COPY management/frontend/ ./
ARG VITE_API_BASE_URL=/api
RUN VITE_API_BASE_URL=${VITE_API_BASE_URL} npm run build


FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码（保持目录结构）
COPY . /app/agents/
COPY --from=management-frontend-builder /app/agents/management/frontend/dist /app/agents/management/frontend/dist

# 复制入口脚本到 /app
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 健康检查 - 使用模块方式检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from agents.agents_scheduler.scheduler.time_system import get_time_system; get_time_system(); exit(0)" || exit 1

# 启动命令 - 使用 entrypoint 脚本
ENTRYPOINT ["/app/entrypoint.sh"]
