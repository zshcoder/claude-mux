# Claude Proxy Router 一键分发实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一行命令下载、安装和使用 Claude Proxy Router，考虑国内网络环境

**Architecture:** 提供多种安装方式：
1. **pipx + GitHub** - 最佳开发者体验
2. **pip + 国内镜像** - 兼容国内网络
3. **Docker** - 隔离环境
4. **一键安装脚本** - 智能检测网络环境

**Tech Stack:** Python 3.13+, pip, pipx, Docker, shell script

---

## 分发方案分析

### 方案对比

| 方案 | 安装命令 | 网络兼容性 | 依赖管理 | 适用场景 |
|------|----------|------------|----------|----------|
| pipx + GitHub | `pipx install git+...` | ⚠️ 需代理 | ⭐⭐⭐⭐⭐ | 开发者 |
| pip + 镜像 | `pip install -i ...` | ✅ 良好 | ⭐⭐⭐ | 国内用户 |
| Docker | `docker run ...` | ✅ 良好 | ⭐⭐⭐⭐ | 运维部署 |
| 一键脚本 | `curl ...\|bash` | ✅ 良好 | ⭐⭐⭐⭐⭐ | 快速体验 |

### 网络优化策略

1. **pip 镜像**: 优先使用清华、阿里云等国内镜像
2. **GitHub**: 提供镜像或代理建议
3. **Docker 镜像**: 使用国内镜像加速器

---

## 文件结构

```
claude-mux/
├── .github/
│   └── workflows/
│       └── release.yml          # 发布到 PyPI
├── scripts/
│   ├── install.sh               # Linux/macOS 一键安装
│   ├── install.bat              # Windows 一键安装
│   └── quick-start.sh           # 快速启动脚本
├── Dockerfile                   # Docker 构建文件
├── docker-compose.yml           # Docker Compose 配置
├── pyproject.toml               # 项目元数据（添加 scripts）
├── CLAUDE.md                    # 安装说明
└── README.md                    # 更新安装文档
```

---

## Task 1: 完善 pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 添加项目元数据和入口点**

```toml
[project]
name = "claude-mux"
version = "0.1.0"
description = "Claude Proxy Router - 智能代理路由器"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
keywords = ["claude", "proxy", "router", "anthropic", "api"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
]

dependencies = [
    "httpx[http2]>=0.28.1",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "structlog>=24.4.0",
    "pydantic>=2.10.0",
    "python-dotenv>=1.0.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.28.0",
]

[project.scripts]
claude-mux = "main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
```

- [ ] **Step 2: 更新版本号**

```toml
version = "0.1.0"  # 改为 "1.0.0" 表示正式发布
```

- [ ] **Step 3: 提交**

```bash
git add pyproject.toml
git commit -m "feat: 完善项目元数据和入口点配置"
```

---

## Task 2: 创建 Windows 一键安装脚本

**Files:**
- Create: `scripts/install.bat`

- [ ] **Step 1: 创建 install.bat**

```batch
@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo Claude Proxy Router 一键安装脚本
echo ========================================
echo.

:: 检测 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 获取 Python 版本
for /f "delims=" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo 检测到: %PYTHON_VERSION%

:: 设置 pip 镜像（国内网络优化）
set PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple
set PIP_INDEX_URL=%PIP_MIRROR%

echo.
echo [1/4] 正在更新 pip...
python -m pip install --upgrade pip -i %PIP_MIRROR% --quiet

echo.
echo [2/4] 正在安装 Claude Proxy Router...
pip install claude-mux -i %PIP_MIRROR%
if errorlevel 1 (
    echo [错误] 安装失败，尝试使用官方源...
    pip install claude-mux
    if errorlevel 1 (
        echo [错误] 安装失败，请检查网络连接
        pause
        exit /b 1
    )
)

echo.
echo [3/4] 正在生成配置文件...
:: 检查是否已有 .env
if exist ".env" (
    echo 发现已有 .env 文件，跳过创建
) else (
    copy .env.example .env >nul 2>&1
    if exist ".env" (
        echo 已创建 .env 配置文件，请编辑设置 AUTH_TOKEN
    ) else (
        echo [警告] 未找到 .env.example，创建默认配置
        (
            echo AUTH_TOKEN=sk-proxy-change-me
            echo DEFAULT_UPSTREAM=https://api.anthropic.com
            echo SERVER_PORT=12346
        ) > .env
    )
)

echo.
echo [4/4] 安装完成！
echo.
echo ========================================
echo 快速开始:
echo.
echo 1. 编辑 .env 文件设置 AUTH_TOKEN
echo 2. 运行: claude-mux
echo    或: python -m main
echo.
echo 详细文档: see README.md
echo ========================================
pause
```

- [ ] **Step 2: 提交**

```bash
git add scripts/install.bat
git commit -m "feat: 添加 Windows 一键安装脚本"
```

---

## Task 3: 创建 Linux/macOS 一键安装脚本

**Files:**
- Create: `scripts/install.sh`

- [ ] **Step 1: 创建 install.sh**

```bash
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
```

