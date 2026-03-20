#!/usr/bin/env bash
set -e

# ========================================
# Claude Proxy Router 一键安装脚本
# ========================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Claude Proxy Router 一键安装脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检测操作系统
OS="$(uname -s)"
case "${OS}" in
    Linux*)     IS_LINUX=1 ;;
    Darwin*)    IS_MAC=1 ;;
    *)          echo -e "${RED}[错误] 不支持的操作系统: ${OS}${NC}"; exit 1 ;;
esac

# ========================================
# 检测 Docker（推荐无 Python 用户使用）
# ========================================
check_docker() {
    command -v docker &> /dev/null && docker info &> /dev/null
}

# ========================================
# 主逻辑：根据环境选择最佳安装方式
# ========================================

INSTALL_METHOD=""
RUN_CMD=""

# 方案 1: 如果有 uv，使用 uvx（推荐）
if command -v uv &> /dev/null; then
    echo -e "[${GREEN}检测${NC}] 发现 uv，使用 uvx 方案"
    INSTALL_METHOD="uvx"
    RUN_CMD="uvx claude-mux"

# 方案 2: 如果有 Python3，使用 pip + 国内镜像
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "[${GREEN}检测${NC}] 发现 ${YELLOW}${PYTHON_VERSION}${NC}"

    # 设置国内镜像
    PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

    echo -e "[${GREEN}安装${NC}] 使用 pip + 清华镜像安装..."
    pip3 install -i "${PIP_MIRROR}" claude-mux --quiet 2>/dev/null || \
    pip3 install claude-mux

    INSTALL_METHOD="pip"
    RUN_CMD="claude-mux"

# 方案 3: 如果有 Docker（推荐无 Python 用户）
elif check_docker; then
    echo -e "[${GREEN}检测${NC}] 发现 Docker，使用容器方案"
    echo -e "${CYAN}提示${NC}: Docker 方案无需安装 Python，自动搞定一切"

    # 拉取镜像
    docker pull claude-mux:latest 2>/dev/null || \
    docker pull claude-mux:latest

    INSTALL_METHOD="docker"
    RUN_CMD="docker run -p 12346:12346 --env-file .env claude-mux"

# 无法安装
else
    echo -e "${RED}[错误] 未检测到 Python 和 Docker${NC}"
    echo ""
    echo "请选择以下方案之一："
    echo ""
    echo -e "方案 A: 安装 Python（推荐国内用户）"
    echo -e "  ${YELLOW}# 使用国内镜像安装 Python${NC}"
    echo -e "  # Windows: https://www.python.org/downloads/ 或用 pipx"
    echo -e "  # Linux:  sudo apt-get install python3 python3-pip"
    echo ""
    echo -e "方案 B: 安装 Docker"
    echo -e "  ${YELLOW}# Docker 包含 Python 环境，一步到位${NC}"
    echo -e "  # https://docs.docker.com/desktop/install/"
    echo ""
    echo -e "方案 C: 先安装 uv（uv 会自动下载 Python）"
    echo -e "  ${YELLOW}curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
    echo -e "  ${YELLOW}# 注意：uv 需要从 GitHub 下载 Python，国内可能较慢${NC}"
    exit 1
fi

# ========================================
# 创建配置文件
# ========================================
echo ""
echo -e "[${GREEN}配置${NC}] 正在生成配置文件..."
if [ -f ".env" ]; then
    echo "发现已有 .env 文件，跳过创建"
elif [ -f ".env.example" ]; then
    cp .env.example .env
    echo "已创建 .env 配置文件，请编辑设置 AUTH_TOKEN"
else
    echo -e "${YELLOW}[警告] 未找到 .env.example，创建默认配置${NC}"
    cat > .env << 'EOF'
AUTH_TOKEN=sk-proxy-change-me
DEFAULT_UPSTREAM=https://api.anthropic.com
SERVER_PORT=12346
LOG_LEVEL=INFO
LOG_FORMAT=console
EOF
fi

# ========================================
# 完成
# ========================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}安装完成！(${INSTALL_METHOD})${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "1. 编辑 ${YELLOW}.env${NC} 文件设置 AUTH_TOKEN"
echo -e "2. 运行: ${YELLOW}${RUN_CMD}${NC}"
echo ""
echo -e "详细文档: see ${YELLOW}README.md${NC}"
echo -e "${GREEN}========================================${NC}"