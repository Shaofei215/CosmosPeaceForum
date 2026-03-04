#!/bin/bash

# 黑塔树 - 实时日志查看脚本 (Linux/Mac)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

LOGS_DIR="$SCRIPT_DIR/logs"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "======================================"
echo "📊 黑塔树 - 实时日志查看"
echo "======================================"
echo ""

# 检查日志目录
if [ ! -d "$LOGS_DIR" ]; then
    echo -e "${YELLOW}⚠️  日志目录不存在，请先启动服务${NC}"
    echo "   运行：./start.sh"
    exit 1
fi

# 检查日志文件
LOG_FILES=$(find "$LOGS_DIR" -name "*.log" -type f 2>/dev/null)

if [ -z "$LOG_FILES" ]; then
    echo -e "${YELLOW}⚠️  未找到日志文件，请先启动服务${NC}"
    echo "   运行：./start.sh"
    exit 1
fi

echo -e "${GREEN}✓ 找到以下日志文件:${NC}"
echo ""

i=1
for file in $LOG_FILES; do
    filename=$(basename "$file")
    echo "   $i. $filename"
    i=$((i+1))
done

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}按 Ctrl+C 退出日志查看${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# 使用 tail -f 实时查看所有日志
tail -f "$LOGS_DIR"/*.log