- [ ] **Step 2: 设置执行权限**

```bash
chmod +x scripts/install.sh
```

- [ ] **Step 3: 提交**

```bash
git add scripts/install.sh
git commit -m "feat: 添加 Linux/macOS 一键安装脚本"
```

---

## Task 4: 创建快速启动脚本

**Files:**
- Create: `scripts/quick-start.sh`

- [ ] **Step 1: 创建 quick-start.sh**

```bash
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
```

- [ ] **Step 2: 设置执行权限并提交**

```bash
chmod +x scripts/quick-start.sh
git add scripts/quick-start.sh
git commit -m "feat: 添加快速启动脚本"
```

---

## Task 5: 创建 Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: 创建优化的 Dockerfile**

```dockerfile
# 构建阶段
FROM python:3.13-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 升级 pip
RUN pip install --no-cache-dir --upgrade pip

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 运行时阶段
FROM python:3.13-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制已安装的包
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY . .

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 12346

# 使用 tini 初始化
ENTRYPOINT ["tini", "--"]
CMD ["python", "main.py"]
```

- [ ] **Step 2: 提交**

```bash
git add Dockerfile
git commit -m "feat: 添加优化版 Dockerfile"
```

---

## Task 6: 创建 Docker Compose 配置

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: 创建 docker-compose.yml**

```yaml
version: "3.8"

services:
  claude-proxy:
    build: .
    image: claude-mux:latest
    container_name: claude-proxy
    ports:
      - "12346:12346"
    environment:
      - AUTH_TOKEN=${AUTH_TOKEN:-sk-proxy-change-me}
      - DEFAULT_UPSTREAM=${DEFAULT_UPSTREAM:-https://api.anthropic.com}
      - SERVER_PORT=12346
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - LOG_FORMAT=${LOG_FORMAT:-console}
      - OPUS_PATTERN=${OPUS_PATTERN:-claude-opus-*}
      - OPUS_UPSTREAM=${OPUS_UPSTREAM:-https://api.anthropic.com}
      - OPUS_AUTH_TOKEN=${OPUS_AUTH_TOKEN:-}
      - SONNET_PATTERN=${SONNET_PATTERN:-glm-*}
      - SONNET_UPSTREAM=${SONNET_UPSTREAM:-https://open.bigmodel.cn/api/anthropic}
      - SONNET_AUTH_TOKEN=${SONNET_AUTH_TOKEN:-}
      - HAIKU_PATTERN=${HAIKU_PATTERN:-MiniMax-*}
      - HAIKU_UPSTREAM=${HAIKU_UPSTREAM:-https://api.minimaxi.com/anthropic}
      - HAIKU_AUTH_TOKEN=${HAIKU_AUTH_TOKEN:-}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:12346/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

- [ ] **Step 2: 创建 .dockerignore**

```dockerignore
__pycache__
*.pyc
*.pyo
*.pyd
.Python
.env
.venv
venv/
.git
.gitignore
.vscode
*.md
!README.md
docs/
scripts/
.kiro/
*.log
```

- [ ] **Step 3: 提交**

```bash
git add docker-compose.yml .dockerignore
git commit -m "feat: 添加 Docker Compose 配置"
```

---

## Task 7: 更新 README.md 安装文档

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 添加一键安装章节**

在 README.md 的 "快速开始" 章节之前添加：

```markdown
## 一键安装

### 推荐：uvx（最简单，无需预先安装）

```bash
# 一行命令即可运行（自动创建临时环境）
curl -LsSf https://astral.sh/uv/uvx-install.sh | sh && uvx claude-mux
```

或分步执行：

```bash
# 1. 安装 uv（如果还没有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 直接运行 claude-mux（无需安装！）
uvx claude-mux
```

### uvx 工作原理

```bash
uvx claude-mux
```

执行流程：
1. **uv 检测本地是否有 Python**（通过 `uv python find`）
2. **如果没有，自动下载 Python**（安装到 `~/.local/share/uv/python/`）
3. **创建临时虚拟环境**（在 `~/.cache/uv*/...`，不影响系统）
4. **下载 claude-mux 包**（从 PyPI）
5. **在临时环境中运行**

| 组件 | 来源 | 存放位置 |
|------|------|----------|
| uv | 一键安装脚本 | `~/.local/bin/uv` |
| Python | uv 自动下载 | `~/.local/share/uv/python/` |
| 临时环境 | uv 自动创建 | `~/.cache/uv*/...` |
| claude-mux | 从 PyPI 下载 | 临时环境中 |

**结论**：`uvx` 只需要安装 `uv` 这一个小工具，就能自动搞定 Python + claude-mux。

### uvx 工作原理

```bash
uvx claude-mux
```

执行流程：
1. **uv 检测本地是否有 Python**（通过 `uv python find`）
2. **如果没有，自动下载 Python**（安装到 `~/.local/share/uv/python/`）
3. **创建临时虚拟环境**（在 `~/.cache/uv*/...`，不影响系统）
4. **下载 claude-mux 包**（从 PyPI）
5. **在临时环境中运行**

