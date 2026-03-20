# Claude Proxy Router

基于 FastAPI 的智能代理路由器，根据 Claude 模型类型将请求自动路由到不同的上游服务器，实现**成本优化**和**渠道灵活配置**。

## 功能特性

- **智能路由**：根据模型名称自动路由到不同的上游服务器
- **通配符匹配**：支持模型名称通配符匹配（如 `claude-opus-*`、`glm-*`）
- **SSE 流式响应**：完整支持 Server-Sent Events 流式传输
- **代理认证**：内置 Token 认证机制，保护代理服务安全
- **结构化日志**：使用 structlog 支持 Console/JSON 双格式日志
- **高性能异步**：基于 FastAPI 和 httpx 的异步架构，支持连接池管理
- **CLI 工具**：内置 Token 生成和 Claude Code 配置工具

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

**国内网络提示**：uv 下载 Python 需要访问 GitHub（~50-100MB），国内可能较慢。如遇下载问题，建议使用 Docker 方案。

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

## 快速开始

### 1. 安装依赖

推荐使用 [uv](https://github.com/astral-sh/uv) 进行包管理：

```bash
# 安装 uv
pip install uv

# 安装依赖
uv sync
```

或使用传统 pip：

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制配置模板并编辑：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 代理认证 Token（必需，用于验证请求）
AUTH_TOKEN="sk-proxy-your-random-token-here"

# 默认上游 URL（模型不匹配任何规则时使用）
DEFAULT_UPSTREAM="https://api.anthropic.com"

# 服务器配置
SERVER_HOST="0.0.0.0"
SERVER_PORT="12346"

# 日志配置
LOG_LEVEL="INFO"           # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT="console"       # console（开发）或 json（生产）

# 路由组（逗号分隔）
ROUTE_NAMES="OPUS,SONNET,HAIKU"

# Opus 路由 -> Anthropic 官方 API
OPUS_PATTERN="claude-opus-*"
OPUS_UPSTREAM="https://api.anthropic.com"
OPUS_AUTH_TOKEN="sk-ant-your-opus-key"

# Sonnet 路由 -> 智谱AI (GLM)
SONNET_PATTERN="glm-*"
SONNET_UPSTREAM="https://open.bigmodel.cn/api/anthropic"
SONNET_AUTH_TOKEN="your-glm-key"

# Haiku 路由 -> MiniMax
HAIKU_PATTERN="MiniMax-*"
HAIKU_UPSTREAM="https://api.minimaxi.com/anthropic"
HAIKU_AUTH_TOKEN="your-minimax-key"
```

### 3. 运行服务

```bash
# 直接运行
python main.py

# 指定端口
python main.py --port 8080

# 使用 uvicorn
uvicorn main:app --host 0.0.0.0 --port 12346 --reload
```

### 4. 配置 Claude Code

使用内置 CLI 工具自动配置：

```bash
python main.py setup
```

或手动编辑 `~/.claude/settings.json`（Windows: `%USERPROFILE%\.claude\settings.json`）：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:12346",
    "ANTHROPIC_AUTH_TOKEN": "sk-proxy-your-random-token-here",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-4",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "MiniMax-"
  }
}
```

## CLI 工具

### 生成认证 Token

```bash
python main.py gen-token
# 输出示例: sk-proxy-abc123xyz... （将此设置为 AUTH_TOKEN 和 ANTHROPIC_AUTH_TOKEN）
```

### 配置 Claude Code

```bash
python main.py setup
# 交互式配置 Claude Code 的 settings.json
```

## API 端点

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/{path}` | POST | 代理所有请求到相应的上游服务器 | 必需 |
| `/health` | GET | 健康检查 | 可选 |
| `/` | GET | 服务信息 | 可选 |
| `/docs` | GET | API 文档（Swagger UI） | 可选 |

### 认证方式

通过请求头传递认证 Token（与 `AUTH_TOKEN` 一致）：

```bash
# 方式1：x-api-key 请求头
x-api-key: sk-proxy-your-token

# 方式2：Authorization Bearer
Authorization: Bearer sk-proxy-your-token
```

## 使用示例

### 调用 Opus 模型（路由到 Anthropic）

```bash
curl -X POST http://localhost:12346/v1/messages \
  -H "x-api-key: sk-proxy-your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-opus-",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'
```

### 调用 Sonnet 模型（路由到智谱AI）

```bash
curl -X POST http://localhost:12346/v1/messages \
  -H "x-api-key: sk-proxy-your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-4-flash",
    "messages": [{"role": "user", "content": "你好！"}],
    "max_tokens": 100
  }'
```

### Python 客户端

```python
import httpx

# 配置
BASE_URL = "http://localhost:12346"
API_KEY = "sk-proxy-your-token"

# 调用 Opus
response = httpx.post(
    f"{BASE_URL}/v1/messages",
    headers={"x-api-key": API_KEY},
    json={
        "model": "claude-opus-",
        "messages": [{"role": "user", "content": "Hello!"}],
        "max_tokens": 100
    }
)
print(response.json())

# 调用 Sonnet
response = httpx.post(
    f"{BASE_URL}/v1/messages",
    headers={"x-api-key": API_KEY},
    json={
        "model": "glm-4-flash",
        "messages": [{"role": "user", "content": "你好！"}],
        "max_tokens": 100
    }
)
print(response.json())
```

### 流式响应

```python
import httpx

with httpx.stream(
    "POST",
    "http://localhost:12346/v1/messages",
    headers={"x-api-key": "sk-proxy-your-token"},
    json={
        "model": "glm-4",
        "messages": [{"role": "user", "content": "介绍一下 Python"}],
        "max_tokens": 500,
        "stream": True
    }
) as response:
    for line in response.iter_lines():
        if line.strip():
            print(line.decode())
