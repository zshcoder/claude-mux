# uv / uvx 安装 claude-mux 详细指南

## 概述

本文档详细介绍如何使用 `uv` 和 `uvx` 安装和运行 claude-mux，包括下载位置、配置方法等。

---

## uv 与 uvx 的区别

| 命令 | 行为 | 适用场景 |
|------|------|----------|
| `uvx claude-mux` | 每次创建**临时环境**，用完可能清理 | 临时试用、快速体验 |
| `uv tool install claude-mux` | 永久安装到系统，**长期使用** | 日常使用、部署 |

---

## 方式一：uvx 临时运行（推荐先试用）

### 1. 安装 uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

### 2. 直接运行

```bash
uvx claude-mux
```

### 3. uvx 工作原理

```
uvx claude-mux
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  1. 检测本地是否有 Python                            │
│     - 有：使用本地 Python                           │
│     - 无：自动下载 Python 到 ~/.local/share/uv/     │
└─────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  2. 创建临时虚拟环境                                │
│     位置：~/.cache/uv/uvx-once-xxx/               │
└─────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  3. 从 PyPI 下载 claude-mux                       │
│     安装到临时环境中                                │
└─────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  4. 运行 claude-mux                               │
└─────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  5. 退出后，临时环境可能被清理                      │
│     (uv 会缓存以便下次更快启动)                      │
└─────────────────────────────────────────────────────┘
```

### 4. uvx 缓存位置

**Linux/macOS**：
```
~/.cache/uv/
```

**Windows**：
```
C:\Users\<用户名>\AppData\Local\uv\cache\
```

### 5. 缺点

- **临时环境**：每次运行可能不同位置
- **.env 配置麻烦**：需要在项目目录运行，或用 `--env-file` 指定

---

## 方式二：uv tool install 永久安装（推荐日常使用）

### 1. 安装 uv（同上）

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

### 2. 永久安装 claude-mux

```bash
uv tool install claude-mux
```

### 3. 安装位置

**Linux/macOS**：
```
~/.local/share/uv/tools/claude-mux/
```

**Windows**：
```
C:\Users\<用户名>\AppData\Roaming\uv\tools\claude-mux\
```

### 4. 目录结构（Windows 详解）

```
C:\Users\<用户名>\AppData\Roaming\uv\tools\claude-mux\
│
├── Scripts\                    # Windows 可执行文件
│   └── claude-mux.exe         # 主程序入口
│
├── Lib\
│   └── site-packages\         # Python 包目录
│       ├── main.py            ← 你的源代码
│       ├── router.py
│       ├── client.py
│       ├── config.py
│       ├── auth.py
│       ├── logger.py
│       ├── errors.py
│       ├── middleware\
│       │   ├── __init__.py
│       │   └── request_id.py
│       └── ...                ← 所有依赖
│
├── pyvenv.cfg                 # 虚拟环境配置
├── uv-receipt.toml            # uv 安装收据
└── CACHEDIR.TAG
```

### 5. 验证安装

```bash
# 查看已安装的工具
uv tool list

# 查找可执行文件位置
where claude-mux          # Windows
which claude-mux          # Linux/macOS
```

### 6. 常用命令

```bash
# 列出已安装的工具
uv tool list

# 升级工具
uv tool upgrade claude-mux

# 卸载工具
uv tool uninstall claude-mux

# 重新安装
uv tool uninstall claude-mux && uv tool install claude-mux
```

---

## 配置 .env 文件

### 问题

uvx 或 uv tool install 安装的 claude-mux 运行时，**不会自动找到项目目录下的 .env 文件**。

### 解决方案

#### 方案一：在项目目录下运行（推荐）

```bash
cd /path/to/your/project    # 进入项目目录（有 .env 的地方）
claude-mux                  # 直接运行，会自动加载当前目录的 .env
```

#### 方案二：指定 env-file

```bash
uvx claude-mux --env-file /path/to/.env

# 或
claude-mux --env-file /path/to/.env
```

#### 方案三：设置环境变量

