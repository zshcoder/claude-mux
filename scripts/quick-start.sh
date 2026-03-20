#!/usr/bin/env bash
set -e

# ========================================
# Claude Proxy Router 快速启动脚本
# ========================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# 加载 .env 如果存在
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# 默认值
AUTH_TOKEN="${AUTH_TOKEN:-sk-proxy-change-me}"
SERVER_PORT="${SERVER_PORT:-12346}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

echo "========================================"
echo "Claude Proxy Router 快速启动"
echo "========================================"
echo "端口: $SERVER_PORT"
echo "日志级别: $LOG_LEVEL"
echo "========================================"

python3 main.py --port "$SERVER_PORT" --log-level "$LOG_LEVEL"