```

## 路由规则说明

路由匹配使用 `fnmatch` 通配符语法，按配置顺序依次匹配：

| 通配符 | 含义 | 示例 |
|--------|------|------|
| `*` | 匹配任意数量字符 | `claude-opus-*` 匹配 `claude-opus-20240229` |
| `?` | 匹配单个字符 | `model-?` 匹配 `model-a` 不匹配 `model-ab` |
| `[seq]` | 匹配 seq 中任意字符 | `model-[abc]` 匹配 `model-a` |
| `[!seq]` | 匹配不在 seq 中的字符 | `model-[!abc]` 匹配 `model-d` |

### 匹配示例

| 模型名称 | 匹配规则 | 路由到 |
|---------|---------|--------|
| `claude-opus-` | `OPUS_PATTERN="claude-opus-*"` | Anthropic |
| `claude-opus-20240229` | `OPUS_PATTERN="claude-opus-*"` | Anthropic |
| `glm-4` | `SONNET_PATTERN="glm-*"` | 智谱AI |
| `glm-4-flash` | `SONNET_PATTERN="glm-*"` | 智谱AI |
| `MiniMax-M2` | `HAIKU_PATTERN="MiniMax-*"` | MiniMax |
| `unknown-model` | 无匹配规则 → `DEFAULT_UPSTREAM` | Anthropic |

## 日志

### Console 格式（开发环境）

```
2024-03-20 10:30:45 [info] request_received model=glm-4 path=/v1/messages
2024-03-20 10:30:46 [info] request_success model=glm-4 status=200 duration=1.23
```

### JSON 格式（生产环境）

```json
{
  "event": "request_received",
  "model": "claude-opus-",
  "path": "/v1/messages",
  "timestamp": "2024-03-20T10:30:45.123Z",
  "level": "info"
}
```

### 配置日志

在 `.env` 中设置：

```bash
LOG_LEVEL="DEBUG"   # 输出详细调试信息
LOG_FORMAT="json"   # 生产环境使用 JSON 格式
```

## 项目结构

```
claude-mux/
├── main.py          # FastAPI 入口，代理端点，CLI 工具
├── router.py        # 智能路由器（fnmatch 通配符匹配）
├── client.py        # 上游 HTTP 客户端（SSE 流式转发）
├── config.py        # 环境变量配置管理
├── auth.py          # Token 认证
├── errors.py        # 自定义异常（5 种）
├── logger.py        # structlog 日志配置
├── .env.example     # 配置模板
├── pyproject.toml   # 项目元数据（uv）
├── requirements.txt # Python 依赖
└── README.md        # 项目文档
```

### 核心模块

| 模块 | 职责 |
|------|------|
| `main.py` | FastAPI 应用、请求代理、CLI 命令 |
| `router.py` | 模型路由匹配逻辑 |
| `client.py` | 上游请求转发、SSE 流式处理 |
| `config.py` | 从 `.env` 加载配置 |
| `auth.py` | Token 验证（防时序攻击） |
| `errors.py` | 异常定义和 HTTP 映射 |
| `logger.py` | 结构化日志配置 |
| `request_id_logging.py` | Request ID 日志增强（通用模块） |

## 请求追踪

每个请求自动生成唯一 `request_id`，绑定到日志上下文，方便追踪并发请求。

**详细文档**：[docs/request-id-guide.md](docs/request-id-guide.md)

## 部署

### Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 12346
CMD ["python", "main.py"]
```

构建运行：

```bash
docker build -t claude-proxy-router .
docker run -p 12346:12346 --env-file .env claude-proxy-router
```

### 生产环境部署

使用 Gunicorn + Uvicorn 多进程：

```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:12346
```

### Systemd 服务

创建 `/etc/systemd/system/claude-proxy.service`：

```ini
[Unit]
Description=Claude Proxy Router
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/claude-proxy
Environment="PATH=/opt/claude-proxy/.venv/bin"
ExecStart=/opt/claude-proxy/.venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable claude-proxy
sudo systemctl start claude-proxy
```

## 故障排查

### 常见问题

**1. 认证失败（401）**
```
认证失败: Invalid token
```
- 检查 `.env` 中的 `AUTH_TOKEN`
- 检查请求头 `x-api-key` 或 `Authorization: Bearer`

**2. 路由匹配失败**
```
routing_error: No route found for model: xxx
```
- 检查 `ROUTE_NAMES` 配置
- 检查 `{NAME}_PATTERN` 通配符是否正确
- 确认请求体中的 `model` 字段

**3. 上游连接失败**
```
upstream_connection_failed: Connection error
```
- 检查 `{NAME}_UPSTREAM` URL 是否正确
- 检查网络连接和防火墙
- 确认上游服务状态

**4. API 密钥无效**
```
401 Unauthorized from upstream
```
- 检查 `{NAME}_AUTH_TOKEN` 是否有效
- 确认上游账户余额和配额

### 调试模式

启用调试日志：

```bash
# .env
LOG_LEVEL="DEBUG"
LOG_FORMAT="console"
```

重启服务查看详细日志。

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.115+ | Web 框架 |
| httpx | 0.28+ | 异步 HTTP 客户端 |
| uvicorn | 0.32+ | ASGI 服务器 |
| structlog | 24.4+ | 结构化日志 |
| pydantic | 2.10+ | 数据验证 |
| python-dotenv | 1.0+ | 环境变量管理 |

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
