# Python 打包构建指南：python -m build 与 hatchling

> 本文档沉淀自 Claude Code 对话，介绍 Python 现代化打包流程的核心概念。

## 概述

Python 项目使用 `python -m build` 实现标准化构建，所有配置集中于 `pyproject.toml`，无需传统的 `setup.py`。

## python -m build 工作原理

### 构建流程

```bash
python -m build
    │
    ├── 1. 读取 pyproject.toml 配置
    │
    ├── 2. 解析 [build-system] 确定构建后端
    │
    ├── 3. 创建隔离虚拟环境
    │
    ├── 4. 安装构建后端（如 hatchling）
    │
    ├── 5. 调用后端执行构建
    │       ├── 生成 wheel (.whl) - 二进制分发
    │       └── 生成 sdist (.tar.gz) - 源码分发
    │
    └── 6. 输出到 dist/ 目录
```

### 产出文件

```
dist/
├── claude_mux-1.0.0-py3-none-any.whl    # Wheel 文件
└── claude_mux-1.0.0.tar.gz              # 源码包
```

| 格式 | 说明 | 安装速度 | 跨平台 |
|------|------|----------|--------|
| Wheel (.whl) | 二进制预编译 | ⚡ 快 | 可能有平台限制 |
| sdist (.tar.gz) | 源码包 | 🐢 慢 | ✅ 通用 |

## pyproject.toml 核心配置

### 构建系统配置

```toml
[build-system]
requires = ["hatchling"]          # 构建依赖
build-backend = "hatchling.build" # 实际执行构建的后端
```

- `requires`：构建时需要安装的包
- `build-backend`：指定构建后端工具

### 项目元数据

```toml
[project]
name = "claude-mux"                    # 包名
version = "1.0.0"                      # 版本号（发布时被 sed 替换）
description = "Claude Proxy Router"    # 描述
requires-python = ">=3.10"             # Python 版本要求
dependencies = [                        # 运行时依赖
    "httpx[http2]>=0.28.1",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
]
```

### CLI 入口点

```toml
[project.scripts]
claude-mux = "main:main"  # 安装后生成 claude-mux 命令
```

### hatchling 特定配置

```toml
[tool.hatch.build.targets.wheel]
packages = ["."]  # 包含当前目录下所有代码
```

## 构建后端对比

| 构建后端 | 特点 | 配置复杂度 | 适用场景 |
|----------|------|------------|----------|
| **hatchling** | 现代化、简洁、插件丰富 | ⭐ 低 | 新项目、版本管理需求 |
| setuptools | 传统、功能强大 | ⭐⭐⭐ 高 | 遗留项目、复杂打包 |
| flit | 极简、纯 pyproject | ⭐ 低 | 纯 Python 简单包 |
| pdm | 包管理 + 构建一体化 | ⭐⭐ 中 | 完整包管理工作流 |

## 为什么选择 hatchling

### 1. 简洁的配置

```toml
# hatchling（当前项目）
[tool.hatch.build.targets.wheel]
packages = ["."]

# setuptools 等效配置（更复杂）
[options]
packages = find:
package_dir = {"" = "."}
include_package_data = true

[tool.setuptools.find]
where = ["."]
include = ["*"]
exclude = ["tests*", "docs*"]
```

### 2. 内置版本管理

hatch 可直接管理版本，与 Git 标签集成良好：

```bash
hatch version      # 显示当前版本
hatch version 1.0.1  # 更新版本
```

### 3. 插件生态系统

```toml
[build-system]
requires = ["hatchling", "hatch-vcs"]  # 自动从 Git 获取版本
```

常用插件：
- `hatch-vcs`：从 Git 标签自动获取版本
- `hatch-fancy-pypi-readme`：美化 PyPI 页面
- `hatch-nodejs-version`：Node.js 版本同步

### 4. 性能优化

- 增量构建缓存
- 并行处理优化
- 构建速度比 setuptools 快

## 切换构建后端示例

### 切换到 setuptools

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[options]
packages = find:
```

### 切换到 flit

```toml
[build-system]
requires = ["flit_core>=3.2"]
build-backend = "flit_core.buildapi"
```

## 版本号管理机制

本项目采用 **"标签驱动版本"** 策略：

```
pyproject.toml:  version = "1.0.0"  # 占位符
Git 标签:        v1.0.4             # 实际版本源
发布时:          sed 替换 → version = "1.0.4"
```

### GitHub Actions 中的版本替换

```yaml
- name: Set version from tag
  run: |
    TAG=${GITHUB_REF#refs/tags/}    # v1.0.4
    VERSION=${TAG#v}                 # 1.0.4
    sed -i "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
```

### 环境变量对照表

| GITHUB_REF 值 | ${TAG#v} 结果 |
|---------------|---------------|
| `refs/tags/v1.0.4` | `1.0.4` |
| `refs/tags/v2.0.0` | `2.0.0` |
| `refs/heads/main` | 不触发 |

## 相关标准

| PEP | 说明 |
|-----|------|
| PEP 517 | 构建系统接口标准 |
| PEP 518 | 构建依赖规范 |
| PEP 621 | 项目元数据标准 |
| PEP 660 | 可编辑安装标准 |

## 验证构建结果

```bash
# 本地构建
pip install build
python -m build

# 检查 wheel 内容
unzip -l dist/claude_mux-1.0.0-py3-none-any.whl

# 检查 sdist 内容
tar -tzf dist/claude_mux-1.0.0.tar.gz

# 本地安装测试
pip install dist/*.whl
claude-mux --help
```

## 相关文档

- [GitHub Actions PyPI 发布配置](github-actions-pypi-release.md) - CI/CD 发布流程
- [pyproject.toml](../pyproject.toml) - 项目配置源码
- [.github/workflows/release.yml](../.github/workflows/release.yml) - 发布工作流