```bash
# Linux/macOS
export AUTH_TOKEN="sk-proxy-your-token"
export DEFAULT_UPSTREAM="https://api.anthropic.com"
claude-mux

# Windows (PowerShell)
$env:AUTH_TOKEN="sk-proxy-your-token"
$env:DEFAULT_UPSTREAM="https://api.anthropic.com"
claude-mux
```

---

## 完整安装流程（Windows 示例）

### 步骤 1：安装 uv

```powershell
# 打开 PowerShell，运行：
irm https://astral.sh/uv/install.ps1 | iex
```

### 步骤 2：验证 uv 安装

```powershell
uv --version
# 输出类似：uv 0.8.22
```

### 步骤 3：安装 claude-mux

```powershell
uv tool install claude-mux
```

### 步骤 4：验证安装

```powershell
# 查看已安装工具
uv tool list

# 查找程序位置
where claude-mux
# 输出：
# C:\Users\<用户名>\AppData\Roaming\uv\tools\claude-mux\Scripts\claude-mux.exe
# C:\Users\<用户名>\.local\bin\claude-mux.exe
```

### 步骤 5：配置 .env

在项目目录下创建或编辑 `.env` 文件：

```bash
AUTH_TOKEN=sk-proxy-your-token
DEFAULT_UPSTREAM=https://api.anthropic.com
SERVER_PORT=12346
LOG_LEVEL=INFO
LOG_FORMAT=console
```

### 步骤 6：运行

```powershell
# 进入项目目录
cd D:\path\to\claude-mux-project

# 运行（会自动加载当前目录的 .env）
claude-mux
```

---

## 卸载

```bash
# 卸载 claude-mux
uv tool uninstall claude-mux

# 卸载 uv（如果需要）
# Linux/macOS: rm ~/.local/bin/uv ~/.local/bin/uvx
# Windows: 删除 C:\Users\<用户名>\.local\bin\uv.exe
```

---

## 常见问题

### Q: uvx 和 uv tool install 哪个更好？

| 场景 | 推荐 |
|------|------|
| 想先试用一下 | `uvx claude-mux` |
| 日常使用 | `uv tool install claude-mux` |
| 需要配置 .env | `uv tool install` + 在项目目录运行 |

### Q: .env 文件放在哪里？

**uv tool install**：在项目目录运行即可自动加载。

**uvx**：需要在项目目录运行，或用 `--env-file` 指定。

### Q: 如何查看 claude-mux 安装在哪里？

```bash
where claude-mux    # Windows
which claude-mux    # Linux/macOS
```

### Q: 如何更新到新版本？

```bash
uv tool upgrade claude-mux
```

### Q: Windows 上找不到 .local 目录？

Windows 上 uv 默认安装在：
```
C:\Users\<用户名>\AppData\Roaming\uv\
```

可用以下方式打开：
1. 按 `Win + R`
2. 输入 `%AppData%`
3. 回车

---

## 架构图：uvx vs uv tool install

```
┌─────────────────────────────────────────────────────────────┐
│                      用户操作                               │
│  uvx claude-mux          uv tool install claude-mux        │
└─────────────────────────────────────────────────────────────┘
            │                              │
            ▼                              ▼
┌───────────────────────┐    ┌───────────────────────────────┐
│    临时环境            │    │       永久环境               │
│  ~/.cache/uv/         │    │  ~/.local/share/uv/tools/   │
│  (每次可能不同)        │    │  (固定位置)                  │
└───────────────────────┘    └───────────────────────────────┘
            │                              │
            ▼                              ▼
┌───────────────────────┐    ┌───────────────────────────────┐
│   用完可能清理         │    │       长期保留               │
│   适合试用             │    │       适合日常使用            │
└───────────────────────┘    └───────────────────────────────┘
```

---

## 总结

| 安装方式 | 命令 | .env 加载 | 适用场景 |
|----------|------|-----------|----------|
| uvx 临时 | `uvx claude-mux` | 需在项目目录或用 --env-file | 快速试用 |
| uv tool 安装 | `uv tool install claude-mux` | 在项目目录运行自动加载 | **日常使用（推荐）** |

**推荐日常使用 `uv tool install claude-mux`**，然后在项目目录下运行即可。