| 组件 | 来源 | 存放位置 |
|------|------|----------|
| uv | 一键安装脚本 | `~/.local/bin/uv` |
| Python | uv 自动下载 | `~/.local/share/uv/python/` |
| 临时环境 | uv 自动创建 | `~/.cache/uv*/...` |
| claude-mux | 从 PyPI 下载 | 临时环境中 |

**⚠️ 国内网络提示**：uv 下载 Python 需要访问 GitHub（~50-100MB），国内可能较慢。如遇下载问题，建议使用 Docker 方案。

### uvx 特性

| 特性 | 说明 |
|------|------|
| **无需安装** | 直接运行，不影响系统 |
| **版本指定** | `uvx claude-mux==1.0.0` |
| **GitHub 运行** | `uvx --from git+https://github.com/... claude-mux` |
| **全球最快** | 比 pipx 快 10-100 倍 |

### Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/claude-mux/main/scripts/install.sh | bash
```

### Windows

在 PowerShell 中运行：

```powershell
irm https://raw.githubusercontent.com/YOUR_USERNAME/claude-mux/main/scripts/install.bat | iex
```

或下载 `scripts/install.bat` 后双击运行。

### Docker（推荐）

```bash
# 克隆并启动
git clone https://github.com/YOUR_USERNAME/claude-mux.git
cd claude-mux
docker-compose up -d
```

### PyPI 安装

```bash
pip install claude-mux
```

---

## Task 8: 验证安装流程

- [ ] **Step 1: 测试 pip 安装（需先发布到 PyPI）**

```bash
# 本地测试 wheel 构建
pip install build
python -m build

# 验证 wheel
pip install dist/*.whl
claude-mux --help
```

- [ ] **Step 2: 测试 Docker 构建**

```bash
docker build -t claude-mux:test .
docker run -p 12346:12346 --env-file .env claude-mux:test
curl http://localhost:12346/health
```

- [ ] **Step 3: 测试脚本执行**

```bash
# Linux/macOS
./scripts/install.sh
./scripts/quick-start.sh

# Windows
scripts\install.bat
```

---

## Task 9: 创建 GitHub Actions 发布工作流

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: 创建发布工作流**

```yaml
name: Release to PyPI

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build

      - name: Build package
        run: python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          user: __token__
          password: ${{ secrets.PYPI_API_TOKEN }}
```

- [ ] **Step 2: 提交**

```bash
git add .github/workflows/release.yml
git commit -m "ci: 添加 PyPI 发布工作流"
```

---

## Task 10: 最终检查并更新版本

- [ ] **Step 1: 更新版本号为 1.0.0**

```bash
# 编辑 pyproject.toml
version = "1.0.0"
```

- [ ] **Step 2: 创建 GitHub Release 说明**

```markdown
## Claude Proxy Router v1.0.0

### 一键安装

**Linux/macOS:**
```bash
curl -fsSL https://install.claude-mux.dev | bash
```

**Windows:**
```powershell
irm https://install.claude-mux.dev/win | iex
```

**Docker:**
```bash
docker pull claude-mux:latest
docker run -p 12346:12346 -e AUTH_TOKEN=your-token claude-mux
```

### 主要功能
- 智能路由：根据模型名称自动路由到不同上游
- 通配符匹配：支持 fnmatch 通配符
- SSE 流式响应：完整支持 Server-Sent Events
- 认证保护：内置 Token 认证
- 结构化日志：Console/JSON 双格式
```

- [ ] **Step 3: 提交并打标签**

```bash
git add -A
git commit -m "feat: 完成一键分发功能 v1.0.0"
git tag v1.0.0
git push origin main --tags
```

---

## 安装命令汇总

| 安装方式 | 命令 | 网络优化 | 适用场景 |
|----------|------|----------|----------|
| **uvx（推荐）** | `curl -LsSf https://astral.sh/uv/uvx-install.sh \| sh && uvx claude-mux` | ✅ 极速 | 快速体验、零门槛 |
| **pipx** | `pipx install claude-mux` | ⚠️ 需代理 | 开发者长期使用 |
| **pip + 镜像** | `pip install claude-mux -i https://pypi.tuna.tsinghua.edu.cn/simple` | ✅ | 常规安装 |
| **Docker** | `docker run -p 12346:12346 claude-mux` | ✅ 镜像加速 | 隔离环境 |
| **Docker Compose** | `docker-compose up -d` | ✅ | 生产部署 |

---

## 网络优化说明

1. **pip 镜像**: 默认使用清华镜像 (`https://pypi.tuna.tsinghua.edu.cn/simple`)
2. **GitHub**: 建议用户配置代理或使用镜像站点
3. **Docker**: 使用 `docker mirror` 配置国内镜像加速器

---

## 后续工作（可选）

1. **注册 PyPI 账号** 并获取 API Token
2. **配置 GitHub Secrets** 中的 `PYPI_API_TOKEN`
3. **创建 install.claude-mux.dev 域名** 指向安装脚本
4. **发布到 AUR** (Arch Linux 用户)
5. **发布到 Homebrew** (macOS 用户)
