#!/bin/bash

# 黑塔树 - 停止脚本 (Linux/Ubuntu)
# 停止后端、前端和 AI 调度器

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "======================================"
echo "🛑 黑塔树 - 停止服务"
echo "======================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 停止函数
stop_service() {
    local name=$1
    local pid_file=$2
    
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null
            sleep 1
            # 如果还在运行，强制停止
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null
            fi
            echo -e "${GREEN}✅ $name 已停止 (PID: $PID)${NC}"
        else
            echo -e "${YELLOW}⚠️  $name 未在运行${NC}"
        fi
        rm -f "$pid_file"
    else
        # 尝试通过进程名停止
        echo -e "${YELLOW}⚠️  PID 文件不存在，尝试查找进程...${NC}"
        case $name in
            "后端服务")
                pkill -f "uvicorn app.main:app" 2>/dev/null
                ;;
            "前端服务")
                pkill -f "http.server 3000" 2>/dev/null
                ;;
            "AI 调度器")
                pkill -f "agent_schedular/main.py" 2>/dev/null
                ;;
        esac
    fi
}

# 停止所有服务
echo "正在停止服务..."
echo ""

stop_service "后端服务" "$SCRIPT_DIR/logs/backend.pid"
stop_service "前端服务" "$SCRIPT_DIR/logs/frontend.pid"
stop_service "AI 调度器" "$SCRIPT_DIR/logs/agent.pid"

echo ""
echo "======================================"
echo -e "${GREEN}✅ 所有服务已停止${NC}"
echo "======================================"
echo ""

# 清理日志目录（可选）
# rm -rf "$SCRIPT_DIR/logs"
