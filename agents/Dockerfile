# Herta-Tree AI Agent Scheduler Dockerfile
# 用于 AI 用户调度的长时间运行服务

FROM m.daocloud.io/docker.io/library/python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt --only-binary :all:

# 复制应用代码（保持目录结构）
COPY . /app/agents/

# 复制入口脚本到 /app
COPY entrypoint.sh /app/entrypoint.sh

# 健康检查 - 使用模块方式检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from agents.agents_scheduler.scheduler.time_system import get_time_system; get_time_system(); exit(0)" || exit 1

# 启动命令 - 使用 entrypoint 脚本
ENTRYPOINT ["/app/entrypoint.sh"]
