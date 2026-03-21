---
name: pypi-release
description: PyPI 发布助手 - 用于 claude-mux 项目自动发布到 PyPI，包含版本管理、GitHub Actions 配置和故障排查。
---

# PyPI 发布助手

用于 claude-mux 项目 PyPI 自动发布的专属技能。

## When to Use This Skill

- 发布新版本到 PyPI
- 查看 PyPI 发布流程
- 配置 PyPI API Token
- 排查发布失败问题
- 管理版本标签

---

## 发布机制概述

### 核心原理

**git tag 驱动发布**：推送 `v*` 标签自动触发 GitHub Actions 构建并发布到 PyPI。

```
git push origin v1.0.4  →  GitHub Actions  →  PyPI
```

### 版本号规则

| 位置 | 版本 | 说明 |
|------|------|------|
| `pyproject.toml` | `1.0.0` | 占位符，本地开发用 |
| git tag | `v1.0.4` | 决定实际发布版本 |

GitHub Actions 自动替换：
```bash
# tag: v1.0.4
sed -i "s/^version = \".*\"/version = \"1.0.4\"/" pyproject.toml
```

### 触发条件

| 事件 | 是否触发 |
|------|----------|
| `git push`（推送代码） | ❌ |
| 推送普通标签 | ❌ |
| 推送 `v*` 标签 | ✅ |

---

## 发布流程

### 标准发布步骤

```bash
# 1. 更新 CHANGELOG
# 编辑 CHANGELOG.md，记录本次更新内容

# 2. 提交代码
git add -A
git commit -m "release: v1.0.4"

# 3. 推送代码（不触发发布）
git push origin master

# 4. 创建并推送标签（触发发布）
git tag v1.0.4
git push origin v1.0.4
```

### 发布后验证

```bash
# 查看 PyPI 页面
# https://pypi.org/project/claude-mux/

# 安装测试
pip install claude-mux --upgrade
claude-mux --help
```

---

## 首次配置

### 1. 注册 PyPI 账号

访问 [https://pypi.org](https://pypi.org) 注册并验证邮箱。

### 2. 生成 API Token

1. 登录 PyPI → **Account Settings** → **API tokens**
2. 点击 **Add API token**
3. 选择范围：
   - **Entire account**：可发布所有包
   - **Scope to a specific package**：仅发布指定包（推荐）
4. 复制 token（格式：`pypi-xxx`）

### 3. 配置 GitHub Secret

1. 打开 GitHub 仓库
2. **Settings** → **Secrets and variables** → **Actions**
3. **New repository secret**：
   - **Name**: `PYPI_API_TOKEN`
   - **Secret**: 你的 PyPI API Token

---

## GitHub Actions 工作流

**文件位置**: `.github/workflows/release.yml`

```yaml
name: Release to PyPI

on:
  push:
    tags:
      - 'v*'   # 只有 v 开头的标签才触发

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

### 流程图

```
git push origin v1.0.4
        ↓
GitHub Actions 检测到 v* 标签
        ↓
Checkout → 安装依赖 → sed 替换版本号
        ↓
rm -rf dist/ → python -m build
        ↓
pypa/gh-action-pypi-publish → PyPI
        ↓
✅ 发布成功
```

---

## 故障排查

### 问题 1：推送标签后没有触发 Actions

**检查标签是否正确推送**：
```bash
git tag -l            # 列出本地标签
git ls-remote --tags  # 列出远程标签
```

**确认标签格式**：必须是 `v*` 开头（如 `v1.0.4`）

### 问题 2：发布失败 "File already exists"

**原因**：PyPI 不允许重复发布同一版本

**解决**：
```bash
# 使用新版本号
git tag v1.0.5
git push origin v1.0.5
```

### 问题 3：发布失败 "Invalid credentials"

**检查**：
- GitHub Secret `PYPI_API_TOKEN` 是否正确配置
- Token 是否过期或被撤销

### 问题 4：发布的版本号不对

**原因**：`pyproject.toml` 硬编码版本未替换

**确认 workflow 中有版本替换步骤**

### 问题 5：上传的是旧的 wheel 文件

**原因**：`dist/` 目录有残留文件

**确认 workflow 中有 `rm -rf dist/` 清理步骤**

---

## 本地测试构建

在发布前可以本地验证构建：

```bash
# 清理旧构建
rm -rf dist/

# 本地构建
python -m build

# 查看产物
ls dist/
```

---

## 发布检查清单

发布前确认：

- [ ] 更新 `CHANGELOG.md` 记录变更
- [ ] 确认 `pyproject.toml` 占位符版本
- [ ] 本地测试构建成功：`python -m build`
- [ ] GitHub Secret `PYPI_API_TOKEN` 已配置
- [ ] 标签版本号格式正确：`vX.Y.Z`

---

## 快速命令

```bash
# 发布新版本
git tag v1.0.4 && git push origin v1.0.4

# 查看标签
git tag -l

# 删除本地标签
git tag -d v1.0.4

# 删除远程标签
git push origin --delete v1.0.4

# 本地构建测试
rm -rf dist/ && python -m build
```
