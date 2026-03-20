# GitHub Actions PyPI 自动发布配置

## 概述

本项目使用 GitHub Actions 实现 **PyPI 自动发布**：只需推送 `v*` 标签，即可自动构建并发布到 PyPI。

## 工作流文件

**位置**: `.github/workflows/release.yml`

```yaml
name: Release to PyPI

on:
  push:
    tags:
      - 'v*'   # 只有推送 v 开头的标签才触发

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

      - name: Set version from tag
        run: |
          TAG=${GITHUB_REF#refs/tags/}
          VERSION=${TAG#v}
          sed -i "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
          cat pyproject.toml | grep "^version"

      - name: Build package
        run: |
          rm -rf dist/
          python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          user: __token__
          password: ${{ secrets.PYPI_API_TOKEN }}
```

## 版本号机制

**重要**：`pyproject.toml` 中的版本号是**占位符**，实际发布的版本号由 **git tag** 决定。

### 本地 pyproject.toml
```toml
version = "1.0.0"  # 占位符，本地开发用
```

### 发布流程中的版本替换

```bash
# 1. 打标签（TAG=v1.0.4）
git tag v1.0.4

# 2. GitHub Actions 中自动替换
TAG=${GITHUB_REF#refs/tags/}   # v1.0.4
VERSION=${TAG#v}                # 1.0.4
sed -i "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
# pyproject.toml 变成: version = "1.0.4"
```

### 为什么需要 sed 替换？

- `pyproject.toml` 硬编码版本号（如 "1.0.0"）
- `python -m build` 从 `pyproject.toml` 读取版本号
- GitHub Actions 每次 checkout 是干净的代码
- 如果不替换，构建出来的还是旧版本

### GITHUB_REF 环境变量

| GITHUB_REF 值 | ${TAG#v} 结果 |
|---------------|----------------|
| `refs/tags/v1.0.4` | `1.0.4` |
| `refs/tags/v2.0.0` | `2.0.0` |
| `refs/heads/main` | 不触发（不是 tags） |

## 触发机制

| 事件 | 是否触发发布 |
|------|-------------|
| 推送代码 (`git push`) | ❌ |
| 推送普通标签 | ❌ |
| 推送 `v*` 标签 | ✅ |

### 触发示例

```bash
# 不触发
git tag v1.0.0-beta
git push origin v1.0.0-beta

# 触发发布
git tag v1.0.0
git push origin v1.0.0
```

## 配置步骤

### 1. 注册 PyPI 账号

1. 访问 [https://pypi.org](https://pypi.org)
2. 注册账号并验证邮箱

### 2. 生成 API Token

1. 登录 PyPI
2. 进入 **Account Settings** → **API tokens**
3. 点击 **Add API token**
4. 选择范围：
   - **Entire account**: 可发布所有包
   - **Scope to a specific package**: 只发布指定包（推荐）
5. 复制生成的 token（格式: `pypi-xxx`）

### 3. 配置 GitHub Secrets

1. 打开 GitHub 仓库
2. 进入 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 填写：
   - **Name**: `PYPI_API_TOKEN`
   - **Secret**: 你的 PyPI API Token

### 4. 发布新版本

```bash
# 确保代码已提交
git add -A
git commit -m "release: v1.0.0"

# 推送代码（不触发发布）
git push origin master

# 打标签并推送（触发发布）
git tag v1.0.0
git push origin v1.0.0
```

## 发布流程

```
┌─────────────────────────────────────────────────────────────┐
│  git push origin v1.0.4                                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub Actions 检测到 v* 标签                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Checkout 代码（干净的环境）                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 设置 Python 3.13                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 安装 build 工具                                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: sed 替换版本号（v1.0.4 → pyproject.toml）         │
│           sed -i "s/^version = \".*\"/version = \"1.0.4\""│
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: rm -rf dist/ 清理旧构建                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6: python -m build 构建新版本                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 7: pypa/gh-action-pypi-publish 发布到 PyPI           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  ✅ 发布成功，可在 PyPI 查看 v1.0.4                         │
└─────────────────────────────────────────────────────────────┘
```

## 验证发布

发布成功后，访问 [https://pypi.org/project/claude-mux/](https://pypi.org/project/claude-mux/) 查看。

## 常见问题

### Q: 推送标签后没有触发 Actions？

检查标签是否正确推送：
```bash
git tag -l           # 列出所有本地标签
git ls-remote --tags # 列出所有远程标签
```

### Q: 发布失败 "File already exists"？

说明该版本已发布过。PyPI 不允许重复发布同一版本。

### Q: 发布失败 "Invalid credentials"？

检查 `PYPI_API_TOKEN` 是否正确配置在 GitHub Secrets 中。

### Q: 想发布到 Test PyPI？

可以添加另一个 workflow 使用 Test PyPI：
```yaml
- name: Publish to Test PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    user: __token__
    password: ${{ secrets.TEST_PYPI_API_TOKEN }}
    repository-url: https://test.pypi.org/legacy/
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `pyproject.toml` | Python 项目配置，包含包名、版本（占位符）、依赖 |
| `.github/workflows/release.yml` | GitHub Actions 发布工作流 |
| `dist/` | 构建输出目录（自动生成，被 .gitignore 忽略）|
| `docs/debug-notes.md` | 包含发布问题的排查记录 |

## 故障排查记录

### v1.0.1 失败：dist/ 未清理

**问题**：上传的是旧版本的 wheel 文件。

**原因**：`python -m build` 使用了 `dist/` 目录中残留的旧文件。

**修复**：
```yaml
- name: Build package
  run: |
    rm -rf dist/    # 先清理
    python -m build
```

### v1.0.2 失败：版本号硬编码

**问题**：PyPI 上传的是 `claude_mux-1.0.0-py3-none-any.whl`。

**原因**：`pyproject.toml` 中 `version = "1.0.0"` 是硬编码，`python -m build` 总是构建 1.0.0 版本。

**修复**：
```yaml
- name: Set version from tag
  run: |
    TAG=${GITHUB_REF#refs/tags/}
    VERSION=${TAG#v}
    sed -i "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
```

**相关 commit**：`6d70e16`、`3adf581`

## 后续优化（可选）

1. **发布前运行测试**：
   ```yaml
   - name: Run tests
     run: pytest
   ```

2. **同时发布到 Test PyPI 和正式 PyPI**

3. **自动生成 GitHub Release**

4. **发布到 Conda-forge**（社区维护的 conda 源）
